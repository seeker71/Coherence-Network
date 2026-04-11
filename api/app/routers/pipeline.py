"""Pipeline status routes for the agent pipeline loop."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services import pipeline_service

router = APIRouter()


@router.get("/pipeline/status", summary="Get Pipeline Status")
async def get_pipeline_status() -> JSONResponse:
    status = pipeline_service.get_status()
    if not status.get("running"):
        return JSONResponse(status_code=503, content=status)
    return JSONResponse(status_code=200, content=status)


@router.get("/pipeline/summary", summary="Lightweight summary for the live dashboard — never returns 503")
async def get_pipeline_summary() -> JSONResponse:
    """Lightweight summary for the live dashboard — never returns 503."""
    status = pipeline_service.get_status()
    return JSONResponse(status_code=200, content=status)
