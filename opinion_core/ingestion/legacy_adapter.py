"""Non-destructive migration; no inference of stance from sentiment."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from opinion_core.schemas.records import PostRecord, AnnotationRecord, FieldAnnotation


def migrate_file(source, output, *, schema_version, mapping_version, topic_map, source_timezone=None):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise FileExistsError('migration requires a new output file')
    raw = source.read_bytes()
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError('legacy input must be a list')
    fingerprint = hashlib.sha256(raw).hexdigest()
    posts, annotations, archived = [], [], set()
    for i, record in enumerate(records):
        post_id = f'legacy-{fingerprint[:16]}-{i}'
        original_time = record.get('publish_time') or None
        parsed, status = None, 'missing'
        if original_time:
            try:
                parsed = datetime.fromisoformat(original_time)
                if parsed.tzinfo is None:
                    if source_timezone:
                        parsed = parsed.replace(tzinfo=ZoneInfo(source_timezone))
                    else:
                        parsed, status = None, 'unresolved'
                if parsed is not None:
                    status = 'parsed'
            except ValueError:
                parsed, status = None, 'invalid'
        post = PostRecord(post_id=post_id, platform=record.get('platform', 'legacy'),
                          raw_id=str(record.get('id', i)), content=record.get('content', ''),
                          published_at=parsed, original_time=original_time, time_status=status,
                          author_ref=record.get('user_id'), source_url=record.get('url'),
                          media_refs=record.get('image_urls') or [], raw_asset_ref=f'{fingerprint}#{i}')
        ann = AnnotationRecord(post_id=post_id, schema_version=schema_version, model_version='legacy-unverified')
        topics = record.get('topics') or ([record['topic']] if record.get('topic') else [])
        if topics:
            mapped = []
            for topic in topics:
                key = (topic.get('parent_topic'), topic.get('sub_topic')) if isinstance(topic, dict) else (None, str(topic))
                mapped.append(topic_map.get(key))
            value = mapped[0] if None not in mapped and len(set(mapped)) == 1 else None
            ann.topic = FieldAnnotation(status='accepted', value=value) if value else FieldAnnotation(status='abstained', reason='unmapped_topic')
        sentiment = record.get('sentiment_polarity')
        if sentiment is not None and sentiment != '':
            if type(sentiment) in (int, float) and sentiment in (1, 2, 3, 4, 5):
                ann.sentiment = FieldAnnotation(status='accepted', value=(sentiment - 3) / 2)
            else:
                ann.sentiment = FieldAnnotation(status='abstained', reason='unknown_legacy_value')
        archived.update(set(record) - {'content', 'platform', 'id', 'publish_time', 'user_id', 'url', 'image_urls', 'topic', 'sentiment_polarity'})
        posts.append(post.model_dump(mode='json'))
        annotations.append(ann.model_dump(mode='json'))
    result = {'contract_version': '1', 'posts': posts, 'annotations': annotations,
              'migration': {'source_sha256': fingerprint, 'mapping_version': mapping_version,
                            'source_timezone': source_timezone, 'converted': len(posts),
                            'needs_relabeling': len(posts), 'archived_fields': sorted(archived),
                            'lost_fields': [], 'raw_records': records}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
    return result
