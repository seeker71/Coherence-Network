#!/usr/bin/env python3
"""Runtime-surface report — how much of the API runs in CPython vs the Form kernel.

The sibling instrument to ``kernel_attribution_report.py``. That one answers
*which Blueprints fire* when the kernel runs. This one answers a different,
blunter question the body keeps fooling itself about: **how much execution has
actually left CPython for the Form kernel?**

The honest gap this names
-------------------------
"22 routes kernel-served" is true and easy to read as progress. It is also a
flattering half-truth. Two distinct axes hide inside that one number:

  • **kernel USAGE** — how many routes call the kernel at all (22 of 784, ~2.8%).
  • **Python RUNTIME-SHARE** — how much of a request's execution actually runs
    Form-native rather than CPython.

These are NOT the same, and the body must track the second one to honestly
report the journey from Python-runtime toward kernel-runtime. Even on a
kernel-served route the kernel is a **called subroutine inside a CPython
request**, never the runtime:

    FastAPI routes the request           → CPython
    Query/path params bind + coerce       → CPython
    Pydantic validates the inputs         → CPython
    serve_via_kernel orchestrates         → CPython  (preload, parse, fallback)
        └─ the kernel walks the recipe    → Form-native  ← the ONLY kernel part
    parse(value) re-wraps to a Py type    → CPython
    Pydantic builds + serializes response → CPython

The kernel handles the **pure-compute core**; the entire request lifecycle —
routing, binding, validation, orchestration, response — stays CPython by design
(the eligibility seam in ``kernels/API_KERNEL_READINESS.md``). So "kernel-served"
overstates how much runtime left CPython. This report states both numbers and
the layering between them, so the move toward kernel-runtime tracks the RIGHT
metric (runtime-share), not just the route count.

The counter-intuitive truth, made concrete
-------------------------------------------
Transmuting a route INCREASES kernel usage but can ADD CPython: each transmuted
route lands a FastAPI handler, a Pydantic response model, AND a value-identical
``*_py`` fallback (run when no kernel is reachable). The computation moves to the
kernel; the request lifecycle plus a CPython twin of the math stay in the host.
Net Python LOC may GROW even as kernel usage grows. This report measures that
directly: the CPython lines now sitting in the kernel-router files, and the count
of ``*_py`` fallbacks that transmutation added.

What is measured vs stated (the honesty bar)
--------------------------------------------
  • Route counts are EXACT — the same ``@router.<verb>(`` decorator scan the
    wellness probe's vitality denominator uses, so the two readings agree.
  • Kernel-served routes are the ``KERNEL_SERVED_RECIPES`` list imported from
    ``kernel_attribution_report`` (routes as DATA — one source, no duplication).
  • The per-route layering is STRUCTURAL FACT — read off a real handler. The
    CPython-LOC-per-kernel-route figure is a real line count of the kernel-router
    files; it is offered as evidence of the layering's weight, NOT as a precise
    "fraction of runtime" (wall-clock fraction depends on inputs and is dominated
    by FastAPI+Pydantic+network for any real request — stated, not faked).
  • Kernel-FIRST has two honest readings, both exact. SERVED = 0: no route is
    served by the kernel at the LIVE front door (Traefik routes every request to
    CPython; the 22 kernel-served routes are CPython handlers calling the kernel
    as a subroutine). CAPABLE = the count of native handlers in the kernel-router
    manifest (deploy/kernel-router/production-routes.fk) — whole-lifecycle-Form
    routes proven byte-identical in shadow, awaiting the front-door flip. CAPABLE
    is the native surface that EXISTS; SERVED is what fronts live traffic.

This is a SENSING instrument — read-only, no behavior change, like the wellness
probe and the attribution report. It tells the body the unflattering truth about
its runtime-split so the reversal (kernel-as-router) has a baseline to move.

Run
---
    python3 scripts/runtime_surface_report.py            # human-readable
    python3 scripts/runtime_surface_report.py --json     # machine-readable

Exit 0 always — a sensing readout, never a gate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_ROUTERS_DIR = ROOT / "api" / "app" / "routers"

# The route-decorator scan, IDENTICAL to wellness_check._count_api_routes so the
# total-route denominator this report prints matches the wellness vitality line
# to the route. (head/options are excluded the same way — the kernel-served
# surface is all get/post, so the comparison stays apples-to-apples.)
_ROUTE_RE = re.compile(r"@router\.(get|post|patch|put|delete)\(")

# The CPython routers that hold the transmuted (kernel-served) endpoints. Each
# file carries the request-lifecycle code that stays CPython on every kernel
# request: the async handler (routing + query binding), the Pydantic response
# model (validation + serialization), and the value-identical ``*_py`` fallback.
# These are the files whose Python LOC is the per-route CPython weight — the
# honest counterweight to "the computation moved to the kernel". Named as DATA;
# the set tracks the kernel_* router family in api/app/routers/.
_KERNEL_ROUTER_FILES = [
    "kernel_shared.py",      # the shared /utils router + query/result coercion
    "kernel_nodeid.py",
    "kernel_grounded_cv.py",
    "kernel_matching.py",
    "kernel_breath.py",
    "kernel_grounding.py",
    "kernel_scoring.py",
]

# The PRODUCTION kernel-router manifest. Routes with a native Form handler bound
# here are served ENTIRELY in Form by the kernel-router — routing, query binding,
# the compute, AND the JSON response all Form-native, no CPython in the path. That
# is the whole request lifecycle, a categorically deeper move than serve_via_kernel
# (which keeps the lifecycle in CPython and calls the kernel as a guest subroutine).
_KERNEL_ROUTER_MANIFEST = ROOT / "deploy" / "kernel-router" / "production-routes.fk"


def kernel_first_capable_routes() -> list[str]:
    """API routes with a NATIVE Form handler in the kernel-router manifest.

    These serve their ENTIRE request lifecycle in Form (X-Form-Router:
    native-kernel) — the categorical step past serve_via_kernel's guest
    subroutine. They are CAPABLE / proven-byte-identical-in-shadow, NOT yet
    served at the live front door: the manifest is what the durable runtime-share
    flip will front with, but until that flip Traefik still routes every request
    to CPython. So this is the native surface that EXISTS and is proven, awaiting
    the front-door cutover — distinct from kernel-first SERVED, which stays 0.

    Read from the manifest's ``(let routes ...)`` block as DATA (the manifest is
    the one source); ``/health`` and other non-``/api`` probes are excluded so the
    count compares apples-to-apples with the route total. The ``;``-comment lines
    that mention ``/api/...`` paths never match the ``(list "<path>" <handler>)``
    shape, so the scan reads bindings only. Returns [] if the manifest is absent
    (the report degrades to the SERVED count and says so).
    """
    if not _KERNEL_ROUTER_MANIFEST.is_file():
        return []
    try:
        text = _KERNEL_ROUTER_MANIFEST.read_text(encoding="utf-8")
    except OSError:
        return []
    idx = text.find("(let routes")
    block = text[idx:] if idx != -1 else text
    return re.findall(r'\(list\s+"(/api/[^"]+)"\s+[A-Za-z_]\w*\)', block)


def _load_attribution_module():
    """Import kernel_attribution_report for KERNEL_SERVED_RECIPES + trace helpers.

    Loaded by path (sibling script, not a package) so this report reuses the ONE
    canonical kernel-served-routes list rather than duplicating it. Returns the
    module, or None if it cannot be loaded (the report then degrades to route
    counts only and says so).
    """
    path = ROOT / "scripts" / "kernel_attribution_report.py"
    if not path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("kernel_attribution_report", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:
        return None


def count_total_routes() -> int:
    """Total API route decorators across api/app/routers/*.py (probe-exact)."""
    if not _ROUTERS_DIR.is_dir():
        return 0
    total = 0
    for p in _ROUTERS_DIR.glob("*.py"):
        try:
            total += len(_ROUTE_RE.findall(p.read_text(encoding="utf-8")))
        except OSError:
            continue
    return total


def _code_lines(path: Path) -> int:
    """Non-blank, non-comment Python lines in a file (a coarse LOC measure).

    Drops blank lines and full-line ``#`` comments. Not a tokenizer — a stable,
    honest order-of-magnitude count of the CPython that lives in the file. Good
    enough to size the per-route request-lifecycle weight; not claimed as exact.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(1 for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#"))


def _count_py_fallbacks() -> int:
    """Count the value-identical ``*_py`` fallback functions in the kernel routers.

    These are the CPython twins of the kernel recipes — the math, re-implemented
    in Python, run when no kernel is reachable (fresh checkout / CI without the
    compile step / kernel absent). They are net-NEW CPython that transmutation
    ADDED: demonstrable evidence that kernel usage and Python-runtime-reduction
    are different axes. ``def <name>_py(`` across the kernel-router files.
    """
    pat = re.compile(r"\bdef\s+[A-Za-z_][A-Za-z0-9_]*_py\s*\(")
    n = 0
    for name in _KERNEL_ROUTER_FILES:
        p = _ROUTERS_DIR / name
        if p.is_file():
            try:
                n += len(pat.findall(p.read_text(encoding="utf-8")))
            except OSError:
                continue
    return n


def kernel_router_cpython_loc() -> dict:
    """The CPython LOC that lives in the kernel-served routers, per file + total.

    This is the per-route request-lifecycle weight that stays CPython on every
    kernel request — handlers, Pydantic models, and ``*_py`` fallbacks. Set
    against "22 routes serve their compute on the kernel", it is the honest
    counterweight: the computation moved; this Python did not.
    """
    per_file = {}
    total = 0
    for name in _KERNEL_ROUTER_FILES:
        p = _ROUTERS_DIR / name
        loc = _code_lines(p) if p.is_file() else 0
        per_file[name] = loc
        total += loc
    return {"per_file": per_file, "total": total, "present": [n for n in per_file if (_ROUTERS_DIR / n).is_file()]}


def build_report() -> dict:
    """Assemble the runtime-surface reading — the two axes and the honest numbers."""
    total_routes = count_total_routes()
    attr = _load_attribution_module()

    served_routes: list[str] = []
    attr_available = attr is not None
    if attr_available:
        served_routes = [str(e["route"]) for e in attr.KERNEL_SERVED_RECIPES]
    n_served = len(served_routes)

    cpy = kernel_router_cpython_loc()
    py_fallbacks = _count_py_fallbacks()

    capable = kernel_first_capable_routes()
    n_capable = len(capable)

    usage_pct = (100.0 * n_served / total_routes) if total_routes else None
    loc_per_route = (cpy["total"] / n_served) if n_served else None

    return {
        # --- Axis 1: route-level coverage (kernel USAGE) ---
        "total_routes": total_routes,
        "kernel_served_routes": n_served,
        "kernel_served_pct": round(usage_pct, 1) if usage_pct is not None else None,
        # kernel-FIRST = the kernel as the FRONT DOOR (whole lifecycle in Form).
        # Two honest sub-counts the journey needs kept apart:
        #   SERVED  — served kernel-first at the LIVE front door. Still 0: Traefik
        #             routes every request to CPython; the manifest is not yet the
        #             front door (the durable flip is Urs's go + presence).
        #   CAPABLE — native handlers proven byte-identical in shadow in the router
        #             manifest, whole lifecycle in Form, awaiting the front-door
        #             flip. This is the native surface that EXISTS today — the
        #             runtime-share metric genuinely moving, not route-count.
        "kernel_first_served_routes": 0,
        "kernel_first_capable_routes": n_capable,
        "kernel_first_capable_route_names": capable,
        "kernel_first_routes": 0,  # back-compat alias of SERVED: 0 at the front door
        "served_route_names": served_routes,
        # --- Axis 2: the per-route CPython-vs-kernel layering ---
        "kernel_router_cpython_loc": cpy["total"],
        "kernel_router_cpython_loc_per_file": cpy["per_file"],
        "cpython_loc_per_kernel_route": round(loc_per_route, 1) if loc_per_route else None,
        # --- Axis 3: usage vs runtime-reduction are different axes ---
        "py_fallback_functions_added": py_fallbacks,
        # --- meta ---
        "attribution_module_available": attr_available,
    }


# ---------------------------------------------------------------------------
# Rendering — the honest reading, stated plainly. The whole value of this
# instrument is the UNFLATTERING framing, so the prose carries it explicitly.
# ---------------------------------------------------------------------------


def render_human(r: dict) -> str:
    out: list[str] = []
    w = out.append

    w("# Runtime-surface report — CPython vs Form-kernel runtime share")
    w("")
    w("How much of the API actually runs Form-native, stated honestly. The")
    w("companion attribution report says WHICH Blueprints fire; this says HOW")
    w("MUCH execution has left CPython. They are different questions.")
    w("")

    # --- Axis 1 ---
    w("## Axis 1 — kernel USAGE (route-level coverage)")
    w("")
    if r["total_routes"]:
        w(
            f"  {r['kernel_served_routes']}/{r['total_routes']} API routes are "
            f"kernel-served ({r['kernel_served_pct']}%)."
        )
        w(
            f"  {r['total_routes'] - r['kernel_served_routes']} routes run entirely "
            "on CPython — the growth edge."
        )
    else:
        w(f"  {r['kernel_served_routes']} routes kernel-served (total-route count unread).")
    w(
        f"  Served kernel-FIRST at the LIVE front door (kernel as the runtime, "
        f"whole lifecycle in Form): {r['kernel_first_served_routes']}."
    )
    cap = r.get("kernel_first_capable_routes", 0)
    if cap:
        names = ", ".join(r.get("kernel_first_capable_route_names", []))
        w(
            f"  Kernel-FIRST CAPABLE (native handler proven byte-identical in the"
        )
        w(
            f"  router manifest, whole lifecycle in Form, awaiting the front-door"
        )
        w(f"  flip): {cap} — {names}.")
        w("  This is the native surface that EXISTS today: the compute AND the")
        w("  request lifecycle run Form-native, no CPython in the path. It is the")
        w("  runtime-share metric genuinely moving, distinct from route-count.")
    w("  The 22 kernel-SERVED routes above are a different, shallower thing: each")
    w("  is a CPython handler that calls the kernel as a SUBROUTINE inside the")
    w("  request — the kernel is a guest there. The capable routes flip that: the")
    w("  kernel is the runtime, CPython is the upstream for the not-yet-native tail.")
    w("")

    # --- Axis 2 ---
    w("## Axis 2 — the per-route split (what runs where)")
    w("")
    w("  On a kernel-served route, the execution layers like this:")
    w("")
    w("    FastAPI routes the request            → CPython")
    w("    Query/path params bind + coerce        → CPython")
    w("    Pydantic validates the inputs          → CPython")
    w("    serve_via_kernel orchestrates          → CPython  (preload/parse/fallback)")
    w("        └─ the kernel walks the recipe     → Form-native  ← the ONLY kernel part")
    w("    parse(value) re-wraps to a Python type → CPython")
    w("    Pydantic builds + serializes response  → CPython")
    w("")
    w("  The kernel handles the pure-compute CORE; routing, binding, validation,")
    w("  orchestration, and response stay CPython by design (the eligibility seam).")
    w("")
    if r["kernel_router_cpython_loc"]:
        w(
            f"  Weight of that CPython: {r['kernel_router_cpython_loc']} code lines "
            f"across the {len(r['kernel_router_cpython_loc_per_file'])} kernel-router files "
            f"serve {r['kernel_served_routes']} routes"
        )
        if r["cpython_loc_per_kernel_route"]:
            w(
                f"  (~{r['cpython_loc_per_kernel_route']} CPython lines per kernel-served route — "
                "handlers + Pydantic models + fallbacks)."
            )
        w("  Each route's pure-compute core, by contrast, is ONE Form recipe expression.")
        w(
            "  (LOC sizes the layering's weight; it is NOT a wall-clock runtime fraction — "
            "for any real request FastAPI+Pydantic+network dwarf the recipe walk.)"
        )
    w("")

    # --- Axis 3 ---
    w("## Axis 3 — kernel USAGE and Python RUNTIME-REDUCTION are different axes")
    w("")
    w("  Adding a kernel-served route INCREASES usage but can ADD CPython.")
    w("  Transmuting a route lands a FastAPI handler, a Pydantic response model,")
    w("  AND a value-identical *_py fallback. The computation moves to the kernel;")
    w("  the request lifecycle plus a CPython twin of the math stay in the host —")
    w("  so net Python LOC may GROW even as kernel usage grows.")
    w("")
    w(
        f"  Demonstrable: {r['py_fallback_functions_added']} *_py fallback functions live in the "
        "kernel routers — CPython the transmutation ADDED, not removed."
    )
    w("")

    # --- Axis 4 ---
    w("## Axis 4 — where the body is on the journey (Python-runtime → kernel-runtime)")
    w("")
    pct = r["kernel_served_pct"]
    cap = r.get("kernel_first_capable_routes", 0)
    w(
        f"  Still honestly low at the front door. {pct}% of routes touch the kernel"
        if pct is not None
        else "  Still honestly low at the front door"
    )
    w("  at all (as a guest-subroutine); 0 are SERVED kernel-first — Traefik still")
    w("  routes every live request to CPython.")
    w("")
    if cap:
        w(f"  But the reversal is no longer hypothetical. {cap} routes are now")
        w("  kernel-FIRST CAPABLE: native handlers in the router manifest, proven")
        w("  byte-identical to the live api in shadow, whole lifecycle in Form. The")
        w("  capable count moved 0 → {0}: the native front-door surface EXISTS and".format(cap))
        w("  is proven. What remains is the cutover (Traefik → kernel-router), which")
        w("  is a deliberate two-person live-traffic moment, not more code.")
    else:
        w("  The reversal (kernel-as-front-door) has no proven native surface yet.")
    w("")
    w("  The metric to track is runtime-SHARE moving toward the kernel — and it has")
    w("  two honest readings now: kernel-first SERVED (0, the live front door) and")
    w("  kernel-first CAPABLE (the proven native surface, ready to front). Route-")
    w("  count alone stays the wrong metric: it can rise while CPython rises with it.")
    w("")

    if not r["attribution_module_available"]:
        w("  note: kernel_attribution_report not importable — kernel-served count")
        w("        unread; route total + CPython-LOC axes still measured.")
        w("")

    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Runtime-surface report — CPython vs Form-kernel runtime share."
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
