from __future__ import annotations

from app.services.release_gate_service import evaluate_collective_review_gates, evaluate_pr_gates


def test_evaluate_pr_gates_ready_when_required_checks_pass() -> None:
    pr = {"number": 101, "draft": False, "mergeable_state": "clean", "head": {"sha": "abc"}}
    commit_status = {
        "state": "success",
        "statuses": [{"context": "Test", "state": "success"}],
    }
    check_runs = [{"name": "Vercel", "conclusion": "success"}]
    required_contexts = ["Test"]

    out = evaluate_pr_gates(pr, commit_status, check_runs, required_contexts)

    assert out["ready_to_merge"] is True
    assert out["missing_required_contexts"] == []
    assert out["failing_required_contexts"] == []


def test_evaluate_pr_gates_not_ready_when_required_missing() -> None:
    pr = {"number": 102, "draft": False, "mergeable_state": "clean", "head": {"sha": "abc"}}
    commit_status = {"state": "success", "statuses": []}
    check_runs = []
    required_contexts = ["Test"]

    out = evaluate_pr_gates(pr, commit_status, check_runs, required_contexts)

    assert out["ready_to_merge"] is False
    assert out["missing_required_contexts"] == ["Test"]


def test_evaluate_pr_gates_not_ready_for_draft_pr() -> None:
    pr = {"number": 103, "draft": True, "mergeable_state": "clean", "head": {"sha": "abc"}}
    commit_status = {"state": "success", "statuses": [{"context": "Test", "state": "success"}]}
    check_runs = []
    required_contexts: list[str] = ["Test"]

    out = evaluate_pr_gates(pr, commit_status, check_runs, required_contexts)

    assert out["ready_to_merge"] is False
    assert out["draft"] is True


def test_evaluate_collective_review_gates_passes_with_approval() -> None:
    pr = {
        "number": 200,
        "draft": False,
        "base": {"ref": "main"},
        "merged_at": "2026-02-14T20:00:00Z",
    }
    reviews = [
        {"state": "COMMENTED", "user": {"login": "observer"}},
        {"state": "APPROVED", "user": {"login": "reviewer-a"}},
    ]
    out = evaluate_collective_review_gates(pr, reviews, min_approvals=1, min_unique_approvers=1)
    assert out["collective_review_passed"] is True
    assert out["approval_events"] == 1
    assert out["unique_approvers"] == ["reviewer-a"]


def test_evaluate_collective_review_gates_fails_without_approvals() -> None:
    pr = {
        "number": 201,
        "draft": False,
        "base": {"ref": "main"},
        "merged_at": "2026-02-14T20:00:00Z",
    }
    reviews = [{"state": "COMMENTED", "user": {"login": "observer"}}]
    out = evaluate_collective_review_gates(pr, reviews, min_approvals=1, min_unique_approvers=1)
    assert out["collective_review_passed"] is False
    assert out["approval_events"] == 0
