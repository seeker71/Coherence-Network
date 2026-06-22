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
    serve_via_kernel orchestrates         → CPython  (preload, parse, dispatch)
        └─ the kernel walks the recipe    → Form-native  ← the ONLY kernel part
    parse(value) re-wraps to a Py type    → CPython
    Pydantic builds + serializes response → CPython

The kernel handles the **pure-compute core**; the current guest-route lifecycle —
routing, binding, validation, orchestration, response — still runs in CPython.
That is present implementation, not protected architecture. So "kernel-served"
overstates how much runtime left CPython. This report states both numbers and
the layering between them, so the move toward kernel-runtime tracks the RIGHT
metric (runtime-share), not just the route count.

The counter-intuitive truth, made concrete
-------------------------------------------
Transmuting a route still leaves CPython request-lifecycle code in place: each
transmuted route lands a FastAPI handler and a Pydantic response model while the
compute core moves to the kernel. Older passes also left value-identical
``*_py`` parity bodies in production route files; that is now treated as dead
weight. This report measures both: the CPython lines still required for the
guest-route lifecycle, and the count of ``*_py`` bodies still present in kernel
routers. The desired count is zero.

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
  • Kernel-FIRST has two honest readings. SERVED is read from public native
    entrance probes: the production manifest at /api/attention/kernel-runtime
    and the sibling BML read front door at /api/ready. CAPABLE is the count of
    native handlers in deploy/kernel-router/production-routes.fk plus
    deploy/front-door/api.bml whether or not every public router has been flipped
    yet. Byte parity remains useful evidence for promoted twins, but the
    operational gate is simpler: the website, API smoke, tool flows, native
    observability, and fallback all still work.

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
import os
import re
import sys
import urllib.error
import urllib.request
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
# model (validation + serialization). Older passes also carried ``*_py`` parity
# bodies here; the report keeps counting them as a regression guard.
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
_BML_FRONT_DOOR_CATALOG = ROOT / "deploy" / "front-door" / "api.bml"
_KERNEL_ROUTER_COMPOSE = ROOT / "deploy" / "kernel-router" / "docker-compose.kernel-router.yml"
_DEFAULT_FRONT_DOOR_PROBE_PATH = "/api/attention/kernel-runtime"
_DEFAULT_BML_READ_PROBE_PATH = "/api/ready"


def kernel_first_capable_routes() -> list[str]:
    """API routes with a NATIVE handler in the Form manifest or BML catalog.

    These serve their ENTIRE request lifecycle through the kernel router
    (X-Form-Router: native-kernel) — the categorical step past
    serve_via_kernel's guest subroutine. They are CAPABLE: a real native handler
    exists in either the older Form manifest or the high-grammar BML front-door
    catalog and the dispatch mechanism is proven. Whether they are SERVED is
    read from the public front-door provenance probe, because the operational
    truth is the current Traefik entrance and deployed catalog, not an old
    assumption. Byte parity remains useful evidence for promoted twins; the
    native-first deploy gate is web/API/tool smoke, native observability, and
    explicit fallback.

    Read from the manifest's ``(let routes ...)`` block as DATA (the manifest is
    the one source); ``/health`` and other non-``/api`` probes are excluded so the
    count compares apples-to-apples with the route total. The scanner sees both
    raw ``(list "<path>" <handler>)`` rows and higher-grammar
    ``(kh-route-data-ref "<id>" <handler>)`` rows resolved through the sibling
    ``*-data.json`` file, so promoting a route into a ``RouteCell`` does not make
    it invisible. Path-only rows keep returning bare paths for back-compat.
    Method-specific ``kh-route`` rows return ``"METHOD /api/path"`` so PATCH and
    DELETE wildcard bindings sharing a path remain distinct native capabilities.
    The ``;``-comment lines that mention ``/api/...`` paths never match the
    binding shapes, so the scan reads bindings only. Returns [] if the manifest
    is absent (the report degrades to the SERVED count and says so).
    """
    routes: list[str] = []
    seen: set[str] = set()
    for route_label in kernel_router_manifest_routes() + bml_front_door_routes():
        if route_label not in seen:
            routes.append(route_label)
            seen.add(route_label)
    return routes


