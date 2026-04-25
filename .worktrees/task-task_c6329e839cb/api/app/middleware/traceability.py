"""Runtime traceability: decorators and introspection for spec→idea→function chains.

Usage in routers/services:

    from app.middleware.traceability import traces_to

    @traces_to(spec="122", idea="crypto-treasury-bridge")
    async def deposit_eth(...):
        ...

Query at runtime:

    GET /api/traceability                     → all traced functions
    GET /api/traceability/spec/122            → functions implementing spec 122
    GET /api/traceability/idea/fractal-core   → functions tracing to an idea
"""

from __future__ import annotations

import functools
from typing import Any, Callable

# Global registry of traced functions
_TRACE_REGISTRY: list[dict[str, Any]] = []


def traces_to(
    spec: str | None = None,
    idea: str | None = None,
    description: str | None = None,
) -> Callable:
    """Decorator that registers a function's traceability to a spec and/or idea.

    The decorator does NOT alter function behavior — it only records metadata.
    """
    def decorator(func: Callable) -> Callable:
        entry = {
            "function": func.__qualname__,
            "module": func.__module__,
            "spec": spec,
            "idea": idea,
            "description": description or func.__doc__,
        }
        _TRACE_REGISTRY.append(entry)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_all_traces() -> list[dict[str, Any]]:
    """Return all registered traceability entries."""
    return list(_TRACE_REGISTRY)


def get_traces_for_spec(spec_id: str) -> list[dict[str, Any]]:
    """Return functions tracing to a specific spec."""
    return [t for t in _TRACE_REGISTRY if t.get("spec") == spec_id]


def get_traces_for_idea(idea_id: str) -> list[dict[str, Any]]:
    """Return functions tracing to a specific idea."""
    return [t for t in _TRACE_REGISTRY if t.get("idea") == idea_id]
