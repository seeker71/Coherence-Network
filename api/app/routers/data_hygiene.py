"""API routes for database row-count hygiene and growth monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import data_hygiene_service

router = APIRouter()


@router.get("/data-hygiene/status")
async def get_data_hygiene_status(
    record: bool = Query(
        False,
        description="When true, persist one sample row per monitored table after counting.",
    ),
) -> dict:
    return data_hygiene_service.build_status_payload(record_sample=record)


@router.get("/data-hygiene/alerts")
async def get_data_hygiene_alerts(
    record: bool = Query(False, description="Same as /status record (optional sampling)."),
) -> dict:
    payload = data_hygiene_service.build_status_payload(record_sample=record)
    return {
        "captured_at": payload["captured_at"],
        "alerts": payload["alerts"],
        "meta": payload["meta"],
    }
