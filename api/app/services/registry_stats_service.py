"""Registry listing status (6+ discovery targets) + npm download figures — idea-4deb5bd7c800."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

NPM_PACKAGE = "coherence-mcp-server"


class RegistryStats(BaseModel):
    total_downloads: int = 0
    weekly_downloads: int = 0
    registries: list[dict[str, Any]] = []


# Six public discovery registries (5+ MCP/skill) — aligned with docs/REGISTRY_SUBMISSIONS.md
_DEFAULT_REGISTRY_ROWS: list[dict[str, Any]] = [
    {
        "name": "Smithery",
        "type": "MCP",
        "status": "pending",
        "listing_url": None,
        "notes": "https://smithery.ai/submit",
    },
    {
        "name": "Glama (awesome-mcp-servers)",
        "type": "MCP",
        "status": "pending",
        "listing_url": None,
        "notes": "PR to github.com/punkpeye/awesome-mcp-servers",
    },
    {
        "name": "PulseMCP",
        "type": "MCP",
        "status": "pending",
        "listing_url": None,
        "notes": "https://pulsemcp.com/submit",
    },
    {
        "name": "mcp.so",
        "type": "MCP",
        "status": "pending",
        "listing_url": None,
        "notes": "https://mcp.so",
    },
    {
        "name": "skills.sh",
        "type": "Skill",
        "status": "pending",
        "listing_url": None,
        "notes": "https://skills.sh",
    },
    {
        "name": "askill.sh",
        "type": "Skill",
        "status": "pending",
        "listing_url": None,
        "notes": "https://askill.sh",
    },
]


async def _npm_point(client: httpx.AsyncClient, period: str) -> int:
    url = f"https://api.npmjs.org/downloads/point/{period}/{NPM_PACKAGE}"
    try:
        r = await client.get(url)
        r.raise_for_status()
        return int(r.json().get("downloads", 0))
    except Exception as e:
        logger.warning("registry_stats npm %s failed: %s", period, e)
        return 0


async def get_registry_stats() -> RegistryStats:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        last_month = await _npm_point(client, "last-month")
        last_week = await _npm_point(client, "last-week")

    return RegistryStats(
        total_downloads=last_month,
        weekly_downloads=last_week,
        registries=list(_DEFAULT_REGISTRY_ROWS),
    )
