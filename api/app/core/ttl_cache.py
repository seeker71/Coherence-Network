"""Tiny in-process TTL cache for expensive read-only aggregations.

Use case: endpoints that do heavy multi-source joins (e.g.
/api/inventory/flow) and can tolerate a few seconds of staleness. Each
entry is keyed on a tuple of call arguments plus a configurable TTL;
when the entry is expired, the next request recomputes it.

Not a replacement for Redis — single-process only, loses all entries on
restart, no eviction beyond expiry. Deliberately small so it's easy to
reason about.

Configurable via:
  - `ttl_seconds` kwarg on the decorator (default 30s)
  - `COHERENCE_TTL_CACHE_DISABLED=1` env var turns all TTL caches off
    so tests and diagnostics see fresh data on every call.

Example:

    from app.core.ttl_cache import ttl_cached

    @ttl_cached(ttl_seconds=30)
    def expensive_flow(x: int, y: str) -> dict:
        ...

The cache key is `(args, tuple(sorted(kwargs.items())))`, so mutable
arguments (lists, dicts) are not supported — callers must normalize to
hashable types or skip the cache.
"""

from __future__ import annotations

import functools
import os
import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_DISABLE_ENV = "COHERENCE_TTL_CACHE_DISABLED"


def _is_disabled() -> bool:
    raw = os.environ.get(_DISABLE_ENV, "")
    return raw.strip() not in ("", "0", "false", "False", "no", "NO")


class _TtlEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, expires_at: float) -> None:
        self.value = value
        self.expires_at = expires_at


def ttl_cached(
    ttl_seconds: float = 30.0,
    *,
    max_entries: int = 128,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that memoizes by argument tuple with a soft TTL.

    - `ttl_seconds`: how long an entry stays valid. If <=0, caching is
      effectively disabled (every call recomputes).
    - `max_entries`: hard cap to prevent unbounded growth. When
      exceeded, the oldest entry (by insertion order) is evicted.

    Thread-safe via a single per-decorator lock. Not async-aware; wrap
    the sync function and call it from async handlers.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache: dict[tuple, _TtlEntry] = {}
        order: list[tuple] = []
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if _is_disabled() or ttl_seconds <= 0:
                return func(*args, **kwargs)
            try:
                key = (args, tuple(sorted(kwargs.items())))
            except TypeError:
                # Unhashable argument — skip cache entirely.
                return func(*args, **kwargs)

            now = time.monotonic()

            with lock:
                entry = cache.get(key)
                if entry is not None and entry.expires_at > now:
                    return entry.value  # fresh hit

            value = func(*args, **kwargs)

            with lock:
                cache[key] = _TtlEntry(value, now + ttl_seconds)
                if key in order:
                    order.remove(key)
                order.append(key)
                while len(order) > max_entries:
                    evicted = order.pop(0)
                    cache.pop(evicted, None)

            return value

        def _cache_clear() -> None:
            with lock:
                cache.clear()
                order.clear()

        wrapper.cache_clear = _cache_clear  # type: ignore[attr-defined]
        wrapper.cache_info = lambda: {  # type: ignore[attr-defined]
            "size": len(cache),
            "max_entries": max_entries,
            "ttl_seconds": ttl_seconds,
        }
        return wrapper

    return decorator
