"""Pytest contract for idea `consolidate-overlapping-pages`.

Product acceptance (task / idea text):
- Legacy routes ``/usage``, ``/runtime``, and ``/remote-ops`` permanently redirect to
  ``/pipeline`` so bookmarks and external links keep working.
- Consolidated surface: ``/pipeline`` (execution queue, activity, provider signals).
- Primary navigation should surface ``/nodes`` and ``/pipeline`` without listing the
  legacy paths in the primary bar.
- Backend automation and agent APIs remain available; ``/automation`` is still a live page.

Static checks read the repo tree; optional live redirect checks use ``WEB_VERIFICATION_BASE``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NEXT_CONFIG = REPO_ROOT / "web" / "next.config.ts"
NODES_PAGE = REPO_ROOT / "web" / "app" / "nodes" / "page.tsx"
PIPELINE_PAGE = REPO_ROOT / "web" / "app" / "pipeline" / "page.tsx"
SITE_HEADER = REPO_ROOT / "web" / "components" / "site_header.tsx"

EXPECTED_REDIRECTS: tuple[tuple[str, str], ...] = (
    ("/usage", "/pipeline"),
    ("/runtime", "/pipeline"),
    ("/remote-ops", "/pipeline"),
)

_PAIR_RE = re.compile(
    r"source:\s*[\"']([^\"']+)[\"']\s*,\s*destination:\s*[\"']([^\"']+)[\"']",
    re.MULTILINE | re.DOTALL,
)


def _redirect_pairs(config_text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in _PAIR_RE.finditer(config_text)]


@pytest.mark.parametrize("source,destination", EXPECTED_REDIRECTS)
def test_next_config_declares_legacy_to_consolidated_redirect(
    source: str, destination: str
) -> None:
    assert NEXT_CONFIG.is_file(), f"missing {NEXT_CONFIG}"
    text = NEXT_CONFIG.read_text(encoding="utf-8")
    assert "async redirects()" in text, "next.config.ts must define redirects()"
    pairs = _redirect_pairs(text)
    assert (source, destination) in pairs, (
        f"expected redirect {source} -> {destination}, got {pairs!r}"
    )


def test_next_config_redirects_are_permanent() -> None:
    text = NEXT_CONFIG.read_text(encoding="utf-8")
    assert "permanent: true" in text


def test_consolidated_routes_have_app_pages() -> None:
    assert NODES_PAGE.is_file()
    assert PIPELINE_PAGE.is_file()


def test_nodes_page_declares_federation_surface() -> None:
    body = NODES_PAGE.read_text(encoding="utf-8")
    assert "Federation" in body or "federation" in body


def test_pipeline_page_loads_execution_and_network_data() -> None:
    body = PIPELINE_PAGE.read_text(encoding="utf-8")
    assert "/api/agent" in body
    assert "/api/federation/nodes" in body or "/api/providers/stats" in body


def test_site_header_primary_nav_includes_nodes_and_pipeline() -> None:
    body = SITE_HEADER.read_text(encoding="utf-8")
    assert "PRIMARY_NAV" in body
    assert 'href: "/nodes"' in body
    assert 'href: "/pipeline"' in body


def test_site_header_primary_nav_excludes_legacy_ops_paths() -> None:
    body = SITE_HEADER.read_text(encoding="utf-8")
    start = body.find("const PRIMARY_NAV")
    assert start != -1
    end = body.find("];", start)
    assert end != -1
    block = body[start:end]
    for legacy in ("/usage", "/runtime", "/remote-ops"):
        assert legacy not in block, f"{legacy} must not appear in PRIMARY_NAV"


@pytest.mark.asyncio
async def test_api_automation_readiness_still_reachable() -> None:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/automation/usage/readiness")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    assert (
        "generated_at" in payload or "providers" in payload or "readiness" in payload
    )


@pytest.mark.asyncio
async def test_api_pipeline_and_tasks_contract() -> None:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        pipeline = await client.get("/api/agent/pipeline-status")
        tasks = await client.get("/api/agent/tasks", params={"limit": 1})
        missing = await client.get(
            "/api/agent/tasks/00000000-0000-0000-0000-000000000099"
        )
    assert pipeline.status_code == 200
    assert isinstance(pipeline.json(), dict)
    assert tasks.status_code == 200
    tasks_data = tasks.json()
    assert isinstance(tasks_data, dict)
    assert isinstance(tasks_data.get("tasks", []), list)
    assert missing.status_code == 404


@pytest.mark.skipif(
    not os.environ.get("WEB_VERIFICATION_BASE", "").strip(),
    reason="Set WEB_VERIFICATION_BASE to verify live redirects (e.g. production URL).",
)
@pytest.mark.asyncio
async def test_live_legacy_routes_redirect_to_consolidated_paths() -> None:
    base = os.environ["WEB_VERIFICATION_BASE"].strip().rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        for src, dst in EXPECTED_REDIRECTS:
            url = f"{base}{src}"
            response = await client.get(url, follow_redirects=False)
            assert response.status_code in (301, 308), (
                f"{url} expected redirect, got {response.status_code}"
            )
            location = response.headers.get("location") or ""
            assert location.endswith(dst) or dst in location, (
                f"Location {location!r} for {url}"
            )
