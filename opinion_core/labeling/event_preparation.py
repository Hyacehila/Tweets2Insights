"""Search-first schema freezing with bounded calls and durable recovery state."""
import copy
import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from opinion_core.schemas.event import EventSpec, EventSchema, LabelDefinition


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class EventPreparation:
    def __init__(self, root, *, search, builder, builder_version):
        self.path = Path(root) / 'event-preparation.sqlite'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.search, self.builder, self.builder_version = search, builder, builder_version
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS preparations (id TEXT PRIMARY KEY, payload TEXT)')

    def read_attempt(self, preparation_id):
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT payload FROM preparations WHERE id=?', (preparation_id,)).fetchone()
            if row is None:
                raise KeyError(preparation_id)
            return json.loads(row[0])

    def _change(self, key, fn):
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM preparations WHERE id=?', (key,)).fetchone()
            result = fn(json.loads(row[0]) if row else None)
            db.execute('INSERT OR REPLACE INTO preparations VALUES (?,?)', (key, canonical(result)))
            return result

    def prepare(self, event, library, *, max_total_calls=4, search_api_key=None):
        event = EventSpec.model_validate(event)
        if not event.keywords or not ' '.join(event.keywords).strip():
            raise ValueError('schema preparation requires event keywords')
        if max_total_calls < 2:
            raise ValueError('budget must permit search and schema generation')
        library = {name: [LabelDefinition.model_validate(v).model_dump(mode='json') for v in library[name]]
                   for name in ('topics', 'publishers', 'emotions')}
        for name, minimum in (('topics', 5), ('publishers', 5), ('emotions', 10)):
            ids = [value['id'] for value in library[name]]
            if len(ids) < minimum or len(set(ids)) != len(ids):
                raise ValueError('fixed vocabulary needs enough unique labels')
        spec = event.model_dump(mode='json', exclude={'dataset_ref', 'input_mode'})
        key = hashlib.sha256(canonical([spec, library, self.builder_version]).encode()).hexdigest()
        token = uuid.uuid4().hex
        def claim(old):
            if old and (old['status'] == 'frozen' or old.get('lease_until', 0) > time.time()):
                return old
            return {**(old or {}), 'preparation_id': key, 'status': 'preparing', 'schema': None,
                    'token': token, 'lease_until': time.time() + 180, 'event': spec,
                    'builder_version': self.builder_version, 'calls': (old or {}).get('calls', 0),
                    'error_type': '', 'historical_availability_verified': False}
        state = self._change(key, claim)
        if state.get('token') != token or state['status'] == 'frozen':
            return state
        def reserve():
            def update(current):
                if current['token'] != token:
                    raise ValueError('preparation lease lost')
                if current['calls'] >= max_total_calls:
                    raise ValueError('call_budget_exhausted')
                current['calls'] += 1
                return current
            self._change(key, update)
        error_type, schema, evidence = 'search_failed', None, None
        builder_usage = {}
        try:
            reserve()
            evidence = self.search(' '.join(event.keywords), provider=event.search_provider, api_key=search_api_key,
                                    max_results=5, timeout_seconds=20)
            if evidence.get('error') or evidence.get('provider') != event.search_provider or not evidence.get('results'):
                raise ValueError('search_failed')
            retained, unknown = [], 0
            for card in evidence['results']:
                date = card.get('date')
                if date:
                    try:
                        published = datetime.fromisoformat(date.replace('Z', '+00:00'))
                        if published.tzinfo is None:
                            raise ValueError('unknown timezone')
                        if published > event.as_of:
                            continue
                    except (ValueError, TypeError):
                        unknown += 1
                else:
                    unknown += 1
                retained.append(card)
            evidence = {**evidence, 'results': retained, 'unknown_publication_dates': unknown, 'event_context': spec}
            if not retained:
                raise ValueError('no_evidence_before_cutoff')
            error_type = 'schema_invalid'
            reserve()
            draft = self.builder(copy.deepcopy(evidence), copy.deepcopy(library))
            builder_usage = copy.deepcopy(getattr(self.builder, 'last_usage', {}))
            schema = EventSchema(event_id=event.event_id, schema_version='schema-' + key[:32], as_of=event.as_of,
                                 evidence_refs=['ev-' + hashlib.sha256(canonical(card).encode()).hexdigest() for card in retained], **draft)
            for name, low, high in (('topics', 5, 10), ('publishers', 5, 10), ('emotions', 10, 10)):
                selected = getattr(schema, name)
                allowed = {v['id']: v['definition'] for v in library[name]}
                if not low <= len(selected) <= high or any(allowed.get(v.id) != v.definition for v in selected):
                    raise ValueError('schema must select from fixed vocabulary')
            if len(schema.targets) != 1:
                raise ValueError('first release requires exactly one explicit stance target')
            error_type = ''
        except Exception as exc:
            if str(exc) == 'call_budget_exhausted':
                error_type = 'call_budget_exhausted'
            schema = None
        def publish(current):
            if current['token'] != token:
                raise ValueError('preparation lease lost')
            return {**current, 'status': 'frozen' if schema else 'recoverable_failure',
                    'schema': schema.model_dump(mode='json') if schema else None,
                    'evidence': evidence, 'error_type': error_type, 'lease_until': 0,
                    'builder_usage': builder_usage,
                    'prepared_at': datetime.now(timezone.utc).isoformat()}
        return self._change(key, publish)
