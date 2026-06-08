"""Proof that mutable idea/spec routes have native preview bindings."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KERNEL_ROUTES_PATH = ROOT / "deploy" / "kernel-router" / "production-routes.fk"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_native_mutation_preview_routes_are_method_and_header_gated():
    text = _text(KERNEL_ROUTES_PATH)

    expected_rows = (
        '(kh-route "ideas-create-native-preview" "POST" "/api/ideas" 0 "route_ideas_create_native_preview" "X-Form-Native-Preview" 0)',
        '(kh-route "ideas-update-native-preview" "PATCH" "/api/ideas/*" 0 "route_ideas_update_native_preview" "X-Form-Native-Preview" 25)',
        '(kh-route "specs-create-native-preview" "POST" "/api/spec-registry" 0 "route_specs_create_native_preview" "X-Form-Native-Preview" 0)',
        '(kh-route "specs-update-native-preview" "PATCH" "/api/spec-registry/*" 0 "route_specs_update_native_preview" "X-Form-Native-Preview" 25)',
        '(kh-route "specs-delete-native-preview" "DELETE" "/api/spec-registry/*" 0 "route_specs_delete_native_preview" "X-Form-Native-Preview" 25)',
    )
    for row in expected_rows:
        assert row in text

    assert "requests without it exceed the route's pressure budget and fan out to FastAPI" in text


def test_native_mutation_preview_handlers_emit_application_graph_sql():
    text = _text(KERNEL_ROUTES_PATH)

    for handler in (
        "defn route_ideas_create_native_preview",
        "defn route_ideas_update_native_preview",
        "defn route_specs_create_native_preview",
        "defn route_specs_update_native_preview",
        "defn route_specs_delete_native_preview",
    ):
        assert handler in text

    for sql_piece in (
        "INSERT INTO graph_nodes",
        "INSERT INTO graph_node_revisions",
        "properties = properties ||",
        "COALESCE(max(revision_number), 0) + 1",
        "DELETE FROM graph_edges",
        "DELETE FROM graph_nodes",
        "jsonb_build_object",
    ):
        assert sql_piece in text

    assert ',\\"executes\\":false' in text
    assert "cache invalidation, parent/edge side effects, contributor-key audit side effects" in text


def test_native_mutation_preview_uses_live_spec_node_id_convention():
    text = _text(KERNEL_ROUTES_PATH)

    assert 'node_id = f"spec-{data.spec_id}"' not in text
    assert '(let node-id (str_concat "spec-" spec-id))' in text
    assert '(mpv-path-tail path "/api/spec-registry/")' in text


def test_idea_and_spec_forms_name_method_specific_preview_bindings():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "method-specific mutation paths -> header-gated Form-native SQL preview bindings" in text
        assert "X-Form-Native-Preview" in text
        assert "deploy/kernel-router/production-routes.fk::route_ideas_create_native_preview" in text or "deploy/kernel-router/production-routes.fk::route_specs_create_native_preview" in text
        assert "response projection parity proven" in text
        assert "cache invalidation" in text
        assert "reversible flip gate" in text
