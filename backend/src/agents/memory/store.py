import json
import sqlite3
import uuid
from datetime import UTC, datetime


class ThreadStore:
    def __init__(self, root):
        self.path = root / "threads.sqlite"
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY,event TEXT,title TEXT,created TEXT,memory TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS turns (id INTEGER PRIMARY KEY AUTOINCREMENT,thread TEXT,role TEXT,content TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,thread TEXT,kind TEXT,payload TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS executions (id TEXT PRIMARY KEY,thread TEXT,status TEXT,error TEXT)"
            )
            db.execute(
                "UPDATE executions SET status='interrupted',error='gateway_restart' WHERE status='running'"
            )

    def create(self, event, title="新研究会话"):
        from opinion_gateway.dataset_repository import safe_id

        safe_id(event)
        key = uuid.uuid4().hex
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO threads VALUES (?,?,?,?,?)",
                (key, event, title[:120], datetime.now(UTC).isoformat(), "{}"),
            )
        return self.get(key)

    def get(self, key):
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT id,event,title,created,memory FROM threads WHERE id=?", (key,)
            ).fetchone()
            if row is None:
                raise KeyError(key)
            turns = db.execute(
                "SELECT role,content FROM turns WHERE thread=? ORDER BY id", (key,)
            ).fetchall()
        return dict(
            zip(("thread_id", "event_id", "title", "created_at", "memory"), row)
        ) | {
            "memory": json.loads(row[4]),
            "messages": [{"role": r, "content": c} for r, c in turns],
        }

    def list(self):
        with sqlite3.connect(self.path) as db:
            return [
                {"thread_id": i, "event_id": e, "title": t, "created_at": c}
                for i, e, t, c in db.execute(
                    "SELECT id,event,title,created FROM threads ORDER BY created DESC LIMIT 100"
                )
            ]

    def rename(self, key, title):
        title = title.strip()
        if not title or len(title) > 120:
            raise ValueError('title must contain 1 to 120 characters')
        with sqlite3.connect(self.path) as db:
            if not db.execute('UPDATE threads SET title=? WHERE id=?', (title, key)).rowcount:
                raise KeyError(key)
        return self.get(key)

    def append(self, key, role, text):
        self.get(key)
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO turns(thread,role,content) VALUES (?,?,?)",
                (key, role, text),
            )

    def set_memory(self, key, memory):
        self.get(key)
        # Only an explicit operator edit writes durable facts; source text cannot do this.
        payload = json.dumps(memory, ensure_ascii=False, allow_nan=False)
        if len(payload) > 10000:
            raise ValueError("memory exceeds limit")
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE threads SET memory=? WHERE id=?", (payload, key))

    def event(self, key, kind, payload):
        with sqlite3.connect(self.path) as db:
            cursor = db.execute(
                "INSERT INTO events(thread,kind,payload) SELECT ?,?,? "
                "WHERE EXISTS (SELECT 1 FROM threads WHERE id=?)",
                (
                    key,
                    kind,
                    json.dumps({"timestamp": datetime.now(UTC).isoformat(), **payload}, ensure_ascii=False, allow_nan=False),
                    key,
                ),
            )
            return cursor.lastrowid

    def events(self, key, after=0):
        with sqlite3.connect(self.path) as db:
            return [
                {"id": i, "event": k, "data": json.loads(p)}
                for i, k, p in db.execute(
                    "SELECT id,kind,payload FROM events WHERE thread=? AND id>? ORDER BY id LIMIT 100",
                    (key, after),
                )
            ]

    def recent_events(self, key):
        self.get(key)
        with sqlite3.connect(self.path) as db:
            rows = db.execute('SELECT id,kind,payload FROM events WHERE thread=? ORDER BY id DESC LIMIT 100', (key,)).fetchall()
        return [{'id': i, 'event': k, 'data': json.loads(p)} for i, k, p in reversed(rows)]

    def begin_execution(self, thread):
        key = uuid.uuid4().hex
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute("SELECT 1 FROM threads WHERE id=?", (thread,)).fetchone()
                is None
            ):
                raise KeyError(thread)
            if db.execute(
                "SELECT 1 FROM executions WHERE thread=? AND status='running'",
                (thread,),
            ).fetchone():
                raise ValueError("thread already has an active agent run")
            db.execute(
                "INSERT INTO executions VALUES (?,?,?,?)", (key, thread, "running", "")
            )
        return key

    def finish_execution(self, key, status, error=""):
        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE executions SET status=?,error=? WHERE id=?",
                (status, error, key),
            )

    def execution(self, key):
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT id,thread,status,error FROM executions WHERE id=?", (key,)
            ).fetchone()
        if row is None:
            raise KeyError(key)
        return dict(zip(("execution_id", "thread_id", "status", "error_type"), row))

    def latest_execution(self, thread):
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT id FROM executions WHERE thread=? ORDER BY rowid DESC LIMIT 1",
                (thread,),
            ).fetchone()
        return self.execution(row[0]) if row else None
