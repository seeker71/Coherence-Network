"""Vedic (jyotisha) chat — a question about a birth-moment answered by the native vedic-chat.fk cell on fkwu; Python only carries the words."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.form_kernel_bridge import serve_text_via_kernel

router = APIRouter(prefix="/vedic", tags=["vedic"])

RECIPE = "endpoint_vedic_chat.fk"
BODY = "form/form/form-stdlib/vedic-chat.fk"

# The attested ground the door opens on: Urs, 6 October 1971, 09:15 CET = 08:15 UT,
# Luzern (receipts/2026-08-01-genekey-urs.md in the kernel; confirmed by Urs 2026-09-18).
URS_MOMENT = {"y": 1971, "m": 10, "d": 6, "uth": 8, "utm": 15, "lat": 47.05, "lon": 8.31}


class VedicAskResponse(BaseModel):
    question: str
    answer: str
    ground: str = Field(description="The birth-moment the answer is cast from (UT).")
    year: float = Field(description="The decimal year the dasha question is read at.")
    runtime: str = Field(description="Which kernel carrier served the body: fkwu.")
    body: str = Field(default=BODY, description="The Form cell that computed the answer.")
    lane: str = Field(
        default="direct-experience",
        description="The cast is empirical; the names are attested tradition; the meaning stays yours.",
    )


def _decimal_year_now() -> float:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return now.year + (now - start) / (end - start)


def _ground(y: int, m: int, d: int, uth: int, utm: int, lat: float, lon: float) -> str:
    moment = {"y": y, "m": m, "d": d, "uth": uth, "utm": utm, "lat": lat, "lon": lon}
    if moment == URS_MOMENT:
        return "Urs — 6 October 1971, 09:15 CET (08:15 UT), Luzern (47.05 N, 8.31 E)"
    return f"{y:04d}-{m:02d}-{d:02d} {uth:02d}:{utm:02d} UT at {lat} N, {lon} E"


@router.get(
    "/ask",
    response_model=VedicAskResponse,
    summary="Ask the native jyotisha chart a question in plain words",
    description=(
        "The body is form-stdlib/vedic-chat.fk on the c-bootstrapped fkwu runtime: the "
        "nine grahas in their rashis and nakshatras, the lagna, whole-sign bhavas, the "
        "Vimshottari dasha, and a word-keyed dispatcher. The default birth-moment is the "
        "one the body attests for Urs; pass y/m/d/uth/utm/lat/lon for another. Python "
        "carries the question in and the words out and computes nothing of the chart."
    ),
)
def vedic_ask(
    q: str = Query("help", min_length=1, max_length=400, description="The question, in plain words."),
    year: float | None = Query(None, ge=1800, le=2200, description="Decimal year for the dasha question; defaults to now."),
    y: int = Query(URS_MOMENT["y"], ge=1800, le=2100),
    m: int = Query(URS_MOMENT["m"], ge=1, le=12),
    d: int = Query(URS_MOMENT["d"], ge=1, le=31),
    uth: int = Query(URS_MOMENT["uth"], ge=0, le=23, description="Birth hour, UT."),
    utm: int = Query(URS_MOMENT["utm"], ge=0, le=59, description="Birth minute, UT."),
    lat: float = Query(URS_MOMENT["lat"], ge=-89.9, le=89.9, description="Latitude, north positive."),
    lon: float = Query(URS_MOMENT["lon"], ge=-180.0, le=180.0, description="Longitude, east positive."),
) -> VedicAskResponse:
    asked_year = float(year) if year is not None else _decimal_year_now()
    try:
        answer, runtime = serve_text_via_kernel(
            RECIPE,
            bindings={
                "question": q,
                "year": asked_year,
                "y": y, "m": m, "d": d, "uth": uth, "utm": utm,
                "lat": float(lat), "lon": float(lon),
            },
            timeout=20.0,
        )
    except RuntimeError as exc:
        # The body is the kernel; when it cannot answer, the carrier says so plainly.
        raise HTTPException(status_code=503, detail=f"the native jyotisha body is not reachable: {exc}") from exc
    return VedicAskResponse(
        question=q,
        answer=answer,
        ground=_ground(y, m, d, uth, utm, lat, lon),
        year=round(asked_year, 3),
        runtime=runtime,
    )
