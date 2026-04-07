"""Tests for heal-completion-issue-resolution spec (047).

Covers:
  1. Resolution recorded to JSONL with heal_task_id when present
  2. Resolution recorded without heal_task_id when absent
  3. Resolved array capped at 50 with FIFO eviction
  4. Resolved array not written when MONITOR_PERSIST_RESOLVED unset
  5. /api/agent/monitor-issues returns resolved array
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers to import monitor functions without running the full script
# ---------------------------------------------------------------------------
_api_dir = str(Path(__file__).resolve().parents[1])
import sys
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from scripts.monitor_pipeline import (
    _record_resolution,
    _persist_resolved_to_issues_file,
)

log = logging.getLogger("test_monitor_resolution")


# ── 1. Resolution recorded to JSONL with heal_task_id when present ────────

def test_record_resolution_with_heal_task_id(tmp_path, monkeypatch):
    """When a condition clears and the prior issue had heal_task_id, the
    JSONL record must include heal_task_id."""
    jsonl_path = str(tmp_path / "monitor_resolutions.jsonl")
    monkeypatch.setattr(
        "scripts.monitor_pipeline.RESOLUTIONS_FILE", jsonl_path
    )
    monkeypatch.setattr(
        "scripts.monitor_pipeline.LOG_DIR", str(tmp_path)
    )

    _record_resolution("api_unreachable", log, heal_task_id="task_heal_123")

    lines = Path(jsonl_path).read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["condition"] == "api_unreachable"
    assert rec["heal_task_id"] == "task_heal_123"
    assert "resolved_at" in rec


# ── 2. Resolution recorded without heal_task_id when absent ───────────────

def test_record_resolution_without_heal_task_id(tmp_path, monkeypatch):
    """When the prior issue had no heal_task_id, the JSONL record must NOT
    contain a heal_task_id key (no null/empty leakage)."""
    jsonl_path = str(tmp_path / "monitor_resolutions.jsonl")
    monkeypatch.setattr(
        "scripts.monitor_pipeline.RESOLUTIONS_FILE", jsonl_path
    )
    monkeypatch.setattr(
        "scripts.monitor_pipeline.LOG_DIR", str(tmp_path)
    )

    _record_resolution("stale_version", log, heal_task_id=None)

    lines = Path(jsonl_path).read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["condition"] == "stale_version"
    assert "heal_task_id" not in rec


# ── 3. Resolved array capped at 50 with FIFO eviction ────────────────────

def test_persist_resolved_caps_at_50():
    """When resolved list already has 50 entries, appending a new one drops
    the oldest (FIFO) to stay at 50."""
    data: dict = {
        "issues": [],
        "resolved": [
            {"condition": f"old_cond_{i}", "resolved_at": "2026-03-01T00:00:00Z"}
            for i in range(50)
        ],
    }
    assert len(data["resolved"]) == 50

    _persist_resolved_to_issues_file(
        data,
        condition="new_condition",
        resolved_at="2026-04-07T00:00:00Z",
        log=log,
        heal_task_id="task_fix",
        issue_id="iss_001",
    )

    resolved = data["resolved"]
    assert len(resolved) == 50, f"Expected 50, got {len(resolved)}"
    # Oldest (old_cond_0) should have been evicted
    conditions = [r["condition"] for r in resolved]
    assert "old_cond_0" not in conditions, "Oldest entry should be evicted"
    # Newest should be last
    assert resolved[-1]["condition"] == "new_condition"
    assert resolved[-1]["heal_task_id"] == "task_fix"
    assert resolved[-1]["issue_id"] == "iss_001"


def test_persist_resolved_under_cap():
    """When resolved list has fewer than 50, append without eviction."""
    data: dict = {"issues": [], "resolved": []}

    _persist_resolved_to_issues_file(
        data,
        condition="first_resolve",
        resolved_at="2026-04-07T00:00:00Z",
        log=log,
    )

    assert len(data["resolved"]) == 1
    assert data["resolved"][0]["condition"] == "first_resolve"
    assert "heal_task_id" not in data["resolved"][0]


def test_persist_resolved_omits_heal_task_id_when_absent():
    """When heal_task_id is None, the entry must NOT contain that key."""
    data: dict = {"issues": []}

    _persist_resolved_to_issues_file(
        data,
        condition="some_cond",
        resolved_at="2026-04-07T00:00:00Z",
        log=log,
        heal_task_id=None,
        issue_id=None,
    )

    entry = data["resolved"][0]
    assert "heal_task_id" not in entry
    assert "issue_id" not in entry


# ── 4. Resolved array not written when MONITOR_PERSIST_RESOLVED unset ────

def test_resolved_not_persisted_when_env_unset(tmp_path, monkeypatch):
    """When MONITOR_PERSIST_RESOLVED is not set (or not '1'), the saved
    monitor_issues.json must NOT contain a 'resolved' key."""
    issues_file = tmp_path / "monitor_issues.json"
    # Pre-populate with an existing resolved array (from a prior run when
    # the env var was set)
    initial = {
        "issues": [
            {
                "id": "aaa11111",
                "condition": "stale_version",
                "severity": "high",
                "priority": 1,
                "message": "Old code",
                "suggested_action": "Restart",
                "created_at": "2026-03-28T09:00:00Z",
                "resolved_at": None,
            }
        ],
        "last_check": "2026-03-28T09:00:00Z",
        "history": [],
        "resolved": [
            {"condition": "old_resolved", "resolved_at": "2026-03-01T00:00:00Z"}
        ],
    }
    issues_file.write_text(json.dumps(initial))

    monkeypatch.setattr("scripts.monitor_pipeline.ISSUES_FILE", str(issues_file))
    monkeypatch.setattr("scripts.monitor_pipeline.LOG_DIR", str(tmp_path))
    monkeypatch.setattr(
        "scripts.monitor_pipeline.RESOLUTIONS_FILE",
        str(tmp_path / "monitor_resolutions.jsonl"),
    )
    # Ensure MONITOR_PERSIST_RESOLVED is NOT set
    monkeypatch.delenv("MONITOR_PERSIST_RESOLVED", raising=False)

    from scripts.monitor_pipeline import _load_issues, _save_issues

    data = _load_issues()
    # Simulate the resolution logic: condition clears
    prev_conditions = {i["condition"] for i in data.get("issues", [])}
    data["issues"] = []  # all conditions cleared
    current_conditions: set = set()
    resolved_this_run = prev_conditions - current_conditions

    persist_resolved = os.environ.get("MONITOR_PERSIST_RESOLVED") == "1"

    resolved_at_ts = datetime.now(timezone.utc).isoformat()
    for cond in resolved_this_run:
        _record_resolution(cond, log)
        if persist_resolved:
            _persist_resolved_to_issues_file(
                data, condition=cond, resolved_at=resolved_at_ts, log=log
            )
    data["resolved_since_last"] = list(resolved_this_run)

    # R6: strip resolved when env var is not set
    if not persist_resolved:
        data.pop("resolved", None)

    _save_issues(data)

    saved = json.loads(issues_file.read_text())
    assert "resolved" not in saved, (
        "resolved key should not be present when MONITOR_PERSIST_RESOLVED is unset"
    )
    assert "resolved_since_last" in saved
    assert "stale_version" in saved["resolved_since_last"]


def test_resolved_persisted_when_env_set(tmp_path, monkeypatch):
    """When MONITOR_PERSIST_RESOLVED=1, the saved file must contain resolved."""
    issues_file = tmp_path / "monitor_issues.json"
    initial = {
        "issues": [
            {
                "id": "bbb22222",
                "condition": "no_task_running",
                "severity": "high",
                "priority": 1,
                "message": "No task running",
                "suggested_action": "Check pipeline",
                "created_at": "2026-03-28T09:00:00Z",
                "resolved_at": None,
                "heal_task_id": "task_heal_abc",
            }
        ],
        "last_check": "2026-03-28T09:00:00Z",
        "history": [],
    }
    issues_file.write_text(json.dumps(initial))

    monkeypatch.setattr("scripts.monitor_pipeline.ISSUES_FILE", str(issues_file))
    monkeypatch.setattr("scripts.monitor_pipeline.LOG_DIR", str(tmp_path))
    monkeypatch.setattr(
        "scripts.monitor_pipeline.RESOLUTIONS_FILE",
        str(tmp_path / "monitor_resolutions.jsonl"),
    )
    monkeypatch.setenv("MONITOR_PERSIST_RESOLVED", "1")

    from scripts.monitor_pipeline import _load_issues, _save_issues

    data = _load_issues()
    prev_issues = data.get("issues") or []
    prev_conditions = {i["condition"] for i in prev_issues}
    prev_condition_to_heal_task = {
        i["condition"]: i["heal_task_id"]
        for i in prev_issues
        if i.get("heal_task_id")
    }
    prev_condition_to_issue_id = {
        i["condition"]: i["id"] for i in prev_issues if i.get("id")
    }

    data["issues"] = []  # condition cleared
    current_conditions: set = set()
    resolved_this_run = prev_conditions - current_conditions
    persist_resolved = os.environ.get("MONITOR_PERSIST_RESOLVED") == "1"

    resolved_at_ts = datetime.now(timezone.utc).isoformat()
    for cond in resolved_this_run:
        htid = prev_condition_to_heal_task.get(cond)
        _record_resolution(cond, log, heal_task_id=htid)
        if persist_resolved:
            _persist_resolved_to_issues_file(
                data,
                condition=cond,
                resolved_at=resolved_at_ts,
                log=log,
                heal_task_id=htid,
                issue_id=prev_condition_to_issue_id.get(cond),
            )
    data["resolved_since_last"] = list(resolved_this_run)
    if not persist_resolved:
        data.pop("resolved", None)

    _save_issues(data)

    saved = json.loads(issues_file.read_text())
    assert "resolved" in saved
    assert len(saved["resolved"]) == 1
    entry = saved["resolved"][0]
    assert entry["condition"] == "no_task_running"
    assert entry["heal_task_id"] == "task_heal_abc"
    assert entry["issue_id"] == "bbb22222"

    # Verify JSONL too
    jsonl_path = tmp_path / "monitor_resolutions.jsonl"
    lines = jsonl_path.read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["condition"] == "no_task_running"
    assert rec["heal_task_id"] == "task_heal_abc"


# ── 5. GET /api/agent/monitor-issues returns resolved array ──────────────

@pytest.mark.asyncio
async def test_api_returns_resolved_array(tmp_path, monkeypatch):
    """GET /api/agent/monitor-issues returns file content as-is, including
    any resolved array when present."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from app.routers.agent_issues_routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api/agent")

    issues_data = {
        "issues": [],
        "last_check": datetime.now(timezone.utc).isoformat(),
        "history": [],
        "resolved_since_last": ["api_unreachable"],
        "resolved": [
            {
                "condition": "api_unreachable",
                "resolved_at": "2026-03-28T10:10:00Z",
                "heal_task_id": "task_abc123",
                "issue_id": "abc12345",
            }
        ],
    }

    issues_path = tmp_path / "monitor_issues.json"
    issues_path.write_text(json.dumps(issues_data))

    # Monkeypatch the agent_monitor_helpers to point at our tmp dir
    from app.routers import agent_monitor_helpers
    monkeypatch.setattr(agent_monitor_helpers, "agent_logs_dir", lambda: str(tmp_path))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agent/monitor-issues")

    assert resp.status_code == 200
    body = resp.json()
    assert "resolved" in body
    assert len(body["resolved"]) == 1
    assert body["resolved"][0]["condition"] == "api_unreachable"
    assert body["resolved"][0]["heal_task_id"] == "task_abc123"


@pytest.mark.asyncio
async def test_api_no_resolved_when_absent(tmp_path, monkeypatch):
    """When monitor_issues.json has no resolved key, response has no resolved."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from app.routers.agent_issues_routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api/agent")

    issues_data = {
        "issues": [],
        "last_check": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }

    issues_path = tmp_path / "monitor_issues.json"
    issues_path.write_text(json.dumps(issues_data))

    from app.routers import agent_monitor_helpers
    monkeypatch.setattr(agent_monitor_helpers, "agent_logs_dir", lambda: str(tmp_path))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agent/monitor-issues")

    assert resp.status_code == 200
    body = resp.json()
    assert "resolved" not in body
