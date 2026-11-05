"""Read-only summaries for the workbench; all numbers come from stored data."""

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from .assets import ArtifactStore
from .dataset_repository import DatasetRepository, storage_id
from .jobs import JobStore


def chart(title, values, kind="bar"):
    return {"title": title, "chart": {"kind": kind}, "data": values}


@lru_cache(maxsize=16)
def dataset_overview(root, event_id, dataset_id):
    records = DatasetRepository(root).read(event_id, dataset_id)
    return summarize_records(records, dataset_id)


def summarize_records(records, dataset_id):
    """Shared descriptive statistics for full datasets and UI-filtered subsets."""
    daily = defaultdict(lambda: {"posts": 0, "engagement": 0})
    platforms, regions, kinds = Counter(), Counter(), Counter()
    fields = (
        "published_at",
        "author_ref",
        "read_count",
        "like_count",
        "comment_count",
        "repost_count",
    )
    missing = {key: 0 for key in fields}
    totals = Counter()
    authors, dates = set(), []
    top = []
    for row in records:
        for key in fields:
            missing[key] += row.get(key) is None or row.get(key) == ""
        totals["posts"] += 1
        media = row.get("media_refs") or []
        totals["images"] += len(media)
        totals["image_posts"] += bool(media)
        score = sum(
            row.get(key) or 0 for key in ("like_count", "comment_count", "repost_count")
        )
        totals["interactions"] += score
        for key in ("like_count", "comment_count", "repost_count"):
            totals[key] += row.get(key) or 0
        if row.get("author_ref"):
            authors.add(row["author_ref"])
        platforms[row.get("platform") or "未知"] += 1
        regions[row.get("region") or "未知"] += 1
        kinds[row.get("kind") or "post"] += 1
        if row.get("published_at"):
            try:
                date = datetime.fromisoformat(row["published_at"])
                if date.tzinfo is None:
                    raise ValueError("timezone missing")
                day = date.astimezone(timezone(timedelta(hours=8))).date().isoformat()
                dates.append(date.isoformat())
                daily[day]["posts"] += 1
                daily[day]["engagement"] += score
            except (ValueError, TypeError):
                missing["published_at"] += 1
        top.append(
            {
                "post_id": row.get("post_id"),
                "content": str(row.get("content") or "")[:220],
                "score": score,
                "published_at": row.get("published_at"),
                "source_url": row.get("source_url"),
            }
        )
    metrics = {
        key: totals[key] for key in ("posts", "images", "image_posts", "interactions")
    }
    metrics["authors"] = len(authors)
    metrics["days"] = len(daily)
    rows = lambda counts: [
        {"label": str(key), "value": value} for key, value in counts.items()
    ]
    return {
        "dataset_id": dataset_id,
        "metrics": metrics,
        "missing": missing,
        "start": min(dates) if dates else None,
        "end": max(dates) if dates else None,
        "top_posts": sorted(top, key=lambda item: item["score"], reverse=True)[:10],
        "charts": {
            "daily": chart(
                "每日帖子数量",
                [{"label": day, "value": daily[day]["posts"]} for day in sorted(daily)],
                "line",
            ),
            "engagement": chart(
                "每日互动热度",
                [
                    {"label": day, "value": daily[day]["engagement"]}
                    for day in sorted(daily)
                ],
                "line",
            ),
            "platforms": chart("平台分布", rows(platforms), "pie"),
            "media": chart(
                "图文构成",
                rows(
                    {
                        "含配图": totals["image_posts"],
                        "纯文本": len(records) - totals["image_posts"],
                    }
                ),
                "pie",
            ),
            "interactions": chart(
                "互动类型",
                rows(
                    {
                        "点赞": totals["like_count"],
                        "评论": totals["comment_count"],
                        "转发": totals["repost_count"],
                    }
                ),
            ),
            "regions": chart("地区分布", rows(dict(regions.most_common(12)))),
            "missing": chart("字段缺失数量", rows(missing)),
        },
    }


