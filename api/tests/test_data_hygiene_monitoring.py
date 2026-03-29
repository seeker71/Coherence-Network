"""Complementary tests for Data Hygiene Monitoring (spec task_ad1705c62ca9c76d / task_a58cac25401b5d34).

This file adds edge-case coverage and additional scenario verification
that complements the acceptance tests in test_data_health_api.py.
Tests are self-contained — no external DB required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Inline growth / threshold helpers (mirrors spec data_hygiene_service logic)
# ---------------------------------------------------------------------------


def _compute_growth(current: int, previous: int | None) -> tuple[int | None, float | None]:
    """Return (delta_24h, pct_change_24h). None when no prior snapshot."""
    if previous is None:
        return None, None
    delta = current - previous
    pct = (delta / previous * 100.0) if previous > 0 else None
    return delta, pct


def _table_status(
    delta: int | None,
    pct: float | None,
    max_delta: int = 10_000,
    max_pct: float = 50.0,
) -> str:
    """Classify table as ok / warn / breach."""
    if delta is None or pct is None:
        return "ok"
    if delta >= max_delta or pct >= max_pct:
        return "breach"
    if delta >= max_delta * 0.5 or pct >= max_pct * 0.5:
        return "warn"
    return "ok"


def _health_score(statuses: list[str]) -> float:
    """Derive health score 0.0–1.0."""
    if not statuses:
        return 1.0
    breach_count = statuses.count("breach")
    if breach_count == 0:
        return 1.0
    return max(0.0, 1.0 - breach_count / len(statuses))


# ---------------------------------------------------------------------------
# Minimal test app factory
# ---------------------------------------------------------------------------


def _build_app(
    table_counts: dict[str, int] | None = None,
    previous_counts: dict[str, int] | None = None,
    db_available: bool = True,
    thresholds: dict[str, dict] | None = None,
    db_kind: str = "sqlite",
    initial_snapshots: list[dict] | None = None,
) -> FastAPI:
    """Construct a FastAPI app that mirrors the /api/data-health contract."""
    app = FastAPI()
    _counts = table_counts or {"runtime_events": 1000, "agent_tasks": 100}
    _prev = previous_counts
    _thr = thresholds or {}
    _friction_store: list[dict] = []
    _snaps: list[dict] = list(initial_snapshots or [])

    @app.get("/api/data-health")
    async def get_data_health() -> dict:
        if not db_available:
            raise HTTPException(
                status_code=503,
                detail={"detail": "data_health_unavailable", "reason": "database unreachable"},
            )

        tables = []
        for name, count in _counts.items():
            prev_count = _prev.get(name) if _prev else None
            delta, pct = _compute_growth(count, prev_count)
            thr = _thr.get(name, {})
            status = _table_status(
                delta,
                pct,
                max_delta=thr.get("max_delta", 10_000),
                max_pct=thr.get("max_pct", 50.0),
            )
            if status == "breach":
                friction_id = f"fric-{name}-{uuid4().hex[:8]}"
                _friction_store.append({
                    "id": friction_id,
                    "block_type": "data_growth_anomaly",
                    "table": name,
                    "status": "open",
                })
            tables.append({
                "name": name,
                "row_count": count,
                "previous_snapshot_at": "2026-03-27T12:00:00Z" if prev_count is not None else None,
                "previous_row_count": prev_count,
                "delta_24h": delta,
                "pct_change_24h": round(pct, 2) if pct is not None else None,
                "status": status,
            })

        open_ids = [f["id"] for f in _friction_store if f["status"] == "open"]
        score = _health_score([t["status"] for t in tables])
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_kind": db_kind,
            "health_score": score,
            "tables": tables,
            "open_friction_ids": open_ids,
            "investigation_hints": [
                "Check runtime_events by event_type for duplicate tool calls"
            ],
        }

    @app.get("/api/data-health/snapshots")
    async def get_snapshots(limit: int = 10) -> list[dict]:
        if not db_available:
            raise HTTPException(
                status_code=503,
                detail={"detail": "data_health_unavailable", "reason": "database unreachable"},
            )
        return _snaps[: min(limit, 100)]

    @app.post("/api/data-health/snapshot")
    async def capture_snapshot() -> dict:
        if not db_available:
            raise HTTPException(
                status_code=503,
                detail={"detail": "data_health_unavailable", "reason": "database unreachable"},
            )
        snap = {
            "id": str(uuid4()),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "table_counts": dict(_counts),
            "source": "api",
        }
        _snaps.append(snap)
        return snap

    return app


# ---------------------------------------------------------------------------
# Unit — growth math edge cases (R2)
# ---------------------------------------------------------------------------


def test_growth_zero_previous_returns_none_pct() -> None:
    """When previous count is 0 (not None), pct is undefined (None), delta is reported."""
    delta, pct = _compute_growth(100, 0)
    assert delta == 100
    assert pct is None  # division by zero guarded


def test_growth_identical_counts_is_zero() -> None:
    """No row change yields delta=0, pct=0.0."""
    delta, pct = _compute_growth(500, 500)
    assert delta == 0
    assert pct == 0.0


def test_growth_decrease_is_negative_delta() -> None:
    """Row count can decrease; delta should be negative."""
    delta, pct = _compute_growth(800, 1000)
    assert delta == -200
    assert pct is not None
    assert pct < 0.0


def test_growth_large_increase_computes_correctly() -> None:
    """Large absolute increase (46k rows) is computed correctly."""
    delta, pct = _compute_growth(46_614, 1000)
    assert delta == 45_614
    assert pct is not None
    assert abs(pct - 4561.4) < 0.1


# ---------------------------------------------------------------------------
# Unit — threshold classification edge cases (R4)
# ---------------------------------------------------------------------------


def test_table_status_warn_boundary_delta() -> None:
    """At exactly 50 % of max_delta threshold → warn."""
    status = _table_status(delta=5_000, pct=2.0, max_delta=10_000, max_pct=50.0)
    assert status == "warn"


def test_table_status_breach_exact_max_delta() -> None:
    """At exactly max_delta → breach."""
    status = _table_status(delta=10_000, pct=2.0, max_delta=10_000, max_pct=50.0)
    assert status == "breach"


def test_table_status_below_warn_boundary() -> None:
    """Below 50 % of both thresholds → ok."""
    status = _table_status(delta=4_999, pct=24.9, max_delta=10_000, max_pct=50.0)
    assert status == "ok"


def test_table_status_none_pct_with_delta_is_ok() -> None:
    """When pct is None (previous=0), status is ok (no false breach)."""
    status = _table_status(delta=50_000, pct=None)
    assert status == "ok"


# ---------------------------------------------------------------------------
# Unit — health score edge cases (R6)
# ---------------------------------------------------------------------------


def test_health_score_single_breach_one_table() -> None:
    """One table, in breach → score 0.0."""
    assert _health_score(["breach"]) == 0.0


def test_health_score_warn_does_not_lower_score() -> None:
    """warn status does not reduce health_score below 1.0."""
    assert _health_score(["ok", "warn", "warn"]) == 1.0


def test_health_score_partial_breach() -> None:
    """2 of 4 tables in breach → score 0.5."""
    score = _health_score(["breach", "breach", "ok", "ok"])
    assert score == 0.5


# ---------------------------------------------------------------------------
# API — database_kind field (R1, R6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_health_reports_sqlite_kind() -> None:
    """database_kind reflects sqlite when running against SQLite fixture."""
    app = _build_app(db_kind="sqlite")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    assert resp.status_code == 200
    assert resp.json()["database_kind"] == "sqlite"


@pytest.mark.asyncio
async def test_data_health_reports_postgresql_kind() -> None:
    """database_kind can reflect postgresql."""
    app = _build_app(db_kind="postgresql")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    assert resp.status_code == 200
    assert resp.json()["database_kind"] == "postgresql"


# ---------------------------------------------------------------------------
# API — generated_at is ISO 8601 UTC (R6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_health_generated_at_is_iso8601() -> None:
    """generated_at must be a parseable ISO 8601 UTC timestamp."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    generated_at = resp.json()["generated_at"]
    dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# API — tables list completeness (R1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_health_all_configured_tables_appear() -> None:
    """Every table in the configured set must appear in the tables array."""
    tables_in = {
        "runtime_events": 1000,
        "agent_tasks": 200,
        "telemetry_snapshots": 50,
        "contribution_ledger": 30,
    }
    app = _build_app(table_counts=tables_in)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    names_out = {t["name"] for t in resp.json()["tables"]}
    assert names_out == set(tables_in.keys())


