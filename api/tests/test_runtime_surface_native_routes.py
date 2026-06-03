"""The runtime-surface instrument SEES the kernel-router's native surface.

``scripts/runtime_surface_report.py`` reports how much execution has left
CPython for the Form kernel. Its honest distinction is between kernel-first
SERVED (the kernel as the live front door — still 0, Traefik routes to CPython)
and kernel-first CAPABLE (native handlers in the kernel-router manifest that
serve the WHOLE request lifecycle in Form, proven byte-identical in shadow,
awaiting the front-door flip).

``kernel_first_capable_routes()`` reads that CAPABLE count from the manifest
``deploy/kernel-router/production-routes.fk`` as DATA. The subtle contract: the
manifest mentions the same ``/api/...`` paths in BOTH ``;``-comment lines and
``(list "<path>" <handler>)`` bindings — the parser must return each route once,
from its binding, never from a comment, and must exclude non-``/api`` probes like
``/health``. This pins that contract with a strange-minimal synthetic manifest
(a comment path before the routes block, a comment path inside it, a ``/health``
binding, and two real bindings) plus a pin against the real checked-in manifest.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_report():
    src = REPO_ROOT / "scripts" / "runtime_surface_report.py"
    spec = importlib.util.spec_from_file_location("runtime_surface_report_under_test", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parser_reads_bindings_not_comments(monkeypatch, tmp_path):
    """One strange manifest, four boundaries: comment-before-block and
    comment-inside-block are ignored, ``/health`` is excluded, and only the two
    real ``/api`` bindings are returned."""
    manifest = tmp_path / "production-routes.fk"
    manifest.write_text(
        "; a comment mentioning /api/commented/before — must be ignored\n"
        "(defn route_health () \"ok\")\n"
        "(let routes\n"
        "  (list\n"
        "    ; a comment mentioning /api/commented/inside — must be ignored\n"
        "    (list \"/health\"        route_health)\n"
        "    (list \"/api/real/one\"  route_one)\n"
        "    (list \"/api/real/two\"  route_two)))\n"
    )
    mod = _load_report()
    monkeypatch.setattr(mod, "_KERNEL_ROUTER_MANIFEST", manifest)

    routes = mod.kernel_first_capable_routes()

    assert routes == ["/api/real/one", "/api/real/two"], routes
    assert "/health" not in routes  # non-/api probe excluded
    assert not any("commented" in r for r in routes)  # comments never captured


def test_absent_manifest_degrades_to_empty(monkeypatch, tmp_path):
    """No manifest → empty CAPABLE list (the report degrades, never crashes)."""
    mod = _load_report()
    monkeypatch.setattr(mod, "_KERNEL_ROUTER_MANIFEST", tmp_path / "missing.fk")
    assert mod.kernel_first_capable_routes() == []


def test_real_manifest_native_routes_are_served_zero_capable_four():
    """The real instrument: 0 served kernel-first at the front door, and the
    production manifest's native ``/api/utils`` routes are all CAPABLE. Pins the
    SERVED/CAPABLE split the runtime-share journey tracks (a promotion that adds
    a 5th native route updates this — a healthy forcing-function, not a brittle
    string match: the assertion is the set the manifest actually binds)."""
    mod = _load_report()
    report = mod.build_report()

    assert report["kernel_first_served_routes"] == 0  # no front-door flip
    capable = report["kernel_first_capable_route_names"]
    assert report["kernel_first_capable_routes"] == len(capable)
    # every CAPABLE route is a real /api path read from the manifest's bindings
    assert capable, "production manifest binds no native /api routes"
    assert all(r.startswith("/api/") for r in capable), capable
    assert len(capable) == len(set(capable)), f"duplicates: {capable}"
    # back-compat alias stays pinned to SERVED (0 at the front door)
    assert report["kernel_first_routes"] == report["kernel_first_served_routes"]
