"""Health check endpoint (spec 001)."""

from datetime import datetime, timezone
import logging
import os
import ast
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_api_version() -> str:
    """Read API version from setup.py in the api directory."""
    try:
        # Resolve the path to setup.py relative to this file
        setup_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "setup.py")
        if os.path.exists(setup_path):
            with open(setup_path, "r") as f:
                tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "setup":
                        for keyword in node.keywords:
                            if keyword.arg == "version":
                                return str(ast.literal_eval(keyword.value))
    except Exception as e:
        logger.warning(f"Failed to load version from setup.py: {e}")
    
    return "1.0.0"  # Fallback


HEALTH_VERSION = _get_api_version()
def _iso_utc(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PingResponse(BaseModel):
    """GET /api/ping response."""

    model_config = ConfigDict(extra="forbid")
    pong: Annotated[bool, Field(description="Always true when API is reachable")]
    timestamp: Annotated[str, Field(description="ISO8601 UTC")]


@router.get("/version", summary="Return API version (lightweight, for dashboards)")
async def version():
    """Return API version (lightweight, for dashboards)."""
    return {"version": HEALTH_VERSION}


@router.get("/ping", response_model=PingResponse, summary="Lightweight liveness ping with current UTC timestamp")
async def ping():
    """Lightweight liveness ping with current UTC timestamp."""
    now = datetime.now(timezone.utc)
    return PingResponse(pong=True, timestamp=_iso_utc(now))
