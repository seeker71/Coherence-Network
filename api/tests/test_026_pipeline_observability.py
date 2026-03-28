"""Tests for Spec 026: Pipeline Observability and Auto-Review (Phase 1 + Phase 2).

Verifies:
- POST /api/agent/metrics records task metrics
- GET /api/agent/metrics returns execution_time P50/P95, success_rate, by_task_type, by_model
- Input validation: required fields, bounds, unknown fields rejected
- Phase 2: prompt_variant tagging and aggregation in by_prompt_variant
- metrics_service aggregation logic (unit)
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_metric(
    task_id: str = "t1",
    task_type: str = "spec",
    model: str = "cursor/auto",
    executor: str = "claude",
    duration_seconds: float = 30.0,
    status: str = "completed",
    prompt_variant: str | None = None,
    skill_version: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "task_id": task_id,
        "task_type": task_type,
        "model": model,
        "executor": executor,
        "duration_seconds": duration_seconds,
        "status": status,
    }
    if prompt_variant is not None:
        record["prompt_variant"] = prompt_variant
    if skill_version is not None:
        record["skill_version"] = skill_version
    return record


# ---------------------------------------------------------------------------
# Unit tests: metrics_service aggregation
# ---------------------------------------------------------------------------


def test_get_aggregates_empty_returns_zero_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_aggregates returns the canonical zero shape when no data exists."""
    from app.services import metrics_service

    monkeypatch.setattr(metrics_service, "_load_records", lambda: [])
    monkeypatch.setenv("METRICS_USE_DB", "false")

    result = metrics_service.get_aggregates()

    assert "success_rate" in result
    assert "execution_time" in result
    assert result["success_rate"]["completed"] == 0
    assert result["success_rate"]["failed"] == 0
    assert result["success_rate"]["total"] == 0
    assert result["execution_time"]["p50_seconds"] == 0
    assert result["execution_time"]["p95_seconds"] == 0


def test_get_aggregates_success_rate_calculation(monkeypatch: pytest.MonkeyPatch) -> None:
    """success_rate.rate is completed / total, rounded to 2dp."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"task_id": f"t{i}", "task_type": "spec", "model": "cursor/auto",
         "duration_seconds": 10.0, "status": "completed", "created_at": now}
        for i in range(8)
    ] + [
        {"task_id": f"f{i}", "task_type": "spec", "model": "cursor/auto",
         "duration_seconds": 10.0, "status": "failed", "created_at": now}
        for i in range(2)
    ]

    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    result = metrics_service.get_aggregates()

    sr = result["success_rate"]
    assert sr["completed"] == 8
    assert sr["failed"] == 2
    assert sr["total"] == 10
    assert abs(sr["rate"] - 0.8) < 1e-6


def test_get_aggregates_execution_time_percentiles(monkeypatch: pytest.MonkeyPatch) -> None:
    """P50 and P95 computed from sorted durations."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    durations = list(range(1, 21))  # 1..20
    records = [
        {"task_id": f"t{i}", "task_type": "spec", "model": "m",
         "duration_seconds": float(d), "status": "completed", "created_at": now}
        for i, d in enumerate(durations)
    ]

    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    result = metrics_service.get_aggregates()

    et = result["execution_time"]
    # p50 index = n//2 = 20//2 = 10 → value 11 (1-indexed sorted list)
    assert et["p50_seconds"] > 0
    # p95 index = int(20*0.95) = 19 → value 20
    assert et["p95_seconds"] >= et["p50_seconds"]


