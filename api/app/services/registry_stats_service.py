"""Registry install/download count fetching service with file-based cache.

Fetches live counts from public registry APIs (Smithery, PulseMCP) and caches
them for 24 hours.  Registries without public APIs are marked ``unavailable``.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.registry_discovery import (
    RegistryStatSource,
    RegistryStats,
    RegistryStatsList,
    RegistryStatsSummary,
)

_CACHE_TTL_SECONDS = 86_400  # 24 hours


def _cache_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / ".cache" / "registry_stats"


def _read_cache(registry_id: str) -> Optional[dict]:
    path = _cache_dir() / f"{registry_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fetched_ts = data.get("fetched_at_ts", 0)
        age = time.time() - fetched_ts
        if age > _CACHE_TTL_SECONDS:
            return None  # expired
        return data
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _write_cache(registry_id: str, data: dict) -> None:
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{registry_id}.json"
    data["fetched_at_ts"] = time.time()
    try:
        path.write_text(json.dumps(data, default=str), encoding="utf-8")
    except OSError:
        pass


def _read_stale_cache(registry_id: str) -> Optional[dict]:
    """Return cache even if expired — used as fallback when live fetch fails."""
    path = _cache_dir() / f"{registry_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _fetch_smithery_stats(package_name: str = "coherence-mcp-server") -> Optional[dict]:
    """Attempt live fetch from Smithery stats API."""
    try:
        import urllib.request

        url = f"https://registry.smithery.ai/packages/{package_name}/stats"
        req = urllib.request.Request(url, headers={"User-Agent": "coherence-network/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "install_count": data.get("installs") or data.get("install_count"),
                "download_count": data.get("downloads") or data.get("download_count"),
            }
    except Exception:
        return None


def _fetch_pulsemcp_stats(slug: str = "coherence-network") -> Optional[dict]:
    """Attempt live fetch from PulseMCP public API."""
    try:
        import urllib.request

        url = f"https://www.pulsemcp.com/api/servers/{slug}"
        req = urllib.request.Request(url, headers={"User-Agent": "coherence-network/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "install_count": data.get("install_count"),
                "download_count": data.get("download_count"),
            }
    except Exception:
        return None


def _build_stats_item(
    registry_id: str,
    registry_name: str,
    refresh: bool,
    live_fetcher,
) -> RegistryStats:
    """Build a RegistryStats item using cache + optional live fetch."""
    now = datetime.now(timezone.utc)

    if not refresh:
        cached = _read_cache(registry_id)
        if cached is not None:
            return RegistryStats(
                registry_id=registry_id,
                registry_name=registry_name,
                install_count=cached.get("install_count"),
                download_count=cached.get("download_count"),
                fetched_at=now,
                source=RegistryStatSource.CACHED,
            )

    # Attempt live fetch
    live = live_fetcher()
    if live is not None:
        _write_cache(registry_id, live)
        return RegistryStats(
            registry_id=registry_id,
            registry_name=registry_name,
            install_count=live.get("install_count"),
            download_count=live.get("download_count"),
            fetched_at=now,
            source=RegistryStatSource.LIVE,
        )

    # Fallback to stale cache if live fails
    stale = _read_stale_cache(registry_id)
    if stale is not None:
        return RegistryStats(
            registry_id=registry_id,
            registry_name=registry_name,
            install_count=stale.get("install_count"),
            download_count=stale.get("download_count"),
            fetched_at=now,
            source=RegistryStatSource.CACHED,
            error="upstream timeout",
        )

    return RegistryStats(
        registry_id=registry_id,
        registry_name=registry_name,
        install_count=None,
        download_count=None,
        fetched_at=None,
        source=RegistryStatSource.UNAVAILABLE,
        error="upstream timeout",
    )


def fetch_registry_stats(
    refresh: bool = False,
    registry_id_filter: Optional[str] = None,
) -> RegistryStatsList:
    """Return per-registry install/download counts.

    Args:
        refresh: Force live fetch, bypassing cache.
        registry_id_filter: If set, return only the matching registry.
    """
    all_items: list[RegistryStats] = [
        _build_stats_item("smithery", "Smithery", refresh, _fetch_smithery_stats),
        _build_stats_item("pulsemcp", "PulseMCP", refresh, _fetch_pulsemcp_stats),
        # No public API for these registries
        RegistryStats(
            registry_id="glama",
            registry_name="Glama (awesome-mcp-servers)",
            source=RegistryStatSource.UNAVAILABLE,
        ),
        RegistryStats(
            registry_id="mcp-so",
            registry_name="MCP.so",
            source=RegistryStatSource.UNAVAILABLE,
        ),
        RegistryStats(
            registry_id="skills-sh",
            registry_name="skills.sh",
            source=RegistryStatSource.UNAVAILABLE,
        ),
        RegistryStats(
            registry_id="askill-sh",
            registry_name="askill.sh",
            source=RegistryStatSource.UNAVAILABLE,
        ),
    ]

    if registry_id_filter:
        all_items = [item for item in all_items if item.registry_id == registry_id_filter]

    total_installs = sum(item.install_count or 0 for item in all_items)
    total_downloads = sum(item.download_count or 0 for item in all_items)
    with_counts = sum(
        1 for item in all_items
        if item.install_count is not None or item.download_count is not None
    )
    unavailable = sum(1 for item in all_items if item.source == RegistryStatSource.UNAVAILABLE)

    live_items = [item for item in all_items if item.fetched_at is not None]
    last_updated = max((item.fetched_at for item in live_items), default=None)

    return RegistryStatsList(
        summary=RegistryStatsSummary(
            total_installs=total_installs,
            total_downloads=total_downloads,
            registries_with_counts=with_counts,
            registries_unavailable=unavailable,
            last_updated=last_updated,
        ),
        items=all_items,
    )
