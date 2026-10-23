"""SQLite repository with versioned migrations and optimistic layout revisions."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> float:
    return datetime.now(timezone.utc).timestamp()


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def migrate(self):
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("Database schema is newer than this application")
            db.executescript("""
              CREATE TABLE IF NOT EXISTS resources (
                kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
                updated REAL NOT NULL, PRIMARY KEY(kind,id));
              CREATE TABLE IF NOT EXISTS layout_revisions (
                id TEXT NOT NULL, revision INTEGER NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(id,revision));
              CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, requested TEXT,
                inputs TEXT NOT NULL, checkpoint TEXT NOT NULL,
                active_seconds REAL NOT NULL DEFAULT 0, segment_started REAL,
                created REAL NOT NULL, updated REAL NOT NULL, error TEXT);
              PRAGMA user_version=1;
            """)

    def list(self, kind):
        with self.connection() as db:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT data FROM resources WHERE kind=? ORDER BY updated DESC", (kind,))]

    def get(self, kind, key):
        with self.connection() as db:
            row = db.execute("SELECT data FROM resources WHERE kind=? AND id=?", (kind, key)).fetchone()
            return json.loads(row[0]) if row else None

    def put(self, kind, data, immutable=False):
        data = json.loads(json.dumps(data))
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT data FROM resources WHERE kind=? AND id=?", (kind, data["id"])).fetchone()
            if immutable and old:
                if json.loads(old[0]) != data:
                    raise Conflict("Data pack IDs are immutable; import changes under a new ID")
                return data
            if kind == "bases":
                previous = json.loads(old[0]) if old else None
                if previous and data.get("revision") != previous["revision"]:
                    raise Conflict("Layout changed in another tab; reload before saving")
                data["revision"] = (previous["revision"] if previous else 0) + 1
                db.execute("INSERT INTO layout_revisions VALUES (?,?,?)",
                           (data["id"], data["revision"], json.dumps(data)))
            db.execute("INSERT INTO resources VALUES (?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data,updated=excluded.updated",
                       (kind, data["id"], json.dumps(data), now()))
        return data

    def revisions(self, key):
        with self.connection() as db:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT data FROM layout_revisions WHERE id=? ORDER BY revision DESC", (key,))]

    def create_job(self, key, inputs):
        with self.connection() as db:
            db.execute("INSERT INTO jobs(id,status,inputs,checkpoint,created,updated) VALUES (?,?,?,?,?,?)",
                       (key, "queued", json.dumps(inputs), json.dumps({"iteration": 0, "simulations": 0, "leaders": [], "history": []}), now(), now()))

    def job(self, key, include_inputs=False):
        with self.connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (key,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["checkpoint"] = json.loads(result["checkpoint"])
        if include_inputs:
            result["inputs"] = json.loads(result["inputs"])
        else:
            del result["inputs"]
        if result["segment_started"] is not None and result["status"] == "running":
            result["active_seconds"] += max(0, now()-result["segment_started"])
        return result

    def jobs(self):
        with self.connection() as db:
            keys = [r[0] for r in db.execute("SELECT id FROM jobs ORDER BY created DESC")]
        return [self.job(key) for key in keys]

    def backup(self, destination):
        target = sqlite3.connect(destination)
        try:
            with self.connection() as source:
                source.backup(target)
        finally:
            target.close()
