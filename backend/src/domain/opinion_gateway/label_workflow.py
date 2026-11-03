"""Explicit operator CLI for automatic weak labeling; human truth is never a runtime input."""
import argparse
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from opinion_core.labeling.event_preparation import EventPreparation, canonical
from opinion_core.labeling.pipeline import WeakLabeler
from opinion_core.schemas.event import EventSpec
from opinion_gateway.dataset_repository import DatasetRepository, atomic_json


class DurableLabelBudget:
    def __init__(self, path, run_key, max_calls):
        if max_calls < 0:
            raise ValueError('max_calls must be nonnegative')
        self.path, self.run_key = Path(path), run_key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute('CREATE TABLE IF NOT EXISTS budgets (id TEXT PRIMARY KEY, max_calls INTEGER, used INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS budget_configs (id TEXT PRIMARY KEY, payload TEXT)')
            db.execute('INSERT OR IGNORE INTO budgets VALUES (?,?,0)', (run_key, max_calls))
            if db.execute('SELECT max_calls FROM budgets WHERE id=?', (run_key,)).fetchone()[0] != max_calls:
                raise ValueError('existing run budget is immutable; use a new run for changed settings')

    def bind_configuration(self, config):
        payload = canonical(config)
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO budget_configs VALUES (?,?)', (self.run_key, payload))
            if db.execute('SELECT payload FROM budget_configs WHERE id=?', (self.run_key,)).fetchone()[0] != payload:
                raise ValueError('run configuration is frozen; use a new run_id')

    def reserve(self):
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            return db.execute('UPDATE budgets SET used=used+1 WHERE id=? AND used<max_calls', (self.run_key,)).rowcount == 1


def run_label_workflow(root, event, library, *, run_id, provider, builder, search,
                       max_label_calls=10, max_schema_calls=4, batch_size=10, confidence_threshold=.7):
    event = EventSpec.model_validate(event)
    if event.requires_collection:
        raise ValueError('collection must finish and register a dataset before labeling')
    repo = DatasetRepository(root)
    records = repo.read(event.event_id, event.dataset_ref)
    directory = repo.run_dir(event.event_id, event.dataset_ref, run_id)
    source_root = Path(__file__).resolve().parents[1]
    sources = sorted((source_root / 'opinion_core/labeling').rglob('*.py'))
    sources += sorted((source_root / 'opinion_core/schemas').rglob('*.py')) + [Path(__file__)]
    code_hash = hashlib.sha256(b''.join(path.read_bytes() for path in sources)).hexdigest()
    manifest = {'event':event.model_dump(mode='json'), 'run_id':run_id, 'code_version':'sha256:'+code_hash,
                'provider_version':provider.version, 'builder_version':builder.version, 'prompt_version':'weak-json-v1',
                'library_sha256':hashlib.sha256(canonical(library).encode()).hexdigest(),
                'max_label_calls':max_label_calls, 'max_schema_calls':max_schema_calls,
                'batch_size':batch_size, 'confidence_threshold':confidence_threshold}
    run_key = hashlib.sha256(canonical([event.event_id, event.dataset_ref, run_id]).encode()).hexdigest()
    budget = DurableLabelBudget(repo.root / 'label-budget.sqlite', run_key, max_label_calls)
    budget.bind_configuration(manifest)
    prepared = EventPreparation(root, search=search, builder=builder, builder_version=builder.version).prepare(
        event, library, max_total_calls=max_schema_calls)
    if prepared['status'] != 'frozen':
        result = {'status': prepared['status'], 'preparation_id': prepared['preparation_id'],
                  'error_type': prepared['error_type'], 'human_review_required': False}
    else:
        # A run-level call counter persists across process restarts and concurrent callers.
        labeler = WeakLabeler(root, provider, prompt_version='weak-json-v1', batch_size=batch_size,
                              confidence_threshold=confidence_threshold)
        result = labeler.label(records, prepared['schema'], budget=budget)
        result.update(schema=prepared['schema'], preparation_id=prepared['preparation_id'],
                      provider_version=provider.version, event_id=event.event_id,
                      dataset_id=event.dataset_ref, run_id=run_id)
    # Each attempt is immutable; concurrent attempts cannot overwrite each other's evidence.
    attempt_id = uuid.uuid4().hex
    result['manifest'] = manifest
    atomic_json(directory / f'labels-{attempt_id}.json', result)
    return {**result, 'attempt_id': attempt_id}


def main():
    parser = argparse.ArgumentParser(description='Automatic weak labels; may call configured paid APIs.')
    parser.add_argument('--root', default='.opinion-assets')
    parser.add_argument('--event', required=True, help='EventSpec JSON with a registered dataset_ref')
    parser.add_argument('--library', required=True, help='Fixed vocabulary JSON')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--model', default='glm-4.5-air')
    parser.add_argument('--max-label-calls', type=int, default=10)
    parser.add_argument('--max-schema-calls', type=int, default=4)
    parser.add_argument('--batch-size', type=int, default=10)
    parser.add_argument('--confidence-threshold', type=float, default=.7)
    args = parser.parse_args()
    from opinion_core.labeling.glm_provider import GLMJsonProvider, GLMSchemaBuilder
    from opinion_core.evidence.providers import search
    provider = GLMJsonProvider(model=args.model)
    result = run_label_workflow(args.root, json.loads(Path(args.event).read_text(encoding='utf-8')),
        json.loads(Path(args.library).read_text(encoding='utf-8')), run_id=args.run_id,
        provider=provider, builder=GLMSchemaBuilder(provider), search=search,
        max_label_calls=args.max_label_calls, max_schema_calls=args.max_schema_calls,
        batch_size=args.batch_size, confidence_threshold=args.confidence_threshold)
    print(json.dumps({key: result.get(key) for key in ('status', 'attempt_id', 'preparation_id', 'calls', 'cache_hits', 'error_type')}))
    return 0 if result['status'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