def kernel_router_manifest_routes() -> list[str]:
    """Native route labels bound by the production Form router manifest."""
    if not _KERNEL_ROUTER_MANIFEST.is_file():
        return []
    try:
        text = _KERNEL_ROUTER_MANIFEST.read_text(encoding="utf-8")
    except OSError:
        return []
    idx = text.find("(let routes")
    block = _strip_form_line_comments(text[idx:] if idx != -1 else text)
    block = _with_referenced_route_blocks(_strip_form_line_comments(text), block)
    route_data = _kernel_route_data_patterns(_KERNEL_ROUTER_MANIFEST)
    routes: list[str] = []
    seen: set[str] = set()
    route_row = re.compile(
        r'\(list\s+"(/api/[^"]+)"\s+[A-Za-z_]\w*\)'
        r'|\(kh-route-data-ref\s+"([^"]+)"\s+[A-Za-z_]\w*\)'
        r'|\(kh-route\s+"[^"]+"\s+"([A-Z]+|ANY)"\s+"(/api/[^"]+)"'
        r'\s+\d+\s+"[^"]+"\s+"[^"]*"\s+\d+\)'
        r'|\(list\s+43004\s+"[^"]+"\s+"([A-Z]+|ANY)"\s+"(/api/[^"]+)"'
        r'\s+\d+\s+"[^"]+"\s+"[^"]*"\s+\d+\)'
    )
    for match in route_row.finditer(block):
        path = match.group(1)
        route_label = path
        if path is None:
            route_id = match.group(2)
            route_label = route_data.get(route_id) if route_id is not None else None
        if route_label is None and match.group(3) is not None and match.group(4) is not None:
            method = match.group(3)
            path = match.group(4)
            route_label = path if method == "ANY" else f"{method} {path}"
        if route_label is None and match.group(5) is not None and match.group(6) is not None:
            method = match.group(5)
            path = match.group(6)
            route_label = path if method == "ANY" else f"{method} {path}"
        if route_label and route_label not in seen:
            routes.append(route_label)
            seen.add(route_label)
    return routes


def _with_referenced_route_blocks(text: str, route_block: str) -> str:
    """Include zero-arg route-list helper bodies referenced from ``routes``.

    Production manifests can keep method-specific route rows in a helper such as
    ``(mpg-route-choice-routes)`` and splice that helper into ``(let routes ...)``.
    The runtime-surface report is a scanner, not the Form evaluator, so it must
    expand those referenced helper bodies before applying the row regex.
    """
    blocks = [route_block]
    seen: set[str] = set()
    for name in re.findall(r"\(([A-Za-z_][A-Za-z0-9_-]*)\)", route_block):
        if name in seen:
            continue
        seen.add(name)
        start = text.find(f"(defn {name} ")
        if start == -1:
            continue
        helper = _balanced_form_at(text, start)
        if "kh-route" in helper or "(list 43004" in helper:
            blocks.append(helper)
    return "\n".join(blocks)


def _balanced_form_at(text: str, start: int) -> str:
    """Return the balanced s-expression starting at ``start``, or ``\"\"``."""
    depth = 0
    in_string = False
    escaping = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaping:
                escaping = False
            elif ch == "\\":
                escaping = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return ""


def bml_front_door_routes() -> list[str]:
    """API routes with a high-grammar BML front-door handler."""
    if not _BML_FRONT_DOOR_CATALOG.is_file():
        return []
    try:
        text = _BML_FRONT_DOOR_CATALOG.read_text(encoding="utf-8")
    except OSError:
        return []
    routes: list[str] = []
    seen: set[str] = set()
    route_row = re.compile(
        r'route\("[^"]+",\s*"([A-Z]+)",\s*"(/api/[^"]+)",\s*\d+,\s*"[^"]+",\s*"[^"]*"'
    )
    for method, path in route_row.findall(_strip_form_line_comments(text)):
        route_label = path if method == "GET" else f"{method} {path}"
        if route_label not in seen:
            routes.append(route_label)
            seen.add(route_label)
    return routes


def bml_front_door_read_routes() -> list[str]:
    """GET/read BML route labels intended for grouped public ingress."""
    if not _BML_FRONT_DOOR_CATALOG.is_file():
        return []
    try:
        text = _BML_FRONT_DOOR_CATALOG.read_text(encoding="utf-8")
    except OSError:
        return []
    routes: list[str] = []
    seen: set[str] = set()
    route_row = re.compile(
        r'route\("[^"]+",\s*"GET",\s*"(/api/[^"]+)",\s*\d+,\s*"[^"]+",\s*"[^"]*"'
    )
    for path in route_row.findall(_strip_form_line_comments(text)):
        if path not in seen:
            routes.append(path)
            seen.add(path)
    return routes


