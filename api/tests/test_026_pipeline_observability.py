"""Tests for Spec 026: Pipeline Observability and Auto-Review (Phase 1 & 2).

Covers:
- TaskMetricRecord Pydantic model validation (input validation, field constraints)
- metrics_service.record_task — persists records to JSONL
- metrics_service.get_aggregates — P50/P95, success_rate, by_task_type, by_model
- Phase 2: prompt_variant tagging and aggregation
- API endpoints: POST /api/agent/metrics, GET /api/agent/metrics
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models.metrics import (
    ExecutionTimeStats,
    MetricsResponse,
    SuccessRateStats,
    TaskMetricRecord,
)


# ---------------------------------------------------------------------------
# Pydantic model validation tests
# ---------------------------------------------------------------------------


class TestTaskMetricRecordValidation:
    """Spec 026: Input validation — all required fields, bounds, extra=forbid."""

    def test_valid_minimal_record(self) -> None:
        r = TaskMetricRecord(
            task_id="t1",
            task_type="spec",
            model="claude-sonnet-4-6",
            duration_seconds=42.0,
            status="completed",
        )
        assert r.task_id == "t1"
        assert r.status == "completed"
        assert r.prompt_variant is None
        assert r.skill_version is None

    def test_valid_with_optional_fields(self) -> None:
        r = TaskMetricRecord(
            task_id="t2",
            task_type="impl",
            model="cursor/auto",
            executor="claude",
            duration_seconds=10.5,
            status="failed",
            prompt_variant="variant-A",
            skill_version="v1.2",
        )
        assert r.prompt_variant == "variant-A"
        assert r.skill_version == "v1.2"
        assert r.executor == "claude"

    def test_status_timed_out_allowed(self) -> None:
        r = TaskMetricRecord(
            task_id="t3",
            task_type="test",
            model="gpt-4o",
            duration_seconds=300.0,
            status="timed_out",
        )
        assert r.status == "timed_out"

    def test_status_invalid_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskMetricRecord(
                task_id="t4",
                task_type="spec",
                model="m",
                duration_seconds=1.0,
                status="running",
            )

    def test_empty_task_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskMetricRecord(
                task_id="",
                task_type="spec",
                model="m",
                duration_seconds=1.0,
                status="completed",
            )

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskMetricRecord(
                task_id="t5",
                task_type="spec",
                model="m",
                duration_seconds=-1.0,
                status="completed",
            )

    def test_duration_exceeds_day_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskMetricRecord(
                task_id="t6",
                task_type="spec",
                model="m",
                duration_seconds=86401.0,
                status="completed",
            )

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            TaskMetricRecord(
                task_id="t7",
                task_type="spec",
                model="m",
                duration_seconds=1.0,
                status="completed",
                unknown_field="oops",
            )

    def test_missing_required_field_task_id(self) -> None:
        with pytest.raises(ValidationError):
            TaskMetricRecord(  # type: ignore[call-arg]
                task_type="spec",
                model="m",
                duration_seconds=1.0,
                status="completed",
            )

    def test_missing_required_field_status(self) -> None:
        with pytest.raises(ValidationError):
            TaskMetricRecord(  # type: ignore[call-arg]
                task_id="t8",
                task_type="spec",
                model="m",
                duration_seconds=1.0,
            )


class TestMetricsResponseModel:
    """Spec 026: MetricsResponse and sub-models default to empty/zero."""

    def test_default_execution_time_stats(self) -> None:
        s = ExecutionTimeStats()
        assert s.p50_seconds == 0
        assert s.p95_seconds == 0

    def test_default_success_rate_stats(self) -> None:
        s = SuccessRateStats()
        assert s.completed == 0
        assert s.failed == 0
        assert s.total == 0
        assert s.rate == 0.0

    def test_default_metrics_response(self) -> None:
        r = MetricsResponse()
        assert r.by_task_type == {}
        assert r.by_model == {}
        assert r.window_days is None

    def test_success_rate_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            SuccessRateStats(rate=1.5)

    def test_window_days_bounds(self) -> None:
        with pytest.raises(ValidationError):
            MetricsResponse(window_days=0)
        with pytest.raises(ValidationError):
            MetricsResponse(window_days=91)


# ---------------------------------------------------------------------------
# metrics_service unit tests (file-backed, isolated per test via tmp_path)
# ---------------------------------------------------------------------------


@pytest.fixture()
def metrics_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the metrics service to a temp file and disable DB backend."""
    mf = tmp_path / "metrics.jsonl"
    monkeypatch.setenv("METRICS_FILE_PATH", str(mf))
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", "")
    from app.services import metrics_service
    monkeypatch.setattr(metrics_service, "METRICS_FILE", str(mf))
    return mf


