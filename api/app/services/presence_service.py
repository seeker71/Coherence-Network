"""Presence — felt-witness that others are here too.

When a viewer meets an entity, their browser sends a soft heartbeat every
30s. This service tracks recent heartbeats per entity in a bounded
in-memory dict with per-heartbeat TTL. A read returns how many distinct
session fingerprints have beat within the recent window, not identities —
the surface is felt-witness, not tracking.

No DB writes. When the process restarts, presence resets — and that's
correct: presence is ephemeral by nature. A restart means a new breath.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Iterator


# Per entity: {fingerprint: last_seen_unix}. Default TTL for a heartbeat
# is 90s — a bit longer than the web's 30s poll interval so a brief
# tab-backgrounding doesn't drop the viewer out of the count.
_DEFAULT_WINDOW_SECONDS = 90


_presence: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
_lock = threading.Lock()


def _key(entity_type: str, entity_id: str) -> tuple[str, str]:
    return (entity_type, entity_id)


def beat(
    *,
    entity_type: str,
    entity_id: str,
    fingerprint: str,
    window_seconds: int = _DEFAULT_WINDOW_SECONDS,
) -> dict:
    """Record a heartbeat. Returns the current presence count for this entity.

    ``fingerprint`` is a short opaque session id — the web generates it
    per load in localStorage. We don't cross-correlate it with anything.
    """
    if not fingerprint or not entity_id:
        return {"present": 0}
    now = time.time()
    k = _key(entity_type, entity_id)
    with _lock:
        bucket = _presence[k]
        bucket[fingerprint] = now
        # Prune stale entries while we hold the lock.
        cutoff = now - window_seconds
        for fp, ts in list(bucket.items()):
            if ts < cutoff:
                del bucket[fp]
        count = len(bucket)
    return {"present": count}


def count(
    *,
    entity_type: str,
    entity_id: str,
    fingerprint: str | None = None,
    window_seconds: int = _DEFAULT_WINDOW_SECONDS,
) -> dict:
    """Return presence count for an entity without recording a heartbeat.

    If ``fingerprint`` is given, it is subtracted so the UI shows "others
    present" rather than "present including yourself."
    """
    now = time.time()
    cutoff = now - window_seconds
    k = _key(entity_type, entity_id)
    with _lock:
        bucket = _presence.get(k)
        if not bucket:
            return {"present": 0, "others": 0}
        fps = [fp for fp, ts in bucket.items() if ts >= cutoff]
        present = len(fps)
        others = present - (1 if fingerprint and fingerprint in set(fps) else 0)
    return {"present": present, "others": max(0, others)}


def clear_for_tests() -> None:
    """Test hook — wipe all presence state."""
    with _lock:
        _presence.clear()


def _iter_all() -> Iterator[tuple[tuple[str, str], dict[str, float]]]:
    """Diagnostic iterator — used by /api/presence/summary."""
    with _lock:
        items = list(_presence.items())
    return iter(items)


def summary(window_seconds: int = _DEFAULT_WINDOW_SECONDS) -> dict:
    """Where in the organism are people meeting right now? Aggregate count
    of entities with active presence, plus top-N."""
    now = time.time()
    cutoff = now - window_seconds
    rows: list[dict] = []
    for (entity_type, entity_id), bucket in _iter_all():
        alive = sum(1 for ts in bucket.values() if ts >= cutoff)
        if alive:
            rows.append(
                {"entity_type": entity_type, "entity_id": entity_id, "present": alive}
            )
    rows.sort(key=lambda r: r["present"], reverse=True)
    return {
        "total_entities": len(rows),
        "top": rows[:20],
    }
