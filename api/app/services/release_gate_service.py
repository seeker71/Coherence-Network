"""Release gate checks for PR status, collective review, and public validation."""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx


def _headers(github_token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


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
    with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    return data if isinstance(data, list) else []


def get_commit_status(
    repository: str,
    sha: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repository}/commits/{sha}/status"
    with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
        response = client.get(url)
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
    with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
    runs = data.get("check_runs") if isinstance(data, dict) else []
    return runs if isinstance(runs, list) else []


def get_required_contexts(
    repository: str,
    base_branch: str,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> Optional[list[str]]:
    """Return required status check contexts, or None when unavailable."""
    url = f"https://api.github.com/repos/{repository}/branches/{base_branch}/protection"
    try:
        with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
            response = client.get(url)
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
    with httpx.Client(timeout=timeout, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
    return data if isinstance(data, list) else []


def get_pull_request_reviews(
    repository: str,
    pr_number: int,
    github_token: str | None = None,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """Return reviews for a pull request."""
    url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/reviews"
    with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
    return data if isinstance(data, list) else []


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
    checks_green = combined_state == "success"
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
        with httpx.Client(timeout=timeout, headers=_headers(github_token)) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
        sha = (data.get("commit") or {}).get("sha") if isinstance(data, dict) else None
        return sha if isinstance(sha, str) else None
    except httpx.HTTPError:
        return None


def evaluate_pr_to_public_report(
    repository: str,
    branch: str,
    base: str = "main",
    api_base: str = "https://coherence-network-production.up.railway.app",
    web_base: str = "https://coherence-network.vercel.app",
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
    web_base: str = "https://coherence-network.vercel.app",
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
    if checks_gate.get("combined_status_state") != "success":
        report["result"] = "blocked"
        report["reason"] = "Commit checks are not green on main"
        return report

    endpoints = endpoint_urls or [
        f"{api_base.rstrip('/')}/api/health",
        f"{api_base.rstrip('/')}/api/ideas",
        f"{web_base.rstrip('/')}/",
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
