"""Frequency profile service — every entity in the graph resonates.

Every idea, spec, asset, contributor, contribution, provider, and concept
has a frequency profile: a vector across all dimensions of the system.
Resonance between any two entities = cosine similarity of their profiles.

Profiles are:
  - Computed from the entity's graph neighborhood (what it connects to)
  - Enriched by content analysis (if the entity has text content)
  - Transparent: anyone can request any entity's profile via API
  - Verifiable: the profile is deterministically computed from graph data

An entity's profile emerges from three sources:
  1. Its own properties (concept tags, domains, keywords, content frequency)
  2. Its graph neighborhood (what it connects to, edge types and strengths)
  3. Its activity (what reads/uses/creates it — for contributors)

This replaces all hardcoded category assignments with continuous,
high-dimensional resonance that emerges from the data itself.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

# Profile cache — keyed by entity_id
_cache: dict[str, dict[str, float]] = {}


# ---------------------------------------------------------------------------
# Core: universal entity profiling
# ---------------------------------------------------------------------------

def get_profile(entity_id: str) -> dict[str, float]:
    """Get the frequency profile for ANY entity in the graph.

    Works for concepts, ideas, specs, assets, contributors, providers —
    anything that exists as a graph node.
    """
    if entity_id in _cache:
        return _cache[entity_id]

    profile: dict[str, float] = {}

    try:
        from app.services import graph_service
        node = graph_service.get_node(entity_id)
        if not node:
            return profile

        node_type = node.get("type", "")

        # 1. Properties-based dimensions
        profile.update(_profile_from_properties(node))

        # 2. Graph neighborhood dimensions
        profile.update(_profile_from_neighborhood(entity_id, node_type))

        # 3. Content frequency dimension (if entity has text content)
        profile.update(_profile_from_content(node))

    except Exception:
        pass

    _cache[entity_id] = profile
    return profile


def _profile_from_properties(node: dict) -> dict[str, float]:
    """Extract frequency dimensions from node properties."""
    profile: dict[str, float] = {}

    # Domains
    for domain in node.get("domains", []):
        profile[f"_domain:{domain}"] = 0.5

    # Keywords
    for kw in node.get("keywords", []):
        profile[f"_kw:{kw}"] = 0.3

    # Concept tags (ideas/specs tagged with concepts)
    for tag in node.get("concept_tags", []):
        if isinstance(tag, dict):
            profile[tag.get("concept_id", "")] = float(tag.get("weight", 0.5))
        elif isinstance(tag, str):
            profile[tag] = 0.5

    # Sacred frequency (Hz family)
    hz = node.get("sacred_frequency", {}).get("hz") if isinstance(node.get("sacred_frequency"), dict) else None
    if hz:
        profile[f"_hz:{hz}"] = 0.4

    # Node type as a dimension
    node_type = node.get("type", "")
    if node_type:
        profile[f"_type:{node_type}"] = 0.2

    # Phase/lifecycle
    phase = node.get("phase", "")
    if phase:
        profile[f"_phase:{phase}"] = 0.15

    return profile


def _profile_from_neighborhood(entity_id: str, node_type: str) -> dict[str, float]:
    """Extract frequency dimensions from graph connections."""
    profile: dict[str, float] = {}

    try:
        from app.services import graph_service
        neighbors = graph_service.get_neighbors(entity_id, direction="both")

        for neighbor in neighbors:
            nid = neighbor.get("id", "")
            if not nid:
                continue

            edge_type = neighbor.get("edge_type", "related")
            strength = float(neighbor.get("strength", 0.5))

            # The neighbor's ID becomes a dimension
            # Strength decays: direct connection at 0.6x, further at 0.3x
            profile[nid] = max(profile.get(nid, 0), strength * 0.6)

            # The edge type itself is a dimension
            profile[f"_edge:{edge_type}"] = max(
                profile.get(f"_edge:{edge_type}", 0), 0.2
            )

    except Exception:
        pass

    return profile


def _profile_from_content(node: dict) -> dict[str, float]:
    """Extract frequency dimensions from text content analysis."""
    profile: dict[str, float] = {}

    # Story content (concepts)
    story = node.get("story_content", "")
    # Description (ideas, specs)
    desc = node.get("description", "")
    # Combine available text
    text = story or desc
    if not text or len(text) < 50:
        return profile

    try:
        from app.services import frequency_scoring
        result = frequency_scoring.score_frequency(text)
        profile["_living"] = result.get("score", 0.5)

        # Top markers become dimensions too
        for marker in result.get("top_living", []):
            word = marker.get("word", "")
            if word:
                profile[f"_marker:{word}"] = marker.get("signal", 0.3) * 0.3

    except Exception:
        pass

    return profile


# ---------------------------------------------------------------------------
# Resonance computation
# ---------------------------------------------------------------------------

def resonance(entity_a: str, entity_b: str) -> float:
    """Cosine similarity between two entities' frequency profiles.

    This is the core function. CC flow, tracking priority, search ranking,
    recommendation — everything flows from resonance.
    """
    return resonance_profiles(get_profile(entity_a), get_profile(entity_b))


def resonance_profiles(profile_a: dict[str, float], profile_b: dict[str, float]) -> float:
    """Cosine similarity between two profile vectors."""
    if not profile_a or not profile_b:
        return 0.0

    shared = set(profile_a) & set(profile_b)
    if not shared:
        return 0.0

    dot = sum(profile_a[k] * profile_b[k] for k in shared)
    norm_a = math.sqrt(sum(v * v for v in profile_a.values()))
    norm_b = math.sqrt(sum(v * v for v in profile_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def magnitude(profile: dict[str, float]) -> float:
    """L2 norm — overall resonance strength."""
    if not profile:
        return 0.0
    return math.sqrt(sum(v * v for v in profile.values()))


def top_dimensions(profile: dict[str, float], n: int = 10) -> list[tuple[str, float]]:
    """Strongest dimensions in a profile."""
    return sorted(profile.items(), key=lambda x: -x[1])[:n]


# ---------------------------------------------------------------------------
# Profile verification
# ---------------------------------------------------------------------------

def profile_hash(entity_id: str) -> str:
    """Deterministic SHA-256 hash of an entity's profile.

    For verification: anyone can recompute the profile from the graph
    and confirm it matches this hash.
    """
    profile = get_profile(entity_id)
    # Sort keys for determinism
    canonical = json.dumps(
        {k: round(v, 6) for k, v in sorted(profile.items())},
        sort_keys=True,
    )
    return hashlib.sha256(f"{entity_id}|{canonical}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------

def get_profiles_batch(entity_ids: list[str]) -> dict[str, dict[str, float]]:
    """Get profiles for multiple entities at once."""
    return {eid: get_profile(eid) for eid in entity_ids}


def find_resonant(entity_id: str, candidates: list[str] | None = None,
                  top_n: int = 10) -> list[dict[str, Any]]:
    """Find the most resonant entities to a given entity.

    If candidates is None, searches all concepts in the living-collective domain.
    """
    profile = get_profile(entity_id)
    if not profile:
        return []

    if candidates is None:
        try:
            from app.services import concept_service
            result = concept_service.list_concepts_by_domain("living-collective", limit=200)
            candidates = [c["id"] for c in result.get("items", [])]
        except Exception:
            return []

    results = []
    for cid in candidates:
        if cid == entity_id:
            continue
        score = resonance(entity_id, cid)
        if score > 0:
            results.append({"entity_id": cid, "resonance": round(score, 4)})

    results.sort(key=lambda x: -x["resonance"])
    return results[:top_n]


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def sign_profile(entity_id: str) -> dict[str, str]:
    """Cryptographically sign an entity's frequency profile.

    Returns the profile hash, Ed25519 signature, public key, and timestamp.
    Anyone can verify: recompute the profile, hash it, check the signature.
    """
    from datetime import datetime, timezone

    profile = get_profile(entity_id)
    p_hash = profile_hash(entity_id)
    timestamp = datetime.now(timezone.utc).isoformat()

    # Sign: entity_id | hash | timestamp
    message = f"{entity_id}|{p_hash}|{timestamp}"

    try:
        from app.services.verification_service import sign_message, get_public_key
        signature = sign_message(message.encode("utf-8"))
        pub_key = get_public_key()
    except Exception:
        signature = ""
        pub_key = ""

    return {
        "entity_id": entity_id,
        "profile_hash": p_hash,
        "timestamp": timestamp,
        "signature": signature,
        "public_key": pub_key,
        "message": message,
        "dimensions": len(profile),
    }


def invalidate(entity_id: str | None = None) -> None:
    """Clear cached profiles."""
    if entity_id:
        _cache.pop(entity_id, None)
    else:
        _cache.clear()
