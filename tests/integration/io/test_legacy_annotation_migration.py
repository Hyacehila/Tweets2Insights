import json
import pytest
from pathlib import Path
from opinion_core.ingestion.legacy_adapter import migrate_file


def test_actual_stage1_topics_list_migrates_only_unambiguous_mapping(tmp_path):
    source = Path('tests/fixtures/sample_enhanced.json')
    result = migrate_file(source, tmp_path / 'new.json', schema_version='s', mapping_version='m',
                          topic_map={('社会民生', '居民生活'): 'life'})
    assert result['annotations'][0]['topic']['value'] == 'life'
    assert result['annotations'][1]['topic']['status'] == 'abstained'


def test_migration_preserves_source_and_requires_explicit_topic_map(tmp_path):
    source = tmp_path / 'old.json'
    records = [{'content': '支持救援', 'user_id': 'u', 'publish_time': '2026-11-01 08:00:00',
                'topic': {'parent_topic': '社会', 'sub_topic': '救援'},
                'sentiment_polarity': 3, 'belief': 'old'},
               {'content': '未知', 'sentiment_polarity': '未知'}]
    source.write_text(json.dumps(records, ensure_ascii=False), encoding='utf-8')
    original = source.read_bytes()
    output = tmp_path / 'new.json'
    result = migrate_file(source, output, schema_version='s1', mapping_version='map1',
                          topic_map={('社会', '救援'): 'rescue'}, source_timezone='Asia/Shanghai')
    assert source.read_bytes() == original
    assert result['annotations'][0]['stance']['status'] == 'missing'
    assert result['annotations'][0]['topic']['value'] == 'rescue'
    assert result['annotations'][0]['sentiment']['value'] == 0.0
    assert result['annotations'][1]['sentiment']['status'] == 'abstained'
    assert result['posts'][0]['published_at'] == '2026-11-01T00:00:00Z'
    assert result['posts'][1]['published_at'] is None
    assert result['migration']['needs_relabeling'] == 2
    assert 'belief' in result['migration']['archived_fields']
    assert json.loads(output.read_text(encoding='utf-8')) == result
    with pytest.raises(FileExistsError):
        migrate_file(source, output, schema_version='s1', mapping_version='map1', topic_map={})


def test_unmapped_topic_and_naive_time_are_not_guessed(tmp_path):
    source = tmp_path / 'old.json'
    source.write_text(json.dumps([{'content': 'x', 'publish_time': '2026-11-01 08:00:00',
                                   'topic': {'parent_topic': 'a', 'sub_topic': 'b'}}]))
    result = migrate_file(source, tmp_path / 'new.json', schema_version='s',
                          mapping_version='m', topic_map={})
    assert result['annotations'][0]['topic']['status'] == 'abstained'
    assert result['posts'][0]['time_status'] == 'unresolved'
    assert result['posts'][0]['published_at'] is None