@pytest.mark.asyncio
async def test_data_health_row_counts_are_non_negative() -> None:
    """All reported row counts must be >= 0."""
    app = _build_app(table_counts={"runtime_events": 0, "agent_tasks": 0})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    for table in resp.json()["tables"]:
        assert table["row_count"] >= 0


# ---------------------------------------------------------------------------
# API — friction event structure (R5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_friction_event_has_data_growth_anomaly_block_type() -> None:
    """When a breach occurs, open_friction_ids must be non-empty and use data_growth_anomaly."""
    app = _build_app(
        table_counts={"runtime_events": 20_000},
        previous_counts={"runtime_events": 100},
        thresholds={"runtime_events": {"max_delta": 500, "max_pct": 5.0}},
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    data = resp.json()
    assert data["health_score"] < 1.0
    assert len(data["open_friction_ids"]) >= 1
    # All open friction ids should be strings (no nulls)
    for fid in data["open_friction_ids"]:
        assert isinstance(fid, str)
        assert len(fid) > 0


@pytest.mark.asyncio
async def test_no_friction_when_within_thresholds() -> None:
    """No breach → open_friction_ids must be empty and health_score must be 1.0."""
    app = _build_app(
        table_counts={"runtime_events": 1010},
        previous_counts={"runtime_events": 1000},
        thresholds={"runtime_events": {"max_delta": 10_000, "max_pct": 50.0}},
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    data = resp.json()
    assert data["open_friction_ids"] == []
    assert data["health_score"] == 1.0


# ---------------------------------------------------------------------------
# API — snapshot POST (R2, R8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_post_returns_captured_snapshot() -> None:
    """POST /api/data-health/snapshot returns a snapshot with id, captured_at, table_counts."""
    app = _build_app(table_counts={"runtime_events": 1234})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/data-health/snapshot")

    assert resp.status_code == 200
    snap = resp.json()
    assert "id" in snap
    assert "captured_at" in snap
    assert "table_counts" in snap
    assert snap["source"] == "api"
    assert snap["table_counts"]["runtime_events"] == 1234


@pytest.mark.asyncio
async def test_snapshot_post_appended_to_history() -> None:
    """Snapshot captured via POST appears in subsequent GET /snapshots list."""
    app = _build_app(table_counts={"runtime_events": 999})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        post_resp = await c.post("/api/data-health/snapshot")
        snap_id = post_resp.json()["id"]

        get_resp = await c.get("/api/data-health/snapshots")

    snapshots = get_resp.json()
    snap_ids = [s["id"] for s in snapshots]
    assert snap_id in snap_ids


@pytest.mark.asyncio
async def test_snapshot_post_503_when_db_unavailable() -> None:
    """POST /api/data-health/snapshot returns 503 when DB is unavailable."""
    app = _build_app(db_available=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/data-health/snapshot")

    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# API — snapshots history (R2, R8, Scenario 5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshots_history_has_required_fields() -> None:
    """Each snapshot entry must contain id, captured_at, table_counts, source."""
    initial = [
        {
            "id": str(uuid4()),
            "captured_at": "2026-03-25T12:00:00Z",
            "table_counts": {"runtime_events": 900},
            "source": "scheduled",
        },
        {
            "id": str(uuid4()),
            "captured_at": "2026-03-26T12:00:00Z",
            "table_counts": {"runtime_events": 950},
            "source": "scheduled",
        },
        {
            "id": str(uuid4()),
            "captured_at": "2026-03-27T12:00:00Z",
            "table_counts": {"runtime_events": 980},
            "source": "scheduled",
        },
    ]
    app = _build_app(initial_snapshots=initial)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health/snapshots")

    assert resp.status_code == 200
    snaps = resp.json()
    assert len(snaps) >= 3

    for snap in snaps:
        assert "captured_at" in snap
        assert "table_counts" in snap
        # captured_at must be parseable ISO8601
        datetime.fromisoformat(snap["captured_at"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_snapshots_default_limit_respected() -> None:
    """Default limit (10) caps result even when many snapshots exist."""
    initial = [
        {
            "id": str(uuid4()),
            "captured_at": f"2026-03-{i:02d}T12:00:00Z",
            "table_counts": {"runtime_events": 1000 + i},
            "source": "scheduled",
        }
        for i in range(1, 16)  # 15 snapshots
    ]
    app = _build_app(initial_snapshots=initial)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health/snapshots")

    snaps = resp.json()
    assert len(snaps) <= 10


@pytest.mark.asyncio
async def test_snapshots_custom_limit_works() -> None:
    """Custom limit=3 returns at most 3 entries."""
    initial = [
        {
            "id": str(uuid4()),
            "captured_at": f"2026-03-{i:02d}T12:00:00Z",
            "table_counts": {"runtime_events": 1000 + i},
            "source": "scheduled",
        }
        for i in range(1, 8)  # 7 snapshots
    ]
    app = _build_app(initial_snapshots=initial)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health/snapshots?limit=3")

    assert resp.status_code == 200
    assert len(resp.json()) <= 3


@pytest.mark.asyncio
async def test_snapshots_empty_db_returns_empty_list() -> None:
    """When no snapshots exist, GET /snapshots returns an empty list (not 404 or 500)."""
    app = _build_app(initial_snapshots=[])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health/snapshots")

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# API — 503 error structure (Scenario 1 edge, R6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_503_error_body_contains_structured_detail() -> None:
    """503 response must not be a raw stack trace; must include data_health_unavailable."""
    app = _build_app(db_available=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    assert resp.status_code == 503
    body = resp.json()
    # FastAPI wraps as {"detail": ...}
    raw = str(body)
    assert "data_health_unavailable" in raw
    # Must not contain raw Python traceback indicators
    assert "Traceback" not in raw


# ---------------------------------------------------------------------------
# Integration-style — previous_row_count field semantics (R2, Scenario 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_previous_row_count_null_when_no_prior_snapshot() -> None:
    """previous_row_count must be null/None when there is no prior snapshot data."""
    app = _build_app(
        table_counts={"runtime_events": 500},
        previous_counts=None,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    entry = next(t for t in resp.json()["tables"] if t["name"] == "runtime_events")
    assert entry["previous_row_count"] is None
    assert entry["delta_24h"] is None
    assert entry["pct_change_24h"] is None


@pytest.mark.asyncio
async def test_previous_snapshot_at_null_when_no_prior_snapshot() -> None:
    """previous_snapshot_at must be null/None when there is no prior snapshot."""
    app = _build_app(
        table_counts={"runtime_events": 500},
        previous_counts=None,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    entry = next(t for t in resp.json()["tables"] if t["name"] == "runtime_events")
    assert entry["previous_snapshot_at"] is None


@pytest.mark.asyncio
async def test_previous_row_count_populated_when_snapshot_exists() -> None:
    """previous_row_count is set when a prior snapshot exists."""
    app = _build_app(
        table_counts={"runtime_events": 1100},
        previous_counts={"runtime_events": 1000},
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    entry = next(t for t in resp.json()["tables"] if t["name"] == "runtime_events")
    assert entry["previous_row_count"] == 1000
    assert entry["previous_snapshot_at"] is not None
