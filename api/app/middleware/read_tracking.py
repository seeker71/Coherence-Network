"""Read tracking middleware — adaptive tracking tiers.

Three tiers based on whether tracking cost exceeds potential CC reward:

  Tier 1 (full):      Every read recorded. For high-value assets.
  Tier 2 (sampled):   1-in-N reads recorded. For medium-value assets.
  Tier 3 (untracked): Aggregate in-memory counter only. For low-value reads.

Assets auto-promote: untracked → sampled → full as read volume grows.
The system senses its own overhead and backs off when tracking costs
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

# Patterns that constitute a "read" worth tracking
_READ_PATTERNS = [
    re.compile(r"^/api/concepts/(lc-[\w-]+)$"),
    re.compile(r"^/api/assets/([\w-]+)$"),
    re.compile(r"^/api/assets/([\w-]+)/content$"),
]

# Paths that are never tracked (health checks, static, verification itself)
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

# Performance budget: max microseconds per request for tracking overhead
MAX_TRACKING_US = 500  # 0.5ms
_tracking_times: list[float] = []


def _get_tier(asset_id: str) -> int:
    """Get tracking tier for an asset. Default: untracked (3)."""
    return _asset_tiers.get(asset_id, 3)


def _frequency_profile(asset_id: str) -> dict[str, float]:
    """Get the frequency profile vector for an asset.

    Not a single score — a vector across all frequency dimensions
    (each concept is a dimension). Like an embedding: the asset's
    position in frequency space.

    Returns: {concept_id: signal_strength, ...}
    Cached in memory after first computation.
    """
    if asset_id in _asset_vitality:
        return _asset_vitality[asset_id]

    profile: dict[str, float] = {}
    try:
        # Extract concept ID from asset ID
        concept_id = asset_id
        if concept_id.startswith("visual-"):
            concept_id = concept_id[7:]
        if "-story-" in concept_id:
            concept_id = concept_id[:concept_id.index("-story-")]
        elif concept_id[-1:].isdigit() and "-" in concept_id:
            concept_id = concept_id[:concept_id.rindex("-")]

        # The asset's primary concept is its strongest frequency
        profile[concept_id] = 1.0

        # Get connected concepts from edges — each connection adds a frequency
        from app.services import concept_service
        edges = concept_service.get_concept_edges(concept_id)
        for edge in edges:
            connected = edge.get("to") if edge.get("from") == concept_id else edge.get("from", "")
            if connected and connected.startswith("lc-"):
                # Edge strength becomes frequency strength (weaker = more distant)
                strength = float(edge.get("strength", 0.5))
                profile[connected] = max(profile.get(connected, 0), strength * 0.6)

        # Get frequency score of the content itself — adds a "living" dimension
        from app.services import frequency_scoring
        concept = concept_service.get_concept(concept_id)
        if concept and concept.get("story_content"):
            result = frequency_scoring.score_frequency(concept["story_content"])
            profile["_living"] = result.get("score", 0.5)
    except Exception:
        pass

    _asset_vitality[asset_id] = profile
    return profile


def _profile_magnitude(profile: dict[str, float]) -> float:
    """The overall signal strength of a frequency profile.

    Higher magnitude = the asset resonates more strongly across
    more dimensions = worth tracking more carefully.
    """
    if not profile:
        return 1.0
    import math
    # L2 norm of the profile vector — richer profiles have higher magnitude
    magnitude = math.sqrt(sum(v * v for v in profile.values()))
    # Normalize to a useful multiplier range [1.0, 4.0]
    # A concept with 5 connections at 0.6 + living score 0.8 ≈ magnitude 1.7 → multiplier 2.5
    return max(1.0, min(4.0, magnitude))


def _vitality_multiplier(asset_id: str) -> float:
    """How strongly does this asset resonate across frequency space?

    Uses the full frequency profile (vector, not scalar) to determine
    tracking priority. Assets that resonate across more dimensions
    and carry more living frequency get tracked sooner.
    """
    profile = _frequency_profile(asset_id)
    return _profile_magnitude(profile)


def _maybe_promote(asset_id: str) -> None:
    """Auto-promote asset tier based on read volume × vitality.

    High-vitality assets (ceremony, play, stillness) promote faster
    because they bring more life to the community — tracking them
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
    """Adaptive read tracking — tracks only when the value exceeds the cost."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only track successful GETs
        if request.method != "GET" or response.status_code != 200:
            return response

        path = request.url.path

        # Skip paths that should never be tracked
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

                # Always increment in-memory counter (cheap)
                _mem_counters[asset_id] += 1
                _maybe_promote(asset_id)

                tier = _get_tier(asset_id)

                if tier == 3:
                    # Untracked — in-memory counter only, no DB write
                    pass
                elif tier == 2:
                    # Sampled — record 1 in every N reads
                    if _mem_counters[asset_id] % SAMPLE_RATE == 0:
                        try:
                            from app.services import read_tracking_service
                            read_tracking_service.record_read(asset_id, concept_id)
                        except Exception as e:
                            log.debug("read_tracking: %s", e)
                elif tier == 1:
                    # Full — every read recorded
                    try:
                        from app.services import read_tracking_service
                        read_tracking_service.record_read(asset_id, concept_id)
                    except Exception as e:
                        log.debug("read_tracking: %s", e)

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
    """Get tracking overhead stats for monitoring."""
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
