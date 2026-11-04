"""
Pure helpers for Pipeline Console page validation and config shaping.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid


REQUIRED_PATH_FIELDS = (
    ("data.input_path", "Input data path"),
    ("data.output_path", "Enhanced data output path"),
    ("data.topics_path", "Topics path"),
    ("data.sentiment_attributes_path", "Sentiment attributes path"),
    ("data.publisher_objects_path", "Publisher objects path"),
    ("data.belief_system_path", "Belief system path"),
)


def validate_pipeline_form(flat_config: Dict[str, Any]) -> List[str]:
    """Validate pipeline form values before save/run actions."""
    errors: List[str] = []

    for key, label in REQUIRED_PATH_FIELDS:
        if not str(flat_config.get(key, "")).strip():
            errors.append(f"{label} cannot be empty.")

    try:
        forum_max = int(flat_config.get("stage2.forum_max_rounds", 0))
        forum_min = int(flat_config.get("stage2.forum_min_rounds_for_sufficient", 0))
    except (TypeError, ValueError):
        errors.append("Stage2 forum rounds must be integers.")
        return errors

    if forum_min > forum_max:
        errors.append(
            "stage2.forum_min_rounds_for_sufficient must be <= stage2.forum_max_rounds."
        )

    return errors


def build_failure_status_payload(
    status: Dict[str, Any],
    *,
    error_message: str,
    stage: str = "",
    node_name: str = "PipelineConsole",
    now_utc: str | None = None,
) -> Dict[str, Any]:
    payload = dict(status or {})
    now = (now_utc or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")).strip()
    payload["version"] = 2
    payload["run_id"] = str(payload.get("run_id", "")).strip() or uuid.uuid4().hex
    payload.setdefault("events", [])

    events = payload["events"]
    if not isinstance(events, list):
        events = []
        payload["events"] = events
    next_seq = len(events) + 1

    entry = {
        "seq": next_seq,
        "ts": now,
        "event": "exit",
        "stage": stage or str(payload.get("current_stage", "")).strip(),
        "node": node_name,
        "branch_id": "main",
        "status": "failed",
        "error": str(error_message or "").strip(),
    }
    events.append(entry)
    payload["current_stage"] = entry["stage"]
    payload["current_node"] = node_name
    return payload
