"""Tests for spec 045: GET /api/agent/effectiveness — Plan Progress Phase 6/7.

Verifies that:
- plan_progress contains phase_6 and phase_7 fields (spec 045 requirement)
- Phase 6 total == 2, Phase 7 total == 17
- Completion is derived from PM state backlog_index
- Graceful degradation on missing / corrupt state files
- Various index scenarios (cold start, partial, complete)
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state_file(tmp_dir: str, filename: str, content: Any) -> str:
    """Write content to a temp state file and return path."""
    path = os.path.join(tmp_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(content, str):
            f.write(content)
        else:
            json.dump(content, f)
    return path


# ---------------------------------------------------------------------------
# Unit tests for _plan_progress() — directly exercise the service function
# ---------------------------------------------------------------------------


def test_plan_progress_returns_phase_6_and_phase_7_keys() -> None:
    """_plan_progress() must include phase_6 and phase_7 in its output."""
    import app.services.effectiveness_service as eff_svc

    result = eff_svc._plan_progress()
    assert "phase_6" in result, "phase_6 missing from _plan_progress output"
    assert "phase_7" in result, "phase_7 missing from _plan_progress output"


def test_plan_progress_phase_totals() -> None:
    """Phase 6 total must be 2, Phase 7 total must be 17 (spec 045 constants)."""
    import app.services.effectiveness_service as eff_svc

    result = eff_svc._plan_progress()
    p6 = result["phase_6"]
    p7 = result["phase_7"]
    assert p6["total"] == 2, f"phase_6.total expected 2, got {p6['total']}"
    assert p7["total"] == 17, f"phase_7.total expected 17, got {p7['total']}"


def test_plan_progress_phase_completed_fields_are_ints() -> None:
    """phase_6.completed and phase_7.completed must be integers."""
    import app.services.effectiveness_service as eff_svc

    result = eff_svc._plan_progress()
    assert isinstance(result["phase_6"]["completed"], int)
    assert isinstance(result["phase_7"]["completed"], int)


def test_plan_progress_cold_start_no_state_file(tmp_path: Any) -> None:
    """With no state files present, phase_6.completed=0 and phase_7.completed=0."""
    import app.services.effectiveness_service as eff_svc

    nonexistent = [
        str(tmp_path / "nonexistent_1.json"),
        str(tmp_path / "nonexistent_2.json"),
    ]
    with patch.object(eff_svc, "STATE_FILES", nonexistent):
        result = eff_svc._plan_progress()

    assert result["phase_6"]["completed"] == 0
    assert result["phase_7"]["completed"] == 0
    assert result["index"] == 0


def test_plan_progress_phase_6_partially_complete_index_56(tmp_path: Any) -> None:
    """backlog_index=56 → phase_6.completed=1, phase_6.pct=50.0, phase_7.completed=0.

    Phase 6 spans items 56–57 (1-based), so index 56 means 1 item completed.
    Phase 6 start index (0-based in code) = 55, so completed = 56 - 55 = 1.
    """
    import app.services.effectiveness_service as eff_svc

    state_path = _make_state_file(str(tmp_path), "state.json", {"backlog_index": 56})
    with patch.object(eff_svc, "STATE_FILES", [state_path]):
        result = eff_svc._plan_progress()

    p6 = result["phase_6"]
    p7 = result["phase_7"]
    assert p6["completed"] == 1, f"Expected phase_6.completed=1, got {p6['completed']}"
    assert p6["pct"] == 50.0, f"Expected phase_6.pct=50.0, got {p6['pct']}"
    assert p7["completed"] == 0, f"Expected phase_7.completed=0, got {p7['completed']}"


def test_plan_progress_phase_6_complete_phase_7_in_progress_index_65(tmp_path: Any) -> None:
    """backlog_index=65 → phase_6.completed=2 (100%), phase_7.completed=8.

    Phase 7 start (0-based) = 57. completed = min(17, 65 - 57) = 8.
    """
    import app.services.effectiveness_service as eff_svc

    state_path = _make_state_file(str(tmp_path), "state.json", {"backlog_index": 65})
    with patch.object(eff_svc, "STATE_FILES", [state_path]):
        result = eff_svc._plan_progress()

    p6 = result["phase_6"]
    p7 = result["phase_7"]
    assert p6["completed"] == 2, f"Expected phase_6.completed=2, got {p6['completed']}"
    assert p6["pct"] == 100.0, f"Expected phase_6.pct=100.0, got {p6['pct']}"
    assert p7["completed"] == 8, f"Expected phase_7.completed=8, got {p7['completed']}"


def test_plan_progress_full_completion_index_74(tmp_path: Any) -> None:
    """backlog_index=74 → phase_6.pct=100.0, phase_7.pct=100.0."""
    import app.services.effectiveness_service as eff_svc

    state_path = _make_state_file(str(tmp_path), "state.json", {"backlog_index": 74})
    with patch.object(eff_svc, "STATE_FILES", [state_path]):
        result = eff_svc._plan_progress()

    assert result["phase_6"]["pct"] == 100.0
    assert result["phase_7"]["pct"] == 100.0


def test_plan_progress_corrupted_state_file_graceful(tmp_path: Any) -> None:
    """Corrupted JSON in state file → graceful 200, completed=0 for both phases."""
    import app.services.effectiveness_service as eff_svc

    state_path = _make_state_file(str(tmp_path), "state.json", "{NOT VALID JSON")
    with patch.object(eff_svc, "STATE_FILES", [state_path]):
        result = eff_svc._plan_progress()

    assert result["index"] == 0
    assert result["phase_6"]["completed"] == 0
    assert result["phase_7"]["completed"] == 0


def test_plan_progress_null_backlog_index_treated_as_zero(tmp_path: Any) -> None:
    """backlog_index=null in state file → index=0, completed=0 for both phases."""
    import app.services.effectiveness_service as eff_svc

    state_path = _make_state_file(str(tmp_path), "state.json", {"backlog_index": None})
    with patch.object(eff_svc, "STATE_FILES", [state_path]):
        result = eff_svc._plan_progress()

    assert result["index"] == 0
    assert result["phase_6"]["completed"] == 0
    assert result["phase_7"]["completed"] == 0


def test_plan_progress_overshoot_index_clamped(tmp_path: Any) -> None:
    """backlog_index=200 → completed clamped to total; pct stays 100.0."""
    import app.services.effectiveness_service as eff_svc

    state_path = _make_state_file(str(tmp_path), "state.json", {"backlog_index": 200})
    with patch.object(eff_svc, "STATE_FILES", [state_path]):
        result = eff_svc._plan_progress()

    p6 = result["phase_6"]
    p7 = result["phase_7"]
    assert p6["completed"] == p6["total"]
    assert p7["completed"] == p7["total"]
    assert p6["pct"] == 100.0
    assert p7["pct"] == 100.0


def test_plan_progress_pct_fields_are_float(tmp_path: Any) -> None:
    """phase_6.pct and phase_7.pct must be floats (or int 0), not None."""
    import app.services.effectiveness_service as eff_svc

    state_path = _make_state_file(str(tmp_path), "state.json", {"backlog_index": 60})
    with patch.object(eff_svc, "STATE_FILES", [state_path]):
        result = eff_svc._plan_progress()

    assert isinstance(result["phase_6"]["pct"], (int, float))
    assert isinstance(result["phase_7"]["pct"], (int, float))


# ---------------------------------------------------------------------------
# Integration tests — call GET /api/agent/effectiveness via HTTP client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_effectiveness_endpoint_returns_200() -> None:
    """GET /api/agent/effectiveness returns HTTP 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/effectiveness")
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_effectiveness_endpoint_plan_progress_present() -> None:
    """GET /api/agent/effectiveness response contains plan_progress."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/effectiveness")
    body = r.json()
    assert "plan_progress" in body, "plan_progress missing from effectiveness response"


@pytest.mark.asyncio
async def test_effectiveness_endpoint_phase_6_and_phase_7_present() -> None:
    """GET /api/agent/effectiveness plan_progress includes phase_6 and phase_7 keys."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/effectiveness")
    pp = r.json()["plan_progress"]
    assert "phase_6" in pp, "plan_progress.phase_6 missing"
    assert "phase_7" in pp, "plan_progress.phase_7 missing"


