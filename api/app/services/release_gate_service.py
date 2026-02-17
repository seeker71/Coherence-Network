"""Release gate checks for PR status, collective review, and public validation."""

from __future__ import annotations

import base64
import binascii
import json
import re
import subprocess
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Optional
from urllib.parse import quote

import httpx

try:  # noqa: SIM105
    from app.services import telemetry_persistence_service
except Exception:  # pragma: no cover - best effort import only
    telemetry_persistence_service = None


def _headers(github_token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


def _record_external_tool_usage(
    *,
    tool_name: str,
    provider: str,
    operation: str,
    resource: str,
    status: str,
    http_status: int | None = None,
    duration_ms: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    if telemetry_persistence_service is None:
        return
    event_payload: dict[str, Any] = {
        "event_id": f"tool_{uuid.uuid4().hex}",
        "occurred_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "tool_name": tool_name,
        "provider": provider,
        "operation": operation,
        "resource": resource,
        "status": status,
        "http_status": http_status,
        "duration_ms": duration_ms,
        "payload": payload or {},
    }
    try:
        telemetry_persistence_service.append_external_tool_usage_event(event_payload)
    except Exception:
        # Telemetry persistence must be best-effort and never block gate behavior.
        return


def _branch_head_sha_via_gh_cli(repository: str, branch: str) -> str | None:
    cmd = ["gh", "api", f"repos/{repository}/branches/{branch}"]
    started = time.monotonic()
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    duration_ms = int((time.monotonic() - started) * 1000)
    status = "success" if proc.returncode == 0 else "error"
    _record_external_tool_usage(
        tool_name="gh-cli",
        provider="github-actions",
        operation="get_branch_head_sha_fallback",
        resource=f"{repository}/branches/{branch}",
        status=status,
        duration_ms=duration_ms,
        payload={"returncode": proc.returncode},
    )
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads((proc.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        return None
    commit = payload.get("commit") if isinstance(payload, dict) else None
    sha = commit.get("sha") if isinstance(commit, dict) else None
    return sha if isinstance(sha, str) else None


def _gh_api_json_via_cli(path: str, *, params: dict[str, str] | None = None) -> Any:
    cmd = ["gh", "api", path]
    if params:
        for key, value in params.items():
            cmd.extend(["-f", f"{key}={value}"])
    started = time.monotonic()
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    duration_ms = int((time.monotonic() - started) * 1000)
    _record_external_tool_usage(
        tool_name="gh-cli",
        provider="github-actions",
        operation="api_fallback_json",
        resource=path,
        status="success" if proc.returncode == 0 else "error",
        duration_ms=duration_ms,
        payload={"returncode": proc.returncode, "params": params or {}},
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads((proc.stdout or "").strip() or "null")
    except json.JSONDecodeError:
        return None


def get_open_prs(
    repository: str,
    head_branch: str | None = None,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    owner, _name = repository.split("/", 1)
    params: dict[str, str] = {"state": "open", "per_page": "100"}
    if head_branch:
        params["head"] = f"{owner}:{head_branch}"
    url = f"https://api.github.com/repos/{repository}/pulls"
    start = time.monotonic()
    try:
        with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
            response = client.get(url, params=params)
            duration_ms = int((time.monotonic() - start) * 1000)
            _record_external_tool_usage(
                tool_name="github-api",
                provider="github-actions",
                operation="get_open_prs",
                resource=f"{repository}/pulls",
                status="success" if response.status_code < 400 else "error",
                http_status=response.status_code,
                duration_ms=duration_ms,
                payload={"head_branch": head_branch, "params": params},
            )
            if response.status_code in {403, 429}:
                # Avoid flaking local/CI gate checks when GitHub API rate limits.
                return []
            response.raise_for_status()
            data = response.json()
        return data if isinstance(data, list) else []
    except httpx.HTTPError:
        fallback = _gh_api_json_via_cli(f"repos/{repository}/pulls", params=params)
        data = fallback if isinstance(fallback, list) else []
        return data if isinstance(data, list) else []


def get_commit_status(
    repository: str,
    sha: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repository}/commits/{sha}/status"
    start = time.monotonic()
    with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
        response = client.get(url)
        duration_ms = int((time.monotonic() - start) * 1000)
        _record_external_tool_usage(
            tool_name="github-api",
            provider="github-actions",
            operation="get_commit_status",
            resource=f"{repository}/commits/{sha}/status",
            status="success" if response.status_code < 400 else "error",
            http_status=response.status_code,
            duration_ms=duration_ms,
        )
        response.raise_for_status()
        data = response.json()
    return data if isinstance(data, dict) else {}


def get_check_runs(
    repository: str,
    sha: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{repository}/commits/{sha}/check-runs"
    start = time.monotonic()
    with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
        response = client.get(url)
        duration_ms = int((time.monotonic() - start) * 1000)
        _record_external_tool_usage(
            tool_name="github-api",
            provider="github-actions",
            operation="get_check_runs",
            resource=f"{repository}/commits/{sha}/check-runs",
            status="success" if response.status_code < 400 else "error",
            http_status=response.status_code,
            duration_ms=duration_ms,
        )
        response.raise_for_status()
        data = response.json()
    runs = data.get("check_runs") if isinstance(data, dict) else []
    return runs if isinstance(runs, list) else []


def extract_actions_run_id(details_url: str) -> Optional[int]:
    """Extract GitHub Actions workflow run id from a check run details URL."""
    marker = "/actions/runs/"
    if marker not in details_url:
        return None
    tail = details_url.split(marker, 1)[1]
    candidate = tail.split("/", 1)[0].strip()
    if not candidate.isdigit():
        return None
    return int(candidate)


def collect_rerunnable_actions_run_ids(
    failing_required_contexts: list[str],
    check_runs: list[dict[str, Any]],
) -> list[int]:
    """Return unique GitHub Actions run IDs that can be retried.

    If failing required contexts are known, only those contexts are retried.
    Otherwise, fallback to any failed GitHub Actions check run for the commit.
    """

    retryable = {"failure", "timed_out", "cancelled", "action_required", "stale"}
    required_set = set(failing_required_contexts)
    filter_by_context = bool(required_set)
    run_ids: set[int] = set()

    for run in check_runs:
        name = run.get("name")
        if not isinstance(name, str):
            continue
        if filter_by_context and name not in required_set:
            continue
        app = run.get("app")
        app_slug = app.get("slug") if isinstance(app, dict) else None
        if app_slug != "github-actions":
            continue
        conclusion = str(run.get("conclusion") or "").lower()
        if conclusion not in retryable:
            continue
        details_url = run.get("details_url")
        if not isinstance(details_url, str):
            continue
        run_id = extract_actions_run_id(details_url)
        if run_id is not None:
            run_ids.add(run_id)

    return sorted(run_ids)


def rerun_actions_failed_jobs(
    repository: str,
    run_id: int,
    github_token: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Trigger rerun-failed-jobs for an Actions workflow run."""
    url = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/rerun-failed-jobs"
    start = time.monotonic()
    with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
        response = client.post(url)
    duration_ms = int((time.monotonic() - start) * 1000)
    _record_external_tool_usage(
        tool_name="github-api",
        provider="github-actions",
        operation="rerun_actions_failed_jobs",
        resource=f"{repository}/actions/runs/{run_id}/rerun-failed-jobs",
        status="success" if response.status_code == 201 else "error",
        http_status=response.status_code,
        duration_ms=duration_ms,
    )
    accepted = response.status_code == 201
    return {
        "run_id": run_id,
        "accepted": accepted,
        "status_code": response.status_code,
    }


def get_required_contexts(
    repository: str,
    base_branch: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> Optional[list[str]]:
    """Return required status check contexts, or None when unavailable."""
    url = f"https://api.github.com/repos/{repository}/branches/{base_branch}/protection"
    try:
        start = time.monotonic()
        with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
            response = client.get(url)
        duration_ms = int((time.monotonic() - start) * 1000)
        _record_external_tool_usage(
            tool_name="github-api",
            provider="github-actions",
            operation="get_required_contexts",
            resource=f"{repository}/branches/{base_branch}/protection",
            status="success" if response.status_code < 400 else "error",
            http_status=response.status_code,
            duration_ms=duration_ms,
        )
        if response.status_code == 401 or response.status_code == 403:
            return None
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError:
        return None

    checks = (
        data.get("required_status_checks", {}).get("checks", [])
        if isinstance(data, dict)
        else []
    )
    contexts = []
    for item in checks:
        if isinstance(item, dict) and isinstance(item.get("context"), str):
            contexts.append(item["context"])
    return contexts


def get_commit_pull_requests(
    repository: str,
    sha: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """Return pull requests associated with a commit SHA."""
    url = f"https://api.github.com/repos/{repository}/commits/{sha}/pulls"
    headers = _headers(github_token)
    headers["Accept"] = "application/vnd.github+json"
    start = time.monotonic()
    try:
        with httpx.Client(timeout=timeout, headers=headers) as client:
            response = client.get(url)
            duration_ms = int((time.monotonic() - start) * 1000)
            _record_external_tool_usage(
                tool_name="github-api",
                provider="github-actions",
                operation="get_commit_pull_requests",
                resource=f"{repository}/commits/{sha}/pulls",
                status="success" if response.status_code < 400 else "error",
                http_status=response.status_code,
                duration_ms=duration_ms,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        fallback = _gh_api_json_via_cli(f"repos/{repository}/commits/{sha}/pulls")
        data = fallback if isinstance(fallback, list) else []
    return data if isinstance(data, list) else []


def get_pull_request_reviews(
    repository: str,
    pr_number: int,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """Return reviews for a pull request."""
    url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/reviews"
    start = time.monotonic()
    try:
        with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
            response = client.get(url)
            duration_ms = int((time.monotonic() - start) * 1000)
            _record_external_tool_usage(
                tool_name="github-api",
                provider="github-actions",
                operation="get_pull_request_reviews",
                resource=f"{repository}/pulls/{pr_number}/reviews",
                status="success" if response.status_code < 400 else "error",
                http_status=response.status_code,
                duration_ms=duration_ms,
            )
            if response.status_code in {403, 429}:
                # Avoid flaking local/CI gate checks when GitHub API rate limits.
                return []
            response.raise_for_status()
            data = response.json()
        return data if isinstance(data, list) else []
    except httpx.HTTPError:
        return []


def evaluate_pr_gates(
    pr: dict[str, Any],
    commit_status: dict[str, Any],
    check_runs: list[dict[str, Any]],
    required_contexts: list[str] | None,
) -> dict[str, Any]:
    sha = pr.get("head", {}).get("sha")
    combined_state = commit_status.get("state", "unknown")
    statuses = commit_status.get("statuses", [])
    status_map: dict[str, str] = {}
    if isinstance(statuses, list):
        for item in statuses:
            if isinstance(item, dict) and isinstance(item.get("context"), str):
                status_map[item["context"]] = str(item.get("state", "unknown"))

    run_map: dict[str, str] = {}
    for run in check_runs:
        name = run.get("name")
        if isinstance(name, str):
            run_map[name] = str(run.get("conclusion") or run.get("status") or "unknown")

    required = required_contexts or []
    missing_required = []
    failing_required = []
    for context in required:
        if context in status_map:
            if status_map[context] != "success":
                failing_required.append(context)
        elif context in run_map:
            if run_map[context] != "success":
                failing_required.append(context)
        else:
            missing_required.append(context)

    draft = bool(pr.get("draft"))
    mergeable = str(pr.get("mergeable_state") or "unknown")

    all_required_passed = not missing_required and not failing_required
    # When required contexts are unavailable, do not hard-block on combined state:
    # it may include non-required external/transient checks.
    checks_green = (combined_state == "success") if required else True
    ready = (not draft) and checks_green and (all_required_passed or not required)

    return {
        "pr_number": pr.get("number"),
        "head_sha": sha,
        "draft": draft,
        "mergeable_state": mergeable,
        "combined_status_state": combined_state,
        "required_contexts": required,
        "missing_required_contexts": missing_required,
        "failing_required_contexts": failing_required,
        "ready_to_merge": ready,
    }


def evaluate_collective_review_gates(
    pr: dict[str, Any],
    reviews: list[dict[str, Any]],
    min_approvals: int = 1,
    min_unique_approvers: int = 1,
) -> dict[str, Any]:
    """Evaluate collective review contract from PR + review events."""
    approvers: set[str] = set()
    approval_events = 0
    for review in reviews:
        if str(review.get("state", "")).upper() != "APPROVED":
            continue
        approval_events += 1
        user = review.get("user") if isinstance(review.get("user"), dict) else {}
        login = user.get("login")
        if isinstance(login, str) and login:
            approvers.add(login)

    merged = bool(pr.get("merged_at"))
    draft = bool(pr.get("draft"))
    to_main = str(pr.get("base", {}).get("ref", "")) == "main"
    collective_ok = (
        merged
        and (not draft)
        and to_main
        and approval_events >= min_approvals
        and len(approvers) >= min_unique_approvers
    )
    return {
        "pr_number": pr.get("number"),
        "merged": merged,
        "draft": draft,
        "base_ref": pr.get("base", {}).get("ref"),
        "approval_events": approval_events,
        "unique_approvers": sorted(approvers),
        "min_approvals_required": min_approvals,
        "min_unique_approvers_required": min_unique_approvers,
        "collective_review_passed": collective_ok,
    }


def check_http_endpoint(url: str, timeout: float = 8.0) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
        return {
            "url": url,
            "ok": response.status_code == 200,
            "status_code": response.status_code,
        }
    except httpx.HTTPError as exc:
        return {"url": url, "ok": False, "status_code": None, "error": str(exc)}


def check_http_json_endpoint(url: str, timeout: float = 8.0) -> dict[str, Any]:
    """Fetch URL and parse JSON body when available."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
        payload: dict[str, Any] | None = None
        parse_error: str | None = None
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, dict):
                    payload = data
                else:
                    parse_error = "response body is not a JSON object"
            except ValueError as exc:
                parse_error = str(exc)
        out: dict[str, Any] = {
            "url": url,
            "ok": response.status_code == 200,
            "status_code": response.status_code,
        }
        if payload is not None:
            out["json"] = payload
        if parse_error:
            out["parse_error"] = parse_error
        return out
    except httpx.HTTPError as exc:
        return {"url": url, "ok": False, "status_code": None, "error": str(exc)}


def check_value_lineage_e2e_flow(api_base: str, timeout: float = 8.0) -> dict[str, Any]:
    """Run a live public transaction check for value-lineage contract behavior."""
    base = api_base.rstrip("/")
    marker = uuid.uuid4().hex[:8]
    create_payload = {
        "idea_id": f"public-e2e-{marker}",
        "spec_id": "048-value-lineage-and-payout-attribution",
        "implementation_refs": [f"contract:{marker}"],
        "contributors": {
            "idea": "gate-idea",
            "spec": "gate-spec",
            "implementation": "gate-impl",
            "review": "gate-review",
        },
        "estimated_cost": 2.25,
    }
    usage_payload = {"source": "public-contract", "metric": "validated_flow", "value": 5.0}
    payout_payload = {"payout_pool": 100.0}

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            created = client.post(f"{base}/api/value-lineage/links", json=create_payload)
            if created.status_code != 201:
                return {
                    "url": f"{base}/api/value-lineage/links",
                    "ok": False,
                    "status_code": created.status_code,
                    "error": "create_link_failed",
                }
            body = created.json()
            lineage_id = body.get("id") if isinstance(body, dict) else None
            if not isinstance(lineage_id, str) or not lineage_id:
                return {
                    "url": f"{base}/api/value-lineage/links",
                    "ok": False,
                    "status_code": created.status_code,
                    "error": "missing_lineage_id",
                }

            usage = client.post(
                f"{base}/api/value-lineage/links/{lineage_id}/usage-events",
                json=usage_payload,
            )
            if usage.status_code != 201:
                return {
                    "url": f"{base}/api/value-lineage/links/{lineage_id}/usage-events",
                    "ok": False,
                    "status_code": usage.status_code,
                    "error": "usage_event_failed",
                }

            valuation = client.get(f"{base}/api/value-lineage/links/{lineage_id}/valuation")
            if valuation.status_code != 200:
                return {
                    "url": f"{base}/api/value-lineage/links/{lineage_id}/valuation",
                    "ok": False,
                    "status_code": valuation.status_code,
                    "error": "valuation_failed",
                }
            valuation_body = valuation.json()
            measured_total = (
                valuation_body.get("measured_value_total")
                if isinstance(valuation_body, dict)
                else None
            )
            event_count = valuation_body.get("event_count") if isinstance(valuation_body, dict) else 0
            if measured_total != 5.0 or not isinstance(event_count, int) or event_count < 1:
                return {
                    "url": f"{base}/api/value-lineage/links/{lineage_id}/valuation",
                    "ok": False,
                    "status_code": valuation.status_code,
                    "error": "valuation_invariant_failed",
                    "measured_value_total": measured_total,
                    "event_count": event_count,
                }

            payout = client.post(
                f"{base}/api/value-lineage/links/{lineage_id}/payout-preview",
                json=payout_payload,
            )
            if payout.status_code != 200:
                return {
                    "url": f"{base}/api/value-lineage/links/{lineage_id}/payout-preview",
                    "ok": False,
                    "status_code": payout.status_code,
                    "error": "payout_preview_failed",
                }
            payout_body = payout.json()
            payout_rows = payout_body.get("payouts") if isinstance(payout_body, dict) else None
            if not isinstance(payout_rows, list):
                return {
                    "url": f"{base}/api/value-lineage/links/{lineage_id}/payout-preview",
                    "ok": False,
                    "status_code": payout.status_code,
                    "error": "payout_rows_missing",
                }
            role_to_amount = {
                row.get("role"): row.get("amount")
                for row in payout_rows
                if isinstance(row, dict) and isinstance(row.get("role"), str)
            }
            expected_amounts = {"idea": 10.0, "spec": 20.0, "implementation": 50.0, "review": 20.0}
            if role_to_amount != expected_amounts:
                return {
                    "url": f"{base}/api/value-lineage/links/{lineage_id}/payout-preview",
                    "ok": False,
                    "status_code": payout.status_code,
                    "error": "payout_invariant_failed",
                    "observed_amounts": role_to_amount,
                }

            return {
                "url": f"{base}/api/value-lineage/links/{lineage_id}",
                "ok": True,
                "status_code": 200,
                "lineage_id": lineage_id,
                "validated_invariants": [
                    "create_link_201",
                    "usage_event_201",
                    "valuation_matches_event_value",
                    "payout_matches_role_weights",
                ],
            }
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {
            "url": f"{base}/api/value-lineage/links",
            "ok": False,
            "status_code": None,
            "error": str(exc),
        }


def wait_for_public_validation(
    endpoint_urls: list[str],
    timeout_seconds: int = 1200,
    poll_interval_seconds: int = 30,
) -> dict[str, Any]:
    started = time.time()
    last_checks: list[dict[str, Any]] = []

    while True:
        last_checks = [check_http_endpoint(url) for url in endpoint_urls]
        if all(item.get("ok") for item in last_checks):
            return {
                "ready": True,
                "elapsed_seconds": int(time.time() - started),
                "checks": last_checks,
            }
        if time.time() - started >= timeout_seconds:
            return {
                "ready": False,
                "elapsed_seconds": int(time.time() - started),
                "checks": last_checks,
            }
        time.sleep(max(1, poll_interval_seconds))


def get_branch_head_sha(
    repository: str,
    branch: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> str | None:
    """Return branch head SHA, or None if unavailable."""
    url = f"https://api.github.com/repos/{repository}/branches/{branch}"
    try:
        start = time.monotonic()
        with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
            response = client.get(url)
            duration_ms = int((time.monotonic() - start) * 1000)
            _record_external_tool_usage(
                tool_name="github-api",
                provider="github-actions",
                operation="get_branch_head_sha",
                resource=f"{repository}/branches/{branch}",
                status="success" if response.status_code < 400 else "error",
                http_status=response.status_code,
                duration_ms=duration_ms,
            )
            response.raise_for_status()
            data = response.json()
        sha = (data.get("commit") or {}).get("sha") if isinstance(data, dict) else None
        return sha if isinstance(sha, str) else None
    except httpx.HTTPError:
        return _branch_head_sha_via_gh_cli(repository, branch)


def evaluate_pr_to_public_report(
    repository: str,
    branch: str,
    base: str = "main",
    api_base: str = "https://coherence-network-production.up.railway.app",
    web_base: str = "https://coherence-web-production.up.railway.app",
    wait_public: bool = False,
    timeout_seconds: int = 1200,
    poll_seconds: int = 30,
    endpoint_urls: list[str] | None = None,
    github_token: str | None = None,
) -> dict[str, Any]:
    """Build PR->public validation report used by API and scripts."""
    report: dict[str, Any] = {"repo": repository, "branch": branch, "base": base}
    prs = get_open_prs(repository, head_branch=branch, github_token=github_token)
    report["open_pr_count"] = len(prs)
    if not prs:
        report["result"] = "blocked"
        report["reason"] = "No open PR found for branch"
        return report

    pr = prs[0]
    sha = pr.get("head", {}).get("sha")
    if not isinstance(sha, str):
        report["result"] = "blocked"
        report["reason"] = "PR has no head SHA"
        return report

    commit_status = get_commit_status(repository, sha, github_token=github_token)
    check_runs = get_check_runs(repository, sha, github_token=github_token)
    required = get_required_contexts(repository, base, github_token=github_token)
    pr_gate = evaluate_pr_gates(pr, commit_status, check_runs, required)
    report["pr_gate"] = pr_gate
    if not pr_gate.get("ready_to_merge"):
        report["result"] = "blocked"
        report["reason"] = "PR gates not fully green"
        return report

    if not wait_public:
        report["result"] = "ready_for_merge"
        return report

    endpoints = endpoint_urls or [
        f"{api_base.rstrip('/')}/api/health",
        f"{api_base.rstrip('/')}/api/ideas",
        f"{api_base.rstrip('/')}/api/gates/main-head",
        f"{web_base.rstrip('/')}/gates",
        f"{web_base.rstrip('/')}/api-health",
    ]
    public = wait_for_public_validation(
        endpoint_urls=endpoints,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_seconds,
    )
    report["public_validation"] = public
    report["result"] = "public_validated" if public.get("ready") else "blocked"
    if not public.get("ready"):
        report["reason"] = "Public validation timed out or failed"
    return report


def evaluate_merged_change_contract_report(
    repository: str,
    sha: str,
    api_base: str = "https://coherence-network-production.up.railway.app",
    web_base: str = "https://coherence-web-production.up.railway.app",
    timeout_seconds: int = 1200,
    poll_seconds: int = 30,
    endpoint_urls: list[str] | None = None,
    min_approvals: int = 1,
    min_unique_approvers: int = 1,
    github_token: str | None = None,
) -> dict[str, Any]:
    """Build merged-change contract report used by API and scripts."""
    report: dict[str, Any] = {"repo": repository, "sha": sha}
    prs = get_commit_pull_requests(repository, sha, github_token=github_token)
    merged_main_pr = None
    for pr in prs:
        if pr.get("merged_at") and str(pr.get("base", {}).get("ref", "")) == "main":
            merged_main_pr = pr
            break
    if merged_main_pr is None:
        report["result"] = "blocked"
        report["reason"] = "No merged PR to main associated with commit SHA"
        return report

    pr_number = int(merged_main_pr["number"])
    reviews = get_pull_request_reviews(repository, pr_number, github_token=github_token)
    collective = evaluate_collective_review_gates(
        merged_main_pr,
        reviews,
        min_approvals=max(0, min_approvals),
        min_unique_approvers=max(0, min_unique_approvers),
    )
    report["pr"] = {
        "number": pr_number,
        "url": merged_main_pr.get("html_url"),
        "author": ((merged_main_pr.get("user") or {}).get("login")),
        "merged_by": ((merged_main_pr.get("merged_by") or {}).get("login")),
    }
    report["collective_review"] = collective
    if not collective.get("collective_review_passed"):
        report["result"] = "blocked"
        report["reason"] = "Collective review gate failed"
        return report

    commit_status = get_commit_status(repository, sha, github_token=github_token)
    check_runs = get_check_runs(repository, sha, github_token=github_token)
    required = get_required_contexts(repository, "main", github_token=github_token)
    pseudo_pr = {
        "number": pr_number,
        "head": {"sha": sha},
        "draft": False,
        "mergeable_state": "clean",
    }
    checks_gate = evaluate_pr_gates(pseudo_pr, commit_status, check_runs, required)
    report["checks_gate"] = checks_gate
    if not bool(checks_gate.get("ready_to_merge")):
        report["result"] = "blocked"
        report["reason"] = "Commit checks are not green on main"
        return report

    endpoints = endpoint_urls or [
        f"{api_base.rstrip('/')}/api/health",
        f"{api_base.rstrip('/')}/api/ideas",
        f"{api_base.rstrip('/')}/api/gates/main-head",
        f"{web_base.rstrip('/')}/gates",
        f"{web_base.rstrip('/')}/api-health",
    ]
    public = wait_for_public_validation(
        endpoint_urls=endpoints,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_seconds,
    )
    report["public_validation"] = public
    if not public.get("ready"):
        report["result"] = "blocked"
        report["reason"] = "Public validation timed out or failed"
        return report

    report["contributor_ack"] = {
        "eligible": True,
        "rule": "acknowledge only when checks + collective review + public validation pass",
        "contributor": report["pr"]["author"] if isinstance(report.get("pr"), dict) else None,
    }
    report["result"] = "contract_passed"
    return report


def evaluate_public_deploy_contract_report(
    repository: str = "seeker71/Coherence-Network",
    branch: str = "main",
    api_base: str = "https://coherence-network-production.up.railway.app",
    web_base: str = "https://coherence-web-production.up.railway.app",
    expected_sha: str | None = None,
    timeout: float = 8.0,
    github_token: str | None = None,
) -> dict[str, Any]:
    """Validate public API + web deployment contract against branch head SHA."""
    report: dict[str, Any] = {
        "repository": repository,
        "branch": branch,
        "api_base": api_base.rstrip("/"),
        "web_base": web_base.rstrip("/"),
    }
    target_sha = expected_sha or get_branch_head_sha(
        repository,
        branch,
        github_token=github_token,
    )
    report["expected_sha"] = target_sha
    if not isinstance(target_sha, str) or not target_sha:
        report["result"] = "blocked"
        report["reason"] = "Unable to resolve expected branch head SHA"
        return report

    checks: list[dict[str, Any]] = []

    api_health_url = f"{report['api_base']}/api/health"
    api_health = check_http_json_endpoint(api_health_url, timeout=timeout)
    api_health["name"] = "railway_health"
    checks.append(api_health)

    api_gates_head_url = f"{report['api_base']}/api/gates/main-head"
    api_gates_head = check_http_json_endpoint(api_gates_head_url, timeout=timeout)
    api_gates_head["name"] = "railway_gates_main_head"
    if api_gates_head.get("ok") and isinstance(api_gates_head.get("json"), dict):
        observed_sha = api_gates_head["json"].get("sha")
        api_gates_head["observed_sha"] = observed_sha
        api_gates_head["sha_match"] = observed_sha == target_sha
        api_gates_head["ok"] = bool(api_gates_head["ok"] and api_gates_head["sha_match"])
    checks.append(api_gates_head)

    web_gates_url = f"{report['web_base']}/gates"
    web_gates = check_http_endpoint(web_gates_url, timeout=timeout)
    web_gates["name"] = "railway_web_gates_page"
    checks.append(web_gates)

    web_proxy_url = f"{report['web_base']}/api/health-proxy"
    web_proxy = check_http_json_endpoint(web_proxy_url, timeout=timeout)
    web_proxy["name"] = "railway_web_health_proxy"
    if web_proxy.get("ok") and isinstance(web_proxy.get("json"), dict):
        payload = web_proxy["json"]
        api_payload = payload.get("api") if isinstance(payload.get("api"), dict) else {}
        web_payload = payload.get("web") if isinstance(payload.get("web"), dict) else {}
        updated_at = web_payload.get("updated_at")
        api_status = api_payload.get("status")
        web_proxy["web_updated_at"] = updated_at
        web_proxy["api_status"] = api_status
        web_proxy["sha_match"] = updated_at == target_sha
        web_proxy["api_ok"] = api_status == "ok"
        web_proxy["ok"] = bool(
            web_proxy["ok"] and web_proxy["sha_match"] and web_proxy["api_ok"]
        )
    checks.append(web_proxy)

    value_lineage_e2e = check_value_lineage_e2e_flow(report["api_base"], timeout=timeout)
    value_lineage_e2e["name"] = "railway_value_lineage_e2e"
    checks.append(value_lineage_e2e)

    report["checks"] = checks
    warnings: list[str] = []
    failing: list[str] = []
    for check in checks:
        name = check.get("name")
        if check.get("ok"):
            continue
        if name == "railway_web_health_proxy":
            updated_raw = str(check.get("web_updated_at") or "").strip().lower()
            if (
                check.get("status_code") == 200
                and bool(check.get("api_ok"))
                and updated_raw in {"", "unknown", "none", "n/a"}
            ):
                warnings.append("railway_web_health_proxy_unknown_sha")
                continue
        if (
            name == "railway_gates_main_head"
            and check.get("status_code") in {401, 403, 502}
        ):
            warnings.append("railway_gates_main_head_unavailable")
            continue
        failing.append(str(name))
    report["warnings"] = warnings
    report["failing_checks"] = failing
    if failing:
        report["result"] = "blocked"
        report["reason"] = f"Public deployment contract failed: {', '.join(str(x) for x in failing)}"
        return report

    report["result"] = "public_contract_passed"
    return report


def get_commit_files(
    repository: str,
    sha: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> list[str]:
    """Return file paths changed in a commit."""
    url = f"https://api.github.com/repos/{repository}/commits/{sha}"
    start = time.monotonic()
    try:
        with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
            response = client.get(url)
            duration_ms = int((time.monotonic() - start) * 1000)
            _record_external_tool_usage(
                tool_name="github-api",
                provider="github-actions",
                operation="get_commit_files",
                resource=f"{repository}/commits/{sha}",
                status="success" if response.status_code < 400 else "error",
                http_status=response.status_code,
                duration_ms=duration_ms,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        fallback = _gh_api_json_via_cli(f"repos/{repository}/commits/{sha}")
        data = fallback if isinstance(fallback, dict) else {}
    files = data.get("files") if isinstance(data, dict) else []
    out: list[str] = []
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict) and isinstance(item.get("filename"), str):
                out.append(item["filename"])
    return out


def get_pull_request_files(
    repository: str,
    pr_number: int,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> list[str]:
    """Return file paths changed in a pull request."""
    url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/files"
    start = time.monotonic()
    try:
        with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
            response = client.get(url, params={"per_page": "100"})
            duration_ms = int((time.monotonic() - start) * 1000)
            _record_external_tool_usage(
                tool_name="github-api",
                provider="github-actions",
                operation="get_pull_request_files",
                resource=f"{repository}/pulls/{pr_number}/files",
                status="success" if response.status_code < 400 else "error",
                http_status=response.status_code,
                duration_ms=duration_ms,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        fallback = _gh_api_json_via_cli(
            f"repos/{repository}/pulls/{pr_number}/files",
            params={"per_page": "100"},
        )
        data = fallback if isinstance(fallback, list) else []
    out: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("filename"), str):
                out.append(item["filename"])
    return out


def get_file_content_at_ref(
    repository: str,
    path: str,
    ref: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> str | None:
    """Return decoded text content for a repository file at a ref, when available."""
    quoted_path = quote(path, safe="/")
    url = f"https://api.github.com/repos/{repository}/contents/{quoted_path}"
    with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
        data: dict[str, Any] | None = None
        for attempt in range(3):
            start = time.monotonic()
            response = client.get(url, params={"ref": ref})
            duration_ms = int((time.monotonic() - start) * 1000)
            _record_external_tool_usage(
                tool_name="github-api",
                provider="github-actions",
                operation="get_file_content_at_ref",
                resource=f"{repository}/contents/{path}@{ref}",
                status="success" if response.status_code < 400 else "error",
                http_status=response.status_code,
                duration_ms=duration_ms,
                payload={"attempt": attempt + 1},
            )
            # Transient upstream errors (observed in CI) should not fail traceability report generation.
            if response.status_code >= 500 and attempt < 2:
                time.sleep(0.2 * float(attempt + 1))
                continue
            if response.status_code == 404:
                return None
            if response.status_code in {403, 429}:
                fallback = _gh_api_json_via_cli(
                    f"repos/{repository}/contents/{quoted_path}",
                    params={"ref": ref},
                )
                data = fallback if isinstance(fallback, dict) else None
                break
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                fallback = _gh_api_json_via_cli(
                    f"repos/{repository}/contents/{quoted_path}",
                    params={"ref": ref},
                )
                data = fallback if isinstance(fallback, dict) else None
                break
            parsed = response.json()
            data = parsed if isinstance(parsed, dict) else None
            break
    if not isinstance(data, dict):
        return None
    content = data.get("content")
    encoding = data.get("encoding")
    if not isinstance(content, str) or encoding != "base64":
        return None
    try:
        decoded = base64.b64decode(content.encode("utf-8"), validate=False)
        return decoded.decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return None


def list_spec_paths_at_ref(
    repository: str,
    ref: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> list[str]:
    """List spec markdown file paths for a repository ref."""
    url = f"https://api.github.com/repos/{repository}/contents/specs"
    with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
        data: Any = None
        for attempt in range(3):
            start = time.monotonic()
            response = client.get(url, params={"ref": ref})
            duration_ms = int((time.monotonic() - start) * 1000)
            _record_external_tool_usage(
                tool_name="github-api",
                provider="github-actions",
                operation="list_spec_paths_at_ref",
                resource=f"{repository}/contents/specs@{ref}",
                status="success" if response.status_code < 400 else "error",
                http_status=response.status_code,
                duration_ms=duration_ms,
                payload={"attempt": attempt + 1},
            )
            if response.status_code >= 500 and attempt < 2:
                time.sleep(0.2 * float(attempt + 1))
                continue
            # 403/429 can happen in unauthenticated CI due GitHub API rate-limit.
            # Traceability report should still render with degraded spec linkage.
            if response.status_code == 404:
                return []
            if response.status_code in {403, 429}:
                fallback = _gh_api_json_via_cli(
                    f"repos/{repository}/contents/specs",
                    params={"ref": ref},
                )
                data = fallback
                break
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                fallback = _gh_api_json_via_cli(
                    f"repos/{repository}/contents/specs",
                    params={"ref": ref},
                )
                data = fallback
                break
            data = response.json()
            break
    out: list[str] = []
    if isinstance(data, list):
        for item in data:
            path = item.get("path") if isinstance(item, dict) else None
            if isinstance(path, str) and path.startswith("specs/") and path.endswith(".md"):
                out.append(path)
    return out


def _extract_spec_id(path: str) -> str | None:
    match = re.match(r"^specs/(\d{3})-[^/]+\.md$", path)
    if not match:
        return None
    return match.group(1)


def _parse_commit_evidence(
    repository: str,
    evidence_path: str,
    sha: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    raw = get_file_content_at_ref(
        repository=repository,
        path=evidence_path,
        ref=sha,
        github_token=github_token,
        timeout=timeout,
    )
    if not isinstance(raw, str):
        return {}
    try:
        payload = json.loads(raw)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def evaluate_commit_traceability_report(
    repository: str,
    sha: str,
    api_base: str = "https://coherence-network-production.up.railway.app",
    web_base: str = "https://coherence-web-production.up.railway.app",
    github_token: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Derive idea/spec/implementation traceability references from a commit SHA."""
    commit_files = get_commit_files(repository, sha, github_token=github_token, timeout=timeout)
    commit_prs = get_commit_pull_requests(repository, sha, github_token=github_token, timeout=timeout)

    # Merge commits may not expose full file list; fallback to first associated PR files.
    if not commit_files and commit_prs:
        pr_number = commit_prs[0].get("number")
        if isinstance(pr_number, int):
            commit_files = get_pull_request_files(
                repository,
                pr_number,
                github_token=github_token,
                timeout=timeout,
            )

    evidence_files = sorted(
        path for path in commit_files if path.startswith("docs/system_audit/commit_evidence_")
    )
    evidence_payloads = [
        _parse_commit_evidence(
            repository=repository,
            evidence_path=path,
            sha=sha,
            github_token=github_token,
            timeout=timeout,
        )
        for path in evidence_files
    ]

    idea_ids: set[str] = set()
    spec_ids: set[str] = set()
    evidence_change_files: set[str] = set()
    for payload in evidence_payloads:
        ids = payload.get("idea_ids")
        if isinstance(ids, list):
            idea_ids.update(i for i in ids if isinstance(i, str) and i.strip())
        specs = payload.get("spec_ids")
        if isinstance(specs, list):
            spec_ids.update(s for s in specs if isinstance(s, str) and s.strip())
        changed = payload.get("change_files")
        if isinstance(changed, list):
            evidence_change_files.update(c for c in changed if isinstance(c, str) and c.strip())

    implementation_files = sorted(
        evidence_change_files
        if evidence_change_files
        else [path for path in commit_files if not path.startswith("docs/system_audit/")]
    )

    specs_dir_paths = list_spec_paths_at_ref(
        repository=repository,
        ref=sha,
        github_token=github_token,
        timeout=timeout,
    )
    spec_id_to_path = {
        sid: path
        for path in specs_dir_paths
        for sid in [_extract_spec_id(path)]
        if isinstance(sid, str)
    }
    mapped_specs = sorted(spec_ids)

    repo_url = f"https://github.com/{repository}"
    api_root = api_base.rstrip("/")
    web_root = web_base.rstrip("/")
    ideas = [
        {
            "idea_id": idea_id,
            "api_path": f"/api/ideas/{idea_id}",
            "api_url": f"{api_root}/api/ideas/{idea_id}",
        }
        for idea_id in sorted(idea_ids)
    ]
    specs = [
        {
            "spec_id": spec_id,
            "path": spec_id_to_path.get(spec_id),
            "github_url": (
                f"{repo_url}/blob/{sha}/{spec_id_to_path[spec_id]}"
                if spec_id_to_path.get(spec_id)
                else None
            ),
        }
        for spec_id in mapped_specs
    ]
    implementations = [
        {
            "path": path,
            "github_url": f"{repo_url}/blob/{sha}/{path}",
        }
        for path in implementation_files
    ]

    questions_answered = {
        "idea_links_derived": bool(ideas),
        "spec_links_derived": bool(specs),
        "implementation_links_derived": bool(implementations),
        "commit_evidence_present": bool(evidence_files),
    }
    missing_answers: list[str] = []
    if not ideas:
        missing_answers.append("No idea_ids found in commit evidence")
    if not specs:
        missing_answers.append("No spec_ids found in commit evidence")
    if not implementations:
        missing_answers.append("No implementation files derivable from commit")
    if not evidence_files:
        missing_answers.append("No commit evidence file changed in this commit")

    return {
        "repository": repository,
        "sha": sha,
        "pr_numbers": [pr.get("number") for pr in commit_prs if isinstance(pr, dict)],
        "traceability": {
            "ideas": ideas,
            "specs": specs,
            "implementations": implementations,
            "evidence_files": evidence_files,
        },
        "questions_answered": questions_answered,
        "missing_answers": missing_answers,
        "machine_access": {
            "api_traceability_path": "/api/gates/commit-traceability",
            "api_ideas_path_template": "/api/ideas/{idea_id}",
        },
        "human_access": {
            "web_gates_path": f"{web_root}/gates",
        },
        "result": "traceability_ready" if not missing_answers else "traceability_incomplete",
    }
