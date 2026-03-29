# spec: 181-full-code-traceability
# idea: full-code-traceability
from __future__ import annotations
import inspect, sys
from typing import Any, Callable, TypeVar
F = TypeVar("F", bound=Callable[..., Any])
_SPEC_TRACE_REGISTRY: list[dict[str, Any]] = []

def spec_traced(spec_id: str, idea_id: str | None = None, description: str | None = None) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        fn._spec_id = spec_id
        fn._idea_id = idea_id
        fn._traced = True
        fn._trace_description = description or fn.__doc__
        try:
            source_file = inspect.getfile(fn)
        except (TypeError, OSError):
            source_file = None
        try:
            source_line = inspect.getsourcelines(fn)[1]
        except (TypeError, OSError):
            source_line = None
        _SPEC_TRACE_REGISTRY.append({
            "module": fn.__module__,
            "function": fn.__qualname__,
            "spec_id": spec_id,
            "idea_id": idea_id,
            "description": description or (fn.__doc__ or "").strip().split("
")[0],
            "file": source_file,
            "line": source_line,
        })
        return fn
    return decorator

def get_all_spec_traces() -> list[dict[str, Any]]:
    return list(_SPEC_TRACE_REGISTRY)

def get_spec_traces_for_spec(spec_id: str) -> list[dict[str, Any]]:
    return [t for t in _SPEC_TRACE_REGISTRY if t["spec_id"] == spec_id]

def get_spec_traces_for_idea(idea_id: str) -> list[dict[str, Any]]:
    return [t for t in _SPEC_TRACE_REGISTRY if t.get("idea_id") == idea_id]

def scan_all_modules_for_traced_functions() -> list[dict[str, Any]]:
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
                    "description": str(getattr(obj, "_trace_description", obj.__doc__ or "")).strip().split("
")[0],
                    "file": source_file,
                    "line": source_line,
                })
    return results
