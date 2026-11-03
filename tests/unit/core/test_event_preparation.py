import pytest
from opinion_core.schemas.event import EventSpec
from opinion_core.labeling.event_preparation import EventPreparation


def event(provider='deepseek'):
    return EventSpec(event_id='rain', input_mode='existing', dataset_ref='ds-test', keywords=['rain'],
                     as_of='2026-11-03T00:00:00Z', search_provider=provider)


def vocab():
    return {'topics': [{'id': f't{i}', 'definition': f'topic {i}'} for i in range(6)],
            'publishers': [{'id': f'p{i}', 'definition': f'publisher {i}'} for i in range(6)],
            'emotions': [{'id': f'e{i}', 'definition': f'emotion {i}'} for i in range(12)]}


def builder(evidence, library):
    return {'topics': library['topics'][:5], 'publishers': library['publishers'][:5],
            'emotions': library['emotions'][:10], 'targets': [{'id': 'rescue', 'definition': '支持当前救援措施'}]}


def test_search_before_builder_and_frozen_reuse(tmp_path):
    calls = []
    def search(query, **kwargs):
        calls.append(kwargs['provider'])
        return {'provider': kwargs['provider'], 'error': '', 'results': [
            {'url': 'https://example.com', 'snippet': 'evidence', 'fingerprint': 'abc',
             'date': '2026-11-02T00:00:00Z', 'retrieved_at': '2026-11-03T00:00:00Z'}]}
    service = EventPreparation(tmp_path, search=search, builder=builder, builder_version='test-v1')
    first = service.prepare(event(), vocab())
    assert first['status'] == 'frozen' and calls == ['deepseek']
    assert len(first['schema']['emotions']) == 10 and first['schema']['evidence_refs']
    assert service.prepare(event(), vocab()) == first
    assert calls == ['deepseek']
    different = service.prepare(event('tavily'), vocab())
    assert different['schema']['schema_version'] != first['schema']['schema_version']


def test_failed_search_is_recoverable_and_never_generates_schema(tmp_path):
    service = EventPreparation(tmp_path, search=lambda *a, **k: {'provider':'deepseek', 'error':'timeout', 'results':[]},
                               builder=lambda *a: pytest.fail('builder must not run'), builder_version='v1')
    result = service.prepare(event(), vocab())
    assert result['status'] == 'recoverable_failure' and result['schema'] is None
    assert service.read_attempt(result['preparation_id'])['error_type'] == 'search_failed'


def test_invalid_labels_outside_library_do_not_freeze(tmp_path):
    def bad(*args):
        value = builder(*args)
        value['topics'][0] = {'id':'invented', 'definition':'not from library'}
        return value
    service = EventPreparation(tmp_path, search=lambda *a, **k: {'provider':'deepseek', 'error':'', 'results':[{'url':'https://example.com'}]},
                               builder=bad, builder_version='v1')
    result = service.prepare(event(), vocab())
    assert result['status'] == 'recoverable_failure' and result['error_type'] == 'schema_invalid'


def test_future_sources_rejected_and_unknown_dates_recorded(tmp_path):
    service = EventPreparation(tmp_path, search=lambda *a, **k: {'provider':'deepseek', 'error':'', 'results':[
        {'url':'https://example.com/future', 'date':'2026-11-04T00:00:00Z'},
        {'url':'https://example.com/unknown', 'date':None}]}, builder=builder, builder_version='v1')
    result = service.prepare(event(), vocab())
    assert result['status'] == 'frozen'
    assert len(result['evidence']['results']) == 1
    assert result['evidence']['unknown_publication_dates'] == 1
    assert result['historical_availability_verified'] is False


def test_persisted_call_budget_stops_retry_before_network(tmp_path):
    calls = []
    def failed(*args, **kwargs):
        calls.append(1)
        return {'provider':'deepseek', 'error':'timeout', 'results':[]}
    service = EventPreparation(tmp_path, search=failed, builder=builder, builder_version='v1')
    for _ in range(5):
        result = service.prepare(event(), vocab(), max_total_calls=2)
    assert len(calls) == 2 and result['calls'] == 2
    assert result['error_type'] == 'call_budget_exhausted'


def test_failed_search_never_attributes_old_builder_usage(tmp_path):
    class Builder:
        last_usage = {'input_tokens':999}
        def __call__(self, *args): pytest.fail('must not call builder')
    service = EventPreparation(tmp_path, search=lambda *a,**k: {'provider':'deepseek','error':'timeout','results':[]},
                               builder=Builder(), builder_version='v1')
    assert service.prepare(event(), vocab())['builder_usage'] == {}
