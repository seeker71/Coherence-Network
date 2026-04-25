"""SQLite-backed sample store.

Durability is the only reason this service exists, so we keep the storage
layer deliberately boring: plain sqlite3, WAL mode, schema created lazily
on first connection, short-lived connections per call. No ORM, no globals,
no locks — SQLite in WAL handles the concurrency we need.

The store is the canonical source for both current-state reads and
historical queries. It knows nothing about HTTP or FastAPI.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS samples (
  ts          TEXT    NOT NULL,
  organ       TEXT    NOT NULL,
  ok          INTEGER NOT NULL,
  latency_ms  INTEGER,
  detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_samples_organ_ts ON samples(organ, ts);
CREATE INDEX IF NOT EXISTS idx_samples_ts       ON samples(ts);

CREATE TABLE IF NOT EXISTS silences (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  organ       TEXT    NOT NULL,
  started_at  TEXT    NOT NULL,
  ended_at    TEXT,
  severity    TEXT    NOT NULL,
  note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_silences_started ON silences(started_at);
CREATE INDEX IF NOT EXISTS idx_silences_organ   ON silences(organ, started_at);
"""


@dataclass(frozen=True)
class Sample:
    ts: str          # ISO8601 UTC
    organ: str
    ok: bool
    latency_ms: int | None
    detail: str | None


@dataclass(frozen=True)
class SilenceRow:
    id: int
    organ: str
    started_at: str
    ended_at: str | None
    severity: str
    note: str | None


def iso_utc(dt: datetime | None = None) -> str:
    """Render a datetime as ISO8601 UTC with second precision."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    """Thread-safe sample store. Open a fresh connection per call."""

    def __init__(self, path: str) -> None:
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._ensure_schema()

    # --- connection helpers ------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as c:
            c.executescript(SCHEMA_SQL)

    # --- writes ------------------------------------------------------------

    def insert_sample(self, sample: Sample) -> None:
        with self._connect() as c:
            c.execute(
                "INSERT INTO samples (ts, organ, ok, latency_ms, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    sample.ts,
                    sample.organ,
                    1 if sample.ok else 0,
                    sample.latency_ms,
                    sample.detail,
                ),
            )

    def insert_samples(self, samples: Iterable[Sample]) -> None:
        rows = [
            (s.ts, s.organ, 1 if s.ok else 0, s.latency_ms, s.detail)
            for s in samples
        ]
        if not rows:
            return
        with self._connect() as c:
            c.executemany(
                "INSERT INTO samples (ts, organ, ok, latency_ms, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )

    def open_silence(self, organ: str, started_at: str, severity: str) -> int:
        with self._connect() as c:
            cur = c.execute(
                "INSERT INTO silences (organ, started_at, severity) VALUES (?, ?, ?)",
                (organ, started_at, severity),
            )
            return int(cur.lastrowid or 0)

    def close_silence(self, silence_id: int, ended_at: str) -> None:
        with self._connect() as c:
            c.execute(
                "UPDATE silences SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
                (ended_at, silence_id),
            )

    def escalate_silence(self, silence_id: int, severity: str) -> None:
        with self._connect() as c:
            c.execute(
                "UPDATE silences SET severity = ? WHERE id = ?",
                (severity, silence_id),
            )

    def delete_samples_older_than(self, cutoff_iso: str) -> int:
        with self._connect() as c:
            cur = c.execute("DELETE FROM samples WHERE ts < ?", (cutoff_iso,))
            return cur.rowcount or 0

    # --- reads -------------------------------------------------------------

    def last_sample_for_organ(self, organ: str) -> Sample | None:
        with self._connect() as c:
            row = c.execute(
                "SELECT ts, organ, ok, latency_ms, detail FROM samples "
                "WHERE organ = ? ORDER BY ts DESC LIMIT 1",
                (organ,),
            ).fetchone()
        return _row_to_sample(row) if row else None

    def recent_samples_for_organ(self, organ: str, limit: int) -> list[Sample]:
        with self._connect() as c:
            rows = c.execute(
                "SELECT ts, organ, ok, latency_ms, detail FROM samples "
                "WHERE organ = ? ORDER BY ts DESC LIMIT ?",
                (organ, limit),
            ).fetchall()
        # Reverse to chronological order for analysis.
        return [_row_to_sample(r) for r in reversed(rows)]

    def samples_for_organ_since(self, organ: str, since_iso: str) -> list[Sample]:
        with self._connect() as c:
            rows = c.execute(
                "SELECT ts, organ, ok, latency_ms, detail FROM samples "
                "WHERE organ = ? AND ts >= ? ORDER BY ts ASC",
                (organ, since_iso),
            ).fetchall()
        return [_row_to_sample(r) for r in rows]

    def count_samples(self) -> int:
        with self._connect() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM samples").fetchone()
        return int(row["n"]) if row else 0

    def ongoing_silences(self) -> list[SilenceRow]:
        with self._connect() as c:
            rows = c.execute(
                "SELECT id, organ, started_at, ended_at, severity, note "
                "FROM silences WHERE ended_at IS NULL ORDER BY started_at ASC"
            ).fetchall()
        return [_row_to_silence(r) for r in rows]

    def ongoing_silence_for_organ(self, organ: str) -> SilenceRow | None:
        with self._connect() as c:
            row = c.execute(
                "SELECT id, organ, started_at, ended_at, severity, note "
                "FROM silences WHERE organ = ? AND ended_at IS NULL "
                "ORDER BY started_at DESC LIMIT 1",
                (organ,),
            ).fetchone()
        return _row_to_silence(row) if row else None

    def silences_since(self, since_iso: str) -> list[SilenceRow]:
        with self._connect() as c:
            rows = c.execute(
                "SELECT id, organ, started_at, ended_at, severity, note "
                "FROM silences "
                "WHERE started_at >= ? OR ended_at IS NULL "
                "ORDER BY started_at DESC",
                (since_iso,),
            ).fetchall()
        return [_row_to_silence(r) for r in rows]


def _row_to_sample(row: sqlite3.Row) -> Sample:
    return Sample(
        ts=row["ts"],
        organ=row["organ"],
        ok=bool(row["ok"]),
        latency_ms=row["latency_ms"],
        detail=row["detail"],
    )


def _row_to_silence(row: sqlite3.Row) -> SilenceRow:
    return SilenceRow(
        id=int(row["id"]),
        organ=row["organ"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        severity=row["severity"],
        note=row["note"],
    )
