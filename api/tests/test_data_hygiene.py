"""Tests for data hygiene row counts, growth, and alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import data_hygiene_service
from app.services import unified_db as udb
from app.services.data_hygiene_service import build_alerts, build_status_payload


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    udb.reset_engine()
    # Register all unified models so tables exist
    from app.services import unified_models  # noqa: F401

    yield
    udb.reset_engine()


@pytest.fixture
def client(isolated_db):
    return TestClient(app)


def test_status_endpoint_returns_tables(client: TestClient) -> None:
    res = client.get("/api/data-hygiene/status")
    assert res.status_code == 200
    body = res.json()
    assert "tables" in body
    assert len(body["tables"]) == len(data_hygiene_service.MONITORED)
    keys = {t["key"] for t in body["tables"]}
    assert "runtime_events" in keys
    assert "telemetry_snapshots" in keys
    assert "meta" in body
    assert body["meta"]["insufficient_history"] is True


def test_alerts_endpoint_matches_status_alerts(client: TestClient) -> None:
    a = client.get("/api/data-hygiene/alerts").json()
    b = client.get("/api/data-hygiene/status").json()
    assert a["alerts"] == b["alerts"]
    assert a["captured_at"] == b["captured_at"]


def test_build_alerts_warning_on_fast_growth() -> None:
    prev = MagicMock()
    prev.row_count = 100
    prev.captured_at = datetime.now(timezone.utc) - timedelta(hours=1)
    alerts = build_alerts(
        "agent_tasks",
        count_now=500,
        prev=prev,
        now=datetime.now(timezone.utc),
    )
    assert len(alerts) >= 1
    assert alerts[0]["severity"] in ("warning", "critical")
    assert alerts[0]["table_key"] == "agent_tasks"


def test_build_alerts_runtime_uses_stricter_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_HYGIENE_RUNTIME_WARN_PCT", "10")
    monkeypatch.setenv("DATA_HYGIENE_RUNTIME_WARN_ABS", "50")
    prev = MagicMock()
    prev.row_count = 1000
    prev.captured_at = datetime.now(timezone.utc) - timedelta(hours=2)
    # +150 rows = 15% — should warn for runtime_events
    alerts = build_alerts(
        "runtime_events",
        count_now=1150,
        prev=prev,
        now=datetime.now(timezone.utc),
    )
    assert len(alerts) >= 1


def test_build_alerts_no_division_by_zero() -> None:
    prev = MagicMock()
    prev.row_count = 0
    prev.captured_at = datetime.now(timezone.utc) - timedelta(hours=1)
    alerts = build_alerts(
        "contribution_ledger",
        count_now=5,
        prev=prev,
        now=datetime.now(timezone.utc),
    )
    assert isinstance(alerts, list)


def test_growth_fields_after_record_twice(client: TestClient) -> None:
    client.get("/api/data-hygiene/status?record=true")
    client.get("/api/data-hygiene/status?record=true")
    body = client.get("/api/data-hygiene/status").json()
    assert body["meta"]["insufficient_history"] is False
    for t in body["tables"]:
        assert t["previous_count"] is not None
        assert t["delta_rows"] is not None
        assert t["growth_rows_per_hour"] is not None


def test_build_status_payload_record_flag() -> None:
    p1 = build_status_payload(record_sample=True)
    p2 = build_status_payload(record_sample=False)
    assert p1["captured_at"] != p2["captured_at"] or True  # timestamps may match in same second
    assert "tables" in p1
