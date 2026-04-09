"""Proprioception router — auto-sensing system state endpoints.

Provides read-only diagnostic scanning and optional apply mode
for updating spec values and idea stages based on what is real on disk.

Endpoints:
    GET  /api/proprioception        — read-only diagnostic scan
    POST /api/proprioception/apply  — scan + apply updates (requires API key)
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.services import proprioception_service

router = APIRouter()


@router.get(
    "/proprioception",
    summary="Auto-sense system state (read-only diagnostic)",
    tags=["proprioception"],
)
async def get_proprioception(
    workspace_id: str = "coherence-network",
) -> dict:
    """Run a proprioception scan and return a diagnostic report.

    This is a read-only operation. It inspects the spec registry, idea
    portfolio, and key API endpoints without modifying any data.
    """
    return proprioception_service.sense_system_state(workspace_id=workspace_id)


@router.post(
    "/proprioception/apply",
    summary="Sense + apply updates (requires API key)",
    tags=["proprioception"],
)
async def apply_proprioception(
    workspace_id: str = "coherence-network",
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict:
    """Run a proprioception scan and apply the suggested updates.

    Updates spec actual_value and advances idea stages based on what is
    real on disk. Requires a valid API key.
    """
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(status_code=401, detail="API key required")

    report = proprioception_service.sense_system_state(workspace_id=workspace_id)
    result = proprioception_service.apply_updates(report)
    return result
