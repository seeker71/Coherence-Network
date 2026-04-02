"""Executable checks for spec 156 — Web audit findings 2026-03-24.

Maps acceptance scenarios from specs/156-web-audit-findings-2026-03-24.md to
automatable repository and API contracts (proxy rewrite, deploy docs, PM2
entrypoint, spec table integrity, audited routes present, API non-500 smoke).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app import config_loader
from app.main import app
from app.services import agent_service

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC_PATH = _REPO_ROOT / "specs" / "156-web-audit-findings-2026-03-24.md"
_NEXT_CONFIG = _REPO_ROOT / "web" / "next.config.ts"
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"
_ECOSYSTEM = _REPO_ROOT / "deploy" / "hostinger" / "ecosystem.config.js"
_DEPLOY_SH = _REPO_ROOT / "deploy" / "hostinger" / "deploy.sh"

_VALID_PRIORITIES = frozenset({"P0", "P1", "P2"})
_VALID_STATUSES = frozenset({"Fixed", "Partial", "Open", "Verified"})


def _spec_text() -> str:
    if not _SPEC_PATH.is_file():
        pytest.skip(f"Spec missing: {_SPEC_PATH}")
    return _SPEC_PATH.read_text(encoding="utf-8")


def _findings_table_rows(content: str) -> list[dict[str, str]]:
    """Parse the Prioritized Findings markdown table into row dicts."""
    lines = content.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "### Prioritized Findings":
            start = i
            break
    if start is None:
        return []

    rows: list[dict[str, str]] = []
    in_header = False
    for line in lines[start + 1 :]:
        s = line.strip()
        if not s.startswith("|"):
            if rows:
                break
            continue
        if "Priority" in s and "Finding" in s:
            in_header = True
            continue
        if in_header and re.match(r"^\|[\s\-:|]+\|$", s):
            continue
        if not in_header:
            continue
        parts = [p.strip() for p in s.split("|")]
        parts = [p for p in parts if p]
        if len(parts) < 4:
            continue
        priority, _finding, status, _behavior = parts[0], parts[1], parts[2], parts[3]
        if priority in _VALID_PRIORITIES:
            rows.append(
                {
                    "priority": priority,
                    "status": status,
                }
            )
    return rows


def test_spec_156_findings_table_maps_priority_and_status() -> None:
    """Acceptance criterion 1: each finding has one priority and a valid status."""
    content = _spec_text()
    rows = _findings_table_rows(content)
    assert len(rows) == 6, f"Expected 6 prioritized findings, got {len(rows)}"

    for row in rows:
        assert row["priority"] in _VALID_PRIORITIES, row
        assert row["status"] in _VALID_STATUSES, row

    by_status = {r["status"] for r in rows}
    assert "Fixed" in by_status
    assert "Verified" in by_status
    assert "Partial" in by_status
    assert "Open" in by_status


def test_next_config_proxies_api_path_for_browser_scenario_a() -> None:
    """Scenario A / P0: client uses relative /api/* via Next rewrite (executable config check)."""
    assert _NEXT_CONFIG.is_file(), f"Missing {_NEXT_CONFIG}"
    cfg = _NEXT_CONFIG.read_text(encoding="utf-8")
    assert 'source: "/api/:path*"' in cfg or "/api/:path*" in cfg
    assert "rewrites" in cfg
    assert "destination:" in cfg and "/api/:path*" in cfg


def test_claude_md_deploy_rebuilds_api_and_web_scenario_c() -> None:
    """Scenario 3 / P0: production deploy contract rebuilds both API and web."""
    assert _CLAUDE_MD.is_file()
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    assert "docker compose build" in text
    assert "api web" in text or ("api" in text and "web" in text and "docker compose build --no-cache" in text)
    # Explicit dual-service rebuild in the documented one-liner
    assert "docker compose build --no-cache api web" in text


def test_pm2_ecosystem_uses_server_js_not_typo_scenario_d() -> None:
    """Scenario 4 / P1: PM2 (Hostinger path) starts `server.js`, not `server.j` typo."""
    assert _ECOSYSTEM.is_file()
    body = _ECOSYSTEM.read_text(encoding="utf-8")
    # Literal `server.js` is required; `server.j` alone would be a false substring of `server.js`.
    assert 'script: "server.js"' in body
    assert 'script: "server.j"' not in body


def test_hostinger_deploy_script_builds_next_standalone_scenario_d() -> None:
    """Scenario D: deploy packaging references `.next/standalone` (valid entrypoint layout)."""
    assert _DEPLOY_SH.is_file()
    sh = _DEPLOY_SH.read_text(encoding="utf-8")
    assert "npm run build" in sh
    assert ".next/standalone" in sh


def test_audited_web_routes_have_pages() -> None:
    """P2 nodes + P0 ideas: audited routes exist as Next app pages."""
    ideas = _REPO_ROOT / "web" / "app" / "ideas" / "page.tsx"
    nodes = _REPO_ROOT / "web" / "app" / "nodes" / "page.tsx"
    tasks = _REPO_ROOT / "web" / "app" / "tasks" / "page.tsx"
    assert ideas.is_file(), f"Missing {ideas}"
    assert nodes.is_file(), f"Missing {nodes}"
    assert tasks.is_file(), f"Missing {tasks}"


def test_spec_documents_homepage_readability_partial_scenario_e() -> None:
    """Scenario 5 / P1: audit records homepage readability as Partial (follow-up in spec 150 tests)."""
    content = _spec_text()
    assert "Homepage readability improved" in content
    assert "| P1 |" in content and "Partial" in content
    css = _REPO_ROOT / "web" / "app" / "globals.css"
    assert css.is_file(), "Homepage theme baseline must exist for readability work"
    assert "--foreground:" in css.read_text(encoding="utf-8")


def _reset_agent_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    config_loader.set_config_value("agent_executor", "auto_execute", False)
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


@pytest.mark.asyncio
async def test_agent_tasks_list_non_500_when_healthy_scenario_a(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec API contract: valid GET /api/agent/tasks is not 500 when service is up."""
    _reset_agent_store(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/tasks", params={"limit": 10, "offset": 0})
        assert res.status_code == 200
        body = res.json()
        assert "tasks" in body


@pytest.mark.asyncio
async def test_health_non_500_for_audited_stack() -> None:
    """Existing routes used by audited pages should not 500 on valid GET /api/health."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
