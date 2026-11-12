"""SQLite persistence. One connection guarded by a lock; the service layer owns all logic."""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS elections (
    id TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL, description TEXT NOT NULL, candidates_json TEXT NOT NULL,
    status TEXT NOT NULL, created_at TEXT NOT NULL,
    opened_at TEXT, closed_at TEXT, tallied_at TEXT,
    kem_pk BLOB NOT NULL, kem_sk BLOB NOT NULL, sig_pk BLOB NOT NULL, sig_sk BLOB NOT NULL,
    manifest_sig BLOB NOT NULL, genesis_hash TEXT NOT NULL,
    closed_head TEXT, closed_count INTEGER, head_sig BLOB
);
CREATE TABLE IF NOT EXISTS voters (
    election_id TEXT NOT NULL, voter_id TEXT NOT NULL, name TEXT NOT NULL,
    pw_hash BLOB NOT NULL, pw_salt BLOB NOT NULL, demo_password TEXT NOT NULL,
    credential_issued INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (election_id, voter_id)
);
CREATE TABLE IF NOT EXISTS credentials (
    election_id TEXT NOT NULL, cred_hash TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (election_id, cred_hash)
);
CREATE TABLE IF NOT EXISTS ballots (
    election_id TEXT NOT NULL, seq INTEGER NOT NULL, prev_hash TEXT NOT NULL, entry_hash TEXT NOT NULL,
    kem_ct BLOB NOT NULL, nonce BLOB NOT NULL, ct BLOB NOT NULL, cast_at TEXT NOT NULL, receipt_sig BLOB NOT NULL,
    PRIMARY KEY (election_id, seq)
);
CREATE TABLE IF NOT EXISTS results (
    election_id TEXT PRIMARY KEY, payload TEXT NOT NULL, signature BLOB NOT NULL, tallied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL, election_id TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attack_snapshots (
    election_id TEXT PRIMARY KEY, ballots_json TEXT NOT NULL, results_json TEXT
);
"""


def default_db_path() -> str:
    if os.environ.get("QVOTE_DB"):
        return os.environ["QVOTE_DB"]
    if os.environ.get("VERCEL"):
        return "/tmp/qvote.db"
    return str(Path(__file__).resolve().parent.parent / "data" / "qvote.db")


class Database:
    def __init__(self, path: str | None = None):
        self.path = path or default_db_path()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.lock = threading.RLock()

    def one(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, args).fetchone()

    def all(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, args).fetchall()

    def run(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, args)

    def transaction(self):
        return _Tx(self.conn)


class _Tx:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self):
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        self.conn.execute("ROLLBACK" if exc_type else "COMMIT")
        return False
