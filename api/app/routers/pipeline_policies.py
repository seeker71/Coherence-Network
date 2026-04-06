"""Pipeline policy CRUD endpoints.

Allows runtime inspection and modification of pipeline behavior:
  - phase chain (phase ordering)
  - retry limits
  - failure classification patterns
  - output quality thresholds
  - pass-gate tokens
  - no-retry error categories

All changes take effect within 60 seconds (cache TTL).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import pipeline_policy_service

router = APIRouter()


# ── Request / Response models ────────────────────────────────────

class PolicyUpdate(BaseModel):
    value: Any = Field(..., description="The policy value (any JSON-serializable type)")
    description: str | None = Field(None, description="Optional human-readable description")
    updated_by: str = Field("api", description="Who is making the change")


class PolicyResponse(BaseModel):
    key: str
    value: Any
    source: str | None = None
    description: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None


# ── Endpoints ────────────────────────────────────────────────────

@router.get(
    "/pipeline/policies",
    response_model=list[PolicyResponse],
    summary="List all pipeline policies",
    tags=["pipeline"],
)
def list_policies() -> list[dict[str, Any]]:
    """List all pipeline policies (DB overrides merged with code defaults)."""
    return pipeline_policy_service.list_policies()


@router.get(
    "/pipeline/policies/{key}",
    response_model=PolicyResponse,
    summary="Get a single pipeline policy",
    tags=["pipeline"],
)
def get_policy(key: str) -> dict[str, Any]:
    """Get a pipeline policy by key. Returns code default if no DB override exists."""
    value = pipeline_policy_service.get_policy(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Policy '{key}' not found")
    # Determine source
    all_policies = pipeline_policy_service.list_policies()
    for p in all_policies:
        if p["key"] == key:
            return p
    return {"key": key, "value": value, "source": "code_default"}


@router.put(
    "/pipeline/policies/{key}",
    response_model=PolicyResponse,
    summary="Create or update a pipeline policy",
    tags=["pipeline"],
)
def set_policy(key: str, body: PolicyUpdate) -> dict[str, Any]:
    """Set a pipeline policy value. Creates if new, updates if existing."""
    try:
        result = pipeline_policy_service.set_policy(
            key,
            body.value,
            updated_by=body.updated_by,
            description=body.description,
        )
        return {"key": result["key"], "value": result["value"], "source": "database", "updated_by": result["updated_by"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/pipeline/policies/{key}",
    summary="Delete a pipeline policy (reverts to code default)",
    tags=["pipeline"],
)
def delete_policy(key: str) -> dict[str, Any]:
    """Delete a DB-backed policy. The code default will take effect."""
    deleted = pipeline_policy_service.delete_policy(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Policy '{key}' not found in database")
    return {"key": key, "deleted": True, "message": "Reverted to code default"}


@router.post(
    "/pipeline/policies/seed",
    summary="Seed code defaults into DB",
    tags=["pipeline"],
)
def seed_defaults() -> dict[str, Any]:
    """Write code defaults to DB for any keys not already present. Idempotent."""
    count = pipeline_policy_service.seed_defaults()
    return {"seeded": count, "message": f"Seeded {count} default policies"}


@router.post(
    "/pipeline/policies/invalidate-cache",
    summary="Invalidate the policy cache",
    tags=["pipeline"],
)
def invalidate_cache() -> dict[str, Any]:
    """Force the in-memory policy cache to refresh on next access."""
    pipeline_policy_service.invalidate_cache()
    return {"message": "Cache invalidated — next policy read will hit the database"}
