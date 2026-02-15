"""Release/public gate API routes for machine access."""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException, Query

from app.services import release_gate_service as gates

router = APIRouter()


@router.get(
    "/gates/pr-to-public",
    summary="Validate PR merge readiness",
    description="""
**Purpose**: Automated gate check for PR merge readiness, ensuring changes meet quality standards before merging to main.

**Idea**: `coherence-network-agent-pipeline` - Automated task orchestration with release gates
**Tests**: `api/tests/test_gates.py::test_gate_pr_to_public_endpoint_returns_report`

**Gate Checks**:
- PR exists and is open
- CI checks passing
- Required approvals met
- No merge conflicts
- Optional: wait for deployment to public (wait_public=true)

**Use Case**: Machines can query before merging to verify all quality gates pass, preventing broken releases.

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (if changing gate rationale)
2. **Spec**: Create/update `/specs/054-release-gates-api.md` (spec not yet created)
3. **Tests**: Update `/api/tests/test_gates.py` (add/modify tests)
4. **Implementation**: Update `/api/app/routers/gates.py` (this file)
5. **Validation**: Run `pytest api/tests/test_gates.py -v`
    """,
    responses={
        200: {
            "description": "Gate evaluation report",
            "content": {
                "application/json": {
                    "example": {
                        "result": "ready_for_merge",
                        "pr_gate": {
                            "ready_to_merge": True,
                            "checks_passed": True,
                            "approvals_met": True,
                            "conflicts": False
                        }
                    }
                }
            }
        },
        422: {"description": "Validation error (missing branch parameter)"}
    },
    openapi_extra={
        "x-idea-id": "coherence-network-agent-pipeline",
        "x-test-file": "api/tests/test_gates.py",
        "x-implementation-file": "api/app/routers/gates.py",
        "x-spec-needed": "specs/054-release-gates-api.md"
    }
)
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
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    return report


@router.get(
    "/gates/merged-contract",
    summary="Validate post-merge change contract",
    description="""
**Purpose**: Verify merged changes on main meet contributor acknowledgment requirements for fair value attribution.

**Idea**: `coherence-network-agent-pipeline` - Automated task orchestration with release gates
**Tests**: `api/tests/test_gates.py::test_gate_merged_contract_endpoint_returns_report`

**Contract Checks**:
- Commit exists on main branch
- Required approvals count met (min_approvals)
- Unique approvers count met (min_unique_approvers)
- Contributor attribution eligible
- Change lineage traceable

**Use Case**: Machines can validate merged changes meet quality standards before proceeding with deployment or value distribution.

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (if changing contract rationale)
2. **Spec**: Create/update `/specs/054-release-gates-api.md` (spec not yet created)
3. **Tests**: Update `/api/tests/test_gates.py` (add/modify tests)
4. **Implementation**: Update `/api/app/routers/gates.py` (this file)
5. **Validation**: Run `pytest api/tests/test_gates.py -v`
    """,
    responses={
        200: {
            "description": "Contract evaluation report",
            "content": {
                "application/json": {
                    "example": {
                        "result": "contract_passed",
                        "contributor_ack": {
                            "eligible": True,
                            "approvals": 2,
                            "unique_approvers": 2,
                            "requirements_met": True
                        }
                    }
                }
            }
        },
        422: {"description": "Validation error (missing sha parameter)"}
    },
    openapi_extra={
        "x-idea-id": "coherence-network-agent-pipeline",
        "x-test-file": "api/tests/test_gates.py",
        "x-implementation-file": "api/app/routers/gates.py",
        "x-spec-needed": "specs/054-release-gates-api.md"
    }
)
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
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    return report


@router.get(
    "/gates/main-head",
    summary="Get current main branch HEAD SHA",
    description="""
**Purpose**: Retrieve current HEAD commit SHA for main branch, enabling deployment tracking and contract validation.

**Idea**: `coherence-network-agent-pipeline` - Automated task orchestration with release gates
**Tests**: `api/tests/test_gates.py::test_gate_main_head_502_when_unavailable`

**Response**:
- repo: Repository name
- branch: Branch name (default: main)
- sha: Current HEAD commit SHA

**Use Case**: Machines can query current main HEAD before validating contracts or initiating deployments.

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (if changing rationale)
2. **Spec**: Create/update `/specs/054-release-gates-api.md` (spec not yet created)
3. **Tests**: Update `/api/tests/test_gates.py` (add/modify tests)
4. **Implementation**: Update `/api/app/routers/gates.py` (this file)
5. **Validation**: Run `pytest api/tests/test_gates.py -v`
    """,
    responses={
        200: {
            "description": "Branch HEAD SHA",
            "content": {
                "application/json": {
                    "example": {
                        "repo": "seeker71/Coherence-Network",
                        "branch": "main",
                        "sha": "e4897da1234567890abcdef"
                    }
                }
            }
        },
        502: {"description": "Could not resolve branch head SHA"}
    },
    openapi_extra={
        "x-idea-id": "coherence-network-agent-pipeline",
        "x-test-file": "api/tests/test_gates.py",
        "x-implementation-file": "api/app/routers/gates.py",
        "x-spec-needed": "specs/054-release-gates-api.md"
    }
)
async def gates_main_head(
    repo: str = Query("seeker71/Coherence-Network"),
    branch: str = Query("main"),
) -> dict:
    sha = gates.get_branch_head_sha(repo, branch, github_token=os.getenv("GITHUB_TOKEN"))
    if not sha:
        raise HTTPException(status_code=502, detail="Could not resolve branch head SHA")
    return {"repo": repo, "branch": branch, "sha": sha}


