from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import release_gate_service as gates


@pytest.mark.asyncio
async def test_gate_pr_to_public_endpoint_returns_report(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_report(**_kwargs):
        return {"result": "ready_for_merge", "pr_gate": {"ready_to_merge": True}}

    monkeypatch.setattr(gates, "evaluate_pr_to_public_report", fake_report)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/gates/pr-to-public", params={"branch": "codex/test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "ready_for_merge"
        assert data["pr_gate"]["ready_to_merge"] is True


@pytest.mark.asyncio
async def test_gate_merged_contract_endpoint_returns_report(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_report(**_kwargs):
        return {"result": "contract_passed", "contributor_ack": {"eligible": True}}

    monkeypatch.setattr(gates, "evaluate_merged_change_contract_report", fake_report)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/gates/merged-contract", params={"sha": "abc1234"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "contract_passed"
        assert data["contributor_ack"]["eligible"] is True


@pytest.mark.asyncio
async def test_gate_main_head_502_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gates, "get_branch_head_sha", lambda *args, **kwargs: None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/gates/main-head")
        assert resp.status_code == 502
        assert resp.json()["detail"] == "Could not resolve branch head SHA"