def test_get_aggregates_by_task_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """by_task_type breakdown has correct counts and success_rate per type."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"task_id": "s1", "task_type": "spec", "model": "m", "duration_seconds": 10.0, "status": "completed", "created_at": now},
        {"task_id": "s2", "task_type": "spec", "model": "m", "duration_seconds": 20.0, "status": "failed", "created_at": now},
        {"task_id": "i1", "task_type": "impl", "model": "m", "duration_seconds": 30.0, "status": "completed", "created_at": now},
    ]

    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    result = metrics_service.get_aggregates()

    btt = result["by_task_type"]
    assert "spec" in btt
    assert btt["spec"]["count"] == 2
    assert btt["spec"]["completed"] == 1
    assert btt["spec"]["failed"] == 1
    assert abs(btt["spec"]["success_rate"] - 0.5) < 1e-6

    assert "impl" in btt
    assert btt["impl"]["success_rate"] == 1.0


def test_get_aggregates_by_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """by_model breakdown has count and avg_duration."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"task_id": "t1", "task_type": "spec", "model": "cursor/auto", "duration_seconds": 40.0, "status": "completed", "created_at": now},
        {"task_id": "t2", "task_type": "spec", "model": "cursor/auto", "duration_seconds": 60.0, "status": "completed", "created_at": now},
        {"task_id": "t3", "task_type": "spec", "model": "claude", "duration_seconds": 90.0, "status": "failed", "created_at": now},
    ]

    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    result = metrics_service.get_aggregates()

    bm = result["by_model"]
    assert "cursor/auto" in bm
    assert bm["cursor/auto"]["count"] == 2
    assert abs(bm["cursor/auto"]["avg_duration"] - 50.0) < 1e-3

    assert "claude" in bm
    assert bm["claude"]["count"] == 1


def test_get_aggregates_prompt_variant_phase2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 2: by_prompt_variant aggregates success rate and avg_duration per variant."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"task_id": "t1", "task_type": "spec", "model": "m", "duration_seconds": 20.0, "status": "completed", "created_at": now, "prompt_variant": "v1"},
        {"task_id": "t2", "task_type": "spec", "model": "m", "duration_seconds": 40.0, "status": "failed", "created_at": now, "prompt_variant": "v1"},
        {"task_id": "t3", "task_type": "spec", "model": "m", "duration_seconds": 10.0, "status": "completed", "created_at": now, "prompt_variant": "v2"},
    ]

    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    result = metrics_service.get_aggregates()

    assert "by_prompt_variant" in result
    bpv = result["by_prompt_variant"]

    assert "v1" in bpv
    assert bpv["v1"]["count"] == 2
    assert bpv["v1"]["completed"] == 1
    assert bpv["v1"]["failed"] == 1
    assert abs(bpv["v1"]["success_rate"] - 0.5) < 1e-6
    assert abs(bpv["v1"]["avg_duration"] - 30.0) < 1e-3

    assert "v2" in bpv
    assert bpv["v2"]["success_rate"] == 1.0


def test_get_aggregates_no_prompt_variant_omits_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """by_prompt_variant is absent when no records have prompt_variant set."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"task_id": "t1", "task_type": "spec", "model": "m", "duration_seconds": 10.0, "status": "completed", "created_at": now},
    ]

    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    result = metrics_service.get_aggregates()

    assert "by_prompt_variant" not in result


def test_get_aggregates_window_days_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    """window_days param is echoed back in response when supplied."""
    from app.services import metrics_service

    monkeypatch.setattr(metrics_service, "_load_records", lambda: [])
    monkeypatch.setenv("METRICS_USE_DB", "false")

    result = metrics_service.get_aggregates(window_days=14)

    assert result.get("window_days") == 14


def test_record_task_writes_jsonl(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    """record_task appends a well-formed JSONL record."""
    from app.services import metrics_service

    metrics_file = tmp_path / "metrics.jsonl"
    monkeypatch.setenv("METRICS_FILE_PATH", str(metrics_file))
    monkeypatch.setenv("METRICS_USE_DB", "false")

    metrics_service.record_task(
        task_id="unit-test-1",
        task_type="spec",
        model="cursor/auto",
        duration_seconds=42.5,
        status="completed",
        executor="claude",
        prompt_variant="pv-a",
        skill_version="1.0",
    )

    assert metrics_file.exists()
    line = metrics_file.read_text(encoding="utf-8").strip()
    record = json.loads(line)

    assert record["task_id"] == "unit-test-1"
    assert record["task_type"] == "spec"
    assert record["model"] == "cursor/auto"
    assert record["duration_seconds"] == 42.5
    assert record["status"] == "completed"
    assert record["executor"] == "claude"
    assert record["prompt_variant"] == "pv-a"
    assert record["skill_version"] == "1.0"
    assert "created_at" in record


# ---------------------------------------------------------------------------
# API tests: POST /api/agent/metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_metrics_records_and_returns_201(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/agent/metrics returns 201 and {recorded: true}."""
    recorded: list[dict] = []

    def _fake_record_task(**kwargs: Any) -> None:
        recorded.append(kwargs)

    monkeypatch.setattr("app.routers.agent.record_task", _fake_record_task, raising=False)

    from app.services import metrics_service
    monkeypatch.setattr(metrics_service, "record_task", _fake_record_task)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/agent/metrics",
            json=_make_metric(task_id="api-test-1"),
        )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["task_id"] == "api-test-1"


