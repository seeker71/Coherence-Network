"""Proof that specs can be read from source through a native Form route."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KERNEL_ROUTES_PATH = ROOT / "deploy" / "kernel-router" / "production-routes.fk"
SPECS_INDEX_PATH = ROOT / "specs" / "INDEX.md"
SPEC_MODEL_PATH = ROOT / "api" / "app" / "models" / "spec_registry.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_specs_source_native_route_is_bound_and_reads_index():
    kernel_text = _text(KERNEL_ROUTES_PATH)
    index_text = _text(SPECS_INDEX_PATH)

    source_rows = [line for line in index_text.splitlines() if line.startswith("- [")]
    assert len(source_rows) >= 145

    assert "defn specs_index_text" in kernel_text
    assert "defn route_specs_source_list" in kernel_text
    assert '(list "/api/spec-registry/source-list" route_specs_source_list)' in kernel_text
    assert 'read_file_slice "specs/INDEX.md"' in kernel_text
    assert "ssl-entries-json-from" in kernel_text


def test_specs_source_native_route_emits_spec_registry_entry_shape():
    kernel_text = _text(KERNEL_ROUTES_PATH)
    model_text = _text(SPEC_MODEL_PATH)

    assert "class SpecRegistryEntry(BaseModel)" in model_text
    for field in (
        '\\"spec_id\\"',
        '\\"title\\"',
        '\\"summary\\"',
        '\\"potential_value\\"',
        '\\"actual_value\\"',
        '\\"estimated_cost\\"',
        '\\"actual_cost\\"',
        '\\"value_gap\\"',
        '\\"cost_gap\\"',
        '\\"estimated_roi\\"',
        '\\"actual_roi\\"',
        '\\"created_at\\"',
        '\\"updated_at\\"',
        '\\"content_path\\"',
        '\\"workspace_id\\"',
    ):
        assert field in kernel_text

    assert "2026-06-08T00:00:00Z" in kernel_text
    assert "specs/INDEX.md -> SpecRegistryEntry[]" in kernel_text
