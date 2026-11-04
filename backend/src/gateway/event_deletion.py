"""Delete an event's research state while keeping its registered input datasets."""

import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path

from opinion_gateway.dataset_repository import storage_id


class EventBusy(ValueError):
    pass


def delete_event_research(store, asset_root, thread_id):
    root = Path(asset_root).resolve()
    moved = []
    staging = None
    with closing(sqlite3.connect(store.path, timeout=30)) as db:
        # Acquire the same SQLite writer locks as run submission and the Worker.
        # Queued jobs are removed before a Worker can claim them.
        databases = {
            "runs_db": root / "runs.sqlite",
            "jobs_db": root / "jobs.sqlite",
            "graph_db": store.path.parent / "checkpoints.sqlite",
            "prep_db": root / "event-preparation.sqlite",
            "labels_db": root / "annotation-cache.sqlite",
            "budget_db": root / "label-budget.sqlite",
            "ledger_db": root / "call-ledger.sqlite",
        }
        attached = set()
        for alias, path in databases.items():
            if path.is_file():
                db.execute(f"ATTACH DATABASE ? AS {alias}", (str(path),))
                attached.add(alias)

        def has(alias, table):
            return (
                alias in attached
                and db.execute(
                    f"SELECT 1 FROM {alias}.sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
            )

        def remove(alias, table, column, values):
            if has(alias, table):
                db.executemany(
                    f"DELETE FROM {alias}.{table} WHERE {column}=?",
                    [(v,) for v in values],
                )

        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT event FROM threads WHERE id=?", (thread_id,)
            ).fetchone()
            if row is None:
                raise KeyError(thread_id)
            event_id = row[0]
            event_hash = storage_id(event_id)
            threads = [
                r[0]
                for r in db.execute("SELECT id FROM threads WHERE event=?", (event_id,))
            ]
            if db.execute(
                "SELECT 1 FROM executions JOIN threads ON executions.thread=threads.id "
                "WHERE threads.event=? AND executions.status='running'",
                (event_id,),
            ).fetchone():
                raise EventBusy("event_has_active_work")
            jobs = []
            if has("jobs_db", "jobs"):
                jobs = [
                    json.loads(r[0])
                    for r in db.execute(
                        "SELECT payload FROM jobs_db.jobs WHERE json_extract(payload,'$.event_id')=?",
                        (event_id,),
                    )
                ]
            if any(j["status"] in {"running", "cancel_requested"} for j in jobs):
                raise EventBusy("event_has_active_work")

            schemas = set()
            preparations = []
            if has("prep_db", "preparations"):
                preparations = db.execute(
                    "SELECT id,payload FROM prep_db.preparations WHERE json_extract(payload,'$.event.event_id')=?",
                    (event_id,),
                ).fetchall()
            for _, payload in preparations:
                preparation = json.loads(payload)
                if (
                    preparation.get("status") == "preparing"
                    and preparation.get("lease_until", 0) > time.time()
                ):
                    raise EventBusy("event_has_active_work")
                if preparation.get("schema"):
                    schemas.add(preparation["schema"]["schema_version"])

            scopes = {
                hashlib.sha256((event_id + "\0" + j["run_id"]).encode()).hexdigest()
                for j in jobs
            }
            if has("budget_db", "budget_configs"):
                scopes.update(
                    r[0]
                    for r in db.execute(
                        "SELECT id FROM budget_db.budget_configs WHERE json_extract(payload,'$.event.event_id')=?",
                        (event_id,),
                    )
                )

            # Verify every absolute deletion target before moving or removing it.
            # Datasets and the user's original source files are never targets.
            event_dir = root / event_hash
            targets = []
            if event_dir.exists():
                if event_dir.resolve() != event_dir or event_dir.is_junction():
                    raise ValueError("event_storage_link_not_supported")
                targets = [p for p in event_dir.iterdir() if p.name != "datasets"]
                for target in targets:
                    pending = [target]
                    while pending:
                        path = pending.pop()
                        if (
                            path.is_symlink()
                            or path.is_junction()
                            or not path.resolve().is_relative_to(event_dir)
                        ):
                            raise ValueError("event_storage_link_not_supported")
                        if path.is_dir():
                            pending.extend(path.iterdir())
                if targets:
                    staging = Path(
                        tempfile.mkdtemp(prefix=".event-delete-", dir=root)
                    ).resolve()
                    for target in targets:
                        destination = staging / target.name
                        target.rename(destination)
                        moved.append((target, destination))

            remove("prep_db", "preparations", "id", [r[0] for r in preparations])
            if has("labels_db", "annotations"):
                db.executemany(
                    "DELETE FROM labels_db.annotations WHERE json_extract(payload,'$.schema_version')=?",
                    [(s,) for s in schemas],
                )
            for table in ("budgets", "budget_configs"):
                remove("budget_db", table, "id", scopes)
            for table in ("limits", "calls"):
                remove("ledger_db", table, "scope", scopes)
            for table, column in (
                ("batches", "job"),
                ("job_results", "job"),
                ("jobs", "id"),
            ):
                remove("jobs_db", table, column, [j["job_id"] for j in jobs])
            if has("runs_db", "runs"):
                db.execute(
                    "DELETE FROM runs_db.runs WHERE substr(scope,1,65)=?",
                    (event_hash + ":",),
                )
            for table in ("checkpoints", "writes"):
                remove("graph_db", table, "thread_id", threads)
            for table in ("turns", "events", "executions"):
                db.executemany(
                    f"DELETE FROM {table} WHERE thread=?", [(t,) for t in threads]
                )
            db.execute("DELETE FROM threads WHERE event=?", (event_id,))
            db.commit()
        except BaseException:
            db.rollback()
            for original, staged in reversed(moved):
                staged.rename(original)
            if staging:
                staging.rmdir()
            raise
    if staging:
        if staging.parent != root or not staging.name.startswith(".event-delete-"):
            raise ValueError("invalid deletion staging path")
        shutil.rmtree(staging)
    return {
        "event_id": event_id,
        "deleted_thread_ids": threads,
        "datasets_preserved": True,
    }
