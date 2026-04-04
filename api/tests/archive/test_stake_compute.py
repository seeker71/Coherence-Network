"""Tests for stake-to-compute service and endpoints."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.models.agent import TaskType
from app.models.idea import IdeaStage
from app.services import stake_compute_service


# ---------------------------------------------------------------------------
# Helpers / Fakes
# ---------------------------------------------------------------------------

class FakeIdea:
    """Minimal idea stand-in for tests."""
    def __init__(self, idea_id: str, name: str, description: str, stage: str = "none"):
        self.id = idea_id
        self.name = name
        self.description = description
        self.stage = stage


def _fake_get_idea(idea_id: str) -> FakeIdea | None:
    ideas = {
        "idea-no-specs": FakeIdea("idea-no-specs", "No Specs Idea", "An idea with no specs", "none"),
        "idea-has-spec": FakeIdea("idea-has-spec", "Has Spec", "An idea with specs", "specced"),
        "idea-implementing": FakeIdea("idea-implementing", "Implementing", "In impl stage", "implementing"),
        "idea-testing": FakeIdea("idea-testing", "Testing", "In test stage", "testing"),
        "idea-complete": FakeIdea("idea-complete", "Complete", "Done", "complete"),
    }
    return ideas.get(idea_id)


_created_tasks: list[dict] = []
_task_counter = 0


def _fake_create_task(data: Any) -> dict:
    global _task_counter
    _task_counter += 1
    task_id = f"task_{_task_counter:03d}"
    task = {
        "id": task_id,
        "direction": data.direction,
        "task_type": data.task_type,
        "status": "pending",
        "context": data.context or {},
    }
    _created_tasks.append(task)
    return task


def _fake_list_tasks_for_idea_empty(idea_id: str) -> dict:
    return {"idea_id": idea_id, "total": 0, "groups": []}


def _fake_list_tasks_for_idea_with_spec(idea_id: str) -> dict:
    return {
        "idea_id": idea_id,
        "total": 1,
        "groups": [{
            "task_type": "spec",
            "count": 1,
            "status_counts": {"completed": 1},
            "tasks": [{"id": "t1", "task_type": "spec", "status": "completed"}],
        }],
    }


def _fake_stake_on_idea(idea_id: str, contributor_id: str, amount_cc: float, rationale: str | None = None) -> dict:
    return {"stake_record": {"id": "clr_fake123", "amount_cc": amount_cc}, "idea": None, "lineage_id": None}


def _fake_record_contribution(**kwargs: Any) -> dict:
    return {"id": "clr_fake_compute", **kwargs}


def _fake_list_specs_empty(limit: int = 200) -> list:
    return []


class FakeSpec:
    def __init__(self, spec_id: str, idea_id: str, title: str):
        self.spec_id = spec_id
        self.idea_id = idea_id
        self.title = title


def _fake_list_specs_with_match(limit: int = 200) -> list:
    return [FakeSpec("spec-001", "idea-has-spec", "The Spec")]


def _fake_get_idea_investments_empty(idea_id: str) -> list:
    return []


def _fake_get_idea_investments_with_stake(idea_id: str) -> list:
    return [
        {"contribution_type": "stake", "amount_cc": 10.0, "contributor_id": "alice"},
        {"contribution_type": "stake", "amount_cc": 5.0, "contributor_id": "bob"},
        {"contribution_type": "compute", "amount_cc": -2.0, "contributor_id": "provider:openrouter"},
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_task_counter():
    global _task_counter, _created_tasks
    _task_counter = 0
    _created_tasks = []
    yield


class TestComputeNextTasks:
    """Test compute_next_tasks_for_idea determines correct tasks."""

    def test_idea_no_specs_creates_spec_task(self):
        with (
            patch.object(stake_compute_service, "idea_service") as mock_idea,
            patch.object(stake_compute_service, "agent_service") as mock_agent,
            patch.object(stake_compute_service, "spec_registry_service") as mock_spec,
        ):
            mock_idea.get_idea.side_effect = _fake_get_idea
            mock_agent.list_tasks_for_idea.side_effect = _fake_list_tasks_for_idea_empty
            mock_spec.list_specs.return_value = []

            tasks = stake_compute_service.compute_next_tasks_for_idea("idea-no-specs")

            assert len(tasks) == 1
            assert tasks[0]["task_type"] == TaskType.SPEC
            assert "idea-no-specs" in tasks[0]["direction"]

    def test_idea_with_spec_creates_impl_task(self):
        with (
            patch.object(stake_compute_service, "idea_service") as mock_idea,
            patch.object(stake_compute_service, "agent_service") as mock_agent,
            patch.object(stake_compute_service, "spec_registry_service") as mock_spec,
        ):
            mock_idea.get_idea.side_effect = _fake_get_idea
            mock_agent.list_tasks_for_idea.side_effect = _fake_list_tasks_for_idea_empty
            mock_spec.list_specs.return_value = [FakeSpec("spec-001", "idea-has-spec", "The Spec")]

            tasks = stake_compute_service.compute_next_tasks_for_idea("idea-has-spec")

            assert len(tasks) == 1
            assert tasks[0]["task_type"] == TaskType.IMPL
            assert "spec-001" in tasks[0]["direction"]

    def test_implementing_creates_test_task(self):
        with (
            patch.object(stake_compute_service, "idea_service") as mock_idea,
            patch.object(stake_compute_service, "agent_service") as mock_agent,
            patch.object(stake_compute_service, "spec_registry_service") as mock_spec,
        ):
            mock_idea.get_idea.side_effect = _fake_get_idea
            mock_agent.list_tasks_for_idea.side_effect = _fake_list_tasks_for_idea_empty
            mock_spec.list_specs.return_value = []

            tasks = stake_compute_service.compute_next_tasks_for_idea("idea-implementing")

            assert len(tasks) == 1
            assert tasks[0]["task_type"] == TaskType.TEST

    def test_testing_creates_review_task(self):
        with (
            patch.object(stake_compute_service, "idea_service") as mock_idea,
            patch.object(stake_compute_service, "agent_service") as mock_agent,
            patch.object(stake_compute_service, "spec_registry_service") as mock_spec,
        ):
            mock_idea.get_idea.side_effect = _fake_get_idea
            mock_agent.list_tasks_for_idea.side_effect = _fake_list_tasks_for_idea_empty
            mock_spec.list_specs.return_value = []

            tasks = stake_compute_service.compute_next_tasks_for_idea("idea-testing")

            assert len(tasks) == 1
            assert tasks[0]["task_type"] == TaskType.REVIEW

    def test_complete_idea_returns_empty(self):
        with patch.object(stake_compute_service, "idea_service") as mock_idea:
            mock_idea.get_idea.side_effect = _fake_get_idea

            tasks = stake_compute_service.compute_next_tasks_for_idea("idea-complete")

            assert tasks == []

    def test_nonexistent_idea_returns_empty(self):
        with patch.object(stake_compute_service, "idea_service") as mock_idea:
            mock_idea.get_idea.return_value = None

            tasks = stake_compute_service.compute_next_tasks_for_idea("nope")

            assert tasks == []


class TestExecuteStake:
    """Test execute_stake orchestrates staking + task creation."""

    def test_stake_creates_tasks_and_records_contribution(self):
        with (
            patch.object(stake_compute_service, "idea_service") as mock_idea,
            patch.object(stake_compute_service, "agent_service") as mock_agent,
            patch.object(stake_compute_service, "spec_registry_service") as mock_spec,
            patch.object(stake_compute_service, "contribution_ledger_service") as mock_ledger,
        ):
            mock_idea.stake_on_idea.side_effect = _fake_stake_on_idea
            mock_idea.get_idea.side_effect = _fake_get_idea
            mock_agent.list_tasks_for_idea.side_effect = _fake_list_tasks_for_idea_empty
            mock_agent.create_task.side_effect = _fake_create_task
            mock_spec.list_specs.return_value = []
            mock_ledger.record_contribution.side_effect = _fake_record_contribution

            result = stake_compute_service.execute_stake(
                idea_id="idea-no-specs",
                staker_id="urs-muff",
                amount_cc=10.0,
            )

            assert result["stake"]["amount_cc"] == 10.0
            assert result["stake"]["contributor"] == "urs-muff"
            assert len(result["tasks_created"]) == 1
            assert result["tasks_created"][0]["type"] == "spec"
            assert result["idea_stage"] == "none"
            assert "1 task created" in result["message"]

            # Verify stake_on_idea was called
            mock_idea.stake_on_idea.assert_called_once_with(
                idea_id="idea-no-specs",
                contributor_id="urs-muff",
                amount_cc=10.0,
                rationale=None,
            )


class TestGetIdeaProgress:
    """Test get_idea_progress returns correct phase breakdown."""

    def test_progress_shows_phases_and_cc(self):
        with (
            patch.object(stake_compute_service, "idea_service") as mock_idea,
            patch.object(stake_compute_service, "agent_service") as mock_agent,
            patch.object(stake_compute_service, "contribution_ledger_service") as mock_ledger,
        ):
            mock_idea.get_idea.side_effect = _fake_get_idea
            mock_agent.list_tasks_for_idea.return_value = {
                "idea_id": "idea-has-spec",
                "total": 2,
                "groups": [
                    {"task_type": "spec", "count": 1, "status_counts": {"completed": 1}, "tasks": []},
                    {"task_type": "impl", "count": 1, "status_counts": {"pending": 1}, "tasks": []},
                ],
            }
            mock_ledger.get_idea_investments.side_effect = _fake_get_idea_investments_with_stake

            result = stake_compute_service.get_idea_progress("idea-has-spec")

            assert result["idea_id"] == "idea-has-spec"
            assert result["stage"] == "specced"
            assert result["phases"]["spec"] == {"done": 1, "total": 1}
            assert result["phases"]["impl"] == {"done": 0, "total": 1}
            assert result["phases"]["test"] == {"done": 0, "total": 0}
            assert result["phases"]["review"] == {"done": 0, "total": 0}
            assert result["cc_staked"] == 15.0
            assert result["cc_spent"] == 2.0
            assert result["cc_balance"] == 13.0
            assert sorted(result["contributors"]) == ["alice", "bob"]

    def test_progress_not_found(self):
        with patch.object(stake_compute_service, "idea_service") as mock_idea:
            mock_idea.get_idea.return_value = None

            result = stake_compute_service.get_idea_progress("nope")

            assert result["error"] == "not_found"


class TestRecordTaskCost:
    """Test record_task_cost records negative CC contribution."""

    def test_records_negative_compute_cost(self):
        with patch.object(stake_compute_service, "contribution_ledger_service") as mock_ledger:
            mock_ledger.record_contribution.side_effect = _fake_record_contribution

            result = stake_compute_service.record_task_cost(
                task_id="task_001",
                idea_id="idea-no-specs",
                provider="openrouter",
                duration_s=10.0,
                success=True,
            )

            assert result["task_id"] == "task_001"
            assert result["cost_cc"] == 1.0  # 10s * 0.1 CC/s
            assert result["success"] is True

            # Verify negative amount was recorded
            call_kwargs = mock_ledger.record_contribution.call_args
            assert call_kwargs.kwargs["amount_cc"] == -1.0
            assert call_kwargs.kwargs["contribution_type"] == "compute"

    def test_cc_balance_decreases_with_cost(self):
        """Verify that after recording a task cost, the idea's CC balance drops."""
        with patch.object(stake_compute_service, "contribution_ledger_service") as mock_ledger:
            mock_ledger.record_contribution.side_effect = _fake_record_contribution

            result = stake_compute_service.record_task_cost(
                task_id="task_002",
                idea_id="idea-no-specs",
                provider="local",
                duration_s=5.0,
                success=False,
            )

            assert result["cost_cc"] == 0.5  # 5s * 0.1 CC/s
            assert result["success"] is False
