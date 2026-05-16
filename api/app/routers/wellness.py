"""Wellness — the body sensing itself, surfaced outward.

`make wellness` (scripts/wellness_check.py) names drift between maps and
body, source-symbol drift, locale parity, idea→spec→code→test chain
health, cell breath, contract patterns, witness budget. It was repo-only.
This endpoint runs the same sensing and surfaces it to visiting bodies.

Output is the script's gentle text, not JSON — its frequency is part of
what's being said. Cached briefly so repeated reads don't re-run the
checks unnecessarily.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "wellness_check.py"
_CACHE_TTL_SECONDS = 300  # 5 minutes — sensing is gentle, not real-time
_cache: dict[str, object] = {"output": None, "captured_at": 0.0, "duration_ms": 0}


class WellnessReading(BaseModel):
    output: str
    captured_at: float
    duration_ms: int
    cached: bool


async def _run_wellness() -> tuple[str, int]:
    if not _SCRIPT.exists():
        raise HTTPException(
            status_code=503,
            detail=f"wellness script not present at {_SCRIPT}",
        )
    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        "python3",
        str(_SCRIPT),
        cwd=str(_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60.0)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise HTTPException(
            status_code=504,
            detail="wellness sensing exceeded 60s budget",
        ) from exc
    duration_ms = int((time.monotonic() - started) * 1000)
    return stdout.decode("utf-8", errors="replace"), duration_ms


@router.get("/wellness", response_model=WellnessReading, tags=["wellness"])
async def get_wellness(refresh: bool = False) -> WellnessReading:
    """Return the body's most recent wellness reading.

    Cached for 5 minutes by default. Pass `?refresh=true` to force a
    fresh sensing.
    """
    now = time.time()
    captured_at = float(_cache.get("captured_at") or 0.0)
    cached_output = _cache.get("output")
    if (
        not refresh
        and cached_output
        and isinstance(cached_output, str)
        and (now - captured_at) < _CACHE_TTL_SECONDS
    ):
        return WellnessReading(
            output=cached_output,
            captured_at=captured_at,
            duration_ms=int(_cache.get("duration_ms") or 0),
            cached=True,
        )
    output, duration_ms = await _run_wellness()
    _cache["output"] = output
    _cache["captured_at"] = now
    _cache["duration_ms"] = duration_ms
    return WellnessReading(
        output=output,
        captured_at=now,
        duration_ms=duration_ms,
        cached=False,
    )
