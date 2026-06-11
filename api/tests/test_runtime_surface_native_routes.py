"""The runtime-surface instrument SEES the kernel-router's native surface.

``scripts/runtime_surface_report.py`` reports how much execution has left
CPython for the Form kernel. Its honest distinction is between kernel-first
SERVED (the kernel as the live front door — still 0, Traefik routes to CPython)
and kernel-first CAPABLE (native handlers in the kernel-router manifest that
serve the WHOLE request lifecycle in Form, proven byte-identical in shadow,
awaiting the front-door flip).

``kernel_first_capable_routes()`` reads that CAPABLE count from both native
sources as DATA: ``deploy/kernel-router/production-routes.fk`` and the BML
front-door catalog ``deploy/front-door/api.bml``. The subtle contract: the Form
manifest may bind ``/api/...`` routes as raw ``(list "<path>" <handler>)`` rows
or as higher-grammar ``kh-route-data-ref`` rows resolved through the sibling
route-data JSON. The BML catalog contributes ``route(...)`` rows. Path-only GET
rows return bare paths; method-specific rows return ``"METHOD /api/path"`` so
two methods can share a wildcard path without becoming one capability. The
parser must return each route once, from its binding, never from a comment, and
must exclude non-``/api`` probes like ``/health``. This pins that contract with a
strange-minimal synthetic manifest plus a pin against the real checked-in
catalogs.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_report():
    src = REPO_ROOT / "scripts" / "runtime_surface_report.py"
    spec = importlib.util.spec_from_file_location("runtime_surface_report_under_test", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parser_reads_bindings_not_comments(monkeypatch, tmp_path):
    """One strange manifest, five boundaries: comments are ignored, ``/health``
    is excluded, raw route rows are read, route-data refs are resolved, and
    missing route-data refs do not create phantom routes."""
    manifest = tmp_path / "production-routes.fk"
    manifest.write_text(
        "; a comment mentioning /api/commented/before — must be ignored\n"
        "(defn route_health () \"ok\")\n"
        "(let routes\n"
        "  (list\n"
        "    ; a comment mentioning (list \"/api/commented/inside\" route_fake) — ignored\n"
        "    (kh-route-data-ref \"real-data\" RealDataRoute_handle)\n"
        "    (kh-route-data-ref \"missing-data\" MissingRoute_handle)\n"
        "    (list \"/health\"        route_health)\n"
        "    (list \"/api/real/one\"  route_one)\n"
        "    (list \"/api/real/two\"  route_two)\n"
        "    (kh-route \"real-post\" \"POST\" \"/api/real/post\" 0 \"route_post\" \"X-Preview\" 0)\n"
        "    (list 43004 \"real-delete\" \"DELETE\" \"/api/real/two\" 0 \"route_delete\" \"\" 20)))\n"
    )
    route_data = tmp_path / "production-routes-data.json"
    route_data.write_text(
        json.dumps(
            {
                "routes": {
                    "real-data": {
                        "name": "real-data",
                        "method": "GET",
                        "pattern": "/api/real/from-data",
                        "priority": 0,
                        "required_header": "",
                        "pressure_budget": 40,
                    },
                    "health-data": {
                        "name": "health-data",
                        "method": "GET",
                        "pattern": "/health",
                        "priority": 0,
                        "required_header": "",
                        "pressure_budget": 40,
                    },
                }
            }
        )
    )
    mod = _load_report()
    monkeypatch.setattr(mod, "_KERNEL_ROUTER_MANIFEST", manifest)
    monkeypatch.setattr(mod, "_BML_FRONT_DOOR_CATALOG", tmp_path / "missing-api.bml")

    routes = mod.kernel_first_capable_routes()

    assert routes == [
        "/api/real/from-data",
        "/api/real/one",
        "/api/real/two",
        "POST /api/real/post",
        "DELETE /api/real/two",
    ], routes
    assert "/health" not in routes  # non-/api probe excluded
    assert not any("commented" in r for r in routes)  # comments never captured


def test_absent_manifest_degrades_to_empty(monkeypatch, tmp_path):
    """No native catalogs → empty CAPABLE list (the report degrades, never crashes)."""
    mod = _load_report()
    monkeypatch.setattr(mod, "_KERNEL_ROUTER_MANIFEST", tmp_path / "missing.fk")
    monkeypatch.setattr(mod, "_BML_FRONT_DOOR_CATALOG", tmp_path / "missing-api.bml")
    assert mod.kernel_first_capable_routes() == []


def test_real_manifest_native_routes_are_served_zero_and_include_ideas_structure(monkeypatch):
    """The real instrument: 0 served kernel-first at the front door, and the
    production manifest's native routes are all CAPABLE. Pins the SERVED/CAPABLE
    split the runtime-share journey tracks, including native Form source/structure
    source-portfolio, graph-projection, and specs source routes that do not have
    a CPython twin."""
    mod = _load_report()
    monkeypatch.setattr(
        mod,
        "probe_kernel_front_door",
        lambda: {
            "url": "https://api.example/api/attention/kernel-runtime",
            "reachable": False,
            "status": None,
            "x_form_router": "",
            "kernel_front_door": False,
            "reported_native_route_count": None,
            "error": "test-no-public-probe",
        },
    )
    report = mod.build_report()

    assert report["kernel_first_served_routes"] == 0  # no live front-door probe in this unit test
    capable = report["kernel_first_capable_route_names"]
    capable_paths = {r.split(" ", 1)[1] if " " in r else r for r in capable}
    assert report["kernel_first_capable_routes"] == len(capable)
    # every CAPABLE route is a real /api path read from the manifest's bindings
    assert capable, "production manifest binds no native /api routes"
    assert all(path.startswith("/api/") for path in capable_paths), capable
    assert "/api/ideas/router-structure" in capable_paths
    assert "/api/ideas/source-index" in capable_paths
    assert "/api/ideas/source-portfolio" in capable_paths
    assert "/api/ideas/graph-projection" in capable_paths
    assert "/api/spec-registry/source-list" in capable_paths
    assert "/api/spec-registry" in capable_paths
    assert "/api/spec-registry/{spec_id}" in capable_paths
    assert "/api/ideas/{idea_id}/specs" in capable_paths
    assert "/api/sensings" in capable_paths
    assert "/api/sensings/{sensing_id}" in capable_paths
    assert "/api/translations/{entity_type}/{entity_id}" in capable_paths
    assert "/api/concepts/{concept_id}/carried-by" in capable_paths
    assert "/api/presences/{presence_id}/resonances" in capable_paths
    assert "/api/workspaces" in capable_paths
    assert "POST /api/ideas" in capable
    assert "POST /api/meetings/anonymous-traces" in capable
    assert "PATCH /api/ideas/*" in capable
    assert "POST /api/spec-registry" in capable
    assert "PATCH /api/spec-registry/*" in capable
    assert "DELETE /api/spec-registry/*" in capable
    assert len(capable) == len(set(capable)), f"duplicates: {capable}"
    # back-compat alias stays pinned to SERVED (0 at the front door)
    assert report["kernel_first_routes"] == report["kernel_first_served_routes"]


def test_bml_read_front_door_probe_counts_grouped_read_batch(monkeypatch):
    """The BML read front door is a sibling native entrance, so the served
    count includes the grouped GET/read batch once its public proof route is
    live instead of staying pinned to the production-manifest metric."""
    mod = _load_report()
    monkeypatch.setattr(
        mod,
        "probe_kernel_front_door",
        lambda: {
            "url": "https://api.example/api/attention/kernel-runtime",
            "reachable": True,
            "status": 200,
            "x_form_router": "native-kernel",
            "kernel_front_door": True,
            "reported_native_route_count": 45,
            "body_preview": '{"native_route_count":45}',
        },
    )
    monkeypatch.setattr(
        mod,
        "probe_bml_read_front_door",
        lambda: {
            "url": "https://api.example/api/ready",
            "reachable": True,
            "status": 200,
            "x_form_router": "native-kernel",
            "x_form_handler": "api_ready",
            "x_form_python_authority": "false",
            "bml_read_front_door": True,
            "body_preview": "{}",
        },
    )

    report = mod.build_report()

    assert report["bml_front_door_read_ingress_declared"] is True
    assert report["bml_front_door_read_capable_routes"] >= 50
    assert report["kernel_first_served_routes"] == min(
        report["kernel_first_capable_routes"],
        45 + report["bml_front_door_read_capable_routes"],
    )
    assert report["kernel_first_served_routes"] > 45