@router.get(
    "/gates/main-contract",
    summary="Validate main branch contract compliance",
    description="""
**Purpose**: Verify current main branch HEAD meets change contract requirements, enabling safe deployment decisions.

**Idea**: `coherence-network-agent-pipeline` - Automated task orchestration with release gates
**Tests**: Related to `test_gate_merged_contract_endpoint_returns_report` in `api/tests/test_gates.py`

**Contract Checks**:
- Retrieves current main HEAD SHA
- Validates HEAD commit approvals (min_approvals)
- Validates unique approvers count (min_unique_approvers)
- Checks contributor attribution eligibility
- Verifies change lineage traceability

**Use Case**: Machines can validate main branch quality before deployment without knowing specific SHA upfront.

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (if changing contract rationale)
2. **Spec**: Create/update `/specs/054-release-gates-api.md` (spec not yet created)
3. **Tests**: Update `/api/tests/test_gates.py` (add/modify tests)
4. **Implementation**: Update `/api/app/routers/gates.py` (this file)
5. **Validation**: Run `pytest api/tests/test_gates.py -v`
    """,
    responses={
        200: {
            "description": "Main contract evaluation report",
            "content": {
                "application/json": {
                    "example": {
                        "branch": "main",
                        "result": "contract_passed",
                        "contributor_ack": {
                            "eligible": True,
                            "approvals": 2,
                            "unique_approvers": 2,
                            "requirements_met": True
                        }
                    }
                }
            }
        },
        502: {"description": "Could not resolve branch head SHA"}
    },
    openapi_extra={
        "x-idea-id": "coherence-network-agent-pipeline",
        "x-test-file": "api/tests/test_gates.py",
        "x-implementation-file": "api/app/routers/gates.py",
        "x-spec-needed": "specs/054-release-gates-api.md"
    }
)
async def gates_main_contract(
    repo: str = Query("seeker71/Coherence-Network"),
    branch: str = Query("main"),
    min_approvals: int = Query(1, ge=0, le=10),
    min_unique_approvers: int = Query(1, ge=0, le=10),
    timeout_seconds: int = Query(1200, ge=10, le=7200),
    poll_seconds: int = Query(30, ge=1, le=300),
) -> dict:
    sha = gates.get_branch_head_sha(repo, branch, github_token=os.getenv("GITHUB_TOKEN"))
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
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    report["branch"] = branch
    return report


@router.get(
    "/gates/public-deploy-contract",
    summary="Validate public deployment readiness",
    description="""
**Purpose**: Verify deployed API and web services are healthy and match main branch contract, ensuring safe public releases.

**Spec**: Related to [014-deploy-readiness.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/014-deploy-readiness.md)
**Idea**: `coherence-network-agent-pipeline` - Automated task orchestration with release gates
**Tests**: `api/tests/test_gates.py::test_gate_public_deploy_contract_endpoint_returns_report`

**Deployment Checks**:
- API health endpoint responding (api_base/health)
- Web root responding (web_base/)
- Services match main branch SHA
- No failing health checks
- CORS configured correctly

**Production Environments**:
- API: https://coherence-network-production.up.railway.app (Railway)
- Web: https://coherence-network.vercel.app (Vercel)

**Use Case**: Machines can verify deployment success before marking releases as complete or notifying stakeholders.

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (if changing deployment rationale)
2. **Spec**: Update `/specs/014-deploy-readiness.md` or create `/specs/054-release-gates-api.md`
3. **Tests**: Update `/api/tests/test_gates.py` (add/modify tests)
4. **Implementation**: Update `/api/app/routers/gates.py` (this file)
5. **Validation**: Run `pytest api/tests/test_gates.py -v`
    """,
    responses={
        200: {
            "description": "Public deployment contract report",
            "content": {
                "application/json": {
                    "example": {
                        "result": "public_contract_passed",
                        "failing_checks": [],
                        "api_health": {"status": "ok", "version": "1.0.0"},
                        "web_health": {"status": "ok"},
                        "deployment_match": True
                    }
                }
            }
        }
    },
    openapi_extra={
        "x-spec-file": "specs/014-deploy-readiness.md",
        "x-idea-id": "coherence-network-agent-pipeline",
        "x-test-file": "api/tests/test_gates.py",
        "x-implementation-file": "api/app/routers/gates.py",
        "x-production-api": "https://coherence-network-production.up.railway.app",
        "x-production-web": "https://coherence-network.vercel.app"
    }
)
async def gates_public_deploy_contract(
    repo: str = Query("seeker71/Coherence-Network"),
    branch: str = Query("main"),
    api_base: str = Query("https://coherence-network-production.up.railway.app"),
    web_base: str = Query("https://coherence-network.vercel.app"),
    timeout: float = Query(8.0, ge=1.0, le=60.0),
) -> dict:
    return await asyncio.to_thread(
        gates.evaluate_public_deploy_contract_report,
        repository=repo,
        branch=branch,
        api_base=api_base,
        web_base=web_base,
        timeout=timeout,
        github_token=os.getenv("GITHUB_TOKEN"),
    )
