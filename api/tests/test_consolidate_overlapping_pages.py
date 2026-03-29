"""Acceptance tests: idea consolidate-overlapping-pages (overlapping ops surfaces).

Spec intent:
- Two primary web surfaces: /nodes (federation, health, providers, messaging) and
  /pipeline (queue, running/completed signals, provider performance, activity).
- Legacy /automation, /usage, /remote-ops redirect permanently to /nodes or
  /pipeline so bookmarks keep working.
- Backend automation and agent APIs remain available (consolidation is navigation).

These tests complement ``test_web_ops_consolidation_routes.py`` by locking UI wiring
and ASGI contracts for the consolidated pages.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Repo root: api/tests/ -> api/ -> repo
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_NEXT_CONFIG = REPO_ROOT / "web" / "next.config.ts"
SITE_HEADER = REPO_ROOT / "web" / "components" / "site_header.tsx"
WEB_NODES_PAGE = REPO_ROOT / "web" / "app" / "nodes" / "page.tsx"
WEB_PIPELINE_PAGE = REPO_ROOT / "web" / "app" / "pipeline" / "page.tsx"

_PAIR_RE = re.compile(
    r"source:\s*[\"']([^\"']+)[\"']\s*,\s*destination:\s*[\"']([^\"']+)[\"']",
    re.MULTILINE | re.DOTALL,
)


def _redirects_section(next_config_text: str) -> str:
    start = next_config_text.index("async redirects()")
    end = next_config_text.index("async headers()", start)
    return next_config_text[start:end]


def test_site_header_primary_nav_includes_nodes_and_pipeline() -> None:
    """Primary nav exposes the two consolidated surfaces (clear mental model)."""
    text = SITE_HEADER.read_text(encoding="utf-8")
    assert 'href: "/nodes"' in text
    assert 'href: "/pipeline"' in text
    assert "PRIMARY_NAV" in text
    # Pipeline and nodes appear in the primary strip (not only buried in menus).
    assert re.search(r"PRIMARY_NAV\s*=\s*\[[\s\S]*?/pipeline[\s\S]*?/nodes", text)


def test_nodes_page_wires_federation_registry_and_messaging() -> None:
    """Nodes surface lists federation members and supports cross-node messaging."""
    body = WEB_NODES_PAGE.read_text(encoding="utf-8")
    assert "/api/federation/nodes" in body
    assert "MessageForm" in body
    assert "Federation Nodes" in body


def test_pipeline_page_wires_execution_queue_and_provider_stats() -> None:
    """Pipeline surface pulls task activity, queue counts, and provider stats."""
    body = WEB_PIPELINE_PAGE.read_text(encoding="utf-8")
    for needle in (
        '"/api/federation/nodes"',
        '"/api/agent/tasks/active"',
        '"/api/agent/tasks/activity?limit=50"',
        '"/api/providers/stats"',
        '"/api/agent/tasks?status=pending&limit=1"',
        '"/api/agent/tasks?status=running&limit=1"',
    ):
        assert needle in body, f"Missing pipeline data source: {needle}"


def test_next_config_ops_redirects_use_distinct_legacy_paths() -> None:
    """Each legacy path maps to exactly one target; no duplicate sources in redirects()."""
    full = WEB_NEXT_CONFIG.read_text(encoding="utf-8")
    section = _redirects_section(full)
    pairs = [(m.group(1), m.group(2)) for m in _PAIR_RE.finditer(section)]
    sources = [s for s, _ in pairs]
    assert len(sources) == len(set(sources)), f"Duplicate redirect sources: {pairs!r}"
    assert set(sources) == {"/automation", "/usage", "/remote-ops"}
    dests = {d for _, d in pairs}
    assert dests <= {"/nodes", "/pipeline"}


@pytest.mark.asyncio
async def test_asgi_federation_nodes_for_nodes_page() -> None:
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/federation/nodes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_asgi_pipeline_activity_endpoints() -> None:
    """Endpoints used by the pipeline dashboard respond without server errors."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        active = await client.get("/api/agent/tasks/active")
        activity = await client.get("/api/agent/tasks/activity", params={"limit": 5})
        stats = await client.get("/api/providers/stats")
        pending = await client.get("/api/agent/tasks", params={"status": "pending", "limit": 1})
        running = await client.get("/api/agent/tasks", params={"status": "running", "limit": 1})
    assert active.status_code == 200
    assert isinstance(active.json(), list)
    assert activity.status_code == 200
    assert isinstance(activity.json(), list)
    assert stats.status_code == 200
    assert isinstance(stats.json(), dict)
    assert pending.status_code == 200
    assert running.status_code == 200
