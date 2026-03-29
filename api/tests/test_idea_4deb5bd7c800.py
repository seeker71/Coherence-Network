"""Acceptance tests for idea-4deb5bd7c800 (spec: specs/idea-4deb5bd7c800.md)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.registry_discovery import (
    RegistrySubmissionRecord,
    RegistrySubmissionStatus,
)
from app.services.registry_discovery_service import build_registry_submission_inventory


def test_spec_core_counts_and_mcp_skill_mix() -> None:
    """Verification: >=5 registries, >=2 MCP + >=2 skill (see spec table)."""
    inv = build_registry_submission_inventory()
    assert inv.summary.target_count >= 5
    assert inv.summary.submission_ready_count >= 5
    assert inv.summary.categories.get("mcp", 0) >= 2
    assert inv.summary.categories.get("skill", 0) >= 2
    assert inv.summary.core_requirement_met is True


def test_spec_traceability_canonical_source_paths_per_category() -> None:
    """Traceability: MCP uses api/mcp_server.py; skills use SKILL.md and/or .cursor/skills."""
    inv = build_registry_submission_inventory()
    for item in inv.items:
        if item.status != RegistrySubmissionStatus.SUBMISSION_READY:
            continue
        if item.category == "mcp":
            assert "api/mcp_server.py" in item.source_paths
        else:
            assert any(
                p in item.source_paths for p in ("skills/coherence-network/SKILL.md", ".cursor/skills")
            )


def test_spec_install_clarity_and_evidence_per_ready_entry() -> None:
    """Install clarity + evidence: asset name, hint, proof URL/path, notes."""
    inv = build_registry_submission_inventory()
    for item in inv.items:
        if item.status != RegistrySubmissionStatus.SUBMISSION_READY:
            continue
        assert item.asset_name.strip()
        assert item.install_hint.strip()
        assert item.proof_note.strip()
        assert item.notes.strip()
        assert item.proof_url or item.proof_path


def test_model_rejects_category_outside_mcp_or_skill() -> None:
    with pytest.raises(ValidationError) as exc:
        RegistrySubmissionRecord(
            registry_id="bad-cat",
            registry_name="x",
            category="docs",
            asset_name="x",
            status=RegistrySubmissionStatus.SUBMISSION_READY,
            install_hint="hint",
            proof_note="note",
            notes="notes",
        )
    assert "category" in str(exc.value).lower()


def test_model_rejects_empty_registry_id() -> None:
    with pytest.raises(ValidationError):
        RegistrySubmissionRecord(
            registry_id="",
            registry_name="x",
            category="mcp",
            asset_name="x",
            status=RegistrySubmissionStatus.SUBMISSION_READY,
            install_hint="hint",
            proof_note="note",
            notes="notes",
        )
