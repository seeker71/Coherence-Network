"""Data retention management API routes.

Endpoints:
  GET  /api/data-retention/policy         -- current policy configuration
  GET  /api/data-retention/status         -- row counts, backup sizes, last run
  POST /api/data-retention/run            -- trigger a retention pass
  GET  /api/data-retention/summaries/daily -- daily runtime event aggregates
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import data_retention_service

router = APIRouter()


@router.get("/data-retention/policy", summary="Return the active tiered retention policy")
async def get_retention_policy() -> dict:
    """Return the active tiered retention policy."""
    return data_retention_service.get_policy()


@router.get("/data-retention/status", summary="Return current row counts, backup sizes, and last-run metadata")
async def get_retention_status() -> dict:
    """Return current row counts, backup sizes, and last-run metadata."""
    return data_retention_service.get_status()


@router.post("/data-retention/run", summary="Execute a retention pass: summarize, export backup, then trim stale rows")
async def run_retention_pass(
    dry_run: bool = Query(False, description="Preview only -- do not delete or export"),
) -> dict:
    """Execute a retention pass: summarize, export backup, then trim stale rows."""
    return data_retention_service.run_retention_pass(dry_run=dry_run)


@router.get("/data-retention/summaries/daily", summary="Return pre-computed daily aggregate summaries for runtime_events")
async def get_daily_summaries(
    days_back: int = Query(
        7, ge=1, le=90, description="How many days of daily summaries to return"
    ),
) -> dict:
    """Return pre-computed daily aggregate summaries for runtime_events."""
    summaries = data_retention_service.build_daily_summaries(days_back=days_back)
    return {"days_back": days_back, "summaries": summaries}
