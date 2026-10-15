"""Bounded SQLite history. Reading and anomaly event are committed atomically."""

import json
import sqlite3
from datetime import datetime
from threading import RLock

from .config import MACHINES


class OutOfOrderError(ValueError):
    pass


class Store:
    def __init__(self, settings):
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = settings
        self.lock = RLock()
        self.db = sqlite3.connect(settings.db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS readings_machine ON readings(machine_id, id DESC);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_machine ON events(machine_id, id DESC);
        """)

    def append(self, record):
        machine_id = record["machine_id"]
        with self.lock, self.db:
            latest = self.db.execute(
                "SELECT timestamp FROM readings WHERE machine_id=? ORDER BY id DESC LIMIT 1",
                (machine_id,),
            ).fetchone()
            if latest and datetime.fromisoformat(record["timestamp"]) <= datetime.fromisoformat(
                latest[0]
            ):
                raise OutOfOrderError(
                    "timestamp must be newer than the last reading for this machine"
                )
            payload = json.dumps(record, allow_nan=False)
            cursor = self.db.execute(
                "INSERT INTO readings(machine_id,timestamp,payload) VALUES (?,?,?)",
                (machine_id, record["timestamp"], payload),
            )
            result = dict(record, id=cursor.lastrowid)
            if record["status"] == "anomaly":
                self.db.execute(
                    "INSERT INTO events(machine_id,payload) VALUES (?,?)", (machine_id, payload)
                )
            self.db.execute(
                """DELETE FROM readings WHERE machine_id=? AND id NOT IN
                (SELECT id FROM readings WHERE machine_id=? ORDER BY id DESC LIMIT ?)""",
                (machine_id, machine_id, self.settings.reading_limit),
            )
            self.db.execute(
                "DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT ?)",
                (self.settings.event_limit,),
            )
            return result

    def history(self, machine_id, limit=60):
        with self.lock:
            rows = self.db.execute(
                "SELECT id,payload FROM readings WHERE machine_id=? ORDER BY id DESC LIMIT ?",
                (machine_id, limit),
            ).fetchall()
            return [dict(json.loads(row["payload"]), id=row["id"]) for row in reversed(rows)]

    def events(self, machine_id=None, limit=100):
        with self.lock:
            if machine_id:
                rows = self.db.execute(
                    "SELECT id,payload FROM events WHERE machine_id=? ORDER BY id DESC LIMIT ?",
                    (machine_id, limit),
                ).fetchall()
            else:
                rows = self.db.execute(
                    "SELECT id,payload FROM events ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(json.loads(row["payload"]), id=row["id"]) for row in rows]

    def overview(self):
        with self.lock:
            latest = {
                key: (rows[-1] if (rows := self.history(key, 1)) else None) for key in MACHINES
            }
            return {
                "latest": latest,
                "reading_count": self.db.execute("SELECT count(*) FROM readings").fetchone()[0],
                "event_count": self.db.execute("SELECT count(*) FROM events").fetchone()[0],
            }

    def close(self):
        with self.lock:
            self.db.close()
