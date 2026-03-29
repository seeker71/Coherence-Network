"""Tests for Data Retention Summarization (data-retention-summarization).

Verifies acceptance criteria:
  1. get_policy() returns correct tier days and never_delete / safe_to_trim lists.
  2. get_status() returns row counts for all 5 trimable tables.
  3. build_daily_summaries() computes correct aggregates from runtime_events.
  4. run_retention_pass(dry_run=True) previews without deleting data.
  5. run_retention_pass(dry_run=False) exports to JSONL and deletes stale rows.
  6. Daily summaries are cached (second call reuses cached value).
  7. API endpoint GET /api/data-retention/policy returns 200 with expected keys.
  8. API endpoint GET /api/data-retention/status returns 200 with row_counts.
  9. API endpoint POST /api/data-retention/run returns 200 with table stats.
 10. API endpoint GET /api/data-retention/summaries/daily returns summaries list.
 11. _append_backup writes JSONL files partitioned by month.
 12. run_retention_pass result includes started_at, finished_at, duration_seconds.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture: ensure runtime_events table exists in the unified test DB
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_runtime_events_table() -> None:
    """RuntimeEventRecord uses its own Base; we must also register it in the
    unified DB engine so data_retention_service queries work in tests."""
    from app.services import unified_db as _udb
    from app.services.runtime_event_store import Base as RuntimeBase
    eng = _udb.engine()
    RuntimeBase.metadata.create_all(bind=eng, checkfirst=True)


# ---------------------------------------------------------------------------
# Helper: insert a RuntimeEventRecord with a specific timestamp
# ---------------------------------------------------------------------------

def _insert_runtime_event(session, *, recorded_at: datetime, status_code: int = 200,
                           endpoint: str = "/api/health", runtime_ms: float = 10.0) -> None:
    from app.services.runtime_event_store import RuntimeEventRecord
    import uuid
    row = RuntimeEventRecord(
        id=str(uuid.uuid4()),
        source="test",
        endpoint=endpoint,
        raw_endpoint=endpoint,
        method="GET",
        status_code=status_code,
        runtime_ms=runtime_ms,
        recorded_at=recorded_at,
    )
    session.add(row)


# ---------------------------------------------------------------------------
# 1. get_policy() returns correct tier configuration
# ---------------------------------------------------------------------------

class TestGetPolicy:
    def test_has_required_tier_keys(self) -> None:
        from app.services import data_retention_service as svc
        policy = svc.get_policy()
        assert "hot_days" in policy
        assert "warm_days" in policy
        assert "cold_days" in policy

    def test_never_delete_contains_core_tables(self) -> None:
        from app.services import data_retention_service as svc
        policy = svc.get_policy()
        never_delete = policy["never_delete"]
        for tbl in ("ideas", "specs", "contributions", "audit_ledger"):
            assert tbl in never_delete, f"{tbl} must never be deleted"

    def test_safe_to_trim_contains_telemetry_tables(self) -> None:
        from app.services import data_retention_service as svc
        policy = svc.get_policy()
        safe = policy["safe_to_trim"]
        assert "runtime_events" in safe
        assert "telemetry_task_metrics" in safe
        assert "telemetry_friction_events" in safe

    def test_backup_dir_key_present(self) -> None:
        from app.services import data_retention_service as svc
        policy = svc.get_policy()
        assert "backup_dir" in policy
        assert "backup_root_abs" in policy


# ---------------------------------------------------------------------------
# 2. get_status() returns row counts for all 5 trimmable tables
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_returns_all_five_row_count_keys(self) -> None:
        from app.services import data_retention_service as svc
        status = svc.get_status()
        counts = status["current_row_counts"]
        expected = [
            "runtime_events",
            "telemetry_automation_usage_snapshots",
            "telemetry_task_metrics",
            "telemetry_friction_events",
            "telemetry_external_tool_usage_events",
        ]
        for key in expected:
            assert key in counts, f"missing row count for {key}"

    def test_row_counts_are_non_negative_integers(self) -> None:
        from app.services import data_retention_service as svc
        counts = svc.get_status()["current_row_counts"]
        for key, val in counts.items():
            assert isinstance(val, int), f"{key} count should be int"
            assert val >= 0, f"{key} count should be >= 0"

    def test_policy_included_in_status(self) -> None:
        from app.services import data_retention_service as svc
        status = svc.get_status()
        assert "policy" in status
        assert "hot_days" in status["policy"]

    def test_last_run_is_none_before_any_pass(self) -> None:
        from app.services import data_retention_service as svc
        status = svc.get_status()
        assert status["last_run"] is None


# ---------------------------------------------------------------------------
# 3. build_daily_summaries() computes correct aggregates
# ---------------------------------------------------------------------------

class TestBuildDailySummaries:
    def test_empty_db_returns_empty_list(self) -> None:
        from app.services import data_retention_service as svc
        summaries = svc.build_daily_summaries(days_back=3)
        assert isinstance(summaries, list)
        # No events in DB -> no summaries
        assert len(summaries) == 0

    def test_summary_has_required_fields(self) -> None:
        from app.services import data_retention_service as svc
        from app.services import unified_db as _udb
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        with _udb.session() as s:
            _insert_runtime_event(s, recorded_at=two_days_ago)
        summaries = svc.build_daily_summaries(days_back=3)
        assert len(summaries) >= 1
        s0 = summaries[0]
        for field in ("date", "count", "avg_runtime_ms", "error_count", "error_rate", "top_endpoints"):
            assert field in s0, f"summary missing field {field}"

    def test_count_matches_inserted_events(self) -> None:
        from app.services import data_retention_service as svc
        from app.services import unified_db as _udb
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        with _udb.session() as s:
            for _ in range(3):
                _insert_runtime_event(s, recorded_at=two_days_ago)
        summaries = svc.build_daily_summaries(days_back=3)
        assert len(summaries) == 1
        assert summaries[0]["count"] == 3

    def test_error_rate_computed_correctly(self) -> None:
        from app.services import data_retention_service as svc
        from app.services import unified_db as _udb
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        with _udb.session() as s:
            _insert_runtime_event(s, recorded_at=two_days_ago, status_code=200)
            _insert_runtime_event(s, recorded_at=two_days_ago, status_code=500)
        summaries = svc.build_daily_summaries(days_back=3)
        assert len(summaries) == 1
        s0 = summaries[0]
        assert s0["error_count"] == 1
        assert abs(s0["error_rate"] - 0.5) < 0.001

    def test_top_endpoints_present(self) -> None:
        from app.services import data_retention_service as svc
        from app.services import unified_db as _udb
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        with _udb.session() as s:
            _insert_runtime_event(s, recorded_at=two_days_ago, endpoint="/api/ideas")
            _insert_runtime_event(s, recorded_at=two_days_ago, endpoint="/api/ideas")
            _insert_runtime_event(s, recorded_at=two_days_ago, endpoint="/api/health")
        summaries = svc.build_daily_summaries(days_back=3)
        assert summaries[0]["top_endpoints"][0]["endpoint"] == "/api/ideas"
        assert summaries[0]["top_endpoints"][0]["calls"] == 2


# ---------------------------------------------------------------------------
# 4. run_retention_pass(dry_run=True) previews without deleting
# ---------------------------------------------------------------------------

class TestDryRunRetentionPass:
    def test_dry_run_returns_true(self) -> None:
        from app.services import data_retention_service as svc
        result = svc.run_retention_pass(dry_run=True)
        assert result["dry_run"] is True

    def test_dry_run_does_not_delete_recent_rows(self) -> None:
        from app.services import data_retention_service as svc
        from app.services import unified_db as _udb
        from app.services.runtime_event_store import RuntimeEventRecord
        from sqlalchemy import func as sa_func
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        with _udb.session() as s:
            _insert_runtime_event(s, recorded_at=recent)
        svc.run_retention_pass(dry_run=True)
        with _udb.session() as s:
            count = int(s.query(sa_func.count(RuntimeEventRecord.id)).scalar() or 0)
        assert count == 1, "dry_run must not delete rows"

    def test_dry_run_does_not_persist_last_run_meta(self) -> None:
        from app.services import data_retention_service as svc
        svc.run_retention_pass(dry_run=True)
        status = svc.get_status()
        assert status["last_run"] is None, "dry_run must not persist last_run meta"

    def test_dry_run_result_has_timing_fields(self) -> None:
        from app.services import data_retention_service as svc
        result = svc.run_retention_pass(dry_run=True)
        assert "started_at" in result
        assert "finished_at" in result
        assert "duration_seconds" in result
        assert result["duration_seconds"] >= 0


# ---------------------------------------------------------------------------
# 5. run_retention_pass(dry_run=False) exports and deletes stale rows
# ---------------------------------------------------------------------------

class TestLiveRetentionPass:
    def test_stale_rows_deleted_after_pass(self, tmp_path: Path) -> None:
        from app.services import data_retention_service as svc
        from app.services import unified_db as _udb
        from app.services.runtime_event_store import RuntimeEventRecord
        from sqlalchemy import func as sa_func
        original = svc.BACKUP_ROOT
        svc.BACKUP_ROOT = tmp_path / "backups"
        try:
            stale_ts = datetime.now(timezone.utc) - timedelta(days=svc.HOT_DAYS + 2)
            with _udb.session() as s:
                _insert_runtime_event(s, recorded_at=stale_ts)
            svc.run_retention_pass(dry_run=False)
            with _udb.session() as s:
                count = int(s.query(sa_func.count(RuntimeEventRecord.id)).scalar() or 0)
            assert count == 0, "stale rows should be deleted after live pass"
        finally:
            svc.BACKUP_ROOT = original

    def test_backup_jsonl_created(self, tmp_path: Path) -> None:
        from app.services import data_retention_service as svc
        from app.services import unified_db as _udb
        original = svc.BACKUP_ROOT
        svc.BACKUP_ROOT = tmp_path / "backups"
        try:
            stale_ts = datetime.now(timezone.utc) - timedelta(days=svc.HOT_DAYS + 2)
            with _udb.session() as s:
                _insert_runtime_event(s, recorded_at=stale_ts)
            svc.run_retention_pass(dry_run=False)
            jsonl_files = list((tmp_path / "backups" / "runtime_events").glob("*.jsonl"))
            assert len(jsonl_files) >= 1, "backup JSONL should be created"
            for line in jsonl_files[0].read_text().splitlines():
                if line.strip():
                    parsed = json.loads(line)
                    assert "id" in parsed
        finally:
            svc.BACKUP_ROOT = original

    def test_last_run_persisted_after_live_pass(self, tmp_path: Path) -> None:
        from app.services import data_retention_service as svc
        original = svc.BACKUP_ROOT
        svc.BACKUP_ROOT = tmp_path / "backups"
        try:
            svc.run_retention_pass(dry_run=False)
            status = svc.get_status()
            assert status["last_run"] is not None, "last_run must be set after live pass"
            assert "total_deleted" in status["last_run"]
        finally:
            svc.BACKUP_ROOT = original

    def test_recent_rows_not_deleted(self, tmp_path: Path) -> None:
        from app.services import data_retention_service as svc
        from app.services import unified_db as _udb
        from app.services.runtime_event_store import RuntimeEventRecord
        from sqlalchemy import func as sa_func
        original = svc.BACKUP_ROOT
        svc.BACKUP_ROOT = tmp_path / "backups"
        try:
            recent = datetime.now(timezone.utc) - timedelta(hours=1)
            with _udb.session() as s:
                _insert_runtime_event(s, recorded_at=recent)
            svc.run_retention_pass(dry_run=False)
            with _udb.session() as s:
                count = int(s.query(sa_func.count(RuntimeEventRecord.id)).scalar() or 0)
            assert count == 1, "recent rows should survive retention pass"
        finally:
            svc.BACKUP_ROOT = original


# ---------------------------------------------------------------------------
# 6. Daily summaries are cached (second call reuses cached value)
# ---------------------------------------------------------------------------

class TestDailySummaryCaching:
    def test_cached_summary_returned_on_second_call(self) -> None:
        from app.services import data_retention_service as svc
        from app.services import unified_db as _udb
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        with _udb.session() as s:
            _insert_runtime_event(s, recorded_at=two_days_ago)
        summaries1 = svc.build_daily_summaries(days_back=3)
        assert len(summaries1) == 1
        day_key = summaries1[0]["date"]
        meta_val = svc._meta_get(f"retention:runtime_daily_summary:{day_key}")
        assert meta_val, "meta key should be set after first call"
        summaries2 = svc.build_daily_summaries(days_back=3)
        assert len(summaries2) == 1
        assert summaries2[0]["date"] == day_key


# ---------------------------------------------------------------------------
# 7-10. API endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


class TestDataRetentionAPI:
    def test_get_policy_returns_200(self, client) -> None:
        resp = client.get("/api/data-retention/policy")
        assert resp.status_code == 200
        body = resp.json()
        assert "hot_days" in body
        assert "never_delete" in body
        assert "safe_to_trim" in body

    def test_get_status_returns_200(self, client) -> None:
        resp = client.get("/api/data-retention/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "current_row_counts" in body

    def test_post_run_dry_run_returns_200(self, client) -> None:
        resp = client.post("/api/data-retention/run?dry_run=true")
        assert resp.status_code == 200
        body = resp.json()
        assert body["dry_run"] is True
        assert "tables" in body

    def test_get_daily_summaries_returns_200(self, client) -> None:
        resp = client.get("/api/data-retention/summaries/daily?days_back=3")
        assert resp.status_code == 200
        body = resp.json()
        assert "summaries" in body
        assert "days_back" in body
        assert body["days_back"] == 3

    def test_daily_summaries_days_back_validated(self, client) -> None:
        resp = client.get("/api/data-retention/summaries/daily?days_back=0")
        assert resp.status_code == 422

    def test_post_run_returns_table_stats(self, client) -> None:
        resp = client.post("/api/data-retention/run?dry_run=true")
        body = resp.json()
        tables = body["tables"]
        assert isinstance(tables, list)
        table_names = {t.get("table") for t in tables if "table" in t}
        assert "runtime_events" in table_names


# ---------------------------------------------------------------------------
# 11. _append_backup writes JSONL files partitioned by month
# ---------------------------------------------------------------------------

class TestAppendBackup:
    def test_partitions_by_month(self, tmp_path: Path) -> None:
        from app.services import data_retention_service as svc
        original = svc.BACKUP_ROOT
        svc.BACKUP_ROOT = tmp_path / "backups"
        try:
            jan = datetime(2025, 1, 15, tzinfo=timezone.utc)
            feb = datetime(2025, 2, 20, tzinfo=timezone.utc)
            records = [
                {"id": "a", "recorded_at": jan.isoformat()},
                {"id": "b", "recorded_at": feb.isoformat()},
            ]
            written = svc._append_backup("runtime_events", records)
            assert written == 2
            jan_file = tmp_path / "backups" / "runtime_events" / "2025-01.jsonl"
            feb_file = tmp_path / "backups" / "runtime_events" / "2025-02.jsonl"
            assert jan_file.exists()
            assert feb_file.exists()
        finally:
            svc.BACKUP_ROOT = original

    def test_empty_records_returns_zero(self, tmp_path: Path) -> None:
        from app.services import data_retention_service as svc
        original = svc.BACKUP_ROOT
        svc.BACKUP_ROOT = tmp_path / "backups"
        try:
            count = svc._append_backup("runtime_events", [])
            assert count == 0
        finally:
            svc.BACKUP_ROOT = original

    def test_appends_valid_jsonl(self, tmp_path: Path) -> None:
        from app.services import data_retention_service as svc
        original = svc.BACKUP_ROOT
        svc.BACKUP_ROOT = tmp_path / "backups"
        try:
            ts = datetime(2025, 3, 1, tzinfo=timezone.utc)
            svc._append_backup("runtime_events", [{"id": "x", "recorded_at": ts.isoformat()}])
            file_path = tmp_path / "backups" / "runtime_events" / "2025-03.jsonl"
            lines = [l for l in file_path.read_text().splitlines() if l.strip()]
            assert len(lines) == 1
            assert json.loads(lines[0])["id"] == "x"
        finally:
            svc.BACKUP_ROOT = original


# ---------------------------------------------------------------------------
# 12. run_retention_pass result includes timing metadata
# ---------------------------------------------------------------------------

class TestRetentionPassResult:
    def test_result_has_started_at_iso_format(self) -> None:
        from app.services import data_retention_service as svc
        result = svc.run_retention_pass(dry_run=True)
        datetime.fromisoformat(result["started_at"].replace("Z", "+00:00"))

    def test_result_has_finished_at_iso_format(self) -> None:
        from app.services import data_retention_service as svc
        result = svc.run_retention_pass(dry_run=True)
        datetime.fromisoformat(result["finished_at"].replace("Z", "+00:00"))

    def test_duration_seconds_non_negative(self) -> None:
        from app.services import data_retention_service as svc
        result = svc.run_retention_pass(dry_run=True)
        assert result["duration_seconds"] >= 0

    def test_daily_summaries_built_key_present(self) -> None:
        from app.services import data_retention_service as svc
        result = svc.run_retention_pass(dry_run=True)
        assert "daily_summaries_built" in result
        assert isinstance(result["daily_summaries_built"], int)
