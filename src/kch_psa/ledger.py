"""SQLite append-only hash-chain ledger with deterministic replay verification."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator
from uuid import uuid4

from .canonical import canonical_json, digest, utc_now


GENESIS_HASH = "0" * 64
LEDGER_SCHEMA = "kch-psa.hash-chain-ledger.v0.1.0"


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    sequence: int
    event_id: str
    occurred_at: str
    event_type: str
    payload: Any
    payload_sha256: str
    previous_hash: str
    event_hash: str


@dataclass(frozen=True, slots=True)
class LedgerVerification:
    valid: bool
    event_count: int
    head: str
    first_bad_sequence: int | None = None
    reason: str | None = None


class HashChainLedger:
    """A single-writer-safe event ledger; hash chaining is tamper evidence, not a signature."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path, timeout=30, isolation_level=None, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            );
            CREATE INDEX IF NOT EXISTS events_type_sequence
                ON events(event_type, sequence);
            """
        )
        self._connection.execute(
            "INSERT OR IGNORE INTO metadata(key,value) VALUES('schema',?)",
            (LEDGER_SCHEMA,),
        )
        row = self._connection.execute(
            "SELECT value FROM metadata WHERE key='schema'"
        ).fetchone()
        if row is None or row["value"] != LEDGER_SCHEMA:
            raise RuntimeError("LEDGER_SCHEMA_MISMATCH")

    @staticmethod
    def _event_hash(
        sequence: int,
        event_id: str,
        occurred_at: str,
        event_type: str,
        payload_sha256: str,
        previous_hash: str,
    ) -> str:
        envelope = {
            "sequence": sequence,
            "event_id": event_id,
            "occurred_at": occurred_at,
            "event_type": event_type,
            "payload_sha256": payload_sha256,
            "previous_hash": previous_hash,
        }
        return digest(envelope)

    def append(
        self,
        event_type: str,
        payload: Any,
        *,
        event_id: str | None = None,
        occurred_at: str | None = None,
    ) -> LedgerEvent:
        if not event_type or len(event_type) > 160:
            raise ValueError("EVENT_TYPE_INVALID")
        payload_json = canonical_json(payload)
        payload_sha256 = sha256(payload_json.encode("utf-8")).hexdigest()
        event_id = event_id or str(uuid4())
        occurred_at = occurred_at or utc_now()
        with self._lock:
            cursor = self._connection.cursor()
            transaction_started = False
            try:
                cursor.execute("BEGIN IMMEDIATE")
                transaction_started = True
                row = cursor.execute(
                    "SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                previous_hash = row["event_hash"] if row else GENESIS_HASH
                sequence = (row["sequence"] + 1) if row else 1
                event_hash = self._event_hash(
                    sequence,
                    event_id,
                    occurred_at,
                    event_type,
                    payload_sha256,
                    previous_hash,
                )
                cursor.execute(
                    """
                    INSERT INTO events(
                        sequence,event_id,occurred_at,event_type,payload_json,
                        payload_sha256,previous_hash,event_hash
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        sequence,
                        event_id,
                        occurred_at,
                        event_type,
                        payload_json,
                        payload_sha256,
                        previous_hash,
                        event_hash,
                    ),
                )
                cursor.execute("COMMIT")
                transaction_started = False
            except Exception:
                if transaction_started:
                    cursor.execute("ROLLBACK")
                raise
        return LedgerEvent(
            sequence,
            event_id,
            occurred_at,
            event_type,
            json.loads(payload_json),
            payload_sha256,
            previous_hash,
            event_hash,
        )

    def events(self) -> Iterator[LedgerEvent]:
        cursor = self._connection.execute("SELECT * FROM events ORDER BY sequence")
        for row in cursor:
            yield LedgerEvent(
                row["sequence"],
                row["event_id"],
                row["occurred_at"],
                row["event_type"],
                json.loads(row["payload_json"]),
                row["payload_sha256"],
                row["previous_hash"],
                row["event_hash"],
            )

    def verify(self) -> LedgerVerification:
        previous_hash = GENESIS_HASH
        count = 0
        cursor = self._connection.execute("SELECT * FROM events ORDER BY sequence")
        for row in cursor:
            count += 1
            sequence = row["sequence"]
            if sequence != count:
                return LedgerVerification(False, count - 1, previous_hash, sequence, "SEQUENCE_GAP")
            try:
                payload = json.loads(row["payload_json"])
                payload_sha256 = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
            except (json.JSONDecodeError, TypeError, ValueError):
                return LedgerVerification(False, count - 1, previous_hash, sequence, "PAYLOAD_JSON_INVALID")
            if payload_sha256 != row["payload_sha256"]:
                return LedgerVerification(False, count - 1, previous_hash, sequence, "PAYLOAD_HASH_MISMATCH")
            if row["previous_hash"] != previous_hash:
                return LedgerVerification(False, count - 1, previous_hash, sequence, "PREVIOUS_HASH_MISMATCH")
            expected = self._event_hash(
                sequence,
                row["event_id"],
                row["occurred_at"],
                row["event_type"],
                row["payload_sha256"],
                row["previous_hash"],
            )
            if expected != row["event_hash"]:
                return LedgerVerification(False, count - 1, previous_hash, sequence, "EVENT_HASH_MISMATCH")
            previous_hash = row["event_hash"]
        return LedgerVerification(True, count, previous_hash)

    @property
    def head(self) -> str:
        row = self._connection.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return row["event_hash"] if row else GENESIS_HASH

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "HashChainLedger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
