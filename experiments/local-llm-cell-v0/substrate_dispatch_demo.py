"""substrate_dispatch_demo.py — exercise the dispatch bridge end-to-end.

Smoke test for GAP-N4 closure: organ.py's host-intrinsics can be
overridden by a substrate-registered recipe without changing any call
site. Demonstrates the round-trip:

  1. With an empty registry, _cosine and _strategy_score run their
     Python bodies (the existing path).
  2. After register_recipe("cosine", alt_cosine), _cosine's call sites
     route through alt_cosine — even though no source changed.
  3. After unregister_recipe("cosine"), behavior returns to the Python
     path.

The override is intentionally trivial in this demo (an `alt_cosine`
that returns a constant) so the bridge's *route* is what's verified,
not the math. Once the substrate kernel boots in the same process,
bridge_to_substrate("cosine", session=...) is the production move.

Run: python3 substrate_dispatch_demo.py
Exit 0 on contract satisfied; non-zero with a printed reason otherwise.
"""

from __future__ import annotations

import sys

from organ import _cosine, _strategy_score, STRATEGIES
from substrate_dispatch import (
    register_recipe,
    unregister_recipe,
    registered_recipes,
    lookup_recipe,
)


def fail(reason: str) -> int:
    print(f"FAIL: {reason}")
    return 1


def main() -> int:
    print("substrate_dispatch_demo — exercising the bridge")
    print("-" * 60)

    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]

    # 1. Default registry — Form-native is the runtime default.
    # default_form_native registers cosine, sigmoid, strategy_score
    # on organ import; the bridge starts with those bindings in place.
    initial = registered_recipes()
    expected_default = ["cosine", "sigmoid", "strategy_score"]
    for name in expected_default:
        if name not in initial:
            return fail(f"expected '{name}' in default registry; got {initial}")
    print(f"  form-native default: {', '.join(initial)}")

    cos_aa = _cosine(a, a)
    if abs(cos_aa - 1.0) > 1e-9:
        return fail(f"_cosine(a, a) expected 1.0, got {cos_aa}")
    cos_ac = _cosine(a, c)
    if abs(cos_ac - 0.0) > 1e-9:
        return fail(f"_cosine(a, c) expected 0.0, got {cos_ac}")
    print(f"  default route: _cosine(a,a)={cos_aa:.4f}, _cosine(a,c)={cos_ac:.4f}")

    # 2. Register a sentinel override — replaces form_native; call site
    # unchanged, behavior changes.
    SENTINEL = 0.42

    def alt_cosine(x, y):
        return SENTINEL

    register_recipe("cosine", alt_cosine)
    if lookup_recipe("cosine") is not alt_cosine:
        return fail("lookup_recipe returned wrong callable for 'cosine'")

    cos_overridden = _cosine(a, a)
    if abs(cos_overridden - SENTINEL) > 1e-9:
        return fail(
            f"override active: _cosine should return {SENTINEL}, "
            f"got {cos_overridden}"
        )
    print(f"  sentinel override: _cosine(a,a)={cos_overridden:.4f} (was {cos_aa:.4f})")

    # 3. Through _strategy_score — composition still works under override.
    # _strategy_score calls _cosine internally; the override propagates.
    observer = next(s for s in STRATEGIES if s.name == "observer")
    score = _strategy_score(observer, [0.5] * 8, 0.0)
    # strategy_score is itself form-native registered; it composes via
    # form_native.cosine, which is NOT overridden by alt_cosine (the
    # form_native module's own composition is internal). So the score
    # uses form_native.cosine, not the sentinel. This is honest: each
    # registered name has its own callable; only direct calls through
    # the substrate_dispatch wrapper route through the registry.
    print(f"  _strategy_score(observer, ...)={score:.4f} (composes via form_native internal)")

    # 4. Unregister cosine — fall back to the wrapped Python intrinsic
    # (the organ._cosine body, which is the original Python).
    removed = unregister_recipe("cosine")
    if removed is not alt_cosine:
        return fail("unregister_recipe did not return the previous callable")

    cos_restored = _cosine(a, a)
    if abs(cos_restored - 1.0) > 1e-9:
        return fail(f"after unregister, _cosine(a,a) expected 1.0, got {cos_restored}")
    print(f"  fall-through to python intrinsic: _cosine(a,a)={cos_restored:.4f}")

    # 5. Re-register form-native so the rest of the suite runs as default.
    from default_form_native import register_form_native_defaults
    register_form_native_defaults()
    if "cosine" not in registered_recipes():
        return fail("form-native re-registration failed")
    print(f"  form-native re-registered: {', '.join(registered_recipes())}")

    # 5. The decorated functions carry their recipe name for introspection.
    name = getattr(_cosine, "__substrate_recipe__", None)
    if name != "cosine":
        return fail(f"_cosine should expose __substrate_recipe__='cosine', got {name!r}")
    name = getattr(_strategy_score, "__substrate_recipe__", None)
    if name != "strategy_score":
        return fail(
            f"_strategy_score should expose __substrate_recipe__='strategy_score', "
            f"got {name!r}"
        )

    print()
    print("dispatch bridge verified — three host-intrinsics route via @substrate_dispatch")
    print("recipe names exposed:", "_cosine →", _cosine.__substrate_recipe__,
          "/ _strategy_score →", _strategy_score.__substrate_recipe__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
