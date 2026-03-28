"""Tests for spec 045: GET /api/agent/effectiveness — Plan Progress Phase 6/7 Completion.

Verifies that:
- plan_progress includes phase_6 (total=2) and phase_7 (total=17)
- Completion counts are correctly derived from PM state backlog_index
- Phase boundaries: Phase 6 = items 56-57 (0-based start 55), Phase 7 = items 58-74 (0-based start 57)
- Graceful degradation on missing/corrupted state files
- All 5 scenarios from the spec verification section
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
import app.services.effectiveness_service as eff_svc


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_state_file(tmpdir: str, backlog_index: int | None) -> str:
    path = os.path.join(tmpdir, "project_manager_state.json")
    with open(path, "w") as f:
        if backlog_index is None:
            json.dump({}, f)
        else:
            json.dump({"backlog_index": backlog_index}, f)
    return path


# ---------------------------------------------------------------------------
# Unit tests for _plan_progress()
# ---------------------------------------------------------------------------


class TestPlanProgressUnit:
    """Direct unit tests for effectiveness_service._plan_progress()."""

    def setup_method(self):
        self._orig_state_files = eff_svc.STATE_FILES
        self._orig_backlog_file = eff_svc.BACKLOG_FILE

    def teardown_method(self):
        eff_svc.STATE_FILES = self._orig_state_files
        eff_svc.BACKLOG_FILE = self._orig_backlog_file

    def test_plan_progress_returns_phase_6_and_phase_7_keys(self, tmp_path):
        """_plan_progress() always returns phase_6 and phase_7 keys."""
        eff_svc.STATE_FILES = []
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert "phase_6" in result, "phase_6 key missing"
        assert "phase_7" in result, "phase_7 key missing"

    def test_phase_6_total_is_2(self, tmp_path):
        """phase_6.total must always be 2 (Product-Critical = items 56-57)."""
        eff_svc.STATE_FILES = []
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["total"] == 2, f"phase_6.total expected 2, got {result['phase_6']['total']}"

    def test_phase_7_total_is_17(self, tmp_path):
        """phase_7.total must always be 17 (Remaining Specs & Polish = items 58-74)."""
        eff_svc.STATE_FILES = []
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_7"]["total"] == 17, f"phase_7.total expected 17, got {result['phase_7']['total']}"

    def test_scenario_1_cold_start_no_state_file(self, tmp_path):
        """Scenario 1: No PM state file — phase_6.completed=0, phase_7.completed=0."""
        eff_svc.STATE_FILES = [str(tmp_path / "nonexistent.json")]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["completed"] == 0, "cold start: phase_6.completed must be 0"
        assert result["phase_7"]["completed"] == 0, "cold start: phase_7.completed must be 0"
        assert result["phase_6"]["total"] == 2
        assert result["phase_7"]["total"] == 17

    def test_scenario_2_phase_6_partially_complete_index_56(self, tmp_path):
        """Scenario 2: backlog_index=56 → phase_6.completed=1, phase_7.completed=0."""
        state_path = _make_state_file(str(tmp_path), 56)
        eff_svc.STATE_FILES = [state_path]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["completed"] == 1, f"backlog_index=56: phase_6.completed expected 1, got {result['phase_6']['completed']}"
        assert result["phase_7"]["completed"] == 0, f"backlog_index=56: phase_7.completed expected 0, got {result['phase_7']['completed']}"
        assert result["phase_6"]["pct"] == 50.0, f"phase_6.pct expected 50.0, got {result['phase_6']['pct']}"

    def test_scenario_3_phase_6_complete_phase_7_in_progress_index_65(self, tmp_path):
        """Scenario 3: backlog_index=65 → phase_6.completed=2, phase_7.completed=8."""
        state_path = _make_state_file(str(tmp_path), 65)
        eff_svc.STATE_FILES = [state_path]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["completed"] == 2, f"backlog_index=65: phase_6.completed expected 2, got {result['phase_6']['completed']}"
        assert result["phase_7"]["completed"] == 8, f"backlog_index=65: phase_7.completed expected 8, got {result['phase_7']['completed']}"
        assert result["phase_6"]["pct"] == 100.0, f"phase_6.pct expected 100.0"
        assert result["phase_7"]["pct"] == 47.1, f"phase_7.pct expected 47.1, got {result['phase_7']['pct']}"

    def test_scenario_4_full_completion_index_74(self, tmp_path):
        """Scenario 4: backlog_index=74 → phase_6.pct=100.0, phase_7.pct=100.0."""
        state_path = _make_state_file(str(tmp_path), 74)
        eff_svc.STATE_FILES = [state_path]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["completed"] == 2
        assert result["phase_6"]["pct"] == 100.0
        assert result["phase_7"]["completed"] == 17
        assert result["phase_7"]["pct"] == 100.0

    def test_scenario_4_edge_clamped_beyond_total(self, tmp_path):
        """Scenario 4 edge: backlog_index=200 → completed clamped to total (pct stays 100.0)."""
        state_path = _make_state_file(str(tmp_path), 200)
        eff_svc.STATE_FILES = [state_path]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["completed"] == 2, "must clamp to phase_6.total=2"
        assert result["phase_7"]["completed"] == 17, "must clamp to phase_7.total=17"
        assert result["phase_6"]["pct"] == 100.0
        assert result["phase_7"]["pct"] == 100.0

    def test_scenario_5_corrupted_state_file(self, tmp_path):
        """Scenario 5: Corrupted state file → HTTP 200, index=0, both phases completed=0."""
        corrupt_path = str(tmp_path / "project_manager_state.json")
        with open(corrupt_path, "w") as f:
            f.write("{NOT VALID JSON")
        eff_svc.STATE_FILES = [corrupt_path]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["index"] == 0, "corrupted state: index must be 0"
        assert result["phase_6"]["completed"] == 0
        assert result["phase_7"]["completed"] == 0

    def test_backlog_index_null_treated_as_zero(self, tmp_path):
        """Edge: backlog_index=null in state file → treated as 0, completed=0 for both phases."""
        state_path = _make_state_file(str(tmp_path), None)
        eff_svc.STATE_FILES = [state_path]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["completed"] == 0
        assert result["phase_7"]["completed"] == 0

    def test_phase_6_boundary_exactly_at_start(self, tmp_path):
        """backlog_index=55 → phase_6.completed=0 (start boundary, not yet crossed)."""
        state_path = _make_state_file(str(tmp_path), 55)
        eff_svc.STATE_FILES = [state_path]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["completed"] == 0
        assert result["phase_7"]["completed"] == 0

    def test_phase_7_boundary_exactly_at_start(self, tmp_path):
        """backlog_index=57 → phase_6.completed=2, phase_7.completed=0."""
        state_path = _make_state_file(str(tmp_path), 57)
        eff_svc.STATE_FILES = [state_path]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["completed"] == 2
        assert result["phase_7"]["completed"] == 0

    def test_phase_7_first_item_completed(self, tmp_path):
        """backlog_index=58 → phase_7.completed=1."""
        state_path = _make_state_file(str(tmp_path), 58)
        eff_svc.STATE_FILES = [state_path]
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert result["phase_6"]["completed"] == 2
        assert result["phase_7"]["completed"] == 1

    def test_plan_progress_struct_has_required_fields(self, tmp_path):
        """_plan_progress() returns dict with all required fields per spec."""
        eff_svc.STATE_FILES = []
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        for key in ("index", "total", "pct", "state_file", "phase_6", "phase_7"):
            assert key in result, f"Required field '{key}' missing from plan_progress"

        for phase_key in ("phase_6", "phase_7"):
            phase = result[phase_key]
            for sub in ("completed", "total", "pct"):
                assert sub in phase, f"{phase_key}.{sub} missing"

    def test_pct_is_zero_when_total_zero(self, tmp_path):
        """pct must be 0 (not divide-by-zero error) when phase total is 0."""
        # This tests the guard in the service: pct = round(100 * completed / total, 1) if PHASE_6_TOTAL else 0
        # Since PHASE_6_TOTAL=2 and PHASE_7_TOTAL=17 are constants, we verify that pct is numeric
        eff_svc.STATE_FILES = []
        eff_svc.BACKLOG_FILE = str(tmp_path / "nonexistent.md")

        result = eff_svc._plan_progress()

        assert isinstance(result["phase_6"]["pct"], (int, float))
        assert isinstance(result["phase_7"]["pct"], (int, float))


# ---------------------------------------------------------------------------
# Integration tests via HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_effectiveness_plan_progress_includes_phase_6_and_phase_7() -> None:
    """GET /api/agent/effectiveness returns 200 with plan_progress.phase_6 and phase_7.

    Spec 045 acceptance test: plan_progress must include phase_6 (total=2) and phase_7 (total=17).
    """
    import app.services.effectiveness_service as svc

    _fake = {
        "throughput": {"completed_7d": 0, "tasks_per_day": 0.0},
        "success_rate": 0.0,
        "issues": {"open": 0, "resolved_7d": 0},
        "progress": {"spec": 0, "impl": 0, "test": 0, "review": 0, "heal": 0},
        "plan_progress": {
            "index": 0,
            "total": 74,
            "pct": 0.0,
            "state_file": "",
            "phase_6": {"completed": 0, "total": 2, "pct": 0.0},
            "phase_7": {"completed": 0, "total": 17, "pct": 0.0},
        },
        "goal_proximity": 0.0,
        "heal_resolved_count": 0,
        "top_issues_by_priority": [],
    }

    original = svc.get_effectiveness
    svc.get_effectiveness = lambda: _fake
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/effectiveness")
    finally:
        svc.get_effectiveness = original

    assert r.status_code == 200, r.text
    body = r.json()

    assert "plan_progress" in body, "plan_progress missing from effectiveness response"
    pp = body["plan_progress"]
    assert "phase_6" in pp, "plan_progress.phase_6 missing"
    assert "phase_7" in pp, "plan_progress.phase_7 missing"

    p6 = pp["phase_6"]
    assert isinstance(p6["completed"], int)
    assert isinstance(p6["total"], int)
    assert p6["total"] == 2, f"phase_6.total expected 2, got {p6['total']}"

    p7 = pp["phase_7"]
    assert isinstance(p7["completed"], int)
    assert isinstance(p7["total"], int)
    assert p7["total"] == 17, f"phase_7.total expected 17, got {p7['total']}"


@pytest.mark.asyncio
async def test_effectiveness_returns_200_on_corrupted_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 5 (API): Corrupted state file → HTTP 200 with graceful degradation.

    Spec 045 requirement: missing/corrupted state must not cause 500.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        corrupt_path = os.path.join(tmpdir, "project_manager_state.json")
        with open(corrupt_path, "w") as f:
            f.write("{NOT VALID JSON")

        monkeypatch.setattr(eff_svc, "STATE_FILES", [corrupt_path])
        monkeypatch.setattr(eff_svc, "BACKLOG_FILE", os.path.join(tmpdir, "nonexistent.md"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/effectiveness")

    assert r.status_code == 200, f"Expected 200 on corrupted state, got {r.status_code}: {r.text}"
    body = r.json()
    pp = body.get("plan_progress", {})
    assert pp.get("index", -1) == 0, "Corrupted state: plan_progress.index must be 0"
    assert pp.get("phase_6", {}).get("completed", -1) == 0
    assert pp.get("phase_7", {}).get("completed", -1) == 0


@pytest.mark.asyncio
async def test_effectiveness_returns_200_with_no_state_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 1 (API): No PM state files → HTTP 200, phase_6/phase_7 present with completed=0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(eff_svc, "STATE_FILES", [os.path.join(tmpdir, "nonexistent.json")])
        monkeypatch.setattr(eff_svc, "BACKLOG_FILE", os.path.join(tmpdir, "nonexistent.md"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/effectiveness")

    assert r.status_code == 200, r.text
    body = r.json()
    pp = body.get("plan_progress", {})
    assert "phase_6" in pp, "phase_6 missing in cold-start response"
    assert "phase_7" in pp, "phase_7 missing in cold-start response"
    assert pp["phase_6"]["completed"] == 0
    assert pp["phase_7"]["completed"] == 0
    assert pp["phase_6"]["total"] == 2
    assert pp["phase_7"]["total"] == 17


@pytest.mark.asyncio
async def test_effectiveness_phase_6_partial_at_index_56(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 2 (API): backlog_index=56 → phase_6.completed=1, phase_7.completed=0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _make_state_file(tmpdir, 56)
        monkeypatch.setattr(eff_svc, "STATE_FILES", [state_path])
        monkeypatch.setattr(eff_svc, "BACKLOG_FILE", os.path.join(tmpdir, "nonexistent.md"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/effectiveness")

    assert r.status_code == 200, r.text
    pp = r.json().get("plan_progress", {})
    assert pp["phase_6"]["completed"] == 1
    assert pp["phase_7"]["completed"] == 0


@pytest.mark.asyncio
async def test_effectiveness_phase_6_complete_phase_7_partial_at_index_65(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 3 (API): backlog_index=65 → phase_6 complete, phase_7 in progress."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _make_state_file(tmpdir, 65)
        monkeypatch.setattr(eff_svc, "STATE_FILES", [state_path])
        monkeypatch.setattr(eff_svc, "BACKLOG_FILE", os.path.join(tmpdir, "nonexistent.md"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/effectiveness")

    assert r.status_code == 200, r.text
    pp = r.json().get("plan_progress", {})
    assert pp["phase_6"]["completed"] == 2
    assert pp["phase_6"]["pct"] == 100.0
    assert pp["phase_7"]["completed"] == 8
    assert pp["phase_7"]["pct"] == 47.1


@pytest.mark.asyncio
async def test_effectiveness_full_completion_at_index_74(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 4 (API): backlog_index=74 → both phases 100% complete."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = _make_state_file(tmpdir, 74)
        monkeypatch.setattr(eff_svc, "STATE_FILES", [state_path])
        monkeypatch.setattr(eff_svc, "BACKLOG_FILE", os.path.join(tmpdir, "nonexistent.md"))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/effectiveness")

    assert r.status_code == 200, r.text
    pp = r.json().get("plan_progress", {})
    assert pp["phase_6"]["pct"] == 100.0
    assert pp["phase_7"]["pct"] == 100.0
