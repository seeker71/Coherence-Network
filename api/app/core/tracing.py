# spec: 181-full-code-traceability
# idea: full-traceability-chain
"""Runtime traceability decorator: @spec_traced attaches spec/idea metadata to functions.

Phase 3.1 of full-code-traceability spec (Spec 181).

Usage:
    from app.core.tracing import spec_traced

    @spec_traced("181-full-code-traceability", idea_id="full-traceability-chain")
    async def my_endpoint(...):
        ...

The decorator has zero call-time overhead — metadata is stored on the function object
at import time (decoration time), not at call time.
"""

from __future__ import annotations

import inspect
import sys
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# Global registry of spec-traced functions
_SPEC_TRACE_REGISTRY: list[dict[str, Any]] = []


def spec_traced(spec_id: str, idea_id: str | None = None, description: str | None = None) -> Callable[[F], F]:
    """Decorator that attaches traceability metadata to a function.

    Stores metadata on the function object at decoration time.
    Zero runtime overhead — does not wrap or alter function behavior.

    Args:
        spec_id: The spec ID this function implements (e.g. "181-full-code-traceability").
        idea_id: Optional idea slug this traces back to.
        description: Optional human description of what this function implements.
    """
    def decorator(fn: F) -> F:
        # Attach metadata directly to the function object
        fn._spec_id = spec_id  # type: ignore[attr-defined]
        fn._idea_id = idea_id  # type: ignore[attr-defined]
        fn._traced = True  # type: ignore[attr-defined]
        fn._trace_description = description or fn.__doc__  # type: ignore[attr-defined]

        # Register in global registry
        try:
            source_file = inspect.getfile(fn)
        except (TypeError, OSError):
            source_file = None

        try:
            source_line = inspect.getsourcelines(fn)[1]
        except (TypeError, OSError):
            source_line = None

        entry: dict[str, Any] = {
            "module": fn.__module__,
            "function": fn.__qualname__,
            "spec_id": spec_id,
            "idea_id": idea_id,
            "description": description or (fn.__doc__ or "").strip().split("\n")[0],
            "file": source_file,
            "line": source_line,
        }
        _SPEC_TRACE_REGISTRY.append(entry)
        return fn

    return decorator  # type: ignore[return-value]


def get_all_spec_traces() -> list[dict[str, Any]]:
    """Return all functions registered with @spec_traced."""
    return list(_SPEC_TRACE_REGISTRY)


def get_spec_traces_for_spec(spec_id: str) -> list[dict[str, Any]]:
    """Return all @spec_traced functions for a given spec."""
    return [t for t in _SPEC_TRACE_REGISTRY if t["spec_id"] == spec_id]


def get_spec_traces_for_idea(idea_id: str) -> list[dict[str, Any]]:
    """Return all @spec_traced functions tracing to a given idea."""
    return [t for t in _SPEC_TRACE_REGISTRY if t.get("idea_id") == idea_id]


def scan_all_modules_for_traced_functions() -> list[dict[str, Any]]:
    """Scan all loaded modules for functions with _traced=True attribute.

    Returns entries including both @spec_traced and legacy @traces_to decorated functions.
    """
    results = list(_SPEC_TRACE_REGISTRY)
    seen = {(r["module"], r["function"]) for r in results}

    for module_name, module in list(sys.modules.items()):
        if module is None or not hasattr(module, "__dict__"):
            continue
        if not (module_name.startswith("app.") or module_name.startswith("api.")):
            continue
        for attr_name in list(vars(module).keys()):
            obj = getattr(module, attr_name, None)
            if obj is None:
                continue
            # Check if callable and has _traced attribute
            if callable(obj) and getattr(obj, "_traced", False):
                key = (getattr(obj, "__module__", module_name), getattr(obj, "__qualname__", attr_name))
                if key in seen:
                    continue
                seen.add(key)
                try:
                    source_file = inspect.getfile(obj)
                except (TypeError, OSError):
                    source_file = None
                try:
                    source_line = inspect.getsourcelines(obj)[1]
                except (TypeError, OSError):
                    source_line = None

                results.append({
                    "module": key[0],
                    "function": key[1],
                    "spec_id": getattr(obj, "_spec_id", getattr(obj, "spec", None)),
                    "idea_id": getattr(obj, "_idea_id", getattr(obj, "idea", None)),
                    "description": str(getattr(obj, "_trace_description", obj.__doc__ or "")).strip().split("\n")[0],
                    "file": source_file,
                    "line": source_line,
                })
    return results