def bml_read_ingress_declared() -> bool:
    """Whether the deploy overlay declares the grouped BML GET/read ingress."""
    if not _KERNEL_ROUTER_COMPOSE.is_file():
        return False
    try:
        text = _KERNEL_ROUTER_COMPOSE.read_text(encoding="utf-8")
    except OSError:
        return False
    required = (
        "coherence-api-bml-read-core-batch",
        "coherence-api-bml-read-ideas-agent-batch",
        "coherence-api-bml-read-relation-batch",
        "coherence-api-bml-read-sensing-batch",
        "coherence-api-bml-read-operations-batch",
        "coherence-api-bml-read-observe-batch",
    )
    return all(name in text for name in required)


def _strip_form_line_comments(text: str) -> str:
    """Remove Form ``;`` line comments before regex scanning route rows."""
    return "\n".join(line.split(";", 1)[0] for line in text.splitlines())


def _kernel_route_data_patterns(manifest: Path) -> dict[str, str]:
    """Route-data id → path for ``RouteCell``/``kh-route-data-ref`` rows."""
    path = manifest.with_name(f"{manifest.stem}-data.json")
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    routes = payload.get("routes")
    if not isinstance(routes, dict):
        return {}
    out: dict[str, str] = {}
    for route_id, row in routes.items():
        if not isinstance(route_id, str) or not isinstance(row, dict):
            continue
        pattern = row.get("pattern")
        if isinstance(pattern, str) and pattern.startswith("/api/"):
            out[route_id] = pattern
    return out

