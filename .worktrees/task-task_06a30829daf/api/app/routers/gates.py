"""Release/public gate API routes for machine access."""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException, Query

from app.services import release_gate_service as gates

router = APIRouter()


def _github_token() -> str | None:
    return os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")


@router.get("/gates/pr-to-public")
async def gate_pr_to_public(
    branch: str = Query(..., min_length=1, description="PR head branch"),
    repo: str = Query("seeker71/Coherence-Network"),
    base: str = Query("main"),
    wait_public: bool = Query(False),
    timeout_seconds: int = Query(1200, ge=10, le=7200),
    poll_seconds: int = Query(30, ge=1, le=300),
) -> dict:
    report = await asyncio.to_thread(
        gates.evaluate_pr_to_public_report,
        repository=repo,
        branch=branch,
        base=base,
        wait_public=wait_public,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        github_token=_github_token(),
    )
    return report


@router.get("/gates/merged-contract")
async def gate_merged_contract(
    sha: str = Query(..., min_length=7, description="Merged commit SHA on main"),
    repo: str = Query("seeker71/Coherence-Network"),
    min_approvals: int = Query(1, ge=0, le=10),
    min_unique_approvers: int = Query(1, ge=0, le=10),
    timeout_seconds: int = Query(1200, ge=10, le=7200),
    poll_seconds: int = Query(30, ge=1, le=300),
) -> dict:
    report = await asyncio.to_thread(
        gates.evaluate_merged_change_contract_report,
        repository=repo,
        sha=sha,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        min_approvals=min_approvals,
        min_unique_approvers=min_unique_approvers,
        github_token=_github_token(),
    )
    return report


@router.get("/gates/main-head")
async def gates_main_head(
    repo: str = Query("seeker71/Coherence-Network"),
    branch: str = Query("main"),
    timeout_seconds: float = Query(6.0, ge=1.0, le=60.0),
) -> dict:
    try:
        sha = gates.get_branch_head_sha(
            repo,
            branch,
            github_token=_github_token(),
            timeout=timeout_seconds,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to resolve branch head SHA")
    if not sha:
        raise HTTPException(status_code=502, detail="Could not resolve branch head SHA")
    return {"repo": repo, "branch": branch, "sha": sha}


@router.get("/gates/main-contract")
async def gates_main_contract(
    repo: str = Query("seeker71/Coherence-Network"),
    branch: str = Query("main"),
    min_approvals: int = Query(1, ge=0, le=10),
    min_unique_approvers: int = Query(1, ge=0, le=10),
    timeout_seconds: int = Query(1200, ge=10, le=7200),
    poll_seconds: int = Query(30, ge=1, le=300),
) -> dict:
    sha = gates.get_branch_head_sha(
        repo,
        branch,
        github_token=_github_token(),
        timeout=8.0,
    )
    if not sha:
        raise HTTPException(status_code=502, detail="Could not resolve branch head SHA")
    report = await asyncio.to_thread(
        gates.evaluate_merged_change_contract_report,
        repository=repo,
        sha=sha,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        min_approvals=min_approvals,
        min_unique_approvers=min_unique_approvers,
        github_token=_github_token(),
    )
    report["branch"] = branch
    return report


@router.get("/gates/public-deploy-contract")
async def gates_public_deploy_contract(
    repo: str = Query("seeker71/Coherence-Network"),
    branch: str = Query("main"),
    api_base: str = Query("https://coherence-network-production.up.railway.app"),
    web_base: str = Query("https://coherence-web-production.up.railway.app"),
    timeout: float = Query(8.0, ge=1.0, le=60.0),
) -> dict:
    return await asyncio.to_thread(
        gates.evaluate_public_deploy_contract_report,
        repository=repo,
        branch=branch,
        api_base=api_base,
        web_base=web_base,
        timeout=timeout,
        github_token=_github_token(),
    )


@router.post("/gates/public-deploy-verification-jobs")
async def create_public_deploy_verification_job(
    repo: str = Query("seeker71/Coherence-Network"),
    branch: str = Query("main"),
    api_base: str = Query("https://coherence-network-production.up.railway.app"),
    web_base: str = Query("https://coherence-web-production.up.railway.app"),
    expected_sha: str | None = Query(None),
    timeout: float = Query(8.0, ge=1.0, le=60.0),
    poll_seconds: float = Query(30.0, ge=1.0, le=600.0),
    max_attempts: int | None = Query(None, ge=1, le=200),
) -> dict:
    return await asyncio.to_thread(
        gates.create_public_deploy_verification_job,
        repository=repo,
        branch=branch,
        api_base=api_base,
        web_base=web_base,
        expected_sha=expected_sha,
        max_attempts=max_attempts,
        timeout=timeout,
        poll_seconds=poll_seconds,
        github_token=_github_token(),
    )


@router.get("/gates/public-deploy-verification-jobs")
async def list_public_deploy_verification_jobs() -> list[dict]:
    return await asyncio.to_thread(gates.list_public_deploy_verification_jobs)


@router.post("/gates/public-deploy-verification-jobs/{job_id}/tick")
async def tick_public_deploy_verification_job(job_id: str) -> dict:
    return await asyncio.to_thread(
        gates.tick_public_deploy_verification_job,
        job_id=job_id,
        github_token=_github_token(),
    )


@router.post("/gates/public-deploy-verification-jobs/tick")
async def tick_public_deploy_verification_jobs(
    due_only: bool = Query(True),
) -> dict:
    return await asyncio.to_thread(
        gates.tick_public_deploy_verification_jobs,
        github_token=_github_token(),
        due_only=due_only,
    )


@router.get("/gates/commit-traceability")
async def gates_commit_traceability(
    sha: str = Query(..., min_length=7, description="Commit SHA to derive traceability from"),
    repo: str = Query("seeker71/Coherence-Network"),
    api_base: str = Query(
        "",
        description="Optional absolute API base URL (if omitted, response uses only relative paths).",
    ),
    web_base: str = Query(
        "",
        description="Optional absolute web base URL (if omitted, response uses only relative paths).",
    ),
    timeout: float = Query(10.0, ge=1.0, le=60.0),
) -> dict:
    return await asyncio.to_thread(
        gates.evaluate_commit_traceability_report,
        repository=repo,
        sha=sha,
        api_base=api_base,
        web_base=web_base,
        timeout=timeout,
        github_token=_github_token(),
    )
