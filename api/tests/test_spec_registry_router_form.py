"""Proof that the spec registry has a high-level Form expression."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"
ROUTER_PATH = ROOT / "api" / "app" / "routers" / "spec_registry.py"
KERNEL_ROUTES_PATH = ROOT / "deploy" / "kernel-router" / "production-routes.fk"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_spec_registry_router_form_declares_route_shapes_and_structure():
    text = _text(FORM_PATH)

    for required in (
        "form spec_route_shape",
        "form spec_route_recipe_shape",
        "defn spec_route(",
        "defn spec_route_recipe(",
        "defn browse_specs_recipe",
        "defn mutate_specs_recipe",
        "defn spec_registry_router_structure()",
        "defn spec_registry_router_reading()",
        "example_spec_registry_router_structure",
    ):
        assert required in text


def test_spec_registry_router_form_describes_live_and_native_carriers():
    form_text = _text(FORM_PATH)
    router_text = _text(ROUTER_PATH)
    kernel_text = _text(KERNEL_ROUTES_PATH)

    for live_route in (
        '@router.get("/spec-registry"',
        '@router.post("/spec-registry"',
        '@router.patch("/spec-registry/{spec_id}"',
        '@router.delete("/spec-registry/{spec_id}"',
    ):
        assert live_route in router_text

    assert "/api/spec-registry/source-list" in form_text
    assert "deploy/kernel-router/production-routes.fk::route_specs_source_list" in form_text
    assert "defn route_specs_source_list" in kernel_text
    assert '(list "/api/spec-registry/source-list" route_specs_source_list)' in kernel_text

    assert "gn-create-node" in form_text
    assert "gn-replace-node" in form_text
    assert "gn-delete-node" in form_text
    assert "public /api/spec-registry mutation paths still fan out" in form_text
    assert "auth-port.fk preserves API-key/contributor-key decision parity" in form_text
    assert "direct application graph_nodes Postgres writes" in form_text
