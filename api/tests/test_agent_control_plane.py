from __future__ import annotations

from datetime import datetime, timezone

from app.services import agent_service_pipeline_status as status_service
from app.services.agent_service_store import _store


def test_internal_task_normalizes_to_control_plane_shape() -> None:
    task = {
        "id": "task-control-001",
        "direction": "Implement the follow-through status surface",
        "task_type": "impl",
        "status": "running",
        "model": "openai/gpt-4o-mini",
        "claimed_by": "runner-a",
        "claimed_at": datetime(2026, 4, 29, tzinfo=timezone.utc),
        "context": {
            "source": {"kind": "internal_api", "external_id": "task-control-001"},
            "files_allowed": ["api/app/services/agent_service_pipeline_status.py"],
            "done_when": ["pipeline status exposes blockers"],
            "commands": ["cd api && pytest -q tests/test_agent_control_plane.py"],
            "constraints": ["no deploy required"],
            "workspace": {
                "branch": "codex/followthrough-vitality",
                "path": "/tmp/worktree",
                "key": "followthrough-vitality",
            },
            "execution": {"executor": "codex", "attempts": 1, "max_attempts": 2},
            "proof": {"followthrough_status": "clear"},
        },
    }

    normalized = status_service.normalize_task_to_control_plane(task)

    assert normalized["id"] == "task-control-001"
    assert normalized["source"]["kind"] == "internal_api"
    assert normalized["state"] == "running"
    assert normalized["files_allowed"] == ["api/app/services/agent_service_pipeline_status.py"]
    assert normalized["workspace"]["branch"] == "codex/followthrough-vitality"
    assert normalized["execution"]["claimed_by"] == "runner-a"
    assert normalized["proof"]["followthrough_status"] == "clear"


def test_followthrough_blocker_from_stale_green_pr_recommends_merge() -> None:
    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    row = {
        "number": 1260,
        "headRefName": "codex/grok-lineage-events-20260427",
        "updatedAt": "2026-04-29T09:00:00Z",
        "url": "https://github.com/seeker71/Coherence-Network/pull/1260",
    }

    def fake_gh_json(args: list[str], *, timeout: int = 5) -> dict:
        assert args[:3] == ["pr", "view", "1260"]
        return {
            "isDraft": False,
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [
                {
                    "__typename": "CheckRun",
                    "name": "validate-thread-process",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                }
            ],
        }

    original = status_service._gh_json
    try:
        status_service._gh_json = fake_gh_json
        blocker = status_service._followthrough_blocker_from_pr(
            row,
            repo="seeker71/Coherence-Network",
            now=now,
            stale_minutes=90,
        )
    finally:
        status_service._gh_json = original

    assert blocker is not None
    assert blocker["kind"] == "stale_pr"
    assert blocker["url"] == "https://github.com/seeker71/Coherence-Network/pull/1260"
    assert blocker["reason"] == "merge or close stale green PR"
    assert "gh pr merge 1260" in blocker["command"]


def test_pipeline_status_surfaces_vitality_and_hardened_tissue(monkeypatch) -> None:
    original_store = dict(_store)
    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    try:
        _store.clear()
        _store["task-running"] = {
            "id": "task-running",
            "direction": "Keep circulation moving",
            "task_type": "impl",
            "status": "running",
            "model": "openai/gpt-4o-mini",
            "created_at": now,
            "updated_at": now,
            "started_at": now,
            "context": {"workspace": {"branch": "codex/followthrough-vitality"}},
        }
        _store["task-failed-1"] = {
            "id": "task-failed-1",
            "direction": "failed one",
            "task_type": "impl",
            "status": "failed",
            "model": "openai/gpt-4o-mini",
            "created_at": now,
            "updated_at": now,
            "output": "",
        }
        _store["task-failed-2"] = {
            "id": "task-failed-2",
            "direction": "failed two",
            "task_type": "impl",
            "status": "failed",
            "model": "openai/gpt-4o-mini",
            "created_at": now,
            "updated_at": now,
            "output": "",
        }
        _store["task-failed-3"] = {
            "id": "task-failed-3",
            "direction": "failed three",
            "task_type": "impl",
            "status": "failed",
            "model": "openai/gpt-4o-mini",
            "created_at": now,
            "updated_at": now,
            "output": "",
        }

        monkeypatch.setattr(status_service, "_ensure_store_loaded", lambda include_output=False: None)
        monkeypatch.setattr(
            status_service,
            "collect_followthrough_status",
            lambda now: {
                "status": "blocked",
                "collector_available": True,
                "blockers": [
                    {
                        "kind": "stale_pr",
                        "url": "https://github.com/seeker71/Coherence-Network/pull/1260",
                        "command": "gh pr merge 1260 --repo seeker71/Coherence-Network --merge",
                        "owner": "codex",
                        "reason": "merge or close stale green PR",
                    }
                ],
            },
        )

        status = status_service.get_pipeline_status(now_utc=now)
    finally:
        _store.clear()
        _store.update(original_store)

    assert status["followthrough"]["status"] == "blocked"
    assert status["followthrough"]["blockers"][0]["url"].endswith("/pull/1260")
    assert "followthrough_blocked" in status["attention"]["flags"]
    assert status["orchestration_tissue"]["circulation"] == "constricted"
    assert status["orchestration_tissue"]["stale_tissue_count"] >= 1
    assert status["orchestration_tissue"]["hardened_tissue_count"] >= 1
    assert status["orchestration_tissue"]["vitality_score"] < 100
    assert status["control_plane"]["normalized_active_count"] == 1
