"""Event-owned image assets retained alongside registered datasets."""

import hashlib
import os
import re
import tempfile

from opinion_core.labeling.media import load_image, normalize_image

from .dataset_repository import DatasetRepository, storage_id


class MediaAssets:
    def __init__(self, root, event_id):
        self.repo = DatasetRepository(root)
        self.event = storage_id(event_id)

    def save(self, data):
        normalize_image(data)  # Validate while preserving the original upload.
        digest = hashlib.sha256(data).hexdigest()
        path = self.repo.path(self.event, "datasets", "images", digest + ".image")
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return "dataset-image:" + digest

    def load(self, ref):
        if not ref.startswith("dataset-image:"):
            return load_image(ref)
        digest = ref.removeprefix("dataset-image:")
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("invalid image asset reference")
        data = self.repo.path(
            self.event, "datasets", "images", digest + ".image"
        ).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("image asset fingerprint mismatch")
        return normalize_image(data)
