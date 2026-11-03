"""Seeded sampling for schema discovery only; never truncates analytical observations."""

import hashlib
import json
import random
import numpy as np
from opinion_core.schemas.records import PostRecord
from opinion_core.schemas.workflow import SamplingSpec


def sample_for_schema(posts, specification):
    spec = SamplingSpec.model_validate(specification)
    rows = sorted(
        [PostRecord.model_validate(p) for p in posts], key=lambda p: p.post_id
    )
    known = [p for p in rows if p.read_count is not None]
    threshold = (
        float(np.quantile([p.read_count for p in known], spec.high_read_quantile))
        if known
        else None
    )
    if not known and spec.missing_reads == "error":
        raise ValueError("read counts unavailable for high-read sampling")
    pool = [p for p in known if p.read_count >= threshold] if known else rows
    selected = random.Random(spec.seed).sample(pool, min(spec.sample_size, len(pool)))
    fingerprint = hashlib.sha256(
        json.dumps(
            [p.model_dump(mode="json") for p in selected],
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {
        "sample": [p.model_dump(mode="json") for p in selected],
        "post_ids": [p.post_id for p in selected],
        "seed": spec.seed,
        "read_threshold": threshold,
        "known_read_count": len(known),
        "pool_count": len(pool),
        "sample_count": len(selected),
        "dataset_count": len(rows),
        "fingerprint": fingerprint,
        "strategy": "random_within_high_read_pool"
        if known
        else "uniform_missing_read_counts",
        "purpose": "schema_discovery_only",
        "analytical_population_truncated": False,
    }
