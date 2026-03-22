"""Pipeline status routes for the agent pipeline loop."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services import pipeline_service

router = APIRouter()


@router.get("/pipeline/status")
async def get_pipeline_status() -> JSONResponse:
    status = pipeline_service.get_status()
    if not status.get("running"):
        return JSONResponse(status_code=503, content=status)
    return JSONResponse(status_code=200, content=status)
