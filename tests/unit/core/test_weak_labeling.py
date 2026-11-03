import pytest
from opinion_core.labeling.pipeline import WeakLabeler, LabelBudget
from opinion_core.schemas.event import EventSchema
from opinion_core.schemas.records import PostRecord


def schema():
    return EventSchema(event_id='e', schema_version='s', as_of='2026-11-03T00:00:00Z',
                       topics=[{'id':'topic', 'definition':'t'}], publishers=[{'id':'person', 'definition':'p'}],
                       emotions=[{'id':'worry', 'definition':'e'}], targets=[{'id':'target', 'definition':'支持措施'}], evidence_refs=['ev'])


class Provider:
    version = 'fixture-provider-v1'
    def __init__(self): self.calls = 0
    def predict(self, posts, schema):
        self.calls += 1
        return {'records': [{'post_id': p.post_id, 'fields': {
            'topic': {'value':'topic', 'confidence':.9},
            'publisher': {'value':'person', 'confidence':.9},
            'emotion': {'value':'worry', 'confidence':.2},
            'sentiment': {'value':0.0, 'confidence':.95},
            'stance': {'value':'neutral', 'confidence':.9, 'target_id':'wrong'},
        }} for p in posts], 'usage': {'input_tokens':10, 'output_tokens':5}, 'cost':None}


def test_field_abstention_target_binding_and_persistent_cache(tmp_path):
    provider = Provider()
    posts = [PostRecord(post_id='p', raw_id='1', platform='test', content='text')]
    labeler = WeakLabeler(tmp_path, provider, prompt_version='p1', confidence_threshold=.7)
    first = labeler.label(posts, schema(), budget=LabelBudget(max_calls=1))
    ann = first['annotations'][0]
    assert ann['topic']['status'] == 'accepted'
    assert ann['topic']['provider_confidence'] == .9 and ann['topic']['probability'] is None
    assert ann['sentiment']['value'] == 0.0
    assert ann['emotion']['status'] == 'abstained'
    assert ann['stance']['status'] == 'abstained' and ann['stance']['value'] is None
    assert provider.calls == 1 and first['calls'] == 1 and first['usage']['input_tokens'] == 10
    cached = WeakLabeler(tmp_path, provider, prompt_version='p1', confidence_threshold=.7).label(posts, schema(), budget=LabelBudget(max_calls=0))
    assert cached['cache_hits'] == 1 and provider.calls == 1
    changed = schema().model_copy(update={'schema_version':'s2'})
    third = labeler.label(posts, changed, budget=LabelBudget(max_calls=0))
    assert third['status'] == 'partial' and third['annotations'][0]['topic']['reason'] == 'budget_exhausted'


def test_calls_batching_failure_and_no_human_review(tmp_path):
    provider = Provider()
    posts = [PostRecord(post_id=f'p{i}', raw_id=str(i), platform='test', content='text') for i in range(5)]
    result = WeakLabeler(tmp_path, provider, prompt_version='p', batch_size=2).label(posts, schema(), budget=LabelBudget(max_calls=2))
    assert provider.calls == 2 and result['status'] == 'partial'
    assert len(result['annotations']) == 5 and result['human_review_required'] is False
    assert result['annotations'][-1]['topic']['status'] == 'missing'


def test_failed_call_not_cached_as_neutral(tmp_path):
    provider = Provider()
    def fail(*a): raise TimeoutError('secret credentials must not be persisted')
    provider.predict = fail
    posts = [PostRecord(post_id='p', raw_id='1', platform='test', content='x')]
    result = WeakLabeler(tmp_path, provider, prompt_version='p').label(posts, schema(), budget=LabelBudget(max_calls=1))
    assert result['annotations'][0]['sentiment']['status'] == 'failed'
    assert result['annotations'][0]['stance']['value'] is None
    assert result['uncertain_calls'] == 1
    assert 'secret' not in str(result)


def test_confidence_and_response_ids_validated_per_field(tmp_path):
    provider = Provider()
    provider.predict = lambda posts, s: {'records':[{'post_id':'p', 'fields':{
        'topic':{'value':'invented', 'confidence':.99}, 'sentiment':{'value':float('nan'), 'confidence':.9},
        'stance':{'value':'neutral', 'confidence':.9, 'target_id':'target'}}}]}
    result = WeakLabeler(tmp_path, provider, prompt_version='p').label(
        [PostRecord(post_id='p', raw_id='1', platform='test', content='x')], schema(), budget=LabelBudget(max_calls=1))
    fields = result['annotations'][0]
    assert fields['topic']['status'] == 'abstained' and fields['sentiment']['status'] == 'abstained'
    assert fields['stance']['value'] == 'neutral'
    assert fields['publisher']['status'] == 'missing'


def test_invalid_batch_does_not_leave_partially_committed_cache(tmp_path):
    provider = Provider()
    original = provider.predict
    def corrupt(posts, s):
        result = original(posts, s)
        result['records'][1]['fields'] = []
        return result
    provider.predict = corrupt
    posts = [PostRecord(post_id=f'p{i}', raw_id=str(i), platform='test', content='x') for i in range(2)]
    labeler = WeakLabeler(tmp_path, provider, prompt_version='p')
    assert labeler.label(posts, schema(), budget=LabelBudget(max_calls=1))['status'] == 'partial'
    assert labeler.label(posts, schema(), budget=LabelBudget(max_calls=0))['cache_hits'] == 0
