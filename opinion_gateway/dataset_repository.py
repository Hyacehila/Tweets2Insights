import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
        raise ValueError('invalid asset identifier')
    return value


def storage_id(value):
    """Preserve case distinctions and avoid Windows reserved filenames."""
    return hashlib.sha256(safe_id(value).encode('utf-8')).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class DatasetRepository:
    """Immutable content-addressed datasets; callers receive fresh values, never a shared cache."""
    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, *parts):
        path = self.root.joinpath(*(safe_id(p) for p in parts)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('asset escaped repository')
        return path

    def register(self, event_id, records):
        if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
            raise ValueError('dataset must be a list of records')
        encoded = json.dumps(records, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
        version = hashlib.sha256(encoded).hexdigest()
        dataset_id = 'ds-' + version
        atomic_json(self.path(storage_id(event_id), 'datasets', dataset_id + '.json'), records)
        return {'event_id': event_id, 'dataset_id': dataset_id, 'data_version': version, 'count': len(records)}

    def read(self, event_id, dataset_id):
        records = json.loads(self.path(storage_id(event_id), 'datasets', safe_id(dataset_id) + '.json').read_text(encoding='utf-8'))
        digest = hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        if dataset_id != 'ds-' + digest:
            raise ValueError('dataset fingerprint mismatch')
        return records

    def run_dir(self, event_id, dataset_id, run_id):
        self.read(event_id, dataset_id)
        target = self.path(storage_id(event_id), 'runs', dataset_id, storage_id(run_id))
        target.mkdir(parents=True, exist_ok=True)
        return target