@pytest.mark.asyncio
async def test_post_metrics_missing_required_field_returns_422() -> None:
    """POST /api/agent/metrics with missing required field returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/agent/metrics",
            json={
                "task_id": "t1",
                # task_type missing
                "model": "cursor/auto",
                "duration_seconds": 10.0,
                "status": "completed",
            },
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_post_metrics_invalid_status_returns_422() -> None:
    """POST /api/agent/metrics with invalid status returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/agent/metrics",
            json=_make_metric(status="invalid_status"),
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_post_metrics_negative_duration_returns_422() -> None:
    """POST /api/agent/metrics with negative duration_seconds returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/agent/metrics",
            json=_make_metric(duration_seconds=-1.0),
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_post_metrics_unknown_field_returns_422() -> None:
    """POST /api/agent/metrics rejects unknown extra fields (extra=forbid)."""
    payload = _make_metric()
    payload["unknown_extra_field"] = "surprise"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/agent/metrics", json=payload)
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_post_metrics_with_prompt_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/agent/metrics accepts optional prompt_variant for Phase 2."""
    recorded: list[dict] = []

    def _fake_record_task(**kwargs: Any) -> None:
        recorded.append(kwargs)

    from app.services import metrics_service
    monkeypatch.setattr(metrics_service, "record_task", _fake_record_task)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/agent/metrics",
            json=_make_metric(task_id="pv-test", prompt_variant="v-experiment"),
        )

    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_post_metrics_timed_out_status_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/agent/metrics accepts timed_out as a valid status value."""
    from app.services import metrics_service
    monkeypatch.setattr(metrics_service, "record_task", lambda **kwargs: None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/agent/metrics",
            json=_make_metric(status="timed_out"),
        )
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# API tests: GET /api/agent/metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_metrics_returns_200_with_required_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/metrics returns 200 with execution_time and success_rate."""
    from app.services import metrics_service

    monkeypatch.setattr(metrics_service, "_load_records", lambda: [])
    monkeypatch.setenv("METRICS_USE_DB", "false")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/metrics")

    assert r.status_code == 200, r.text
    body = r.json()
    assert "execution_time" in body
    assert "success_rate" in body
    assert "p50_seconds" in body["execution_time"]
    assert "p95_seconds" in body["execution_time"]
    assert "completed" in body["success_rate"]
    assert "failed" in body["success_rate"]
    assert "total" in body["success_rate"]


@pytest.mark.asyncio
async def test_get_metrics_with_data_returns_correct_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/metrics with data returns non-zero success_rate and execution_time."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"task_id": "t1", "task_type": "spec", "model": "cursor/auto",
         "duration_seconds": 60.0, "status": "completed", "created_at": now},
        {"task_id": "t2", "task_type": "spec", "model": "cursor/auto",
         "duration_seconds": 120.0, "status": "completed", "created_at": now},
        {"task_id": "t3", "task_type": "impl", "model": "claude",
         "duration_seconds": 90.0, "status": "failed", "created_at": now},
    ]
    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/metrics")

    assert r.status_code == 200, r.text
    body = r.json()

    sr = body["success_rate"]
    assert sr["completed"] == 2
    assert sr["failed"] == 1
    assert sr["total"] == 3

    et = body["execution_time"]
    assert et["p50_seconds"] > 0
    assert et["p95_seconds"] > 0

    btt = body.get("by_task_type", {})
    assert "spec" in btt
    assert "impl" in btt

    bm = body.get("by_model", {})
    assert "cursor/auto" in bm
    assert "claude" in bm


