"""Read sensing middleware — adaptive sensing tiers.

Three tiers based on whether sensing cost exceeds potential CC reward:

  Tier 1 (full):      Every read recorded. For high-value assets.
  Tier 2 (sampled):   1-in-N reads recorded. For medium-value assets.
  Tier 3 (untracked): Aggregate in-memory counter only. For low-value reads.

Assets auto-promote: untracked → sampled → full as read volume grows.
The system senses its own overhead and backs off when sensing costs
more than it returns.
"""

from __future__ import annotations

import re
import time
import logging
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger(__name__)

# Patterns that constitute a "read" worth sensing
_READ_PATTERNS = [
    re.compile(r"^/api/concepts/(lc-[\w-]+)$"),
    re.compile(r"^/api/assets/([\w-]+)$"),
    re.compile(r"^/api/assets/([\w-]+)/content$"),
]

# Paths that are never sensed (health checks, static, verification itself)
_SKIP_PATTERNS = [
    re.compile(r"^/api/health"),
    re.compile(r"^/api/verification/"),
    re.compile(r"^/api/meta/"),
    re.compile(r"^/api/config"),
    re.compile(r"^/_next/"),
    re.compile(r"^/favicon"),
]

# ---------------------------------------------------------------------------
# Adaptive tier state (in-memory, resets on restart — that's fine)
# ---------------------------------------------------------------------------

# In-memory counters for untracked/sampled assets
_mem_counters: dict[str, int] = defaultdict(int)
_last_flush = time.monotonic()

# Tier thresholds (base — adjusted by vitality score)
SAMPLE_PROMOTE_THRESHOLD = 10   # reads before untracked → sampled
FULL_PROMOTE_THRESHOLD = 100    # reads before sampled → full
SAMPLE_RATE = 10                # 1-in-N for sampled tier

# Asset tier cache (in-memory, starts empty — everything begins untracked)
_asset_tiers: dict[str, int] = {}  # asset_id → tier (1=full, 2=sampled, 3=untracked)
_asset_vitality: dict[str, float] = {}  # cached frequency score per asset

# Performance budget: max microseconds per request for sensing overhead
MAX_TRACKING_US = 500  # 0.5ms
_tracking_times: list[float] = []


def _get_tier(asset_id: str) -> int:
    """Get sensing tier for an asset. Default: untracked (3)."""
    return _asset_tiers.get(asset_id, 3)


def _vitality_multiplier(asset_id: str) -> float:
    """How strongly does this asset resonate across frequency space?

    Uses the universal frequency profile service to get the profile
    vector, then derives a sensing multiplier from its magnitude.
    """
    if asset_id in _asset_vitality:
        return _asset_vitality[asset_id]

    multiplier = 1.0
    try:
        from app.services import frequency_profile_service
        views = frequency_profile_service.get_profile(asset_id)
        if any(views.values()):
            mag = frequency_profile_service.magnitude(views)
            # Normalize magnitude to multiplier range [1.0, 4.0]
            multiplier = max(1.0, min(4.0, mag))
    except Exception:
        pass

    _asset_vitality[asset_id] = multiplier
    return multiplier


def _maybe_promote(asset_id: str) -> None:
    """Auto-promote asset tier based on read volume × vitality.

    High-vitality assets (ceremony, play, stillness) promote faster
    because they bring more life to the community — sensing them
    is more worthwhile.
    """
    count = _mem_counters[asset_id]
    vitality = _vitality_multiplier(asset_id)
    current = _get_tier(asset_id)

    # Vitality lowers the promotion threshold
    # ceremony (3.0x) promotes to sampled at ~3 reads instead of 10
    # ceremony promotes to full at ~33 reads instead of 100
    sample_threshold = max(2, int(SAMPLE_PROMOTE_THRESHOLD / vitality))
    full_threshold = max(10, int(FULL_PROMOTE_THRESHOLD / vitality))

    if current == 3 and count >= sample_threshold:
        _asset_tiers[asset_id] = 2
        log.debug("read_tracking: %s promoted to sampled (count=%d, vitality=%.1f)",
                   asset_id, count, vitality)
    elif current == 2 and count >= full_threshold:
        _asset_tiers[asset_id] = 1
        log.debug("read_tracking: %s promoted to full (count=%d, vitality=%.1f)",
                   asset_id, count, vitality)