@pytest.mark.asyncio
async def test_effectiveness_endpoint_phase_totals_correct() -> None:
    """Phase 6 total must be 2, Phase 7 total must be 17 via the live endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/effectiveness")
    pp = r.json()["plan_progress"]
    assert pp["phase_6"]["total"] == 2, f"phase_6.total expected 2, got {pp['phase_6']['total']}"
    assert pp["phase_7"]["total"] == 17, f"phase_7.total expected 17, got {pp['phase_7']['total']}"


@pytest.mark.asyncio
async def test_effectiveness_endpoint_phase_completed_are_ints() -> None:
    """phase_6.completed and phase_7.completed must be integers."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/effectiveness")
    pp = r.json()["plan_progress"]
    assert isinstance(pp["phase_6"]["completed"], int)
    assert isinstance(pp["phase_7"]["completed"], int)


@pytest.mark.asyncio
async def test_effectiveness_endpoint_with_mocked_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/effectiveness with monkeypatched service returns expected plan_progress shape."""
    import app.services.effectiveness_service as eff_svc

    _fake = {
        "throughput": {"completed_7d": 0, "tasks_per_day": 0.0},
        "success_rate": 0.0,
        "issues": {"open": 0, "resolved_7d": 0},
        "progress": {"spec": 0, "impl": 0, "test": 0, "review": 0, "heal": 0},
        "plan_progress": {
            "index": 56,
            "total": 74,
            "pct": 75.7,
            "state_file": "project_manager_state.json",
            "phase_6": {"completed": 1, "total": 2, "pct": 50.0},
            "phase_7": {"completed": 0, "total": 17, "pct": 0.0},
        },
        "goal_proximity": 0.0,
        "heal_resolved_count": 0,
        "top_issues_by_priority": [],
    }
    monkeypatch.setattr(eff_svc, "get_effectiveness", lambda: _fake)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/effectiveness")

    assert r.status_code == 200
    pp = r.json()["plan_progress"]
    assert pp["phase_6"]["completed"] == 1
    assert pp["phase_6"]["total"] == 2
    assert pp["phase_6"]["pct"] == 50.0
    assert pp["phase_7"]["completed"] == 0
    assert pp["phase_7"]["total"] == 17


@pytest.mark.asyncio
async def test_effectiveness_endpoint_existing_fields_retained() -> None:
    """All existing effectiveness fields remain present alongside plan_progress (non-regression)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/effectiveness")
    body = r.json()
    for field in ("throughput", "success_rate", "issues", "progress", "plan_progress", "goal_proximity"):
        assert field in body, f"Existing field {field!r} missing from effectiveness response"
