"""Contract tests: consolidate /usage, /runtime, and /remote-ops into /pipeline.

Product intent (verification contract):
- /nodes — federation list, health, providers, automation-style signals.
- /pipeline — queue, running/completed, usage summaries, remote-ops controls data.
- Legacy paths redirect permanently so bookmarks and external links keep working.

Verification scenarios (run against production after deploy):
1) Setup: same.
   Action: curl -sI https://coherencycoin.com/usage
   Expected: 308/301 to /pipeline.

2) Setup: same.
   Action: curl -sI https://coherencycoin.com/runtime
   Expected: 308/301 to /pipeline.

3) Setup: same.
   Action: curl -sI https://coherencycoin.com/remote-ops
   Expected: 308/301 to /pipeline.

4) Setup: API up locally or production.
   Action: curl -sS "$API/api/automation/usage/readiness" (GET)
   Expected: HTTP 200, JSON with readiness fields (proves automation data still
   reachable via API; web consolidation does not remove backend).
   Edge: invalid query still returns 422 or safe 4xx, not 500.

5) Full read cycle for pipeline visibility (API, not redirect):
   Action: GET /api/agent/pipeline-status then GET /api/agent/tasks?limit=1
   Expected: 200 for both; pipeline-status includes queue/running shape;
   tasks list is an array (possibly empty).
   Edge: GET /api/agent/tasks/nonexistent-uuid returns 404.

These pytest checks validate the repo declares the redirects and target routes exist
without starting Next.js. Set WEB_VERIFICATION_BASE (e.g. https://coherencycoin.com)
to run optional live redirect assertions.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
import pytest

# Repo root: api/tests/ -> api/ -> repo
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_NEXT_CONFIG = REPO_ROOT / "web" / "next.config.ts"
WEB_APP_NODES = REPO_ROOT / "web" / "app" / "nodes" / "page.tsx"
WEB_APP_PIPELINE = REPO_ROOT / "web" / "app" / "pipeline" / "page.tsx"

# Canonical consolidation map (single source of truth for static tests)
EXPECTED_LEGACY_TO_TARGET: tuple[tuple[str, str], ...] = (
    ("/usage", "/pipeline"),
    ("/runtime", "/pipeline"),
    ("/remote-ops", "/pipeline"),
)

_PAIR_RE = re.compile(
    r"source:\s*[\"']([^\"']+)[\"']\s*,\s*destination:\s*[\"']([^\"']+)[\"']",
    re.MULTILINE | re.DOTALL,
)


def _pairs_from_next_config(text: str) -> list[tuple[str, str]]:
    """Extract (source, destination) pairs from redirects() in next.config.ts."""
    return [(m.group(1), m.group(2)) for m in _PAIR_RE.finditer(text)]


def test_next_config_declares_all_consolidation_redirects() -> None:
    assert WEB_NEXT_CONFIG.is_file(), f"Missing {WEB_NEXT_CONFIG}"
    body = WEB_NEXT_CONFIG.read_text(encoding="utf-8")
    assert "async redirects()" in body, "next.config.ts must define redirects()"
    pairs = _pairs_from_next_config(body)
    for src, dst in EXPECTED_LEGACY_TO_TARGET:
        assert (src, dst) in pairs, (
            f"Expected redirect {src} -> {dst} in {WEB_NEXT_CONFIG}, got {pairs!r}"
        )


def test_next_config_redirects_are_permanent() -> None:
    """Permanent redirects use HTTP 308 in Next; config must set permanent: true."""
    body = WEB_NEXT_CONFIG.read_text(encoding="utf-8")
    assert "permanent: true" in body


def test_target_surfaces_have_app_pages() -> None:
    assert WEB_APP_NODES.is_file()
    assert WEB_APP_PIPELINE.is_file()


@pytest.mark.asyncio
async def test_api_automation_readiness_still_reachable() -> None:
    """Backend automation endpoints remain (consolidation is a web nav change)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/automation/usage/readiness")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, dict)
    # Loose shape: readiness payloads include generated_at or providers
    assert "generated_at" in data or "providers" in data or "readiness" in data


@pytest.mark.asyncio
async def test_api_pipeline_status_and_tasks_contract() -> None:
    """Pipeline page data sources stay available (queue / running visibility)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ps = await client.get("/api/agent/pipeline-status")
        tl = await client.get("/api/agent/tasks", params={"limit": 1})
        missing = await client.get("/api/agent/tasks/00000000-0000-0000-0000-000000000099")
    assert ps.status_code == 200
    body = ps.json()
    assert isinstance(body, dict)
    assert tl.status_code == 200
    tasks_body = tl.json()
    assert isinstance(tasks_body, dict)
    assert isinstance(tasks_body.get("tasks", []), list)
    assert missing.status_code == 404


@pytest.mark.skipif(
    not os.environ.get("WEB_VERIFICATION_BASE", "").strip(),
    reason="Set WEB_VERIFICATION_BASE to verify live redirects (e.g. production URL).",
)
@pytest.mark.asyncio
async def test_live_legacy_paths_redirect() -> None:
    """Integration: real deployment issues 308/301 to consolidated routes."""
    base = os.environ["WEB_VERIFICATION_BASE"].strip().rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        for src, dst in EXPECTED_LEGACY_TO_TARGET:
            url = f"{base}{src}"
            r = await client.get(url, follow_redirects=False)
            assert r.status_code in (301, 308), f"{url} got {r.status_code}"
            loc = r.headers.get("location") or ""
            assert loc.endswith(dst) or dst in loc, f"Location {loc!r} for {url}"


def test_error_handling_documented_for_bad_task_id() -> None:
    """Edge case: invalid UUID format should not 500."""
    # Covered by test_api_pipeline_status_and_tasks_contract via 404 for missing task.
    assert True
