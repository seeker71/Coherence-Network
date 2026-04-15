"""FastAPI entry point for the Pulse Monitor.

Env vars:
  PULSE_API_BASE         base URL of the main API           (default https://api.coherencycoin.com)
  PULSE_WEB_BASE         base URL of the main web           (default https://coherencycoin.com)
  PULSE_DB_PATH          path to the SQLite file            (default ./data/pulse.db)
  PULSE_INTERVAL_SECONDS probe interval                     (default 30)
  PULSE_RETENTION_DAYS   raw-sample retention               (default 180)
  PULSE_CORS_ORIGINS     comma-separated list               (default *)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from pulse_app import __version__
from pulse_app.analysis import (
    duration_seconds_until_now,
    overall_status,
    rollup_daily,
    silence_duration,
    since_iso,
    status_from_last_sample,
    uptime_percent,
)
from pulse_app.models import (
    DailyBar,
    OngoingSilence,
    OrganHistory,
    OrganNow,
    PulseHistory,
    PulseNow,
    PulseSilences,
    Silence,
    WitnessHealth,
)
from pulse_app.organs import ORGANS, organs_by_name
from pulse_app.scheduler import PulseScheduler, SchedulerConfig
from pulse_app.storage import Store, iso_utc


logger = logging.getLogger("pulse")


# ----- config -------------------------------------------------------------

def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _cors_origins() -> list[str]:
    raw = os.environ.get("PULSE_CORS_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()]


API_BASE = _env("PULSE_API_BASE", "https://api.coherencycoin.com")
WEB_BASE = _env("PULSE_WEB_BASE", "https://coherencycoin.com")
DB_PATH = _env("PULSE_DB_PATH", "./data/pulse.db")
INTERVAL = _env_int("PULSE_INTERVAL_SECONDS", 30)
RETENTION = _env_int("PULSE_RETENTION_DAYS", 180)

STARTED_AT = datetime.now(timezone.utc)


# ----- lifespan -----------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info(
        "pulse witness starting api=%s web=%s db=%s interval=%ds retention=%dd",
        API_BASE, WEB_BASE, DB_PATH, INTERVAL, RETENTION,
    )

    store = Store(DB_PATH)
    scheduler = PulseScheduler(
        store=store,
        config=SchedulerConfig(
            api_base=API_BASE,
            web_base=WEB_BASE,
            interval_seconds=INTERVAL,
            retention_days=RETENTION,
        ),
    )
    scheduler.start()

    app.state.store = store
    app.state.scheduler = scheduler
    app.state.started_at = STARTED_AT

    try:
        yield
    finally:
        scheduler.shutdown()
        logger.info("pulse witness stopped")


# ----- app ----------------------------------------------------------------

app = FastAPI(
    title="Pulse Monitor",
    version=__version__,
    description="The witness that remembers the breath of Coherence Network.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


# ----- routes -------------------------------------------------------------

@app.get("/pulse/health", response_model=WitnessHealth)
async def witness_health() -> WitnessHealth:
    """Liveness ping for the witness itself (so it can be pinged externally)."""
    store: Store = app.state.store
    now = datetime.now(timezone.utc)
    return WitnessHealth(
        status="ok",
        version=__version__,
        started_at=iso_utc(app.state.started_at),
        uptime_seconds=int((now - app.state.started_at).total_seconds()),
        samples_total=store.count_samples(),
    )


@app.get("/pulse/now", response_model=PulseNow)
async def pulse_now() -> PulseNow:
    store: Store = app.state.store
    now = datetime.now(timezone.utc)

    organ_now: list[OrganNow] = []
    statuses: list[str] = []
    for organ in ORGANS:
        last = store.last_sample_for_organ(organ.name)
        status = status_from_last_sample(last)

        # Soften: if the last sample is older than 3× the interval, it's stale → unknown.
        if last is not None:
            age = (now - _parse_ts(last.ts)).total_seconds()
            if age > 3 * INTERVAL:
                status = "unknown"

        statuses.append(status)
        organ_now.append(
            OrganNow(
                name=organ.name,
                label=organ.label,
                description=organ.description,
                status=status,  # type: ignore[arg-type]
                latency_ms=last.latency_ms if last else None,
                last_sample_at=last.ts if last else None,
                detail=last.detail if last and not last.ok else None,
            )
        )

    ongoing_rows = store.ongoing_silences()
    ongoing = [
        OngoingSilence(
            id=row.id,
            organ=row.organ,
            started_at=row.started_at,
            severity=row.severity,  # type: ignore[arg-type]
            duration_seconds=duration_seconds_until_now(row.started_at, now),
        )
        for row in ongoing_rows
    ]

    return PulseNow(
        overall=overall_status(statuses),  # type: ignore[arg-type]
        checked_at=iso_utc(now),
        witness_started_at=iso_utc(app.state.started_at),
        organs=organ_now,
        ongoing_silences=ongoing,
    )


@app.get("/pulse/history", response_model=PulseHistory)
async def pulse_history(days: int = Query(90, ge=1, le=180)) -> PulseHistory:
    store: Store = app.state.store
    now = datetime.now(timezone.utc)
    since = since_iso(days, now)

    organ_histories: list[OrganHistory] = []
    for organ in ORGANS:
        samples = store.samples_for_organ_since(organ.name, since)
        buckets = rollup_daily(samples, days=days, now=now)
        organ_histories.append(
            OrganHistory(
                name=organ.name,
                label=organ.label,
                description=organ.description,
                uptime_pct=uptime_percent(samples),
                daily=[
                    DailyBar(
                        date=b.date,
                        status=b.status,  # type: ignore[arg-type]
                        samples=b.samples,
                        failures=b.failures,
                    )
                    for b in buckets
                ],
            )
        )

    return PulseHistory(
        days=days,
        generated_at=iso_utc(now),
        organs=organ_histories,
    )


@app.get("/pulse/silences", response_model=PulseSilences)
async def pulse_silences(days: int = Query(90, ge=1, le=180)) -> PulseSilences:
    store: Store = app.state.store
    now = datetime.now(timezone.utc)
    since = since_iso(days, now)
    rows = store.silences_since(since)
    by_name = organs_by_name()

    silences = [
        Silence(
            id=row.id,
            organ=row.organ,
            organ_label=by_name[row.organ].label if row.organ in by_name else row.organ,
            started_at=row.started_at,
            ended_at=row.ended_at,
            duration_seconds=silence_duration(row, now),
            severity=row.severity,  # type: ignore[arg-type]
            note=row.note,
        )
        for row in rows
    ]

    return PulseSilences(
        days=days,
        generated_at=iso_utc(now),
        silences=silences,
    )


# ----- helpers ------------------------------------------------------------

def _parse_ts(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "pulse",
        "version": __version__,
        "endpoints": [
            "/pulse/now",
            "/pulse/history",
            "/pulse/silences",
            "/pulse/health",
        ],
    }
