"""Data hygiene router — /api/db-status and related endpoints.

Provides row count monitoring, growth anomaly detection, and data health reports.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Annotated, Any

from app.services import data_hygiene_service

router = APIRouter()


class TableStatusResponse(BaseModel):
    table: str
    row_count: int
    exists: bool
    error: str | None = None
    expected_max_daily: int | None = None
    alert: bool
    alert_reason: str | None = None


class DbStatusResponse(BaseModel):
    generated_at: Annotated[str, Field(description="ISO8601 UTC timestamp")]
    tables: list[TableStatusResponse]
    total_rows: int
    alert_count: int
    alerts: list[dict[str, Any]]


@router.get("/db-status", response_model=DbStatusResponse, tags=["data-hygiene"])
async def get_db_status():
    """Return row counts per monitored table with growth anomaly alerts.

    Used by `cc db-status` CLI command and the data health dashboard.
    Tables with row counts exceeding noise thresholds are flagged with alerts.
    """
    report = data_hygiene_service.get_db_status()
    return DbStatusResponse(
        generated_at=report.generated_at,
        tables=[
            TableStatusResponse(
                table=s.table,
                row_count=s.row_count,
                exists=s.exists,
                error=s.error,
                expected_max_daily=s.expected_max_daily,
                alert=s.alert,
                alert_reason=s.alert_reason,
            )
            for s in report.tables
        ],
        total_rows=report.total_rows,
        alert_count=report.alert_count,
        alerts=report.alerts,
    )


@router.get("/db-status/investigate/runtime-events", tags=["data-hygiene"])
async def investigate_runtime_events():
    """Deep-dive investigation of runtime_events table noise.

    Returns breakdown by event_type and age buckets to help identify
    the source of the 46k row accumulation in a young system.
    """
    return data_hygiene_service.get_runtime_events_investigation()
