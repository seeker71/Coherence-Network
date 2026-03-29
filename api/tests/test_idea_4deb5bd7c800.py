"""Tests for idea-4deb5bd7c800 (specs/idea-4deb5bd7c800.md).

Registry discovery acceptance: minimum five registries with proof, MCP/skill mix,
canonical source traceability, and inventory edge behavior.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

MCP_SOURCE = "api/mcp_server.py"
SKILL_SKILL_MD = "skills/coherence-network/SKILL.md"
SKILL_CURSOR = ".cursor/skills"


class TestIdea4deb5HappyPath:
    @pytest.mark.asyncio
    async def test_api_reports_five_plus_registries_and_mcp_skill_mix(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/discovery/registry-submissions")
        assert resp.status_code == 200
        body = resp.json()
        summary = body["summary"]
        assert len(body["items"]) >= 5
        assert summary["submission_ready_count"] >= 5
        assert summary["categories"]["mcp"] >= 2
        assert summary["categories"]["skill"] >= 2
        assert summary["core_requirement_met"] is True

    @pytest.mark.asyncio
    async def test_traceability_and_install_hints_per_entry(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/discovery/registry-submissions")
        assert resp.status_code == 200
        for row in resp.json()["items"]:
            rid = row["registry_id"]
            assert row["proof_url"] or row["proof_path"], f"proof missing: {rid}"
            assert row["install_hint"].strip(), f"install_hint: {rid}"
            assert row["asset_name"].strip(), f"asset_name: {rid}"
            if row["category"] == "mcp":
                assert MCP_SOURCE in row["source_paths"], f"MCP canonical path: {rid}"
            elif row["category"] == "skill":
                assert SKILL_SKILL_MD in row["source_paths"] or SKILL_CURSOR in row["source_paths"], (
                    f"skill canonical path: {rid}"
                )


class TestIdea4deb5Edges:
    def test_empty_inventory_fails_core_requirement(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services import registry_discovery_service as rds

        monkeypatch.setattr(rds, "_read_json", lambda _root, _rel: {"items": []})
        inv = rds.build_registry_submission_inventory()
        assert inv.summary.core_requirement_met is False
        assert inv.summary.submission_ready_count == 0

    def test_missing_proof_marks_submission_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services import registry_discovery_service as rds

        payload = {
            "items": [
                {
                    "registry_id": "edge-no-proof",
                    "registry_name": "Edge No Proof",
                    "category": "mcp",
                    "asset_name": "coherence-mcp-server",
                    "install_hint": "npx coherence-mcp-server",
                    "source_paths": ["api/mcp_server.py"],
                    "required_files": ["mcp-server/server.json"],
                    "proof_note": "Synthetic row for proof absence.",
                    "notes": "No proof_url or proof_path; assets may exist on disk.",
                }
            ]
        }
        monkeypatch.setattr(rds, "_read_json", lambda _root, _rel: payload)
        inv = rds.build_registry_submission_inventory()
        assert len(inv.items) == 1
        assert inv.items[0].status.value == "missing_assets"
        assert inv.summary.core_requirement_met is False
