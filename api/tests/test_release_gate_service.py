from __future__ import annotations

import base64

import httpx
import pytest
import respx

from app.services.release_gate_service import (
    collect_rerunnable_actions_run_ids,
    evaluate_collective_review_gates,
    evaluate_commit_traceability_report,
    evaluate_merged_change_contract_report,
    evaluate_public_deploy_contract_report,
    evaluate_pr_gates,
    extract_actions_run_id,
    get_branch_head_sha,
    get_file_content_at_ref,
    list_spec_paths_at_ref,
)


def test_evaluate_pr_gates_ready_when_required_checks_pass() -> None:
    pr = {"number": 101, "draft": False, "mergeable_state": "clean", "head": {"sha": "abc"}}
    commit_status = {
        "state": "success",
        "statuses": [{"context": "Test", "state": "success"}],
    }
    check_runs = [{"name": "Deploy", "conclusion": "success"}]
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


def test_evaluate_pr_gates_allows_merge_when_required_contexts_unavailable() -> None:
    pr = {"number": 104, "draft": False, "mergeable_state": "clean", "head": {"sha": "abc"}}
    commit_status = {"state": "failure", "statuses": []}
    check_runs = [{"name": "NonRequired", "conclusion": "failure"}]
    required_contexts: list[str] = []

    out = evaluate_pr_gates(pr, commit_status, check_runs, required_contexts)

    assert out["ready_to_merge"] is True
    assert out["required_contexts"] == []


def test_merged_change_contract_uses_ready_to_merge_not_combined_status(monkeypatch: pytest.MonkeyPatch) -> None:
    merged_pr = {
        "number": 127,
        "merged_at": "2026-02-16T23:37:00Z",
        "base": {"ref": "main"},
        "user": {"login": "seeker71"},
        "merged_by": {"login": "seeker71"},
        "html_url": "https://github.com/seeker71/Coherence-Network/pull/127",
        "draft": False,
    }
    monkeypatch.setattr(
        "app.services.release_gate_service.get_commit_pull_requests",
        lambda *_args, **_kwargs: [merged_pr],
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.get_pull_request_reviews",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.get_commit_status",
        lambda *_args, **_kwargs: {"state": "failure", "statuses": []},
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.get_check_runs",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.get_required_contexts",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.wait_for_public_validation",
        lambda **_kwargs: {"ready": True, "elapsed_seconds": 1, "checks": []},
    )

    out = evaluate_merged_change_contract_report(
        repository="seeker71/Coherence-Network",
        sha="fd3b7daea14feb4d2188b7c61d5f06233f4cfc78",
        min_approvals=0,
        min_unique_approvers=0,
        timeout_seconds=5,
        poll_seconds=1,
    )

    assert out["result"] == "contract_passed"


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


def test_extract_actions_run_id_from_details_url() -> None:
    run_id = extract_actions_run_id(
        "https://github.com/seeker71/Coherence-Network/actions/runs/14001234567/job/39210012345"
    )
    assert run_id == 14001234567


def test_collect_rerunnable_actions_run_ids_filters_by_required_and_failure() -> None:
    failing_required_contexts = ["Test", "Thread Gates"]
    check_runs = [
        {
            "name": "Test",
            "conclusion": "failure",
            "details_url": "https://github.com/seeker71/Coherence-Network/actions/runs/111/job/1",
            "app": {"slug": "github-actions"},
        },
        {
            "name": "Thread Gates",
            "conclusion": "timed_out",
            "details_url": "https://github.com/seeker71/Coherence-Network/actions/runs/222/job/2",
            "app": {"slug": "github-actions"},
        },
        {
            "name": "Deploy",
            "conclusion": "failure",
            "details_url": "https://example.com/build/123",
            "app": {"slug": "other"},
        },
        {
            "name": "Test",
            "conclusion": "success",
            "details_url": "https://github.com/seeker71/Coherence-Network/actions/runs/333/job/3",
            "app": {"slug": "github-actions"},
        },
    ]

    run_ids = collect_rerunnable_actions_run_ids(failing_required_contexts, check_runs)
    assert run_ids == [111, 222]


def test_collect_rerunnable_actions_run_ids_fallbacks_when_required_unknown() -> None:
    check_runs = [
        {
            "name": "Test",
            "conclusion": "failure",
            "details_url": "https://github.com/seeker71/Coherence-Network/actions/runs/444/job/9",
            "app": {"slug": "github-actions"},
        },
        {
            "name": "Change Contract",
            "conclusion": "cancelled",
            "details_url": "https://github.com/seeker71/Coherence-Network/actions/runs/555/job/4",
            "app": {"slug": "github-actions"},
        },
        {
            "name": "Deploy",
            "conclusion": "failure",
            "details_url": "https://example.com/build/456",
            "app": {"slug": "other"},
        },
    ]
    run_ids = collect_rerunnable_actions_run_ids([], check_runs)
    assert run_ids == [444, 555]


