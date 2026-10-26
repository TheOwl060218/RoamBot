"""Server-authored temporary results, bound to the existing browser identity."""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class DiscoverySessions:
    def __init__(self, path: Path, clock=time.time):
        self.path, self.clock = path, clock
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS results (id TEXT PRIMARY KEY"
                ", actor TEXT NOT NULL, body TEXT NOT NULL, snapshot TEX"
                "T NOT NULL, expires REAL NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS results_owner ON results(actor)")
            db.execute("DELETE FROM results WHERE expires<=?", (self.clock(),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, key, actor, body, snapshot):
        if snapshot["status"] not in {"completed", "partial"} or not snapshot.get("cards"):
            return
        with self.connect() as db:
            db.execute("DELETE FROM results WHERE expires<=?", (self.clock(),))
            # Refresh contents without extending the original 24-hour deadline.
            db.execute(
                (
                    "INSERT INTO results VALUES(?,?,?,?,?) ON CONFLICT(id) D"
                    "O UPDATE SET body=excluded.body,snapshot=excluded.snaps"
                    "hot WHERE results.actor=excluded.actor"
                ),
                (
                    key,
                    actor,
                    json.dumps(body, ensure_ascii=False),
                    json.dumps(snapshot, ensure_ascii=False),
                    self.clock() + 86400,
                ),
            )
            db.execute(
                "DELETE FROM results WHERE id IN (SELECT id FROM results"
                " ORDER BY expires DESC LIMIT -1 OFFSET 256)"
            )

    def load(self, key, actor):
        with self.connect() as db:
            db.execute("DELETE FROM results WHERE expires<=?", (self.clock(),))
            row = db.execute(
                "SELECT body,snapshot,expires FROM results WHERE id=? AND actor=?", (key, actor)
            ).fetchone()
        return (json.loads(row[0]), json.loads(row[1]), row[2]) if row else None

    def adopt(self, guest, actor):
        with self.connect() as db:
            db.execute("DELETE FROM results WHERE expires<=?", (self.clock(),))
            db.execute("UPDATE results SET actor=? WHERE actor=?", (actor, guest))
