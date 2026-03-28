"""Fetch consolidated npm + GitHub signals for MCP/skill registry discovery — idea-4deb5bd7c800."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.models.registry_metrics import RegistryMetricSource, RegistryMetricsResponse

logger = logging.getLogger(__name__)

NPM_PACKAGE = "coherence-mcp-server"
NPM_LAST_MONTH_URL = f"https://api.npmjs.org/downloads/point/last-month/{NPM_PACKAGE}"
GITHUB_REPO_API = "https://api.github.com/repos/seeker71/Coherence-Network"
NPM_LISTING = f"https://www.npmjs.com/package/{NPM_PACKAGE}"
GITHUB_LISTING = "https://github.com/seeker71/Coherence-Network"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _fetch_npm_last_month(client: httpx.AsyncClient) -> RegistryMetricSource:
    fetched_at = _utc_iso()
    try:
        r = await client.get(NPM_LAST_MONTH_URL)
        r.raise_for_status()
        data = r.json()
        downloads = int(data.get("downloads", -1))
        return RegistryMetricSource(
            source="npm",
            count=downloads,
            fetched_at=fetched_at,
            listing_url=NPM_LISTING,
        )
    except Exception as e:
        logger.warning("registry_metrics npm fetch failed: %s", e)
        return RegistryMetricSource(
            source="npm",
            count=-1,
            fetched_at=fetched_at,
            listing_url=NPM_LISTING,
            error=str(e),
        )


async def _fetch_github_stars(client: httpx.AsyncClient) -> RegistryMetricSource:
    fetched_at = _utc_iso()
    try:
        r = await client.get(
            GITHUB_REPO_API,
            headers={"Accept": "application/vnd.github+json"},
        )
        r.raise_for_status()
        data = r.json()
        stars = int(data.get("stargazers_count", -1))
        return RegistryMetricSource(
            source="github_stars",
            count=stars,
            fetched_at=fetched_at,
            listing_url=GITHUB_LISTING,
        )
    except Exception as e:
        logger.warning("registry_metrics github fetch failed: %s", e)
        return RegistryMetricSource(
            source="github_stars",
            count=-1,
            fetched_at=fetched_at,
            listing_url=GITHUB_LISTING,
            error=str(e),
        )


async def get_registry_metrics() -> RegistryMetricsResponse:
    """Return npm last-month downloads + GitHub star count; always 200-compatible data."""
    as_of = _utc_iso()
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        npm = await _fetch_npm_last_month(client)
        gh = await _fetch_github_stars(client)

    sources = [npm, gh]
    total = 0
    for s in sources:
        if s.count >= 0:
            total += s.count

    return RegistryMetricsResponse(
        total_installs=total,
        sources=sources,
        as_of=as_of,
    )
