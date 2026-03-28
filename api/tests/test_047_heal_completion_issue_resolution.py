"""Tests for Spec 047: Heal Completion → Issue Resolution.

Covers:
  R1  _record_resolution called for every cleared condition, with heal_task_id if present
  R2  JSONL record shape: condition, resolved_at (ISO8601 UTC), optional heal_task_id
  R3  MONITOR_PERSIST_RESOLVED=1 appends to monitor_issues.json resolved array
  R4  resolved array capped at 50 entries
  R5  open issues remain unchanged in semantics
  R6  GET /api/agent/monitor-issues includes resolved when present, omits when absent
  R7  derived fallback (missing/stale file) does not include resolved
  R8  resolution write failures are best-effort (log debug, no crash)
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers to import the private functions under test without running main().
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_monitor_module():
    """Import monitor_pipeline without executing any top-level side-effects."""
    spec = importlib.util.spec_from_file_location(
        "monitor_pipeline_047",
        str(_SCRIPTS_DIR / "monitor_pipeline.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # Pre-populate sys.modules so relative imports resolve, but keep it isolated
    sys.modules["monitor_pipeline_047"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def monitor():
    return _load_monitor_module()


# ---------------------------------------------------------------------------
# R1 + R2 — _record_resolution writes correct JSONL shape
# ---------------------------------------------------------------------------


class TestRecordResolution:
    """Unit tests for _record_resolution (R1, R2, R8)."""

    def test_writes_jsonl_without_heal_task_id(self, monitor, tmp_path):
        """R2: record without heal_task_id has condition + resolved_at only."""
        log = logging.getLogger("test")
        resolutions_file = tmp_path / "monitor_resolutions.jsonl"

        with patch.object(monitor, "LOG_DIR", str(tmp_path)), \
             patch.object(monitor, "RESOLUTIONS_FILE", str(resolutions_file)):
            monitor._record_resolution("stale_version", log, heal_task_id=None)

        assert resolutions_file.exists()
        record = json.loads(resolutions_file.read_text().strip())
        assert record["condition"] == "stale_version"
        assert "resolved_at" in record
        # Validate ISO8601 UTC
        dt = datetime.fromisoformat(record["resolved_at"].replace("Z", "+00:00"))
        assert dt.tzinfo is not None
        # heal_task_id must not be present (R2: optional key; no null/empty leakage)
        assert "heal_task_id" not in record

    def test_writes_jsonl_with_heal_task_id(self, monitor, tmp_path):
        """R1 + R2: when heal_task_id provided, it appears in the JSONL record."""
        log = logging.getLogger("test")
        resolutions_file = tmp_path / "monitor_resolutions.jsonl"

        with patch.object(monitor, "LOG_DIR", str(tmp_path)), \
             patch.object(monitor, "RESOLUTIONS_FILE", str(resolutions_file)):
            monitor._record_resolution("no_task_running", log, heal_task_id="task_heal_abc")

        record = json.loads(resolutions_file.read_text().strip())
        assert record["condition"] == "no_task_running"
        assert record["heal_task_id"] == "task_heal_abc"

    def test_appends_multiple_records(self, monitor, tmp_path):
        """Multiple calls produce multiple JSONL lines."""
        log = logging.getLogger("test")
        resolutions_file = tmp_path / "monitor_resolutions.jsonl"

        with patch.object(monitor, "LOG_DIR", str(tmp_path)), \
             patch.object(monitor, "RESOLUTIONS_FILE", str(resolutions_file)):
            monitor._record_resolution("cond_a", log)
            monitor._record_resolution("cond_b", log, heal_task_id="task_xyz")

        lines = resolutions_file.read_text().strip().splitlines()
        assert len(lines) == 2
        r0 = json.loads(lines[0])
        r1 = json.loads(lines[1])
        assert r0["condition"] == "cond_a"
        assert r1["condition"] == "cond_b"
        assert r1["heal_task_id"] == "task_xyz"

    def test_write_failure_does_not_crash(self, monitor, tmp_path):
        """R8: write failure is caught and logged at debug; no exception propagates."""
        log = logging.getLogger("test")
        # Point to an unwritable path (directory instead of file)
        bad_path = str(tmp_path / "is_a_dir" / "subfile.jsonl")

        with patch.object(monitor, "LOG_DIR", str(tmp_path)), \
             patch.object(monitor, "RESOLUTIONS_FILE", bad_path):
            # Must not raise
            monitor._record_resolution("api_unreachable", log, heal_task_id=None)

    def test_creates_log_dir_if_missing(self, monitor, tmp_path):
        """_record_resolution creates LOG_DIR if it does not exist."""
        log = logging.getLogger("test")
        new_dir = tmp_path / "new_logs"
        resolutions_file = new_dir / "monitor_resolutions.jsonl"

        with patch.object(monitor, "LOG_DIR", str(new_dir)), \
             patch.object(monitor, "RESOLUTIONS_FILE", str(resolutions_file)):
            monitor._record_resolution("stale_version", log)

        assert resolutions_file.exists()


# ---------------------------------------------------------------------------
# R3 + R4 + R5 — _persist_resolved_to_issues_file
# ---------------------------------------------------------------------------


class TestPersistResolvedToIssuesFile:
    """Unit tests for _persist_resolved_to_issues_file (R3, R4, R5)."""

    def _make_data(self, resolved: list | None = None, issues: list | None = None) -> dict:
        data: dict[str, Any] = {
            "issues": issues or [],
            "last_check": "2026-03-28T10:00:00+00:00",
            "history": [],
        }
        if resolved is not None:
            data["resolved"] = resolved
        return data

    def test_creates_resolved_array_when_absent(self, monitor):
        """R3: creates resolved array if not present."""
        log = logging.getLogger("test")
        data = self._make_data()
        monitor._persist_resolved_to_issues_file(
            data, condition="stale_version", resolved_at="2026-03-28T10:10:00+00:00", log=log
        )
        assert "resolved" in data
        assert len(data["resolved"]) == 1
        entry = data["resolved"][0]
        assert entry["condition"] == "stale_version"
        assert entry["resolved_at"] == "2026-03-28T10:10:00+00:00"

    def test_appends_entry_with_heal_task_id_and_issue_id(self, monitor):
        """R3: entry includes heal_task_id and issue_id when provided."""
        log = logging.getLogger("test")
        data = self._make_data(resolved=[])
        monitor._persist_resolved_to_issues_file(
            data,
            condition="no_task_running",
            resolved_at="2026-03-28T10:10:00+00:00",
            log=log,
            heal_task_id="task_heal_abc",
            issue_id="bbb22222",
        )
        entry = data["resolved"][-1]
        assert entry["heal_task_id"] == "task_heal_abc"
        assert entry["issue_id"] == "bbb22222"

    def test_no_heal_task_id_leakage(self, monitor):
        """R3 edge: heal_task_id absent → must not appear as null in entry."""
        log = logging.getLogger("test")
        data = self._make_data(resolved=[])
        monitor._persist_resolved_to_issues_file(
            data,
            condition="stale_version",
            resolved_at="2026-03-28T10:10:00+00:00",
            log=log,
            heal_task_id=None,
        )
        entry = data["resolved"][-1]
        assert "heal_task_id" not in entry

    def test_cap_at_50_entries(self, monitor):
        """R4: resolved array capped at 50; oldest entries dropped, newest last."""
        log = logging.getLogger("test")
        existing = [
            {"condition": f"old_cond_{i}", "resolved_at": "2026-03-01T00:00:00+00:00"}
            for i in range(50)
        ]
        data = self._make_data(resolved=existing)
        monitor._persist_resolved_to_issues_file(
            data,
            condition="api_error",
            resolved_at="2026-03-28T10:10:00+00:00",
            log=log,
            heal_task_id="task_fix_api",
        )
        assert len(data["resolved"]) == 50
        # Newest entry is last
        assert data["resolved"][-1]["condition"] == "api_error"
        assert data["resolved"][-1]["heal_task_id"] == "task_fix_api"
        # Oldest entry (old_cond_0) dropped
        conditions = [e["condition"] for e in data["resolved"]]
        assert "old_cond_0" not in conditions

    def test_cap_does_not_exceed_50(self, monitor):
        """R4: cap works even when called multiple times."""
        log = logging.getLogger("test")
        existing = [
            {"condition": f"c{i}", "resolved_at": "2026-03-01T00:00:00+00:00"}
            for i in range(49)
        ]
        data = self._make_data(resolved=existing)
        for i in range(5):
            monitor._persist_resolved_to_issues_file(
                data,
                condition=f"new_cond_{i}",
                resolved_at="2026-03-28T10:10:00+00:00",
                log=log,
            )
        assert len(data["resolved"]) == 50

    def test_open_issues_unchanged(self, monitor):
        """R5: open issues in data['issues'] are not affected."""
        log = logging.getLogger("test")
        open_issue = {
            "id": "aaa11111",
            "condition": "some_other_issue",
            "severity": "high",
            "priority": 1,
            "message": "Something",
            "suggested_action": "Fix it",
            "created_at": "2026-03-28T09:00:00+00:00",
            "resolved_at": None,
        }
        data = self._make_data(issues=[open_issue])
        monitor._persist_resolved_to_issues_file(
            data,
            condition="stale_version",
            resolved_at="2026-03-28T10:10:00+00:00",
            log=log,
        )
        # issues unchanged
        assert len(data["issues"]) == 1
        assert data["issues"][0]["id"] == "aaa11111"
        assert data["issues"][0]["resolved_at"] is None


# ---------------------------------------------------------------------------
# R6 + R7 — resolve_monitor_issues_payload (API pass-through)
# ---------------------------------------------------------------------------


class TestResolveMonitorIssuesPayload:
    """Tests for resolve_monitor_issues_payload via agent_monitor_helpers (R6, R7)."""

    def _write_issues_file(self, logs_dir: Path, payload: dict) -> None:
        (logs_dir / "monitor_issues.json").write_text(json.dumps(payload), encoding="utf-8")

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def test_returns_resolved_when_present_in_file(self, tmp_path):
        """R6: resolved field passes through when present in monitor_issues.json."""
        from app.routers.agent_monitor_helpers import resolve_monitor_issues_payload

        resolved_entries = [
            {
                "condition": "api_unreachable",
                "resolved_at": "2026-03-28T10:10:00+00:00",
                "heal_task_id": "task_abc123",
                "issue_id": "abc12345",
            }
        ]
        now = self._now()
        payload = {
            "issues": [],
            "last_check": now.isoformat(),
            "history": [],
            "resolved_since_last": ["api_unreachable"],
            "resolved": resolved_entries,
        }
        self._write_issues_file(tmp_path, payload)

        result = resolve_monitor_issues_payload(str(tmp_path), now=now)
        assert "resolved" in result
        assert len(result["resolved"]) == 1
        assert result["resolved"][0]["condition"] == "api_unreachable"
        assert result["resolved"][0]["heal_task_id"] == "task_abc123"

    def test_no_resolved_when_absent_from_file(self, tmp_path):
        """R6: resolved key absent from response when not in file (backward compat)."""
        from app.routers.agent_monitor_helpers import resolve_monitor_issues_payload

        now = self._now()
        payload = {
            "issues": [],
            "last_check": now.isoformat(),
            "history": [],
        }
        self._write_issues_file(tmp_path, payload)

        result = resolve_monitor_issues_payload(str(tmp_path), now=now)
        assert "resolved" not in result
        assert "issues" in result

    def test_missing_file_fallback_has_no_resolved(self, tmp_path):
        """R7: missing monitor_issues.json → derived fallback excludes resolved."""
        from app.routers.agent_monitor_helpers import resolve_monitor_issues_payload

        now = self._now()
        # No file written — tmp_path is empty
        result = resolve_monitor_issues_payload(str(tmp_path), now=now)
        assert "resolved" not in result
        assert result.get("issues") is not None  # fallback has issues key

    def test_stale_file_fallback_has_no_resolved(self, tmp_path):
        """R7: stale monitor_issues.json → derived fallback excludes resolved."""
        from app.routers.agent_monitor_helpers import resolve_monitor_issues_payload

        # Write a file with a timestamp far in the past
        stale_payload = {
            "issues": [],
            "last_check": "2020-01-01T00:00:00+00:00",
            "history": [],
            "resolved": [{"condition": "x", "resolved_at": "2020-01-01T00:00:00+00:00"}],
        }
        self._write_issues_file(tmp_path, stale_payload)

        now = self._now()
        result = resolve_monitor_issues_payload(str(tmp_path), now=now)
        assert "resolved" not in result

    def test_response_http_200_with_missing_file(self, tmp_path):
        """R7: missing file must return safe fallback dict, not raise (HTTP 200)."""
        from app.routers.agent_monitor_helpers import resolve_monitor_issues_payload

        # Should not raise any exception
        result = resolve_monitor_issues_payload(str(tmp_path), now=self._now())
        assert isinstance(result, dict)
        assert "issues" in result

    def test_fresh_file_with_open_issues_and_resolved(self, tmp_path):
        """R6: both issues and resolved pass through unchanged from file."""
        from app.routers.agent_monitor_helpers import resolve_monitor_issues_payload

        now = self._now()
        open_issue = {
            "id": "abc12345",
            "condition": "api_unreachable",
            "severity": "high",
            "priority": 1,
            "message": "API unreachable",
            "suggested_action": "Restart API",
            "created_at": "2026-03-28T10:00:00+00:00",
            "resolved_at": None,
            "heal_task_id": "task_abc123",
        }
        resolved_entry = {
            "condition": "stale_version",
            "resolved_at": "2026-03-28T10:05:00+00:00",
            "heal_task_id": "task_old_heal",
        }
        payload = {
            "issues": [open_issue],
            "last_check": now.isoformat(),
            "history": [],
            "resolved_since_last": [],
            "resolved": [resolved_entry],
        }
        self._write_issues_file(tmp_path, payload)

        result = resolve_monitor_issues_payload(str(tmp_path), now=now)
        assert len(result["issues"]) == 1
        assert result["issues"][0]["id"] == "abc12345"
        assert len(result["resolved"]) == 1
        assert result["resolved"][0]["condition"] == "stale_version"


# ---------------------------------------------------------------------------
# R2 edge — JSONL field shapes
# ---------------------------------------------------------------------------


class TestResolutionRecordShape:
    """Strict shape validation for JSONL resolution records (R2)."""

    def test_record_has_required_fields(self, monitor, tmp_path):
        """R2: condition and resolved_at are always present."""
        log = logging.getLogger("test")
        resolutions_file = tmp_path / "monitor_resolutions.jsonl"
        with patch.object(monitor, "LOG_DIR", str(tmp_path)), \
             patch.object(monitor, "RESOLUTIONS_FILE", str(resolutions_file)):
            monitor._record_resolution("executor_fail", log)
        record = json.loads(resolutions_file.read_text().strip())
        assert "condition" in record
        assert "resolved_at" in record

    def test_resolved_at_is_utc_iso8601(self, monitor, tmp_path):
        """R2: resolved_at is a valid ISO8601 UTC timestamp."""
        log = logging.getLogger("test")
        resolutions_file = tmp_path / "monitor_resolutions.jsonl"
        with patch.object(monitor, "LOG_DIR", str(tmp_path)), \
             patch.object(monitor, "RESOLUTIONS_FILE", str(resolutions_file)):
            monitor._record_resolution("low_success_rate", log)
        record = json.loads(resolutions_file.read_text().strip())
        ts = record["resolved_at"]
        # Must parse as ISO8601; must include timezone info
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert dt.tzinfo is not None

    def test_heal_task_id_absent_when_none(self, monitor, tmp_path):
        """R2 edge: heal_task_id key must not appear when not passed."""
        log = logging.getLogger("test")
        resolutions_file = tmp_path / "monitor_resolutions.jsonl"
        with patch.object(monitor, "LOG_DIR", str(tmp_path)), \
             patch.object(monitor, "RESOLUTIONS_FILE", str(resolutions_file)):
            monitor._record_resolution("orphan_running", log, heal_task_id=None)
        record = json.loads(resolutions_file.read_text().strip())
        assert "heal_task_id" not in record

    def test_heal_task_id_present_when_given(self, monitor, tmp_path):
        """R2: heal_task_id appears with correct value when passed."""
        log = logging.getLogger("test")
        resolutions_file = tmp_path / "monitor_resolutions.jsonl"
        with patch.object(monitor, "LOG_DIR", str(tmp_path)), \
             patch.object(monitor, "RESOLUTIONS_FILE", str(resolutions_file)):
            monitor._record_resolution("api_unreachable", log, heal_task_id="task_xyz_999")
        record = json.loads(resolutions_file.read_text().strip())
        assert record["heal_task_id"] == "task_xyz_999"
