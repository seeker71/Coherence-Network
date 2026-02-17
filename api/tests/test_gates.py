from __future__ import annotations

import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")


async def _get_main_head_sha(client: AsyncClient) -> str:
    resp = await client.get("/api/gates/main-head")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("repo"), str)
    assert data.get("branch") == "main"
    sha = data.get("sha")
    assert isinstance(sha, str)
    assert SHA40_RE.fullmatch(sha)
    return sha


@pytest.mark.asyncio
async def test_gate_main_head_returns_live_sha() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _ = await _get_main_head_sha(client)


@pytest.mark.asyncio
async def test_gate_pr_to_public_blocks_for_unknown_branch() -> None:
    unknown_branch = f"codex/nonexistent-{uuid.uuid4().hex}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/gates/pr-to-public", params={"branch": unknown_branch})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "blocked"
        assert data["reason"] == "No open PR found for branch"
        assert data["open_pr_count"] == 0
        assert data["branch"] == unknown_branch


@pytest.mark.asyncio
async def test_gate_merged_contract_returns_real_report_shape() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sha = await _get_main_head_sha(client)
        resp = await client.get(
            "/api/gates/merged-contract",
            params={
                "sha": sha,
                "min_approvals": 10,
                "min_unique_approvers": 10,
                "timeout_seconds": 10,
                "poll_seconds": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["repo"] == "seeker71/Coherence-Network"
        assert data["sha"] == sha
        assert data["result"] == "blocked"
        assert isinstance(data.get("reason"), str)


@pytest.mark.asyncio
async def test_gate_public_deploy_contract_returns_real_checks() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/gates/public-deploy-contract")
        assert resp.status_code == 200
        data = resp.json()
        assert data["repository"] == "seeker71/Coherence-Network"
        assert data["branch"] == "main"
        assert isinstance(data.get("expected_sha"), str)
        checks = data.get("checks")
        assert isinstance(checks, list)
        check_names = {
            row.get("name")
            for row in checks
            if isinstance(row, dict) and isinstance(row.get("name"), str)
        }
        assert "railway_health" in check_names
        assert "railway_web_gates_page" in check_names
        assert "railway_web_health_proxy" in check_names
        assert "railway_value_lineage_e2e" in check_names
        assert data["result"] in {"public_contract_passed", "blocked"}


@pytest.mark.asyncio
async def test_gate_public_deploy_verification_job_lifecycle(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    jobs_path = tmp_path / "public_deploy_verification_jobs.json"
    monkeypatch.setenv("PUBLIC_DEPLOY_VERIFICATION_JOBS_PATH", str(jobs_path))
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GH_TOKEN", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created_resp = await client.post(
            "/api/gates/public-deploy-verification-jobs",
            params={"max_attempts": 1, "timeout": 8.0, "poll_seconds": 1.0},
        )
        assert created_resp.status_code == 200
        created = created_resp.json()
        assert created["status"] == "scheduled"
        job_id = created["job_id"]

        monkeypatch.setattr(
            "app.services.release_gate_service.evaluate_public_deploy_contract_report",
            lambda **kwargs: {"result": "public_contract_passed", "reason": "ok"},
        )

        tick_resp = await client.post(f"/api/gates/public-deploy-verification-jobs/{job_id}/tick")
        assert tick_resp.status_code == 200
        ticked = tick_resp.json()
        assert ticked["status"] == "completed"

        list_resp = await client.get("/api/gates/public-deploy-verification-jobs")
        assert list_resp.status_code == 200
        jobs = list_resp.json()
        listed = next(item for item in jobs if item["job_id"] == job_id)
        assert listed["status"] == "completed"


@pytest.mark.asyncio
async def test_gate_commit_traceability_returns_real_report_shape() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sha = await _get_main_head_sha(client)
        resp = await client.get("/api/gates/commit-traceability", params={"sha": sha})
        assert resp.status_code == 200
        data = resp.json()
        assert data["repository"] == "seeker71/Coherence-Network"
        assert data["sha"] == sha
        assert isinstance(data.get("traceability"), dict)
        traceability = data["traceability"]
        assert isinstance(traceability.get("ideas"), list)
        assert isinstance(traceability.get("specs"), list)
        assert isinstance(traceability.get("implementations"), list)
        assert isinstance(traceability.get("evidence_files"), list)
        assert data["result"] in {"traceability_ready", "traceability_incomplete"}