def _write_records(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestRecordTask:
    """metrics_service.record_task — persists data to JSONL."""

    def test_creates_jsonl_entry(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        metrics_service.record_task(
            task_id="abc",
            task_type="spec",
            model="claude-sonnet-4-6",
            duration_seconds=55.0,
            status="completed",
            executor="claude",
        )
        assert metrics_file.exists()
        lines = [json.loads(l) for l in metrics_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        assert lines[0]["task_id"] == "abc"
        assert lines[0]["status"] == "completed"
        assert lines[0]["duration_seconds"] == 55.0

    def test_prompt_variant_stored(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        metrics_service.record_task(
            task_id="pv1",
            task_type="impl",
            model="cursor/auto",
            duration_seconds=20.0,
            status="completed",
            prompt_variant="variant-B",
        )
        lines = [json.loads(l) for l in metrics_file.read_text().splitlines() if l.strip()]
        assert lines[0]["prompt_variant"] == "variant-B"

    def test_skill_version_stored(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        metrics_service.record_task(
            task_id="sv1",
            task_type="impl",
            model="cursor/auto",
            duration_seconds=30.0,
            status="failed",
            skill_version="v2.0",
        )
        lines = [json.loads(l) for l in metrics_file.read_text().splitlines() if l.strip()]
        assert lines[0]["skill_version"] == "v2.0"

    def test_multiple_records_appended(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        for i in range(3):
            metrics_service.record_task(
                task_id=f"t{i}",
                task_type="spec",
                model="m",
                duration_seconds=float(i),
                status="completed",
            )
        lines = metrics_file.read_text().splitlines()
        assert len(lines) == 3


class TestGetAggregatesEmpty:
    """get_aggregates returns safe empty structure when no data."""

    def test_empty_file_returns_zeros(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        result = metrics_service.get_aggregates()
        assert result["success_rate"]["total"] == 0
        assert result["execution_time"]["p50_seconds"] == 0
        assert result["by_task_type"] == {}
        assert result["by_model"] == {}

    def test_missing_file_returns_zeros(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mf = tmp_path / "nonexistent.jsonl"
        monkeypatch.setenv("METRICS_FILE_PATH", str(mf))
        monkeypatch.setenv("METRICS_USE_DB", "0")
        from app.services import metrics_service
        monkeypatch.setattr(metrics_service, "METRICS_FILE", str(mf))

        result = metrics_service.get_aggregates()
        assert result["success_rate"]["total"] == 0


class TestGetAggregatesWithData:
    """get_aggregates computes P50/P95, success_rate, by_task_type, by_model correctly."""

    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def test_success_rate_calculation(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        records = [
            {"task_id": f"c{i}", "task_type": "spec", "model": "m", "duration_seconds": 10.0,
             "status": "completed", "created_at": self._now_iso()}
            for i in range(4)
        ] + [
            {"task_id": "f1", "task_type": "spec", "model": "m", "duration_seconds": 5.0,
             "status": "failed", "created_at": self._now_iso()}
        ]
        _write_records(metrics_file, records)
        result = metrics_service.get_aggregates()
        sr = result["success_rate"]
        assert sr["completed"] == 4
        assert sr["failed"] == 1
        assert sr["total"] == 5
        assert sr["rate"] == 0.8

    def test_execution_time_p50_p95(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        durations = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        records = [
            {"task_id": f"t{i}", "task_type": "spec", "model": "m",
             "duration_seconds": float(d), "status": "completed",
             "created_at": self._now_iso()}
            for i, d in enumerate(durations)
        ]
        _write_records(metrics_file, records)
        result = metrics_service.get_aggregates()
        et = result["execution_time"]
        assert et["p50_seconds"] == 60
        assert et["p95_seconds"] == 100

    def test_by_task_type_breakdown(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        records = [
            {"task_id": "s1", "task_type": "spec", "model": "m", "duration_seconds": 10.0,
             "status": "completed", "created_at": self._now_iso()},
            {"task_id": "s2", "task_type": "spec", "model": "m", "duration_seconds": 20.0,
             "status": "failed", "created_at": self._now_iso()},
            {"task_id": "i1", "task_type": "impl", "model": "m", "duration_seconds": 30.0,
             "status": "completed", "created_at": self._now_iso()},
        ]
        _write_records(metrics_file, records)
        result = metrics_service.get_aggregates()
        btt = result["by_task_type"]
        assert "spec" in btt
        assert btt["spec"]["count"] == 2
        assert btt["spec"]["completed"] == 1
        assert btt["spec"]["failed"] == 1
        assert btt["spec"]["success_rate"] == 0.5
        assert "impl" in btt
        assert btt["impl"]["success_rate"] == 1.0

    def test_by_model_breakdown(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        records = [
            {"task_id": "m1", "task_type": "spec", "model": "claude-sonnet-4-6",
             "duration_seconds": 20.0, "status": "completed", "created_at": self._now_iso()},
            {"task_id": "m2", "task_type": "spec", "model": "claude-sonnet-4-6",
             "duration_seconds": 40.0, "status": "completed", "created_at": self._now_iso()},
            {"task_id": "m3", "task_type": "spec", "model": "cursor/auto",
             "duration_seconds": 50.0, "status": "completed", "created_at": self._now_iso()},
        ]
        _write_records(metrics_file, records)
        result = metrics_service.get_aggregates()
        bm = result["by_model"]
        assert "claude-sonnet-4-6" in bm
        assert bm["claude-sonnet-4-6"]["count"] == 2
        assert bm["claude-sonnet-4-6"]["avg_duration"] == 30.0
        assert "cursor/auto" in bm
        assert bm["cursor/auto"]["count"] == 1

    def test_window_days_filters_old_records(self, metrics_file: Path) -> None:
        from datetime import datetime, timedelta, timezone
        from app.services import metrics_service

        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        new_ts = datetime.now(timezone.utc).isoformat()
        records = [
            {"task_id": "old1", "task_type": "spec", "model": "m", "duration_seconds": 100.0,
             "status": "completed", "created_at": old_ts},
            {"task_id": "new1", "task_type": "spec", "model": "m", "duration_seconds": 10.0,
             "status": "completed", "created_at": new_ts},
        ]
        _write_records(metrics_file, records)
        result = metrics_service.get_aggregates(window_days=7)
        assert result["success_rate"]["total"] == 1
        assert result["window_days"] == 7

    def test_single_record_p50_and_p95_equal(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        records = [
            {"task_id": "t1", "task_type": "spec", "model": "m", "duration_seconds": 42.0,
             "status": "completed", "created_at": self._now_iso()}
        ]
        _write_records(metrics_file, records)
        result = metrics_service.get_aggregates()
        assert result["execution_time"]["p50_seconds"] == 42
        assert result["execution_time"]["p95_seconds"] == 42


class TestPromptVariantAggregation:
    """Spec 026 Phase 2: by_prompt_variant aggregation when variants present."""

    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def test_by_prompt_variant_present_when_variants_exist(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        records = [
            {"task_id": "pv1", "task_type": "impl", "model": "m", "duration_seconds": 20.0,
             "status": "completed", "prompt_variant": "variant-A", "created_at": self._now_iso()},
            {"task_id": "pv2", "task_type": "impl", "model": "m", "duration_seconds": 30.0,
             "status": "completed", "prompt_variant": "variant-A", "created_at": self._now_iso()},
            {"task_id": "pv3", "task_type": "impl", "model": "m", "duration_seconds": 60.0,
             "status": "failed", "prompt_variant": "variant-B", "created_at": self._now_iso()},
        ]
        _write_records(metrics_file, records)
        result = metrics_service.get_aggregates()
        assert "by_prompt_variant" in result
        bpv = result["by_prompt_variant"]
        assert "variant-A" in bpv
        assert bpv["variant-A"]["count"] == 2
        assert bpv["variant-A"]["completed"] == 2
        assert bpv["variant-A"]["success_rate"] == 1.0
        assert bpv["variant-A"]["avg_duration"] == 25.0
        assert "variant-B" in bpv
        assert bpv["variant-B"]["failed"] == 1
        assert bpv["variant-B"]["success_rate"] == 0.0

    def test_no_prompt_variant_key_when_none_present(self, metrics_file: Path) -> None:
        from app.services import metrics_service

        records = [
            {"task_id": "t1", "task_type": "spec", "model": "m", "duration_seconds": 10.0,
             "status": "completed", "created_at": self._now_iso()},
        ]
        _write_records(metrics_file, records)
        result = metrics_service.get_aggregates()
        assert "by_prompt_variant" not in result


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """Create an isolated TestClient with a temp metrics file."""
    mf = tmp_path / "api_metrics.jsonl"
    monkeypatch.setenv("METRICS_FILE_PATH", str(mf))
    monkeypatch.setenv("METRICS_USE_DB", "0")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", "")
    from app.services import metrics_service
    monkeypatch.setattr(metrics_service, "METRICS_FILE", str(mf))
    from app.main import app
    return TestClient(app)


class TestPostMetricsEndpoint:
    """POST /api/agent/metrics — record a task metric via HTTP."""

    def test_post_valid_metric_returns_201(self, api_client: TestClient) -> None:
        payload = {
            "task_id": "task-001",
            "task_type": "spec",
            "model": "claude-sonnet-4-6",
            "duration_seconds": 45.0,
            "status": "completed",
        }
        resp = api_client.post("/api/agent/metrics", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["recorded"] is True
        assert body["task_id"] == "task-001"

    def test_post_with_prompt_variant(self, api_client: TestClient) -> None:
        payload = {
            "task_id": "task-002",
            "task_type": "impl",
            "model": "cursor/auto",
            "duration_seconds": 30.0,
            "status": "completed",
            "prompt_variant": "variant-A",
        }
        resp = api_client.post("/api/agent/metrics", json=payload)
        assert resp.status_code == 201
        assert resp.json()["recorded"] is True

    def test_post_invalid_status_returns_422(self, api_client: TestClient) -> None:
        payload = {
            "task_id": "task-003",
            "task_type": "spec",
            "model": "m",
            "duration_seconds": 10.0,
            "status": "in_progress",
        }
        resp = api_client.post("/api/agent/metrics", json=payload)
        assert resp.status_code == 422

    def test_post_missing_required_field_returns_422(self, api_client: TestClient) -> None:
        payload = {
            "task_type": "spec",
            "model": "m",
            "duration_seconds": 10.0,
            "status": "completed",
        }
        resp = api_client.post("/api/agent/metrics", json=payload)
        assert resp.status_code == 422

    def test_post_negative_duration_returns_422(self, api_client: TestClient) -> None:
        payload = {
            "task_id": "task-004",
            "task_type": "spec",
            "model": "m",
            "duration_seconds": -5.0,
            "status": "completed",
        }
        resp = api_client.post("/api/agent/metrics", json=payload)
        assert resp.status_code == 422

    def test_post_extra_field_returns_422(self, api_client: TestClient) -> None:
        payload = {
            "task_id": "task-005",
            "task_type": "spec",
            "model": "m",
            "duration_seconds": 5.0,
            "status": "completed",
            "unexpected": "field",
        }
        resp = api_client.post("/api/agent/metrics", json=payload)
        assert resp.status_code == 422


class TestGetMetricsEndpoint:
    """GET /api/agent/metrics — returns aggregated pipeline metrics."""

    def test_get_empty_returns_200_with_zeros(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/agent/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert "success_rate" in body
        assert "execution_time" in body
        assert body["success_rate"]["total"] == 0
        assert body["execution_time"]["p50_seconds"] == 0

    def test_get_after_post_reflects_recorded_metrics(
        self, api_client: TestClient
    ) -> None:
        payloads = [
            {"task_id": f"t{i}", "task_type": "spec", "model": "m",
             "duration_seconds": float(10 * (i + 1)), "status": "completed"}
            for i in range(4)
        ] + [
            {"task_id": "f1", "task_type": "impl", "model": "m",
             "duration_seconds": 5.0, "status": "failed"}
        ]
        for p in payloads:
            api_client.post("/api/agent/metrics", json=p)

        resp = api_client.get("/api/agent/metrics")
        assert resp.status_code == 200
        body = resp.json()
        sr = body["success_rate"]
        assert sr["completed"] == 4
        assert sr["failed"] == 1
        assert sr["total"] == 5
        assert sr["rate"] == 0.8

    def test_get_by_task_type_in_response(self, api_client: TestClient) -> None:
        payloads = [
            {"task_id": "s1", "task_type": "spec", "model": "m",
             "duration_seconds": 10.0, "status": "completed"},
            {"task_id": "i1", "task_type": "impl", "model": "m",
             "duration_seconds": 20.0, "status": "completed"},
        ]
        for p in payloads:
            api_client.post("/api/agent/metrics", json=p)

        resp = api_client.get("/api/agent/metrics")
        body = resp.json()
        assert "spec" in body["by_task_type"]
        assert "impl" in body["by_task_type"]

    def test_get_by_model_in_response(self, api_client: TestClient) -> None:
        payloads = [
            {"task_id": "m1", "task_type": "spec", "model": "claude-sonnet-4-6",
             "duration_seconds": 30.0, "status": "completed"},
        ]
        for p in payloads:
            api_client.post("/api/agent/metrics", json=p)

        resp = api_client.get("/api/agent/metrics")
        body = resp.json()
        assert "claude-sonnet-4-6" in body["by_model"]

    def test_get_window_days_param_accepted(self, api_client: TestClient) -> None:
        resp = api_client.get("/api/agent/metrics?window_days=14")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("window_days") == 14

    def test_get_by_prompt_variant_after_post(self, api_client: TestClient) -> None:
        payloads = [
            {"task_id": "pv1", "task_type": "impl", "model": "m",
             "duration_seconds": 25.0, "status": "completed", "prompt_variant": "variant-X"},
            {"task_id": "pv2", "task_type": "impl", "model": "m",
             "duration_seconds": 35.0, "status": "completed", "prompt_variant": "variant-X"},
        ]
        for p in payloads:
            api_client.post("/api/agent/metrics", json=p)

        resp = api_client.get("/api/agent/metrics")
        body = resp.json()
        assert "by_prompt_variant" in body
        assert "variant-X" in body["by_prompt_variant"]
        assert body["by_prompt_variant"]["variant-X"]["count"] == 2