def job_progress(root, event_id, job_id):
    store = JobStore(root / "jobs.sqlite")
    job = store.get(job_id)
    if job.event_id != event_id:
        raise KeyError(job_id)
    checkpoints = store.batches(job_id)
    stages = []
    for task in store.parameters(job_id).get("plan", {}).get("tasks", []):
        key = task["task_id"]
        status = (
            "completed"
            if key in checkpoints
            else job.status
            if key == job.stage
            else "pending"
        )
        stages.append({**task, "status": status})
    events = store.events(job_id)
    error = next(
        (item for item in reversed(events) if item["kind"] in ("failed", "partial")),
        None,
    )
    scope = hashlib.sha256((event_id + "\0" + job.run_id).encode()).hexdigest()
    calls = []
    path = root / "call-ledger.sqlite"
    if path.exists():
        with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
            calls = db.execute(
                "SELECT stage,provider,reserved,actual,status,usage FROM calls WHERE scope=? ORDER BY rowid",
                (scope,),
            ).fetchall()
    usage = {
        "calls": len(calls),
        "known_cost": sum(row[3] or 0 for row in calls),
        "cost_complete": bool(calls) and all(row[3] is not None for row in calls),
        "records": [
            {
                "stage": row[0],
                "provider": row[1],
                "reserved_cost": row[2],
                "actual_cost": row[3],
                "status": row[4],
                "usage": json.loads(row[5]),
            }
            for row in calls
        ],
    }
    return {
        "job": job.model_dump(mode="json", exclude={"worker", "lease_token"}),
        "stages": stages,
        "events": events,
        "error": error,
        "usage": usage,
        "supervisor": next(
            (item for item in reversed(events) if item["kind"] == "supervisor_status"),
            None,
        ),
        "diagnosis": next(
            (
                item
                for item in reversed(events)
                if item["kind"] == "supervisor_diagnosis"
            ),
            None,
        ),
    }


def overview(root, threads, selected=None):
    repo, assets = DatasetRepository(root), ArtifactStore(root)
    store = JobStore(root / "jobs.sqlite")
    candidates = [
        item for item in threads if not selected or item["thread_id"] == selected
    ]
    if selected and not candidates:
        raise KeyError(selected)
    # Prefer the most recent committed run across events, then available partial work.
    with sqlite3.connect(store.path) as db:
        order = {
            json.loads(payload)["job_id"]: index
            for index, (payload,) in enumerate(
                db.execute("SELECT payload FROM jobs ORDER BY rowid")
            )
        }
    choices = []
    for thread in candidates:
        jobs = store.list_jobs(thread["event_id"])
        reports = [job for job in jobs if job.status in ("completed", "partial")]
        job = next(
            (
                job
                for job in reports
                if store.result(job.job_id).get("artifacts", {}).get("report")
            ),
            None,
        )
        if job is None:
            job = jobs[0] if jobs else None
        directory = repo.path(storage_id(thread["event_id"]), "datasets")
        datasets = sorted(
            directory.glob("ds-*.json"),
            key=lambda file: file.stat().st_mtime,
            reverse=True,
        )
        if datasets or job:
            choices.append(
                (
                    bool(job and job in reports),
                    order.get(job.job_id, -1) if job else -1,
                    thread,
                    job,
                    datasets,
                )
            )
    if not choices:
        return {"thread_id": None, "dataset": None, "charts": {}, "report": None}
    _, _, thread, job, datasets = max(choices, key=lambda item: (item[0], item[1]))
    event = thread["event_id"]
    refs = store.batches(job.job_id) if job else {}
    if job and job.status in ("completed", "partial"):
        refs.update(store.result(job.job_id).get("artifacts", {}))

    def read(key):
        ref = refs.get(key)
        return (
            assets.read(event, ref.get("run_id", job.run_id), ref["artifact_id"], key)
            if ref and ref.get("artifact_id")
            else {}
        )

    dataset_id = read("input").get("dataset_id") or (
        datasets[0].stem if datasets else None
    )
    charts = read("charts")
    if not charts:
        for result in read("analysis").get("results", []):
            if result.get("table"):
                charts[result["name"]] = {
                    "title": result.get("description", result["name"]),
                    "chart": result.get("chart", {"kind": "bar"}),
                    "data": result["table"][:200],
                }
    return {
        "thread_id": thread["thread_id"],
        "title": thread["title"],
        "run_id": job.run_id if job else None,
        "dataset": dataset_overview(str(root), event, dataset_id)
        if dataset_id
        else None,
        "charts": charts,
        "report": refs.get("report"),
        "has_analysis": bool(charts),
    }