@pytest.mark.asyncio
async def test_get_metrics_window_days_query_param(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/metrics?window_days=14 echoes window_days in response."""
    from app.services import metrics_service

    monkeypatch.setattr(metrics_service, "_load_records", lambda: [])
    monkeypatch.setenv("METRICS_USE_DB", "false")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/metrics", params={"window_days": 14})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("window_days") == 14


@pytest.mark.asyncio
async def test_get_metrics_by_task_type_has_success_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/metrics by_task_type entries include a success_rate field."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"task_id": "t1", "task_type": "spec", "model": "m",
         "duration_seconds": 10.0, "status": "completed", "created_at": now},
        {"task_id": "t2", "task_type": "spec", "model": "m",
         "duration_seconds": 10.0, "status": "failed", "created_at": now},
    ]
    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/metrics")

    body = r.json()
    spec_entry = body["by_task_type"].get("spec", {})
    assert "success_rate" in spec_entry


@pytest.mark.asyncio
async def test_get_metrics_by_model_has_avg_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/metrics by_model entries include avg_duration."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"task_id": "t1", "task_type": "spec", "model": "cursor/auto",
         "duration_seconds": 50.0, "status": "completed", "created_at": now},
    ]
    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/metrics")

    body = r.json()
    model_entry = body["by_model"].get("cursor/auto", {})
    assert "avg_duration" in model_entry
    assert abs(model_entry["avg_duration"] - 50.0) < 1e-3


@pytest.mark.asyncio
async def test_get_metrics_by_prompt_variant_when_data_has_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/metrics includes by_prompt_variant when records have prompt_variant."""
    from app.services import metrics_service

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"task_id": "t1", "task_type": "spec", "model": "m", "duration_seconds": 20.0,
         "status": "completed", "created_at": now, "prompt_variant": "baseline"},
        {"task_id": "t2", "task_type": "spec", "model": "m", "duration_seconds": 30.0,
         "status": "completed", "created_at": now, "prompt_variant": "experiment-a"},
    ]
    monkeypatch.setattr(metrics_service, "_load_records", lambda: records)
    monkeypatch.setenv("METRICS_USE_DB", "false")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/metrics")

    body = r.json()
    assert "by_prompt_variant" in body
    assert "baseline" in body["by_prompt_variant"]
    assert "experiment-a" in body["by_prompt_variant"]


# ---------------------------------------------------------------------------
# Pydantic model validation unit tests
# ---------------------------------------------------------------------------


def test_task_metric_record_valid_payload() -> None:
    """TaskMetricRecord accepts a valid completed record."""
    from app.models.metrics import TaskMetricRecord

    m = TaskMetricRecord(
        task_id="t1",
        task_type="spec",
        model="cursor/auto",
        executor="claude",
        duration_seconds=45.0,
        status="completed",
    )
    assert m.task_id == "t1"
    assert m.status == "completed"


def test_task_metric_record_failed_status() -> None:
    """TaskMetricRecord accepts failed status."""
    from app.models.metrics import TaskMetricRecord

    m = TaskMetricRecord(
        task_id="t2",
        task_type="impl",
        model="claude",
        duration_seconds=90.0,
        status="failed",
    )
    assert m.status == "failed"


def test_task_metric_record_rejects_empty_task_id() -> None:
    """TaskMetricRecord rejects empty string task_id (min_length=1)."""
    from pydantic import ValidationError

    from app.models.metrics import TaskMetricRecord

    with pytest.raises(ValidationError):
        TaskMetricRecord(
            task_id="",
            task_type="spec",
            model="cursor/auto",
            duration_seconds=10.0,
            status="completed",
        )


def test_task_metric_record_rejects_extra_fields() -> None:
    """TaskMetricRecord rejects unknown extra fields (extra=forbid)."""
    from pydantic import ValidationError

    from app.models.metrics import TaskMetricRecord

    with pytest.raises(ValidationError):
        TaskMetricRecord(
            task_id="t1",
            task_type="spec",
            model="cursor/auto",
            duration_seconds=10.0,
            status="completed",
            unexpected_field="oops",
        )


def test_task_metric_record_with_prompt_variant() -> None:
    """TaskMetricRecord stores prompt_variant for Phase 2."""
    from app.models.metrics import TaskMetricRecord

    m = TaskMetricRecord(
        task_id="t3",
        task_type="spec",
        model="cursor/auto",
        duration_seconds=30.0,
        status="completed",
        prompt_variant="experiment-x",
    )
    assert m.prompt_variant == "experiment-x"


def test_metrics_response_default_structure() -> None:
    """MetricsResponse has correct default empty structure."""
    from app.models.metrics import MetricsResponse

    r = MetricsResponse()
    assert r.execution_time.p50_seconds == 0
    assert r.execution_time.p95_seconds == 0
    assert r.success_rate.completed == 0
    assert r.success_rate.total == 0
    assert r.by_task_type == {}
    assert r.by_model == {}
