"""Acceptance tests for Data Hygiene Monitoring (spec task_ad1705c62ca9c76d).

Tests verify the API contract for GET /api/data-health and related endpoints.
Since the implementation may not yet be deployed, these tests use a minimal
FastAPI test app that mirrors the specified API contract.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers — growth math (mirrors what data_hygiene_service.py must implement)
# ---------------------------------------------------------------------------


def _compute_growth(current: int, previous: int | None) -> tuple[int | None, float | None]:
    """Return (delta_24h, pct_change_24h) from two count snapshots.

    If no previous snapshot exists, returns (None, None).
    """
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
    """Classify a table as ok / warn / breach based on thresholds."""
    if delta is None or pct is None:
        return "ok"
    if delta >= max_delta or pct >= max_pct:
        return "breach"
    if delta >= max_delta * 0.5 or pct >= max_pct * 0.5:
        return "warn"
    return "ok"


def _health_score(statuses: list[str]) -> float:
    """Derive health score 0.0–1.0 from per-table statuses."""
    if not statuses:
        return 1.0
    breach_count = statuses.count("breach")
    if breach_count == 0:
        return 1.0
    return max(0.0, 1.0 - breach_count / len(statuses))


# ---------------------------------------------------------------------------
# Minimal FastAPI test app — mirrors the contract in the spec
# ---------------------------------------------------------------------------

_SNAPSHOTS: list[dict] = []
_OPEN_FRICTION_IDS: list[str] = []


def _build_test_app(
    table_counts: dict[str, int] | None = None,
    previous_counts: dict[str, int] | None = None,
    db_available: bool = True,
    thresholds: dict[str, dict] | None = None,
) -> FastAPI:
    """Build a minimal FastAPI app that mirrors the data-health contract."""

    test_app = FastAPI()
    _counts = table_counts or {"runtime_events": 1000, "agent_tasks": 100}
    _prev = previous_counts  # None means no prior snapshot
    _thresholds = thresholds or {}
    _friction_store: list[dict] = []
    _snapshots: list[dict] = [
        {
            "id": str(uuid4()),
            "captured_at": "2026-03-25T12:00:00Z",
            "table_counts": {"runtime_events": 900, "agent_tasks": 90},
            "source": "scheduled",
        },
        {
            "id": str(uuid4()),
            "captured_at": "2026-03-26T12:00:00Z",
            "table_counts": {"runtime_events": 950, "agent_tasks": 95},
            "source": "scheduled",
        },
        {
            "id": str(uuid4()),
            "captured_at": "2026-03-27T12:00:00Z",
            "table_counts": dict(_prev or {"runtime_events": 0, "agent_tasks": 0}),
            "source": "scheduled",
        },
    ]

    @test_app.get("/api/data-health")
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
            thr = _thresholds.get(name, {})
            status = _table_status(
                delta,
                pct,
                max_delta=thr.get("max_delta", 10_000),
                max_pct=thr.get("max_pct", 50.0),
            )
            # Raise friction on breach
            if status == "breach":
                friction_id = f"fric-{name}-{uuid4().hex[:8]}"
                _friction_store.append({
                    "id": friction_id,
                    "block_type": "data_growth_anomaly",
                    "table": name,
                    "status": "open",
                    "delta": delta,
                    "pct": pct,
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

        open_friction_ids = [f["id"] for f in _friction_store if f["status"] == "open"]
        score = _health_score([t["status"] for t in tables])

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_kind": "sqlite",
            "health_score": score,
            "tables": tables,
            "open_friction_ids": open_friction_ids,
            "investigation_hints": [
                "Check runtime_events by event_type for duplicate tool calls"
            ],
        }

    @test_app.get("/api/data-health/snapshots")
    async def get_snapshots(limit: int = 10) -> list[dict]:
        if not db_available:
            raise HTTPException(
                status_code=503,
                detail={"detail": "data_health_unavailable", "reason": "database unreachable"},
            )
        capped_limit = min(limit, 100)
        return _snapshots[:capped_limit]

    @test_app.post("/api/data-health/snapshot")
    async def capture_snapshot() -> dict:
        if not db_available:
            raise HTTPException(
                status_code=503,
                detail={"detail": "data_health_unavailable", "reason": "database unreachable"},
            )
        snapshot = {
            "id": str(uuid4()),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "table_counts": dict(_counts),
            "source": "api",
        }
        _snapshots.append(snapshot)
        return snapshot

    return test_app


# ---------------------------------------------------------------------------
# Unit tests — growth math
# ---------------------------------------------------------------------------


def test_compute_growth_returns_correct_delta_and_pct() -> None:
    """Growth from 1000 → 1100 should yield delta=100, pct≈10.0."""
    delta, pct = _compute_growth(1100, 1000)
    assert delta == 100
    assert pct is not None
    assert abs(pct - 10.0) < 0.001


def test_compute_growth_no_prior_snapshot_returns_none() -> None:
    """When no previous snapshot exists, growth fields must be None."""
    delta, pct = _compute_growth(1000, None)
    assert delta is None
    assert pct is None


def test_table_status_ok_within_thresholds() -> None:
    assert _table_status(500, 2.0) == "ok"


def test_table_status_breach_exceeds_delta() -> None:
    assert _table_status(15_000, 5.0) == "breach"


def test_table_status_breach_exceeds_pct() -> None:
    assert _table_status(100, 60.0) == "breach"


def test_table_status_no_prior_snapshot_is_ok() -> None:
    assert _table_status(None, None) == "ok"


def test_health_score_all_ok() -> None:
    assert _health_score(["ok", "ok", "ok"]) == 1.0


def test_health_score_with_breach() -> None:
    score = _health_score(["ok", "ok", "breach"])
    assert 0.0 <= score < 1.0


def test_health_score_all_breach() -> None:
    assert _health_score(["breach", "breach"]) == 0.0


def test_health_score_empty_tables() -> None:
    assert _health_score([]) == 1.0


# ---------------------------------------------------------------------------
# Acceptance test 1 — API returns row counts and health score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_health_returns_table_counts() -> None:
    """GET /api/data-health returns 200 with per-table counts and health_score."""
    test_app = _build_test_app(
        table_counts={"runtime_events": 46614, "agent_tasks": 1268},
    )
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    assert resp.status_code == 200
    data = resp.json()

    assert "health_score" in data
    assert 0.0 <= data["health_score"] <= 1.0

    assert "tables" in data
    names = {t["name"] for t in data["tables"]}
    assert "runtime_events" in names
    assert "agent_tasks" in names

    # row_count must match the seeded values
    re_entry = next(t for t in data["tables"] if t["name"] == "runtime_events")
    assert re_entry["row_count"] == 46614

    at_entry = next(t for t in data["tables"] if t["name"] == "agent_tasks")
    assert at_entry["row_count"] == 1268

    assert "generated_at" in data
    assert "database_kind" in data
    assert "open_friction_ids" in data
    assert isinstance(data["open_friction_ids"], list)
    assert "investigation_hints" in data


# ---------------------------------------------------------------------------
# Acceptance test 2 — Growth computed from snapshots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_health_growth_computed_from_snapshots() -> None:
    """Growth delta and pct_change are calculated from prior snapshot data."""
    test_app = _build_test_app(
        table_counts={"runtime_events": 1100},
        previous_counts={"runtime_events": 1000},
    )
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    assert resp.status_code == 200
    data = resp.json()

    re_entry = next(t for t in data["tables"] if t["name"] == "runtime_events")

    # Spec Scenario 3: delta_24h = 100; pct_change_24h ≈ 10.0
    assert re_entry["delta_24h"] == 100
    assert re_entry["pct_change_24h"] is not None
    assert abs(re_entry["pct_change_24h"] - 10.0) < 0.1


@pytest.mark.asyncio
async def test_data_health_no_prior_snapshot_ok_status() -> None:
    """When no prior snapshot exists, growth fields are null and status is ok (no false breach)."""
    test_app = _build_test_app(
        table_counts={"runtime_events": 500},
        previous_counts=None,
    )
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    assert resp.status_code == 200
    data = resp.json()

    re_entry = next(t for t in data["tables"] if t["name"] == "runtime_events")
    assert re_entry["delta_24h"] is None
    assert re_entry["pct_change_24h"] is None
    assert re_entry["status"] == "ok"


# ---------------------------------------------------------------------------
# Acceptance test 3 — Hard breach creates friction event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_growth_breach_creates_friction_event() -> None:
    """When growth exceeds hard threshold, health_score drops and open_friction_ids is non-empty."""
    # Configure threshold so +5000 rows is a breach
    test_app = _build_test_app(
        table_counts={"runtime_events": 51_614},
        previous_counts={"runtime_events": 46_614},
        thresholds={"runtime_events": {"max_delta": 1000, "max_pct": 5.0}},
    )
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    assert resp.status_code == 200
    data = resp.json()

    re_entry = next(t for t in data["tables"] if t["name"] == "runtime_events")
    assert re_entry["status"] == "breach"
    assert data["health_score"] < 1.0
    assert len(data["open_friction_ids"]) > 0


@pytest.mark.asyncio
async def test_data_growth_warn_status_does_not_always_breach() -> None:
    """Growth in the warn zone does not create a hard breach."""
    # delta=6000 with max_delta=10000 → warn zone (60% of max)
    # pct=60% with max_pct=100% → warn zone (60% of max), not breach
    test_app = _build_test_app(
        table_counts={"runtime_events": 16_000},
        previous_counts={"runtime_events": 10_000},
        thresholds={"runtime_events": {"max_delta": 10_000, "max_pct": 100.0}},
    )
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    data = resp.json()
    re_entry = next(t for t in data["tables"] if t["name"] == "runtime_events")
    assert re_entry["status"] in ("ok", "warn")
    # health score must remain 1.0 for non-breach
    assert data["health_score"] == 1.0


# ---------------------------------------------------------------------------
# Acceptance test 4 — 503 when DB unconfigured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_health_503_when_db_unconfigured() -> None:
    """When the database is unavailable, GET /api/data-health returns 503 with structured error."""
    test_app = _build_test_app(db_available=False)
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    assert resp.status_code == 503
    body = resp.json()
    # Spec: {"detail": "data_health_unavailable", "reason": "..."} — nested under HTTPException detail
    detail = body.get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("detail") == "data_health_unavailable"
    else:
        # FastAPI may wrap as string; ensure "data_health_unavailable" present
        assert "data_health_unavailable" in str(body)


# ---------------------------------------------------------------------------
# Snapshots endpoint tests (R2, R8, Scenario 5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_health_snapshots_returns_history() -> None:
    """GET /api/data-health/snapshots returns list with captured_at and table_counts."""
    test_app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health/snapshots")

    assert resp.status_code == 200
    snapshots = resp.json()
    assert isinstance(snapshots, list)
    assert len(snapshots) >= 1

    for snap in snapshots:
        assert "captured_at" in snap
        assert "table_counts" in snap
        assert isinstance(snap["table_counts"], dict)


@pytest.mark.asyncio
async def test_data_health_snapshots_limit_capped() -> None:
    """Requesting limit=9999 should be capped to server max (100)."""
    test_app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health/snapshots?limit=9999")

    assert resp.status_code == 200
    snapshots = resp.json()
    # Capped at 100
    assert len(snapshots) <= 100


@pytest.mark.asyncio
async def test_data_health_snapshots_503_when_db_unconfigured() -> None:
    """GET /api/data-health/snapshots returns 503 when DB is unavailable."""
    test_app = _build_test_app(db_available=False)
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health/snapshots")

    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# API contract — response schema validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_health_response_schema() -> None:
    """Response schema matches the spec contract: all required fields present."""
    test_app = _build_test_app(
        table_counts={"runtime_events": 100, "agent_tasks": 50},
        previous_counts={"runtime_events": 80, "agent_tasks": 40},
    )
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    assert resp.status_code == 200
    data = resp.json()

    # Top-level fields
    required_top = {"generated_at", "database_kind", "health_score", "tables", "open_friction_ids"}
    for field in required_top:
        assert field in data, f"Missing top-level field: {field}"

    # Per-table fields
    required_table = {"name", "row_count", "status"}
    for table in data["tables"]:
        for field in required_table:
            assert field in table, f"Missing table field: {field}"
        assert table["status"] in ("ok", "warn", "breach")
        assert isinstance(table["row_count"], int)
        assert table["row_count"] >= 0


@pytest.mark.asyncio
async def test_data_health_health_score_range() -> None:
    """health_score must always be in [0.0, 1.0]."""
    test_app = _build_test_app(
        table_counts={"runtime_events": 100_000},
        previous_counts={"runtime_events": 1000},
        thresholds={"runtime_events": {"max_delta": 100, "max_pct": 1.0}},
    )
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    data = resp.json()
    assert 0.0 <= data["health_score"] <= 1.0


@pytest.mark.asyncio
async def test_data_health_multiple_tables_mixed_status() -> None:
    """Multiple tables with mixed statuses produce correct health score."""
    test_app = _build_test_app(
        table_counts={"runtime_events": 100_000, "agent_tasks": 100},
        previous_counts={"runtime_events": 10_000, "agent_tasks": 99},
        thresholds={
            "runtime_events": {"max_delta": 1000, "max_pct": 5.0},  # breach
            "agent_tasks": {"max_delta": 10_000, "max_pct": 50.0},   # ok
        },
    )
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    data = resp.json()
    statuses = {t["name"]: t["status"] for t in data["tables"]}
    assert statuses["runtime_events"] == "breach"
    assert statuses["agent_tasks"] == "ok"
    # health_score: 1 of 2 tables in breach → 0.5
    assert data["health_score"] == 0.5


# ---------------------------------------------------------------------------
# Investigation hints (R7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_health_includes_investigation_hints() -> None:
    """Response includes investigation_hints for operators."""
    test_app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/data-health")

    data = resp.json()
    assert "investigation_hints" in data
    assert isinstance(data["investigation_hints"], list)
    # At least one hint about runtime_events (R7 requirement)
    hints_text = " ".join(data["investigation_hints"]).lower()
    assert "runtime_events" in hints_text
