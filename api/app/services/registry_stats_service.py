"""Registry stats service — spec-178.

Fetches npm download counts and returns a structured summary of all
MCP/skill registry submissions tracked in docs/REGISTRY_SUBMISSIONS.md.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel
from typing import Literal

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RegistryEntry(BaseModel):
    name: str
    status: Literal["live", "pending", "unknown", "rejected"]
    listing_url: Optional[str] = None
    installs: Optional[int] = None


class RegistryStats(BaseModel):
    npm_weekly_downloads: int
    npm_total_downloads: int
    registries: list[RegistryEntry]
    fetched_at: datetime
    fetched_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Config — registry list (source of truth is docs/REGISTRY_SUBMISSIONS.md)
# ---------------------------------------------------------------------------

_REGISTRY_DEFAULTS: list[dict] = [
    {"name": "smithery",  "status": "pending", "listing_url": None},
    {"name": "glama",     "status": "pending", "listing_url": None},
    {"name": "pulsemcp",  "status": "pending", "listing_url": None},
    {"name": "mcp_so",    "status": "pending", "listing_url": None},
    {"name": "skills_sh", "status": "pending", "listing_url": None},
    {"name": "askill_sh", "status": "pending", "listing_url": None},
]

_REGISTRY_MD_PATH = Path(__file__).resolve().parents[3] / "docs" / "REGISTRY_SUBMISSIONS.md"

_NPM_WEEKLY_URL = "https://api.npmjs.org/downloads/point/last-week/coherence-mcp-server"
_NPM_TOTAL_URL  = "https://api.npmjs.org/downloads/point/2000-01-01:2099-12-31/coherence-mcp-server"

# Row format in REGISTRY_SUBMISSIONS.md:
# | Smithery | MCP server | 2026-03-28 | live | https://smithery.ai/... | 42 | notes |
_ROW_RE = re.compile(
    r"^\|\s*\[?(?P<name>[^\]|]+)\]?[^|]*\|"   # registry name (with or without link)
    r"[^|]*\|"                                  # type
    r"[^|]*\|"                                  # submitted
    r"\s*(?P<status>live|pending|unknown|rejected)\s*\|"
    r"\s*(?P<url>[^\|]*?)\s*\|"                 # listing URL
    r"\s*(?P<installs>[0-9—\-]*)\s*\|",         # weekly installs
    re.IGNORECASE,
)

_NAME_MAP = {
    "smithery": "smithery",
    "glama": "glama",
    "pulsemcp": "pulsemcp",
    "mcp.so": "mcp_so",
    "skills.sh": "skills_sh",
    "askill.sh": "askill_sh",
}


def _parse_registry_md() -> dict[str, dict]:
    """Parse docs/REGISTRY_SUBMISSIONS.md and return a keyed dict."""
    result: dict[str, dict] = {}
    if not _REGISTRY_MD_PATH.exists():
        return result
    try:
        lines = _REGISTRY_MD_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result

    for line in lines:
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        raw_name = m.group("name").strip().lower()
        # Normalise name via map
        key = _NAME_MAP.get(raw_name, raw_name.replace(".", "_").replace("-", "_"))
        url = m.group("url").strip()
        installs_raw = m.group("installs").strip()
        result[key] = {
            "status": m.group("status").lower(),
            "listing_url": url if url and url not in ("—", "-", "") else None,
            "installs": int(installs_raw) if installs_raw.isdigit() else None,
        }
    return result


async def _fetch_npm_downloads() -> tuple[int, int, Optional[str]]:
    """Return (weekly, total, error_str_or_None)."""
    weekly = 0
    total = 0
    error: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r_weekly = await client.get(_NPM_WEEKLY_URL)
            r_total  = await client.get(_NPM_TOTAL_URL)
            if r_weekly.status_code == 200:
                weekly = r_weekly.json().get("downloads", 0)
            if r_total.status_code == 200:
                total = r_total.json().get("downloads", 0)
    except Exception as exc:  # network unreachable, timeout, etc.
        error = str(exc)
    return weekly, total, error


async def get_registry_stats() -> RegistryStats:
    """Fetch npm download counts and merge with registry submission status."""
    npm_weekly, npm_total, npm_error = await _fetch_npm_downloads()
    md_data = _parse_registry_md()

    registries: list[RegistryEntry] = []
    for default in _REGISTRY_DEFAULTS:
        key = default["name"]
        merged = {**default, **(md_data.get(key, {}))}
        status = merged.get("status", "unknown")
        if status not in ("live", "pending", "unknown", "rejected"):
            status = "unknown"
        registries.append(
            RegistryEntry(
                name=key,
                status=status,  # type: ignore[arg-type]
                listing_url=merged.get("listing_url"),
                installs=merged.get("installs"),
            )
        )

    return RegistryStats(
        npm_weekly_downloads=npm_weekly,
        npm_total_downloads=npm_total,
        registries=registries,
        fetched_at=datetime.now(timezone.utc),
        fetched_error=npm_error,
    )