def test_evaluate_public_deploy_contract_report_live_shape() -> None:
    out = evaluate_public_deploy_contract_report(
        repository="seeker71/Coherence-Network",
        branch="main",
        timeout=8.0,
    )

    assert out["repository"] == "seeker71/Coherence-Network"
    assert out["branch"] == "main"
    assert isinstance(out.get("expected_sha"), str)
    checks = out.get("checks")
    assert isinstance(checks, list)
    check_names = {
        row.get("name")
        for row in checks
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    assert "railway_health" in check_names
    assert "railway_gates_main_head" in check_names
    assert "railway_web_gates_page" in check_names
    assert "railway_web_health_proxy" in check_names
    assert "railway_value_lineage_e2e" in check_names
    assert out["result"] in {"public_contract_passed", "blocked"}
    assert isinstance(out.get("failing_checks"), list)
    assert isinstance(out.get("warnings"), list)


def test_evaluate_commit_traceability_report_live_shape() -> None:
    sha = get_branch_head_sha("seeker71/Coherence-Network", "main")
    assert isinstance(sha, str) and len(sha) == 40

    out = evaluate_commit_traceability_report(
        repository="seeker71/Coherence-Network",
        sha=sha,
    )

    assert out["repository"] == "seeker71/Coherence-Network"
    assert out["sha"] == sha
    assert out["result"] in {"traceability_ready", "traceability_incomplete"}
    assert isinstance(out.get("missing_answers"), list)
    traceability = out.get("traceability")
    assert isinstance(traceability, dict)
    assert isinstance(traceability.get("ideas"), list)
    assert isinstance(traceability.get("specs"), list)
    assert isinstance(traceability.get("implementations"), list)
    assert isinstance(traceability.get("evidence_files"), list)


@respx.mock
def test_get_file_content_at_ref_retries_transient_5xx_then_succeeds() -> None:
    repository = "seeker71/Coherence-Network"
    path = "docs/system_audit/commit_evidence_sample.json"
    ref = "main"
    url = f"https://api.github.com/repos/{repository}/contents/{path}"
    payload = base64.b64encode(b'{"ok": true}').decode("utf-8")

    route = respx.get(url).mock(
        side_effect=[
            httpx.Response(502, json={"message": "bad gateway"}),
            httpx.Response(200, json={"content": payload, "encoding": "base64"}),
        ]
    )

    out = get_file_content_at_ref(repository=repository, path=path, ref=ref, timeout=2.0)

    assert out == '{"ok": true}'
    assert route.call_count == 2


@respx.mock
def test_get_file_content_at_ref_returns_none_when_github_keeps_5xx() -> None:
    repository = "seeker71/Coherence-Network"
    path = "docs/system_audit/commit_evidence_sample.json"
    ref = "main"
    url = f"https://api.github.com/repos/{repository}/contents/{path}"

    route = respx.get(url).mock(return_value=httpx.Response(502, json={"message": "bad gateway"}))

    out = get_file_content_at_ref(repository=repository, path=path, ref=ref, timeout=2.0)

    assert out is None
    assert route.call_count == 3


@respx.mock
def test_list_spec_paths_at_ref_returns_empty_on_403_rate_limit() -> None:
    repository = "seeker71/Coherence-Network"
    ref = "main"
    url = f"https://api.github.com/repos/{repository}/contents/specs"

    route = respx.get(url).mock(
        return_value=httpx.Response(403, json={"message": "API rate limit exceeded"})
    )

    out = list_spec_paths_at_ref(repository=repository, ref=ref, timeout=2.0)

    assert out == []
    assert route.call_count == 1


@respx.mock
def test_list_spec_paths_at_ref_returns_empty_on_429_rate_limit() -> None:
    repository = "seeker71/Coherence-Network"
    ref = "main"
    url = f"https://api.github.com/repos/{repository}/contents/specs"

    route = respx.get(url).mock(
        return_value=httpx.Response(429, json={"message": "API rate limit exceeded"})
    )

    out = list_spec_paths_at_ref(repository=repository, ref=ref, timeout=2.0)

    assert out == []
    assert route.call_count == 1
