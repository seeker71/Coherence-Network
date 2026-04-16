"""Reward policy CRUD endpoints — community-configurable reward formulas.

Each community (workspace) configures its own reward formulas.
These endpoints let communities:
  - View active policies (with source: code_default vs community_override)
  - Override any formula parameter
  - Revert overrides back to defaults
  - Seed defaults into the database
  - Take a policy snapshot for audit/traceability
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import reward_policy_service

router = APIRouter()


# ── Request / Response models ────────────────────────────────────

class RewardPolicyUpdate(BaseModel):
    value: Any = Field(..., description="The policy value (any JSON-serializable type)")
    description: str | None = Field(None, description="Human-readable description")
    updated_by: str = Field("community", description="Who is making the change")


class RewardPolicyResponse(BaseModel):
    workspace_id: str
    key: str
    value: Any
    source: str | None = None
    version: int | None = None
    description: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None


# ── Endpoints ────────────────────────────────────────────────────

@router.get(
    "/reward-policies",
    response_model=list[RewardPolicyResponse],
    summary="List all reward policies for a community",
)
def list_policies(
    workspace_id: str = Query("coherence-network", description="Community/workspace ID"),
) -> list[dict[str, Any]]:
    """All reward policies for a workspace (community overrides merged with defaults)."""
    return reward_policy_service.list_policies(workspace_id)


@router.get(
    "/reward-policies/{key:path}",
    summary="Get a single reward policy",
)
def get_policy(
    key: str,
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Get a specific reward policy. Returns code default if no community override."""
    value = reward_policy_service.get_policy(key, workspace_id)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Policy '{key}' not found")

    all_policies = reward_policy_service.list_policies(workspace_id)
    for p in all_policies:
        if p["key"] == key:
            return p

    return {
        "workspace_id": workspace_id,
        "key": key,
        "value": value,
        "source": "code_default",
    }


@router.put(
    "/reward-policies/{key:path}",
    summary="Set a reward policy for this community",
)
def set_policy(
    key: str,
    body: RewardPolicyUpdate,
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Override a reward policy for this community.

    Any community member with appropriate role can adjust formulas.
    Changes take effect within 60 seconds.
    """
    try:
        result = reward_policy_service.set_policy(
            key,
            body.value,
            workspace_id=workspace_id,
            updated_by=body.updated_by,
            description=body.description,
        )
        return {
            "workspace_id": result["workspace_id"],
            "key": result["key"],
            "value": result["value"],
            "version": result["version"],
            "source": "community_override",
            "updated_by": result["updated_by"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/reward-policies/{key:path}",
    summary="Remove community override (reverts to default)",
)
def delete_policy(
    key: str,
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Remove a community override. The system default takes effect."""
    deleted = reward_policy_service.delete_policy(key, workspace_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No community override found for '{key}' in workspace '{workspace_id}'",
        )
    return {
        "key": key,
        "workspace_id": workspace_id,
        "deleted": True,
        "message": "Reverted to system default",
    }


@router.get(
    "/reward-policies-snapshot",
    summary="Frozen policy snapshot for audit/traceability",
)
def policy_snapshot(
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Frozen snapshot of all active policies. Embed in reward events for traceability."""
    return reward_policy_service.get_policy_snapshot(workspace_id)


@router.post(
    "/reward-policies/seed",
    summary="Seed system defaults into the database",
)
def seed_defaults(
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Write system defaults to DB for any keys not already present. Idempotent."""
    count = reward_policy_service.seed_defaults(workspace_id)
    return {
        "workspace_id": workspace_id,
        "seeded": count,
        "message": f"Seeded {count} default policies",
    }


@router.post(
    "/reward-policies/invalidate-cache",
    summary="Invalidate the policy cache",
)
def invalidate_cache(
    workspace_id: str = Query("coherence-network"),
) -> dict[str, Any]:
    """Force the in-memory policy cache to refresh on next access."""
    reward_policy_service.invalidate_cache(workspace_id)
    return {"message": "Cache invalidated"}
