"""Debug mode toggle — runtime log-level control and diagnostic flags.

GET  /api/debug/status  — current debug state
PATCH /api/debug/status — toggle debug mode, set log level, manage trace targets
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/debug", tags=["debug"])
log = logging.getLogger("coherence.api")

# ── In-memory debug state (survives until process restart) ──────────

_debug_state: dict[str, Any] = {
    "enabled": False,
    "log_level": "INFO",
    "trace_endpoints": [],
    "verbose_sse": False,
}

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class DebugStatusResponse(BaseModel):
    enabled: bool
    log_level: str
    trace_endpoints: list[str]
    verbose_sse: bool


class DebugStatusUpdate(BaseModel):
    enabled: bool | None = None
    log_level: str | None = None
    trace_endpoint_add: str | None = None
    trace_endpoint_remove: str | None = None
    verbose_sse: bool | None = None


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("/status")
async def get_debug_status() -> DebugStatusResponse:
    """Return current debug configuration."""
    return DebugStatusResponse(**_debug_state)


@router.patch("/status")
async def update_debug_status(body: DebugStatusUpdate) -> DebugStatusResponse:
    """Update debug configuration at runtime.

    - ``enabled``: shortcut — true sets log_level=DEBUG, false sets INFO
    - ``log_level``: one of DEBUG, INFO, WARNING, ERROR, CRITICAL
    - ``trace_endpoint_add`` / ``trace_endpoint_remove``: manage traced endpoints
    - ``verbose_sse``: toggle verbose SSE event logging
    """
    if body.enabled is not None:
        _debug_state["enabled"] = body.enabled
        if body.log_level is None:
            _debug_state["log_level"] = "DEBUG" if body.enabled else "INFO"

    if body.log_level is not None:
        level = body.log_level.upper()
        if level not in _VALID_LEVELS:
            from fastapi import HTTPException
            raise HTTPException(400, f"Invalid log_level: {level}. Use one of {sorted(_VALID_LEVELS)}")
        _debug_state["log_level"] = level
        _debug_state["enabled"] = level == "DEBUG"

    # Apply log level change to the root coherence logger
    effective_level = getattr(logging, _debug_state["log_level"], logging.INFO)
    logging.getLogger("coherence").setLevel(effective_level)
    log.info("Debug log_level changed to %s", _debug_state["log_level"])

    if body.trace_endpoint_add:
        ep = body.trace_endpoint_add.strip()
        if ep and ep not in _debug_state["trace_endpoints"]:
            _debug_state["trace_endpoints"].append(ep)

    if body.trace_endpoint_remove:
        ep = body.trace_endpoint_remove.strip()
        _debug_state["trace_endpoints"] = [
            e for e in _debug_state["trace_endpoints"] if e != ep
        ]

    if body.verbose_sse is not None:
        _debug_state["verbose_sse"] = body.verbose_sse

    return DebugStatusResponse(**_debug_state)


def is_debug_enabled() -> bool:
    """Check if debug mode is currently enabled (usable by other services)."""
    return _debug_state.get("enabled", False)


def get_trace_endpoints() -> list[str]:
    """Return list of endpoints being traced."""
    return list(_debug_state.get("trace_endpoints", []))