class ReadTrackingMiddleware(BaseHTTPMiddleware):
    """Adaptive read sensing — tracks only when the value exceeds the cost."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only track successful GETs
        if request.method != "GET" or response.status_code != 200:
            return response

        path = request.url.path

        # Skip paths that should never be sensed
        for skip in _SKIP_PATTERNS:
            if skip.match(path):
                return response

        # Match trackable paths
        for pattern in _READ_PATTERNS:
            match = pattern.match(path)
            if match:
                asset_id = match.group(1)
                concept_id = asset_id if asset_id.startswith("lc-") else None
                t0 = time.monotonic()

                # Check if reader voluntarily identified themselves
                # X-Contributor-Id header: voluntary on reads, required on writes
                reader_id = request.headers.get("x-contributor-id", "")
                session_fingerprint = request.headers.get("x-session-fingerprint", "")
                page_route = request.headers.get("x-page-route", "")
                referrer_contributor_id = request.headers.get("x-referrer-contributor-id", "")

                # Check if this is an NFT/registered asset (has a graph node)
                # NFT assets: identified reads encouraged for CC sensing
                is_nft = asset_id.startswith("visual-") or concept_id is not None

                # Always increment in-memory counter (cheap)
                _mem_counters[asset_id] += 1
                _maybe_promote(asset_id)

                tier = _get_tier(asset_id)

                # Identified readers on NFT assets: always track (they want CC)
                if reader_id and is_nft:
                    tier = min(tier, 1)  # promote to full for identified NFT reads

                if tier == 3:
                    # Untracked — in-memory counter only, no DB write
                    pass
                elif tier == 2:
                    # Sampled — record 1 in every N reads
                    if _mem_counters[asset_id] % SAMPLE_RATE == 0:
                        try:
                            from app.services import read_tracking_service
                            read_tracking_service.record_read(
                                asset_id, concept_id,
                                contributor_id=reader_id or None,
                            )
                        except Exception as e:
                            log.debug("read_tracking: %s", e)
                elif tier == 1:
                    # Full — every read recorded
                    try:
                        from app.services import read_tracking_service
                        read_tracking_service.record_read(
                            asset_id, concept_id,
                            contributor_id=reader_id or None,
                        )
                    except Exception as e:
                        log.debug("read_tracking: %s", e)

                # Record per-contributor view event for EVERY matched read
                # (view events are cheap, per-contributor tracking matters for CC)
                try:
                    from app.services import read_tracking_service
                    read_tracking_service.record_view(
                        asset_id=asset_id,
                        concept_id=concept_id,
                        contributor_id=reader_id or None,
                        session_fingerprint=session_fingerprint or None,
                        source_page=page_route or None,
                        referrer_contributor_id=referrer_contributor_id or None,
                    )
                except Exception as e:
                    log.debug("read_tracking: view event failed: %s", e)

                # Monitor our own overhead
                elapsed_us = (time.monotonic() - t0) * 1_000_000
                _tracking_times.append(elapsed_us)
                if len(_tracking_times) > 1000:
                    _tracking_times.pop(0)
                if elapsed_us > MAX_TRACKING_US:
                    log.warning("read_tracking: overhead %dμs exceeds budget %dμs for %s",
                                int(elapsed_us), MAX_TRACKING_US, asset_id)

                break

        return response


def get_tracking_stats() -> dict:
    """Get sensing overhead stats for monitoring."""
    avg_us = sum(_tracking_times) / len(_tracking_times) if _tracking_times else 0
    tier_counts = defaultdict(int)
    for t in _asset_tiers.values():
        tier_counts[t] += 1
    return {
        "total_in_memory": sum(_mem_counters.values()),
        "unique_assets_seen": len(_mem_counters),
        "tier_1_full": tier_counts.get(1, 0),
        "tier_2_sampled": tier_counts.get(2, 0),
        "tier_3_untracked": len(_mem_counters) - tier_counts.get(1, 0) - tier_counts.get(2, 0),
        "avg_overhead_us": round(avg_us, 1),
        "max_overhead_us": round(max(_tracking_times), 1) if _tracking_times else 0,
        "budget_us": MAX_TRACKING_US,
    }
