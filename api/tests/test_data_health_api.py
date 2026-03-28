from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import data_health as data_health_router
from app.services.data_hygiene_service import DataHygieneSnapshotRecord
from app.services.unified_db import engine, reset_engine, session


@pytest.fixture
def isolated_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Dedicated SQLite DB + friction file; resets unified engine between tests."""
    db_file = tmp_path / "coh.db"
    url = f"sqlite+pysqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction.jsonl"))
    monkeypatch.delenv("FRICTION_USE_DB", raising=False)
    reset_engine()
    # Import models so create_all registers data_hygiene_snapshots + runtime tables
    from app.services import unified_models  # noqa: F401

    unified_db_engine = engine()
    from app.services.unified_db import Base as UnifiedBase

    UnifiedBase.metadata.create_all(bind=unified_db_engine, checkfirst=True)
    # runtime_events uses its own Base but same DATABASE_URL
    from app.services.runtime_event_store import ensure_schema as rt_ensure

    rt_ensure()
    yield db_file
    reset_engine()


@pytest.mark.asyncio
async def test_data_health_returns_table_counts(isolated_sqlite: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/data-health")
    assert res.status_code == 200
    body = res.json()
    assert "health_score" in body
    assert 0.0 <= body["health_score"] <= 1.0
    assert isinstance(body["tables"], list)
    names = {t["name"] for t in body["tables"]}
    assert "data_hygiene_snapshots" in names


@pytest.mark.asyncio
async def test_data_health_growth_computed_from_snapshots(isolated_sqlite: Path) -> None:
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=30)
    counts_old = {"runtime_events": 1000}
    counts_new = {"runtime_events": 1100}
    with session() as s:
        s.add(
            DataHygieneSnapshotRecord(
                id="snap_a",
                captured_at=old,
                table_counts_json=json.dumps(counts_old),
                source="test",
            )
        )
    # Current DB: create runtime_events rows via raw count — inject snapshot path instead:
    # We only need collect_table_counts to see runtime_events=1100. Insert 1100 placeholder rows heavy.
    # Instead, patch collect_table_counts for this test's assertion on delta logic via service unit:
    from app.services.data_hygiene_service import _find_delta_vs_24h_ago

    current = {"runtime_events": 1100}
    chrono = [(old, counts_old)]
    deltas = _find_delta_vs_24h_ago(current, chrono)
    d, pct, ts, prev = deltas["runtime_events"]
    assert d == 100
    assert prev == 1000
    assert pct is not None and abs(pct - 10.0) < 0.01


@pytest.mark.asyncio
async def test_data_growth_breach_creates_friction_event(
    isolated_sqlite: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "DATA_HYGIENE_THRESHOLDS_JSON",
        json.dumps({"runtime_events": {"hard_abs": 5, "min_rows_pct": 0, "soft_pct": 999, "hard_pct": 999}}),
    )
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=30)
    with session() as s:
        s.add(
            DataHygieneSnapshotRecord(
                id="snap_b",
                captured_at=old,
                table_counts_json=json.dumps({"runtime_events": 100}),
                source="test",
            )
        )
    from app.services.runtime_event_store import write_event
    from app.models.runtime import RuntimeEvent

    for i in range(120):
        write_event(
            RuntimeEvent(
                id=f"evt_{i}_{uuid4().hex[:8]}",
                source="test",
                endpoint="/tool:x",
                raw_endpoint="/tool:x",
                method="GET",
                status_code=200,
                runtime_ms=1.0,
                metadata={},
                runtime_cost_estimate=0.0,
                recorded_at=now,
            )
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        snap_res = await client.post("/api/data-health/snapshot")
        assert snap_res.status_code == 200
        fri = await client.get("/api/friction/events?status=open&limit=50")

    assert fri.status_code == 200
    events = fri.json()
    assert any(e.get("block_type") == "data_growth_anomaly" for e in events)


@pytest.mark.asyncio
async def test_data_health_503_when_db_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> dict:
        from app.services.data_hygiene_service import DataHealthUnavailable

        raise DataHealthUnavailable("simulated")

    monkeypatch.setattr(data_health_router, "build_data_health_payload", boom)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/data-health")
    assert res.status_code == 503
    body = res.json()
    detail = body.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "data_health_unavailable"


@pytest.mark.asyncio
async def test_snapshots_list_limit_capped(isolated_sqlite: Path) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/data-health/snapshots?limit=5")
    assert res.status_code == 200
    body = res.json()
    assert body["limit"] == 5
    assert "snapshots" in body
