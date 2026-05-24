"""Instance pulse routes — each coherence instance exposes its own breath.

Federation honors sovereignty: every instance shows its breath to whoever
chooses to look, but no central monitor controls it. These endpoints are
windows, not hooks.

  - GET /api/pulse/self  — this instance's current breath state
  - GET /api/pulse/now   — alias matching the production witness URL shape
  - GET /api/pulse/peers — most-recent observed pulses from watched peers
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.services import instance_pulse_service

router = APIRouter()


def _pulse_payload() -> dict[str, Any]:
    if not instance_pulse_service.pulse_enabled():
        raise HTTPException(status_code=404, detail="instance pulse disabled")
    return instance_pulse_service.self_pulse()


@router.get("/pulse/self", summary="This instance's current breath state")
async def get_self_pulse() -> dict[str, Any]:
    """Return this instance's current breath: overall, organs, uptime."""
    return _pulse_payload()


@router.get("/pulse/now", summary="Alias for /pulse/self matching the witness URL shape")
async def get_pulse_now() -> dict[str, Any]:
    """Alias for /pulse/self.

    Mirrors the URL shape of the production witness at
    ``pulse.coherencycoin.com/pulse/now`` so any instance's API can answer
    the same question uniformly.
    """
    return _pulse_payload()


@router.get("/pulse/peers", summary="Most-recent observed pulses from watched peers")
async def get_peer_pulses() -> dict[str, Any]:
    """Return the most-recent pulse observed from each peer this instance watches.

    Each instance decides which peers to watch; no auto-discovery. This
    endpoint reads from local storage of past observations and never makes
    outbound calls.
    """
    if not instance_pulse_service.pulse_enabled():
        raise HTTPException(status_code=404, detail="instance pulse disabled")
    peers = instance_pulse_service.list_peer_pulses()
    return {
        "instance_id": instance_pulse_service.instance_id(),
        "peers": peers,
        "count": len(peers),
    }