def probe_kernel_front_door() -> dict:
    """Read the public API front-door provenance header.

    The manifest tells us which routes are kernel-first CAPABLE. The live public
    header tells us whether Traefik is actually sending api.coherencycoin.com to
    the kernel-router. When the probe route returns X-Form-Router: native-kernel,
    served count is inferred from the manifest: the same router process owns the
    manifest and will native-serve every listed handler while fanning out the tail.
    If the probe is unreachable, the report marks the front door unread instead
    of preserving the old pre-flip assumption as fact.
    """
    api = os.environ.get("COHERENCE_API_BASE", "https://api.coherencycoin.com").rstrip("/")
    path = os.environ.get("KERNEL_FRONT_DOOR_PROBE_PATH", _DEFAULT_FRONT_DOOR_PROBE_PATH)
    url = f"{api}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "runtime-surface-report/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            body = resp.read(256).decode("utf-8", errors="replace")
            router = resp.headers.get("X-Form-Router", "")
            return {
                "url": url,
                "reachable": True,
                "status": resp.status,
                "x_form_router": router,
                "kernel_front_door": router == "native-kernel",
                "reported_native_route_count": _reported_native_route_count(body),
                "body_preview": body,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(256).decode("utf-8", errors="replace")
        router = exc.headers.get("X-Form-Router", "")
        return {
            "url": url,
            "reachable": True,
            "status": exc.code,
            "x_form_router": router,
            "kernel_front_door": router == "native-kernel",
            "reported_native_route_count": _reported_native_route_count(body),
            "body_preview": body,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "reachable": False,
            "status": None,
            "x_form_router": "",
            "kernel_front_door": False,
            "error": str(exc),
        }


def probe_bml_read_front_door() -> dict:
    """Read a public BML read-route proof header.

    The old kernel-runtime metrics route reports the production Form manifest's
    native route count. The BML front-door is a sibling native entrance, so it
    needs its own proof read: a stable GET/read route must return the BML handler
    and native authority headers before the report counts the grouped BML read
    lane as SERVED.
    """
    api = os.environ.get("COHERENCE_API_BASE", "https://api.coherencycoin.com").rstrip("/")
    path = _DEFAULT_BML_READ_PROBE_PATH
    url = f"{api}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "runtime-surface-report/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            body = resp.read(128).decode("utf-8", errors="replace")
            router = resp.headers.get("X-Form-Router", "")
            handler = resp.headers.get("X-Form-Handler", "")
            authority = resp.headers.get("X-Form-Python-Authority", "")
            return {
                "url": url,
                "reachable": True,
                "status": resp.status,
                "x_form_router": router,
                "x_form_handler": handler,
                "x_form_python_authority": authority,
                "bml_read_front_door": (
                    router == "native-kernel"
                    and handler == "api_ready"
                    and authority.lower() == "false"
                ),
                "body_preview": body,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(128).decode("utf-8", errors="replace")
        router = exc.headers.get("X-Form-Router", "")
        handler = exc.headers.get("X-Form-Handler", "")
        authority = exc.headers.get("X-Form-Python-Authority", "")
        return {
            "url": url,
            "reachable": True,
            "status": exc.code,
            "x_form_router": router,
            "x_form_handler": handler,
            "x_form_python_authority": authority,
            "bml_read_front_door": False,
            "body_preview": body,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "reachable": False,
            "status": None,
            "x_form_router": "",
            "x_form_handler": "",
            "x_form_python_authority": "",
            "bml_read_front_door": False,
            "error": str(exc),
        }


def _reported_native_route_count(body: str) -> int | None:
    match = re.search(r'"native_route_count"\s*:\s*(\d+)', body)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


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


def _count_py_parity_references() -> int:
    """Count ``*_py`` functions still present in the kernel routers.

    These used to be CPython twins of the kernel recipes. Production route
    modules should now be dispatch-only, so this count is a regression guard.
    ``def <name>_py(`` across the kernel-router files.
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
    kernel request — handlers and Pydantic models. Set
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
    py_parity_references = _count_py_parity_references()

    capable = kernel_first_capable_routes()
    n_capable = len(capable)
    manifest_capable = kernel_router_manifest_routes()
    bml_read_routes = bml_front_door_read_routes()
    front_door = probe_kernel_front_door()
    reported_native_route_count = front_door.get("reported_native_route_count")
    bml_ingress_declared = bml_read_ingress_declared()
    bml_front_door = (
        probe_bml_read_front_door()
        if bml_ingress_declared
        else {
            "reachable": False,
            "bml_read_front_door": False,
            "reason": "grouped BML read ingress undeclared",
        }
    )
    manifest_served = 0
    if front_door.get("kernel_front_door"):
        manifest_served = (
            reported_native_route_count
            if isinstance(reported_native_route_count, int)
            else len(manifest_capable)
        )
    bml_read_served = len(bml_read_routes) if bml_front_door.get("bml_read_front_door") else 0
    n_front_door_served = min(n_capable, manifest_served + bml_read_served)

    usage_pct = (100.0 * n_served / total_routes) if total_routes else None
    loc_per_route = (cpy["total"] / n_served) if n_served else None

    return {
        # --- Axis 1: route-level coverage (kernel USAGE) ---
        "total_routes": total_routes,
        "kernel_served_routes": n_served,
        "kernel_served_pct": round(usage_pct, 1) if usage_pct is not None else None,
        # kernel-FIRST = the kernel as the FRONT DOOR (whole lifecycle in Form).
        # Two honest sub-counts the journey needs kept apart:
        #   SERVED  — served kernel-first at the LIVE front door, read from the
        #             public no-header kernel-runtime provenance probe.
        #   CAPABLE — native handlers in the router manifest, whole lifecycle in
        #             Form, ready to front ordinary traffic with Python fan-out for
        #             the tail.
        "kernel_first_served_routes": n_front_door_served,
        "kernel_first_capable_routes": n_capable,
        "kernel_first_capable_route_names": capable,
        "kernel_first_deployed_native_route_count": reported_native_route_count,
        "kernel_first_manifest_capable_routes": len(manifest_capable),
        "kernel_first_manifest_served_routes": manifest_served,
        "bml_front_door_read_capable_routes": len(bml_read_routes),
        "bml_front_door_read_served_routes": bml_read_served,
        "bml_front_door_read_ingress_declared": bml_ingress_declared,
        "bml_front_door_probe": bml_front_door,
        "kernel_first_routes": n_front_door_served,  # back-compat alias of SERVED
        "front_door_probe": front_door,
        "served_route_names": served_routes,
        # --- Axis 2: the per-route CPython-vs-kernel layering ---
        "kernel_router_cpython_loc": cpy["total"],
        "kernel_router_cpython_loc_per_file": cpy["per_file"],
        "cpython_loc_per_kernel_route": round(loc_per_route, 1) if loc_per_route else None,
        # --- Axis 3: usage vs runtime-reduction are different axes ---
        "py_parity_reference_functions_in_kernel_routers": py_parity_references,
        "py_parity_reference_functions_added": py_parity_references,
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
    probe = r.get("front_door_probe") or {}
    if probe:
        if probe.get("reachable"):
            w(
                "  Public front-door probe: {status} {router} at {url}.".format(
                    status=probe.get("status"),
                    router=probe.get("x_form_router") or "<missing-router-header>",
                    url=probe.get("url"),
                )
            )
        else:
            w(
                "  Public front-door probe unread at {url}: {error}.".format(
                    url=probe.get("url"),
                    error=probe.get("error", "unreachable"),
                )
            )
    bml_probe = r.get("bml_front_door_probe") or {}
    bml_read_count = r.get("bml_front_door_read_capable_routes", 0)
    if r.get("bml_front_door_read_ingress_declared"):
        if bml_probe.get("bml_read_front_door"):
            w(
                "  BML read-front-door probe: {status} {handler}; "
                "{count} grouped GET/read routes are publicly native-capable.".format(
                    status=bml_probe.get("status"),
                    handler=bml_probe.get("x_form_handler"),
                    count=bml_read_count,
                )
            )
        else:
            w(
                "  BML read-front-door ingress is declared for "
                f"{bml_read_count} GET/read routes; public probe is not live yet."
            )
    cap = r.get("kernel_first_capable_routes", 0)
    if cap:
        names = ", ".join(r.get("kernel_first_capable_route_names", []))
        w("  Kernel-FIRST CAPABLE (a real native handler in the router manifest,")
        w(f"  whole lifecycle in Form): {cap} — {names}.")
        w("  This is the native surface that EXISTS today: the compute AND the")
        w("  request lifecycle run Form-native, no CPython in the path. It is the")
        w("  runtime-share metric genuinely moving, distinct from route-count.")
        w("  PROVEN so far: the dispatch MECHANISM (a native route is served")
        w("  kernel-first, unmatched paths fan out, X-Form-Router labels each).")
        w("  The gate for native-first is operational now: web/API smoke, tool")
        w("  flows, native observability, and explicit fallback. Byte parity stays")
        w("  useful evidence for promoted twins, not the permission slip for routing.")
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
    w("    serve_via_kernel orchestrates          → CPython  (preload/parse/dispatch)")
    w("        └─ the kernel walks the recipe     → Form-native  ← the ONLY kernel part")
    w("    parse(value) re-wraps to a Python type → CPython")
    w("    Pydantic builds + serializes response  → CPython")
    w("")
    w("  The kernel handles the pure-compute CORE; routing, binding, validation,")
    w("  orchestration, and response still run in CPython today.")
    w("  That is current implementation, not protected architecture.")
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
                "handlers + Pydantic models)."
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
    w("  Adding a kernel-served route INCREASES usage but still leaves CPython")
    w("  lifecycle code around the kernel call. The current direction is to keep")
    w("  production route modules dispatch-only and move reference baselines into")
    w("  source examples, tests, or sensing scripts.")
    w("")
    w(
        f"  Remaining *_py functions in kernel-router files: "
        f"{r['py_parity_reference_functions_in_kernel_routers']}."
    )
    if r["py_parity_reference_functions_in_kernel_routers"] == 0:
        w("  Desired state holds: no production kernel route carries a Python compute twin.")
    w("")

    # --- Axis 4 ---
    w("## Axis 4 — where the body is on the journey (Python-runtime → kernel-runtime)")
    w("")
    pct = r["kernel_served_pct"]
    cap = r.get("kernel_first_capable_routes", 0)
    w(
        f"  Guest-subroutine usage is still {pct}% of routes"
        if pct is not None
        else "  Guest-subroutine usage remains readable only as a count"
    )
    w(
        f"  while {r['kernel_first_served_routes']} are SERVED kernel-first at the "
        "live front door according to the public provenance probe."
    )
    w("")
    if cap:
        w(f"  But the reversal is no longer hypothetical. {cap} routes are now")
        w("  kernel-FIRST CAPABLE: real native handlers in the router manifest, whole")
        w("  lifecycle in Form. The capable count moved 0 → {0}: the native front-door".format(cap))
        w("  surface EXISTS. The deployable move is the Traefik native-first router,")
        w("  then smoke the website/API/tool flows and watch fallback/provenance.")
    else:
        w("  The reversal (kernel-as-front-door) has no proven native surface yet.")
    w("")
    w("  The metric to track is runtime-SHARE moving toward the kernel — and it has")
    w("  two honest readings now: kernel-first SERVED (the public front door) and")
    w("  kernel-first CAPABLE (the native surface that exists in the manifest). Route-")
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
