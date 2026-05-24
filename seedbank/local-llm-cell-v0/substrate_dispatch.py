"""substrate_dispatch.py — route host-intrinsic Python calls through
substrate-resident Form recipes when one exists.

Closes GAP-N4 from cell-numerics.form. The mechanism Urs named:

    a `@substrate_dispatch` decorator on the Python function that looks
    up the recipe by name, executes via Form's evaluator, and returns
    the result. Existing call sites remain valid; the runtime route
    changes without source changes.

Honest scope:
    This is the *bridge*, not the full kernel route. The bridge carries
    an in-process registry of (recipe_name → callable). When the
    registry holds a callable for a name, the dispatcher calls it; when
    the registry is empty for that name, the wrapped Python function
    executes as the fallback path. The wrapped function's behavior is
    unchanged when the registry is empty — same numbers, same return
    shape — so existing Python call sites stay correct.

    The full substrate route — looking up `@recipe(<name>)` in the
    persistent substrate via form_evaluate_text — lands when a host
    process boots a substrate session. Today's bridge is the smallest
    move that demonstrates the route; it composes cleanly with the
    full-substrate route once both are in the same process.

The pattern lets recipes in cell-numerics.form, cosine.form, and
substrate-kernel.form actually *execute* through their Form definition
when an alternate implementation has been registered — without
changing any Python call site.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional


# ─── recipe registry — in-process, thread-friendly ──────────────────────
#
# Maps recipe-name → callable. Each callable takes the same arguments
# as the wrapped host function and returns the same shape. Registration
# is the bridge a substrate session opens when it wants to take over a
# host-intrinsic; deregistration restores the host path.

_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_recipe(name: str, fn: Callable[..., Any]) -> None:
    """Register a callable as the substrate-side implementation of
    `name`. The wrapped Python function with @substrate_dispatch(name)
    will route through this callable on next invocation.

    Idempotent — registering the same (name, fn) twice is a no-op.
    Replacing an existing registration is allowed; the last one wins.
    """
    _REGISTRY[name] = fn


def unregister_recipe(name: str) -> Optional[Callable[..., Any]]:
    """Remove the substrate-side implementation of `name`. The
    wrapped Python function falls back to its own body on next call.
    Returns the previously-registered callable, or None.
    """
    return _REGISTRY.pop(name, None)


def registered_recipes() -> list[str]:
    """Names currently held by the registry. Read-only inspection."""
    return sorted(_REGISTRY.keys())


def lookup_recipe(name: str) -> Optional[Callable[..., Any]]:
    """Return the registered callable for `name`, or None if absent."""
    return _REGISTRY.get(name)


# ─── the decorator ──────────────────────────────────────────────────────


def substrate_dispatch(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: mark a Python function as routable through the
    substrate's recipe registry.

    Usage:

        @substrate_dispatch("cosine")
        def _cosine(a, b):
            # Python fallback implementation
            ...

    When a callable is registered under "cosine", every call to
    `_cosine(...)` routes through the registered callable. When no
    callable is registered, the decorated function executes normally.
    The decorator preserves the function's signature and docstring.
    """
    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            recipe = _REGISTRY.get(name)
            if recipe is not None:
                return recipe(*args, **kwargs)
            return fn(*args, **kwargs)

        # Surface the recipe name for introspection — agents debugging
        # a dispatch route can see which name the function is bound to.
        _wrapped.__substrate_recipe__ = name  # type: ignore[attr-defined]
        return _wrapped

    return _decorator


# ─── route-from-substrate helper (for when a session is available) ──────
#
# When a host process has booted the full substrate kernel + Form
# runtime, this helper composes a substrate-routed implementation from
# a recipe name. Today it stays inactive (no session boot in
# seedbank/); when the kernel boots in the same process, the bridge
# is one register_recipe call away:
#
#     from substrate_dispatch import bridge_to_substrate
#     bridge_to_substrate("cosine", session=my_session)
#
# Until then, the registry stays empty for substrate-defined names and
# every call falls through to the Python host-intrinsic. The path is
# walkable; each registration is one breath.


def bridge_to_substrate(name: str, *, session: Any) -> None:
    """Register a substrate-routed implementation of `name` by
    composing form_evaluate_text against the live session.

    Stays a no-op until a substrate `session` is supplied. When a
    session is given, registers a callable that:
      1. Resolves the recipe by name from the substrate
      2. Evaluates it with the call's positional arguments
      3. Returns the result, marshalling Python ↔ Form values

    This is GAP-N4's substrate-route half. The function is named here
    so the bridge has a single entry point; the full marshalling stays
    deliberately minimal until call patterns settle.
    """
    if session is None:
        return

    def _routed(*args: Any, **_kwargs: Any) -> Any:
        try:
            from app.services.substrate.form import form_evaluate_text  # type: ignore
        except ImportError:
            raise RuntimeError(
                "bridge_to_substrate requires app.services.substrate.form; "
                "boot the full substrate kernel before bridging."
            )
        positional = ", ".join(repr(a) for a in args)
        expr = f"{name}({positional})"
        return form_evaluate_text(session, expr)

    register_recipe(name, _routed)
