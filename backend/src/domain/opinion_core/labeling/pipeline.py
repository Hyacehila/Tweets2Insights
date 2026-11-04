"""Batch weak labeling with typed field rejection, versioned cache and a shared call budget."""

import copy
import hashlib
import json
import math
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from opinion_core.schemas.event import EventSchema
from opinion_core.schemas.records import AnnotationRecord, FieldAnnotation, PostRecord

FIELDS = ("topic", "publisher", "emotion", "sentiment", "stance")


class LabelProvider(Protocol):
    version: str

    def predict(self, posts: list[PostRecord], schema: EventSchema) -> dict: ...


@dataclass
class LabelBudget:
    max_calls: int
    calls: int = field(default=0, init=False)
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False
    )

    def __post_init__(self):
        if self.max_calls < 0:
            raise ValueError("max_calls must be nonnegative")

    def reserve(self):
        with self._lock:
            if self.calls >= self.max_calls:
                return False
            self.calls += 1
            return True


class WeakLabeler:
    def __init__(
        self,
        root,
        provider: LabelProvider,
        *,
        prompt_version,
        confidence_threshold=0.7,
        batch_size=10,
        probability_margin=0.1,
    ):
        if not 0 <= confidence_threshold <= 1 or not 1 <= batch_size <= 100:
            raise ValueError("invalid threshold or batch size")
        self.path = Path(root) / "annotation-cache.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.provider, self.prompt_version = provider, prompt_version
        self.threshold, self.batch_size = confidence_threshold, batch_size
        self.probability_margin = probability_margin
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS annotations (key TEXT PRIMARY KEY, payload TEXT)"
            )

    def _key(self, post, schema, input_fingerprint=None):
        data = [
            post.model_dump(mode="json"),
            schema.model_dump(mode="json"),
            self.provider.version,
            self.prompt_version,
            self.threshold,
            self.probability_margin,
            "field-parser-v2",
        ]
        if input_fingerprint is not None:
            data.append(input_fingerprint)
        return hashlib.sha256(
            json.dumps(
                data, sort_keys=True, ensure_ascii=False, allow_nan=False
            ).encode()
        ).hexdigest()

    def _empty(self, post, schema, status="missing", reason=None):
        return AnnotationRecord(
            post_id=post.post_id,
            schema_version=schema.schema_version,
            model_version=self.provider.version,
            prompt_version=self.prompt_version,
            target_id=schema.targets[0].id,
            **{name: FieldAnnotation(status=status, reason=reason) for name in FIELDS},
        )

    def _field(self, name, raw, schema):
        if not isinstance(raw, dict):
            return FieldAnnotation(reason="provider_field_missing")
        if raw.get("refusal") is True:
            return FieldAnnotation(status="abstained", reason="provider_refusal")
        value, confidence = raw.get("value"), raw.get("confidence")
        allowed = {
            "topic": [v.id for v in schema.topics],
            "publisher": [v.id for v in schema.publishers],
            "emotion": [v.id for v in schema.emotions],
            "sentiment": [-1.0, -0.5, 0.0, 0.5, 1.0],
            "stance": ["support", "oppose", "neutral"],
        }[name]
        reason = None
        probabilities = raw.get("probabilities")
        margin = None
        if probabilities is not None:
            if (
                not isinstance(probabilities, dict)
                or not probabilities
                or any(
                    type(v) not in (int, float)
                    or not math.isfinite(v)
                    or not 0 <= v <= 1
                    for v in probabilities.values()
                )
                or abs(sum(probabilities.values()) - 1) > 0.01
            ):
                return FieldAnnotation(status="failed", reason="invalid_probabilities")
            ranked = sorted(probabilities.values(), reverse=True)
            margin = ranked[0] - (ranked[1] if len(ranked) > 1 else 0)
        if (
            type(value) not in ((int, float) if name == "sentiment" else (str,))
            or value not in allowed
        ):
            reason = "unknown_label"
        elif name == "stance" and raw.get("target_id") != schema.targets[0].id:
            reason = "target_mismatch"
        elif (
            type(confidence) not in (int, float)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            reason = "confidence_unavailable"
        elif confidence < self.threshold:
            reason = "low_confidence"
        elif margin is not None and margin < self.probability_margin:
            reason = "ambiguous_probability_margin"
        if reason:
            return FieldAnnotation(
                status="abstained",
                reason=reason,
                probabilities=probabilities,
                probability_margin=margin,
            )
        # Provider confidence is not claimed to be a calibrated probability.
        return FieldAnnotation(
            status="accepted",
            value=value,
            provider_confidence=confidence,
            probabilities=probabilities,
            probability_margin=margin,
            probability=raw.get("probability"),
            reason="provider_confidence_passed_uncalibrated",
        )

    def label(self, posts, schema, *, budget: LabelBudget, check_cancel=lambda: None):
        schema = EventSchema.model_validate(schema)
        posts = [PostRecord.model_validate(post) for post in posts]
        if len(schema.targets) != 1 or len({post.post_id for post in posts}) != len(
            posts
        ):
            raise ValueError("one target and unique post IDs required")
        results, hits, calls, uncertain = {}, 0, 0, 0
        usage = {"input_tokens": 0, "output_tokens": 0}
        known_cost, cost_complete = 0.0, True
        for start in range(0, len(posts), self.batch_size):
            check_cancel()
            batch, keys = [], {}
            for post in posts[start : start + self.batch_size]:
                check_cancel()
                try:
                    prepare = getattr(self.provider, "prepare_input", None)
                    fingerprint = prepare(post) if prepare else None
                except Exception as exc:  # noqa: BLE001 - isolate unreadable inputs per post
                    results[post.post_id] = self._empty(
                        post, schema, status="failed", reason=type(exc).__name__
                    )
                    continue
                key = self._key(post, schema, fingerprint)
                keys[post.post_id] = key
                with sqlite3.connect(self.path) as db:
                    row = db.execute(
                        "SELECT payload FROM annotations WHERE key=?", (key,)
                    ).fetchone()
                if row:
                    results[post.post_id] = AnnotationRecord.model_validate_json(row[0])
                    hits += 1
                else:
                    batch.append(post)
            if not batch:
                continue
            if not budget.reserve():
                for post in batch:
                    results[post.post_id] = self._empty(
                        post, schema, reason="budget_exhausted"
                    )
                continue
            calls += 1
            try:
                reply = self.provider.predict(
                    copy.deepcopy(batch), schema.model_copy(deep=True)
                )
                for name in usage:
                    value = reply.get("usage", {}).get(name, 0)
                    if type(value) is int and value >= 0:
                        usage[name] += value
                cost = reply.get("cost")
                if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0:
                    known_cost += cost
                else:
                    cost_complete = False
                records = reply["records"]
                mapping = {row["post_id"]: row for row in records}
                if len(mapping) != len(records) or set(mapping) != {
                    p.post_id for p in batch
                }:
                    raise ValueError("response IDs differ from requested batch")
                prepared = []
                for post in batch:
                    ann = self._empty(post, schema)
                    fields = mapping[post.post_id].get("fields", {})
                    if not isinstance(fields, dict):
                        raise ValueError("invalid fields response")  # noqa: TRY004 - provider protocol validation
                    for name in FIELDS:
                        setattr(ann, name, self._field(name, fields.get(name), schema))
                    results[post.post_id] = ann
                    if all(
                        getattr(ann, name).status in ("accepted", "abstained")
                        for name in FIELDS
                    ):
                        prepared.append((keys[post.post_id], ann.model_dump_json()))
                with sqlite3.connect(self.path) as db:
                    db.executemany(
                        "INSERT OR IGNORE INTO annotations VALUES (?,?)", prepared
                    )
            except Exception as exc:  # noqa: BLE001 - preserve failures for each provider batch
                uncertain += 1
                cost_complete = False
                for post in batch:
                    results[post.post_id] = self._empty(
                        post, schema, status="failed", reason=type(exc).__name__
                    )
        annotations = [results[post.post_id].model_dump(mode="json") for post in posts]
        incomplete = any(
            ann[name]["status"] in ("missing", "failed")
            for ann in annotations
            for name in FIELDS
        )
        coverage = {
            name: sum(ann[name]["status"] == "accepted" for ann in annotations)
            / len(posts)
            if posts
            else None
            for name in FIELDS
        }
        result = {
            "status": "partial" if incomplete else "completed",
            "annotations": annotations,
            "cache_hits": hits,
            "calls": calls,
            "uncertain_calls": uncertain,
            "usage": usage,
            "known_cost": known_cost,
            "cost_complete": cost_complete,
            "coverage": coverage,
            "confidence_threshold": self.threshold,
            "confidence_calibrated": False,
            "human_review_required": False,
        }
        policy = getattr(self.provider, "media_policy", None)
        if policy:
            media = policy.summary([post.model_dump(mode="json") for post in posts])
            media["failed_image_posts"] = sum(
                ann["topic"]["reason"] == "ImageInputError" for ann in annotations
            )
            media["empty_input_posts"] = sum(
                ann["topic"]["reason"] == "EmptyModelInput" for ann in annotations
            )
            if media["failed_image_posts"]:
                media["notices"].append("image_read_failed")
            if media["empty_input_posts"]:
                media["notices"].append("empty_model_input")
            result["media_input"] = media
        return result
