from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import smart_reaper_service, timeout_adaptive_service


def test_timeout_recommendation_uses_p90_after_min_samples(monkeypatch, tmp_path: Path) -> None:
    sample_path = tmp_path / "timeout_samples.jsonl"
    monkeypatch.setattr(timeout_adaptive_service, "_samples_path", lambda: sample_path)

    for i, elapsed_ms in enumerate([1000, 1100, 1200, 1300, 2000], start=1):
        timeout_adaptive_service.record_timeout_sample({
            "provider": "codex",
            "task_type": "impl",
            "elapsed_ms": elapsed_ms,
            "outcome": "completed",
            "task_id": f"task-{i}",
        })

    rec = timeout_adaptive_service.timeout_recommendation(
        "impl",
        "codex",
        baseline_seconds=1,
    )
    assert rec["mode"] == "adaptive"
    assert rec["samples"] == 5
    assert rec["timeout_seconds"] >= 2
    assert rec["timeout_seconds"] <= 3


def test_timeout_recommendation_falls_back_before_min_samples(monkeypatch, tmp_path: Path) -> None:
    sample_path = tmp_path / "timeout_samples.jsonl"
    monkeypatch.setattr(timeout_adaptive_service, "_samples_path", lambda: sample_path)
    timeout_adaptive_service.record_timeout_sample({
        "provider": "codex",
        "task_type": "spec",
        "elapsed_ms": 5000,
        "outcome": "completed",
        "task_id": "one",
    })

    rec = timeout_adaptive_service.timeout_recommendation(
        "spec",
        "codex",
        baseline_seconds=1200,
    )
    assert rec["mode"] == "fixed"
    assert rec["timeout_seconds"] == 1200
    assert rec["derivation"] == "fewer_than_min_samples"


def test_resume_direction_preserves_partial_output_marker() -> None:
    resume = smart_reaper_service.build_resume_direction(
        "finish the implementation",
        "partial proof already gathered",
    )
    assert "RESUME FROM TIMEOUT" in resume
    assert "Previous attempt produced this partial work" in resume
    assert "partial proof already gathered" in resume
    assert "Original direction:" in resume


@pytest.mark.asyncio
async def test_timeout_sample_endpoints(monkeypatch, tmp_path: Path) -> None:
    sample_path = tmp_path / "timeout_samples.jsonl"
    monkeypatch.setattr(timeout_adaptive_service, "_samples_path", lambda: sample_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/agent/timeout-samples", json={
            "provider": "codex",
            "task_type": "test",
            "elapsed_ms": 1500,
            "outcome": "completed",
            "task_id": "sample-endpoint",
        })
        assert created.status_code == 201, created.text

        metrics = await client.get("/api/agent/timeout-metrics")
        assert metrics.status_code == 200
        assert metrics.json()["samples"] == 1

        rec = await client.get(
            "/api/agent/timeout-recommendation",
            params={"task_type": "test", "provider": "codex", "baseline_seconds": 1800},
        )
        assert rec.status_code == 200
        assert rec.json()["mode"] == "fixed"
