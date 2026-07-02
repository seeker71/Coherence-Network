"""Stone: retry the ingest on a lock-timeout cancellation (2026-07-02).

The DB now cancels a lock-waiter fast (lock_timeout=5s) instead of hanging for
hours — but the canceled waiter surfaced to the client as a 500. Interning is
content-addressed and idempotent, so a fresh-session retry is safe: it absorbs
transient contention into a transparent success. Bounded, so a genuine long
holder fails fast with a retryable 503, never an unbounded spin.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from app.routers import substrate as sub


class LockNotAvailable(Exception):
    """Stand-in for psycopg2.errors.LockNotAvailable (matched by class name)."""


def _lock_err() -> OperationalError:
    return OperationalError(
        "UPDATE substrate_nodes ...",
        {},
        LockNotAvailable("canceling statement due to lock timeout"),
    )


def _other_op_err() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("connection reset by peer"))


def test_is_lock_timeout_detects_only_lock_cancellations():
    assert sub._is_lock_timeout(_lock_err()) is True
    assert sub._is_lock_timeout(_other_op_err()) is False
    assert sub._is_lock_timeout(ValueError("nope")) is False


def test_ingest_retries_bounded_then_503_on_sustained_lock(monkeypatch):
    """Sustained lock contention: retried exactly _INGEST_LOCK_RETRIES times,
    then a retryable 503 (not a bare 500, not an infinite spin)."""
    calls = {"n": 0}

    def always_locked(*a, **k):
        calls["n"] += 1
        raise _lock_err()

    monkeypatch.setattr(sub, "ingest_markdown_text", always_locked)
    monkeypatch.setattr(sub.time, "sleep", lambda *_: None)  # no real backoff wait

    req = sub.IngestRequest(domain="memory", content="---\nname: x\n---\n\n# x\n\ny")
    with pytest.raises(HTTPException) as ei:
        sub.ingest_content(req)
    assert ei.value.status_code == 503
    assert "lock contention" in str(ei.value.detail).lower()
    assert calls["n"] == sub._INGEST_LOCK_RETRIES


def test_ingest_does_not_retry_non_lock_errors(monkeypatch):
    """A non-lock OperationalError is a real fault — surfaced, not retried."""
    calls = {"n": 0}

    def other_error(*a, **k):
        calls["n"] += 1
        raise _other_op_err()

    monkeypatch.setattr(sub, "ingest_markdown_text", other_error)

    req = sub.IngestRequest(domain="memory", content="---\nname: x\n---\n\n# x\n\ny")
    with pytest.raises(OperationalError):
        sub.ingest_content(req)
    assert calls["n"] == 1  # no retry


def test_ingest_retry_advances_past_a_transient_lock(monkeypatch):
    """A lock-timeout on the first attempt does not fail the request — the loop
    advances to a second attempt (proven by a sentinel raised there)."""
    state = {"n": 0}

    class _Reached(Exception):
        pass

    def flaky(*a, **k):
        state["n"] += 1
        if state["n"] == 1:
            raise _lock_err()      # transient lock — should be retried
        raise _Reached("second attempt reached")

    monkeypatch.setattr(sub, "ingest_markdown_text", flaky)
    monkeypatch.setattr(sub.time, "sleep", lambda *_: None)

    req = sub.IngestRequest(domain="memory", content="---\nname: x\n---\n\n# x\n\ny")
    with pytest.raises(_Reached):
        sub.ingest_content(req)
    assert state["n"] == 2  # lock-timeout on attempt 1 -> retried -> attempt 2
