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
    assert "POST /api/spec-registry + PATCH/DELETE /api/spec-registry/{spec_id}" in form_text
    assert "X-Form-Native-Preview" in form_text
    assert "auth-port.fk preserves API-key/contributor-key decision parity" in form_text
    assert "application-graph-node-port.fk emits direct graph_nodes/graph_node_revisions/graph_edges SQL" in form_text
    assert "header-gated native SQL preview rows" in form_text
    assert "application-graph-live-db-test.sh proves rollback-safe live DB execution" in form_text
    assert "application-graph-response-projection-test.sh proves live graph rows project into SpecRegistryEntry and IdeaWithScore-shaped mutation responses" in form_text
    assert "trust envelope carrying prediction residual" in form_text
    assert "choice_success=1, silence/protocol/fail/stop/BMA markers" in form_text
    assert "native-mutation-side-effects-test.sh proves parent-edge repair" in form_text
    assert "native-mutation-route-side-effects-test.sh proves application graph mutation plus side-effect execution are bound" in form_text
    assert "native-mutation-public-gate-test.sh plus mutation_public_gate_harness.py prove X-Form-Native-Public-Gate" in form_text
    assert "X-Form-Python-Fallback fans out as explicit refusal/control signal" in form_text
    assert "mutation_public_gate_harness.py now proves native HTTP mutation persistence" in form_text
    assert "Public mutable POST/PATCH/DELETE /api/spec-registry Traefik no-header default now enters the kernel-router native default invitation" in form_text
    assert "persists through the mounted production-config carrier" in form_text
    assert "GET /api/spec-registry/{spec_id}, and GET /api/ideas/{idea_id}/specs through one SpecRegistryEntry projection" in form_text
    assert "remaining richer spec-registry cards stay API-backed" in form_text
