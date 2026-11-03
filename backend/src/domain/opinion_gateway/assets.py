"""Immutable, scoped domain artifacts. No caller-supplied filesystem paths."""
import hashlib
import json
from .dataset_repository import DatasetRepository, atomic_json, storage_id, safe_id
from opinion_core.schemas.artifacts import ArtifactRef


class ArtifactStore:
    def __init__(self, root):
        self.repo = DatasetRepository(root)

    def put(self, event_id, run_id, kind, payload):
        safe_id(kind)
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        digest = hashlib.sha256((kind+'\0'+data).encode()).hexdigest()
        ref = ArtifactRef(artifact_id='a-'+digest, event_id=event_id, run_id=run_id, kind=kind, sha256=digest)
        path = self.repo.path(storage_id(event_id), 'artifacts', storage_id(run_id), ref.artifact_id+'.json')
        atomic_json(path, {'ref':ref.model_dump(mode='json'), 'payload':payload})
        return ref.model_dump(mode='json')

    def read(self, event_id, run_id, artifact_id, expected_kind=None):
        path = self.repo.path(storage_id(event_id), 'artifacts', storage_id(run_id), safe_id(artifact_id)+'.json')
        obj = json.loads(path.read_text(encoding='utf-8'))
        ref = ArtifactRef.model_validate(obj['ref'])
        digest = hashlib.sha256((ref.kind+'\0'+json.dumps(obj['payload'], ensure_ascii=False, sort_keys=True, allow_nan=False)).encode()).hexdigest()
        if (ref.event_id,ref.run_id,ref.artifact_id,ref.sha256) != (event_id,run_id,artifact_id,digest):
            raise ValueError('artifact ownership or fingerprint mismatch')
        if expected_kind is not None and ref.kind != expected_kind:
            raise ValueError('wrong artifact kind')
        return obj['payload']

    def list(self, event_id, run_id):
        directory = self.repo.path(storage_id(event_id), 'artifacts', storage_id(run_id))
        return [json.loads(path.read_text(encoding='utf-8'))['ref'] for path in sorted(directory.glob('a-*.json'))]
