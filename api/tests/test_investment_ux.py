"""Acceptance tests for the idea-detail investment UX.

No dedicated ``investment-ux`` spec file exists in this repository, so this
suite verifies the implemented acceptance contract on the idea detail page and
the backend behavior that powers that surface.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
IDEA_DETAIL_PAGE = REPO_ROOT / "web" / "app" / "ideas" / "[idea_id]" / "page.tsx"
AUTH_HEADERS = {"X-API-Key": "dev-key"}


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing expected file: {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolate_agent_task_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PATH", str(tmp_path / "agent_tasks.json"))
    from app.services import agent_service

    agent_service.clear_store()
    yield
    agent_service.clear_store()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _create_idea(client: TestClient) -> str:
    idea_id = f"investment-ux-{uuid.uuid4().hex[:10]}"
    response = client.post(
        "/api/ideas",
        json={
            "id": idea_id,
            "name": "Investment UX Contract",
            "description": "Seed idea for investment UX acceptance tests.",
            "potential_value": 100.0,
            "estimated_cost": 20.0,
            "confidence": 0.7,
            "manifestation_status": "none",
        },
    )
    assert response.status_code == 201, response.text
    return idea_id


def test_investment_ux_page_contains_required_sections() -> None:
    """Idea detail page exposes the visible investment affordances."""
    content = _read(IDEA_DETAIL_PAGE)

    for expected in (
        "Investment",
        "CC staked on this idea and what it produced.",
        "Total CC Staked",
        "No CC staked on this idea yet.",
        "Work cards:",
        "Back this idea",
        "IdeaStakeForm",
    ):
        assert expected in content


def test_investment_ux_page_loads_stakes_and_produced_work_signals() -> None:
    """Idea detail page computes stake totals and work-card output from backing data."""
    content = _read(IDEA_DETAIL_PAGE)

    assert "/api/contributions?limit=500" in content
    assert 'r.idea_id === ideaId && r.contribution_type === "stake"' in content
    assert "stakes.reduce((sum, s) => sum + (s.amount_cc || 0), 0).toFixed(1)" in content
    assert "flow?.process.task_ids.length ?? 0" in content


def test_stake_endpoint_creates_investment_and_next_task(client: TestClient) -> None:
    """Staking into a new idea records the investment and creates the next work card."""
    idea_id = _create_idea(client)

    response = client.post(
        f"/api/ideas/{idea_id}/stake",
        json={
            "contributor_id": "alice",
            "amount_cc": 20.0,
            "rationale": "Fund the next step",
        },
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["stake"]["contributor"] == "alice"
    assert payload["stake"]["amount_cc"] == 20.0
    assert payload["stake"]["record"]["contribution_type"] == "stake"
    assert len(payload["tasks_created"]) == 1
    assert payload["tasks_created"][0]["type"] == "spec"
    assert "1 task created" in payload["message"]

    idea_response = client.get(f"/api/ideas/{idea_id}")
    assert idea_response.status_code == 200
    assert idea_response.json()["potential_value"] == pytest.approx(110.0)


def test_investment_ux_backing_ledger_records_stake_and_generated_tasks(client: TestClient) -> None:
    """The backing ledger preserves both the stake and the work created from it."""
    idea_id = _create_idea(client)

    response = client.post(
        f"/api/ideas/{idea_id}/stake",
        json={"contributor_id": "alice", "amount_cc": 20.0},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200, response.text

    from app.services import contribution_ledger_service

    investments = contribution_ledger_service.get_idea_investments(idea_id)
    stake_entries = [entry for entry in investments if entry["contribution_type"] == "stake"]
    compute_entries = [entry for entry in investments if entry["contribution_type"] == "compute"]

    assert len(stake_entries) == 1
    assert stake_entries[0]["contributor_id"] == "alice"
    assert stake_entries[0]["amount_cc"] == 20.0

    assert len(compute_entries) == 1
    compute_metadata = json.loads(compute_entries[0]["metadata_json"])
    assert compute_metadata["trigger"] == "stake_compute"
    assert len(compute_metadata["task_ids"]) == 1


def test_idea_progress_reports_staked_cc_and_work_card_count(client: TestClient) -> None:
    """The progress endpoint reports the stake total and created spec task count."""
    idea_id = _create_idea(client)

    stake_response = client.post(
        f"/api/ideas/{idea_id}/stake",
        json={"contributor_id": "alice", "amount_cc": 20.0},
        headers=AUTH_HEADERS,
    )
    assert stake_response.status_code == 200, stake_response.text

    response = client.get(f"/api/ideas/{idea_id}/progress")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["idea_id"] == idea_id
    assert payload["stage"] == "none"
    assert payload["cc_staked"] == 20.0
    assert payload["cc_balance"] == 20.0
    assert payload["contributors"] == ["alice"]
    assert payload["phases"]["spec"] == {"done": 0, "total": 1}
    assert payload["total_tasks"] == 1
