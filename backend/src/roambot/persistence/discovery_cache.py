"""Bounded, scoped facts and short-lived retrieval plans; no recommendation text."""

import copy
import hashlib
import json
import sqlite3
import threading
import time
from concurrent.futures import Future
from contextlib import contextmanager
from pathlib import Path


class DiscoveryCache:
    def __init__(self, path: Path, capacity=2000, clock=time.time):
        self.path, self.capacity, self.clock = path, capacity, clock
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.pending = {}
        self.rate_lock = threading.Lock()
        self.next_map_request = 0

        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS facts "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL)"
            )

    def throttle_map(self, interval):
        if interval <= 0:
            return
        with self.rate_lock:
            now = time.monotonic()
            wait = max(0, self.next_map_request - now)
            self.next_map_request = max(now, self.next_map_request) + interval
        if wait:
            time.sleep(wait)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get_or_load(self, scope, kind, key, ttl, load):
        encoded = json.dumps([scope, kind, key], sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.lock:
            with self.connect() as db:
                row = db.execute(
                    "SELECT value, expires FROM facts WHERE key=?", (digest,)
                ).fetchone()
            if row and row[1] > self.clock():
                return json.loads(row[0]), True
            future = self.pending.get(digest)
            owner = future is None
            if owner:
                future = self.pending[digest] = Future()
        if not owner:
            return copy.deepcopy(future.result()), True
        try:
            # No database transaction or global lock is held while contacting a Provider.
            value = load()
            raw = json.dumps(value, ensure_ascii=False)
            with self.connect() as db:
                db.execute("DELETE FROM facts WHERE expires<=?", (self.clock(),))
                if len(raw.encode()) <= 1000000 and value:
                    db.execute(
                        "INSERT OR REPLACE INTO facts VALUES (?, ?, ?)",
                        (digest, raw, self.clock() + ttl),
                    )
                db.execute(
                    "DELETE FROM facts WHERE key IN (SELECT key FROM facts "
                    "ORDER BY expires DESC LIMIT -1 OFFSET ?)",
                    (self.capacity,),
                )
            future.set_result(copy.deepcopy(value))
            return value, False
        except BaseException as error:
            future.set_exception(error)
            raise
        finally:
            with self.lock:
                self.pending.pop(digest, None)

    def get(self, scope, kind, key):
        encoded = json.dumps([scope, kind, key], sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.connect() as db:
            row = db.execute("SELECT value, expires FROM facts WHERE key=?", (digest,)).fetchone()
        if row and row[1] > self.clock():
            return json.loads(row[0]), True
        return None, False

    def remember(self, scope, kind, key, value, ttl=300):
        self.get_or_load(scope, kind, key, ttl, lambda: value)
