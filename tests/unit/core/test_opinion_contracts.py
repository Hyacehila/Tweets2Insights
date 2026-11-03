import pytest
from pydantic import ValidationError

from opinion_core.schemas.event import EventSpec, EventSchema
from opinion_core.schemas.records import FieldAnnotation, AnnotationRecord, PostRecord
from opinion_core.schemas.run import RunManifest


def test_event_routes_and_utc():
    event = EventSpec(event_id='rain', input_mode='upload', dataset_ref='data1',
                      as_of='2026-11-03T08:00:00+08:00', search_provider='tavily')
    assert event.as_of.isoformat() == '2026-11-03T00:00:00+00:00'
    assert not event.requires_collection
    with pytest.raises(ValidationError):
        EventSpec(event_id='../rain', input_mode='keywords', keywords=['rain'],
                  as_of='2026-11-03', search_provider='tavily')
    with pytest.raises(ValidationError):
        EventSpec(event_id='rain', input_mode='upload', as_of='2026-11-03T00:00:00Z')


def test_missing_unknown_failed_and_neutral_are_distinct():
    ann = AnnotationRecord(post_id='p', schema_version='s1', model_version='legacy')
    assert ann.stance.status == 'missing'
    neutral = FieldAnnotation(status='accepted', value='neutral')
    assert neutral.value == 'neutral'
    assert FieldAnnotation(status='abstained', reason='unknown').value is None
    assert FieldAnnotation(status='failed', reason='timeout').value is None
    with pytest.raises(ValidationError):
        FieldAnnotation(status='accepted')
    with pytest.raises(ValidationError):
        FieldAnnotation(status='failed', value='neutral')
    with pytest.raises(ValidationError):
        AnnotationRecord(post_id='p', schema_version='s1', model_version='m', stance=neutral)
    assert AnnotationRecord(post_id='p', schema_version='s1', model_version='m',
                            target_id='policy', stance=neutral).target_id == 'policy'


def test_post_missing_time_and_schema_version():
    post = PostRecord(post_id='p', platform='legacy', raw_id='1', content='text')
    assert post.published_at is None and post.time_status == 'missing'
    with pytest.raises(ValidationError):
        PostRecord(post_id='p', platform='legacy', raw_id='1', content='x', contract_version='2')


def test_manifest_rejects_secrets_recursively():
    args = dict(run_id='r', event_id='e', dataset_id='d', data_version='v', code_version='git')
    with pytest.raises(ValidationError):
        RunManifest(**args, config_snapshot={'llm': {'api_key': 'secret'}})
    assert RunManifest(**args, config_snapshot={'model': 'm'}).contract_version == '1'


def test_frozen_schema_requires_evidence_and_unique_flat_ids():
    args = dict(event_id='e', schema_version='s', as_of='2026-11-03T00:00:00Z',
                topics=[{'id': 't', 'definition': 'topic'}], publishers=[], emotions=[],
                targets=[{'id': 'p', 'definition': 'proposition'}])
    with pytest.raises(ValidationError):
        EventSchema(**args)
    schema = EventSchema(**args, evidence_refs=['ev1'])
    assert schema.topics[0].id == 't'
