from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_external_proof_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "external_proof_demo.py"
    spec = importlib.util.spec_from_file_location("external_proof_demo", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_external_proof_idea_payload_matches_public_contract() -> None:
    module = _load_external_proof_module()

    payload = module._idea_create_payload()

    assert payload["name"] == "External Proof Test Idea [auto-cleanup]"
    assert payload["description"] == "Created by external_proof_demo.py - will be archived."
    assert payload["potential_value"] > 0
    assert payload["estimated_cost"] >= 0
    assert 0 <= payload["confidence"] <= 1
    assert payload["workspace_id"] == "coherence-network"


def test_external_proof_stage_calls_use_public_post_contract() -> None:
    module = _load_external_proof_module()
    runner = module.ProofRunner("https://api.example.test", "dev-key", dry_run=True)
    runner.idea_id = "idea-123"

    runner.advance_stage()
    runner.archive_idea()

    assert runner.endpoints_exercised == [
        "POST /api/ideas/idea-123/stage",
        "PATCH /api/ideas/idea-123",
    ]


def test_external_proof_contribution_uses_open_record_endpoint() -> None:
    module = _load_external_proof_module()
    runner = module.ProofRunner("https://api.example.test", "dev-key", dry_run=True)
    runner.idea_id = "idea-123"

    runner.record_contribution()

    assert runner.endpoints_exercised == ["POST /api/contributions/record"]


def test_external_proof_headers_include_public_api_key_header() -> None:
    module = _load_external_proof_module()
    runner = module.ProofRunner("https://api.example.test", "dev-key", dry_run=True)

    headers = runner._headers()

    assert headers["X-API-Key"] == "dev-key"
    assert headers["Authorization"] == "Bearer dev-key"
    assert headers["Content-Type"] == "application/json"
