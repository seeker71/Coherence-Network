from __future__ import annotations

from app.services.release_gate_service import (
    collect_rerunnable_actions_run_ids,
    evaluate_public_deploy_contract_report,
    evaluate_collective_review_gates,
    evaluate_pr_gates,
    extract_actions_run_id,
)


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
            "name": "Vercel",
            "conclusion": "failure",
            "details_url": "https://vercel.com/build/123",
            "app": {"slug": "vercel"},
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
            "name": "Vercel",
            "conclusion": "failure",
            "details_url": "https://vercel.com/build/456",
            "app": {"slug": "vercel"},
        },
    ]
    run_ids = collect_rerunnable_actions_run_ids([], check_runs)
    assert run_ids == [444, 555]


def test_evaluate_public_deploy_contract_report_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_json(url: str, timeout: float = 8.0) -> dict:
        if url.endswith("/api/gates/main-head"):
            return {"url": url, "ok": True, "status_code": 200, "json": {"sha": "abc123"}}
        if url.endswith("/api/health-proxy"):
            return {
                "url": url,
                "ok": True,
                "status_code": 200,
                "json": {"api": {"status": "ok"}, "web": {"updated_at": "abc123"}},
            }
        return {"url": url, "ok": True, "status_code": 200, "json": {"status": "ok"}}

    monkeypatch.setattr(
        "app.services.release_gate_service.get_branch_head_sha",
        lambda *args, **kwargs: "abc123",
    )
    monkeypatch.setattr("app.services.release_gate_service.check_http_json_endpoint", fake_json)
    monkeypatch.setattr(
        "app.services.release_gate_service.check_http_endpoint",
        lambda url, timeout=8.0: {"url": url, "ok": True, "status_code": 200},
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.check_value_lineage_e2e_flow",
        lambda api_base, timeout=8.0: {"url": api_base, "ok": True, "status_code": 200},
    )

    out = evaluate_public_deploy_contract_report(
        repository="seeker71/Coherence-Network",
        branch="main",
        api_base="https://api.example.com",
        web_base="https://web.example.com",
    )

    assert out["result"] == "public_contract_passed"
    assert out["failing_checks"] == []


def test_evaluate_public_deploy_contract_report_flags_sha_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_json(url: str, timeout: float = 8.0) -> dict:
        if url.endswith("/api/gates/main-head"):
            return {"url": url, "ok": True, "status_code": 200, "json": {"sha": "oldsha"}}
        if url.endswith("/api/health-proxy"):
            return {
                "url": url,
                "ok": True,
                "status_code": 200,
                "json": {"api": {"status": "ok"}, "web": {"updated_at": "oldsha"}},
            }
        return {"url": url, "ok": True, "status_code": 200, "json": {"status": "ok"}}

    monkeypatch.setattr(
        "app.services.release_gate_service.get_branch_head_sha",
        lambda *args, **kwargs: "newsha",
    )
    monkeypatch.setattr("app.services.release_gate_service.check_http_json_endpoint", fake_json)
    monkeypatch.setattr(
        "app.services.release_gate_service.check_http_endpoint",
        lambda url, timeout=8.0: {"url": url, "ok": True, "status_code": 200},
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.check_value_lineage_e2e_flow",
        lambda api_base, timeout=8.0: {"url": api_base, "ok": True, "status_code": 200},
    )

    out = evaluate_public_deploy_contract_report(
        repository="seeker71/Coherence-Network",
        branch="main",
        api_base="https://api.example.com",
        web_base="https://web.example.com",
    )

    assert out["result"] == "blocked"
    assert "railway_gates_main_head" in out["failing_checks"]
    assert "vercel_health_proxy" in out["failing_checks"]


def test_evaluate_public_deploy_contract_report_flags_value_lineage_e2e_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_json(url: str, timeout: float = 8.0) -> dict:
        if url.endswith("/api/gates/main-head"):
            return {"url": url, "ok": True, "status_code": 200, "json": {"sha": "abc123"}}
        if url.endswith("/api/health-proxy"):
            return {
                "url": url,
                "ok": True,
                "status_code": 200,
                "json": {"api": {"status": "ok"}, "web": {"updated_at": "abc123"}},
            }
        return {"url": url, "ok": True, "status_code": 200, "json": {"status": "ok"}}

    monkeypatch.setattr(
        "app.services.release_gate_service.get_branch_head_sha",
        lambda *args, **kwargs: "abc123",
    )
    monkeypatch.setattr("app.services.release_gate_service.check_http_json_endpoint", fake_json)
    monkeypatch.setattr(
        "app.services.release_gate_service.check_http_endpoint",
        lambda url, timeout=8.0: {"url": url, "ok": True, "status_code": 200},
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.check_value_lineage_e2e_flow",
        lambda api_base, timeout=8.0: {
            "url": f"{api_base}/api/value-lineage/links",
            "ok": False,
            "status_code": 500,
            "error": "payout_invariant_failed",
        },
    )

    out = evaluate_public_deploy_contract_report(
        repository="seeker71/Coherence-Network",
        branch="main",
        api_base="https://api.example.com",
        web_base="https://web.example.com",
    )

    assert out["result"] == "blocked"
    assert "railway_value_lineage_e2e" in out["failing_checks"]


def test_evaluate_public_deploy_contract_report_allows_main_head_502_with_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_json(url: str, timeout: float = 8.0) -> dict:
        if url.endswith("/api/gates/main-head"):
            return {"url": url, "ok": False, "status_code": 502}
        if url.endswith("/api/health-proxy"):
            return {
                "url": url,
                "ok": True,
                "status_code": 200,
                "json": {"api": {"status": "ok"}, "web": {"updated_at": "abc123"}},
            }
        return {"url": url, "ok": True, "status_code": 200, "json": {"status": "ok"}}

    monkeypatch.setattr(
        "app.services.release_gate_service.get_branch_head_sha",
        lambda *args, **kwargs: "abc123",
    )
    monkeypatch.setattr("app.services.release_gate_service.check_http_json_endpoint", fake_json)
    monkeypatch.setattr(
        "app.services.release_gate_service.check_http_endpoint",
        lambda url, timeout=8.0: {"url": url, "ok": True, "status_code": 200},
    )
    monkeypatch.setattr(
        "app.services.release_gate_service.check_value_lineage_e2e_flow",
        lambda api_base, timeout=8.0: {"url": api_base, "ok": True, "status_code": 200},
    )

    out = evaluate_public_deploy_contract_report(
        repository="seeker71/Coherence-Network",
        branch="main",
        api_base="https://api.example.com",
        web_base="https://web.example.com",
    )

    assert out["result"] == "public_contract_passed"
    assert out["failing_checks"] == []
    assert "railway_gates_main_head_unavailable" in out["warnings"]
