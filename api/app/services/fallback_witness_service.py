"""Fallback witness — honest record of when the body runs on reserve.

Fallback paths are gentle — a graph lookup misses, a provider quota trips, a
model alias is out-of-date — and the organism silently falls back to a
secondary path. That's a feature. The problem is the silence: operators and
contributors see stale data or slower responses and blame the UI.

This service is an in-process witness. Code paths that fall back call
``witness()`` with a short reason. The record lives in a rolling ring buffer
(no DB writes, no blocking I/O) and is readable via ``GET /api/fallbacks``.

The witness is for honesty, not alerting. A few fallbacks per hour is
healthy breathing. A sudden spike reveals where the organism is tender.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Optional


# Ring buffer of recent fallback events. Bounded so memory stays flat.
_MAX_EVENTS = 500
_events: Deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_lock = threading.Lock()


def witness(
    *,
    source: str,
    reason: str,
    context: Optional[dict[str, Any]] = None,
) -> None:
    """Record a fallback event.

    ``source`` is a short stable identifier: "graph->legacy", "executor:
    openrouter->anthropic", "model:gpt-5.3->gpt-5-codex", "translator:
    libretranslate->pass-through".

    ``reason`` is a human-readable single sentence.

    ``context`` is optional — a small dict with entity_type, workspace_id,
    etc. Keep it small; this stays in memory.
    """
    event = {
        "source": source,
        "reason": reason,
        "context": context or {},
        "at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _events.append(event)


def recent(limit: int = 100, source_prefix: Optional[str] = None) -> list[dict[str, Any]]:
    """Read recent fallback events, newest first. Optionally filter by source
    prefix (e.g. "graph" or "executor").
    """
    with _lock:
        snapshot = list(_events)
    snapshot.reverse()
    if source_prefix:
        snapshot = [e for e in snapshot if e["source"].startswith(source_prefix)]
    return snapshot[:limit]


def summary() -> dict[str, Any]:
    """Aggregate counts by source — a quick breath-check on where the body
    is running on reserve."""
    with _lock:
        snapshot = list(_events)
    counts: dict[str, int] = {}
    for e in snapshot:
        counts[e["source"]] = counts.get(e["source"], 0) + 1
    return {
        "total": len(snapshot),
        "by_source": dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True)),
        "earliest": snapshot[0]["at"] if snapshot else None,
        "latest": snapshot[-1]["at"] if snapshot else None,
    }


def clear() -> None:
    """Test hook — reset the witness."""
    with _lock:
        _events.clear()
