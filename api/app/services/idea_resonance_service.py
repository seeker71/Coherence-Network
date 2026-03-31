"""Idea Resonance Service — structural cross-domain concept attraction.

Uses the Concept Resonance Kernel (CRK) to find ideas that resonate
structurally, even when they share no keywords. Biology–software connections
like symbiosis↔microservices emerge because both solve analogous problems
(mutual dependency, loose coupling, emergent behavior) — the CRK detects
this via harmonic frequency alignment, not text matching.

Key design decisions:
- Each idea is converted to a ConceptSymbol via text_to_symbol()
- CRK scores structural similarity (harmonic alignment), not keyword overlap
- Domain is inferred from tags + interfaces; cross-domain pairs are surfaced
- A resonance event log tracks discoveries so proof grows over time
- Results are cached per-idea to keep p95 latency under 50ms at 500 ideas
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.services.concept_resonance_kernel import (
    compare_concepts,
    text_to_symbol,
    ResonanceResult,
)

log = logging.getLogger(__name__)

# ── Thresholds ──────────────────────────────────────────────────────────────

# Minimum CRK coherence to surface a resonance pair
MIN_COHERENCE = 0.12

# Pairs with coherence >= this are "strong" resonances (highlighted in UI)
STRONG_COHERENCE = 0.35

# Cross-domain pairs need a lower bar — we want to surface surprising links
CROSS_DOMAIN_MIN_COHERENCE = 0.08

# Symbol cache: {idea_id: (symbol, cache_ts)}
_symbol_cache: dict[str, tuple[object, float]] = {}

# Resonance event log: list of ResonanceEvent dicts (append-only)
_resonance_events: list[dict] = []

# Pair-level result cache: {(id_a, id_b): ResonancePair}
_pair_cache: dict[tuple[str, str], "ResonancePair"] = {}

CACHE_TTL_SECONDS = 300  # 5 minutes


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class ResonancePair:
    """Two ideas that resonate structurally."""
    idea_id_a: str
    name_a: str
    domain_a: list[str]
    idea_id_b: str
    name_b: str
    domain_b: list[str]
    crk_score: float
    ot_distance: float
    coherence: float
    d_codex: float
    cross_domain: bool
    strong: bool
    discovered_at: str  # ISO 8601


@dataclass
class ResonanceProof:
    """Evidence that structural resonance is working over time."""
    total_pairs_discovered: int
    cross_domain_pairs: int
    strong_pairs: int
    latest_discovery: Optional[str]
    top_pairs: list[ResonancePair]
    domain_bridge_count: dict[str, int]  # domain → number of cross-domain links
    avg_coherence: float
    proof_quality: str  # "none" | "weak" | "emerging" | "strong"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _infer_domains(tags: list[str], interfaces: list[str]) -> list[str]:
    """Infer conceptual domains from tags and interfaces."""
    domain_keywords: dict[str, list[str]] = {
        "biology":     ["biology", "symbiosis", "evolution", "organism", "cell", "genome", "ecology", "species"],
        "software":    ["software", "microservice", "api", "code", "programming", "architecture", "service", "system"],
        "physics":     ["physics", "quantum", "energy", "wave", "frequency", "resonance", "harmonic", "field"],
        "economics":   ["economics", "market", "value", "cost", "trade", "currency", "token", "incentive"],
        "philosophy":  ["philosophy", "ontology", "consciousness", "ethics", "logic", "epistemology", "meaning"],
        "mathematics": ["math", "mathematics", "algebra", "topology", "graph", "manifold", "calculus", "geometry"],
        "social":      ["social", "community", "governance", "voting", "collaboration", "network", "trust"],
        "cognition":   ["cognition", "learning", "memory", "neural", "intelligence", "reasoning", "belief"],
        "art":         ["art", "music", "creative", "design", "aesthetic", "visual", "sound", "rhythm"],
    }

    domains: set[str] = set()
    all_tokens = " ".join(tags + interfaces).lower()

    for domain, keywords in domain_keywords.items():
        if any(kw in all_tokens for kw in keywords):
            domains.add(domain)

    return sorted(domains) if domains else ["general"]


def _get_or_build_symbol(idea_id: str, name: str, description: str,
                          tags: list[str], interfaces: list[str]) -> object:
    """Get cached symbol or build a new one."""
    now = time.monotonic()
    cached = _symbol_cache.get(idea_id)
    if cached and (now - cached[1]) < CACHE_TTL_SECONDS:
        return cached[0]

    text = f"{name} {description} {' '.join(tags)} {' '.join(interfaces)}"
    symbol = text_to_symbol(text)
    _symbol_cache[idea_id] = (symbol, now)
    return symbol


def _cache_key(id_a: str, id_b: str) -> tuple[str, str]:
    """Canonical pair key (sorted so (a,b) == (b,a))."""
    return (min(id_a, id_b), max(id_a, id_b))


# ── Core functions ────────────────────────────────────────────────────────────

def compute_pair_resonance(
    idea_a: dict,
    idea_b: dict,
) -> Optional[ResonancePair]:
    """Compute CRK-based structural resonance between two ideas.

    Returns a ResonancePair if coherence exceeds the threshold, else None.
    """
    id_a = idea_a["id"]
    id_b = idea_b["id"]

    key = _cache_key(id_a, id_b)
    cached = _pair_cache.get(key)
    if cached is not None:
        return cached

    sym_a = _get_or_build_symbol(
        id_a,
        idea_a.get("name", ""),
        idea_a.get("description", ""),
        idea_a.get("tags", []),
        idea_a.get("interfaces", []),
    )
    sym_b = _get_or_build_symbol(
        id_b,
        idea_b.get("name", ""),
        idea_b.get("description", ""),
        idea_b.get("tags", []),
        idea_b.get("interfaces", []),
    )

    result: ResonanceResult = compare_concepts(sym_a, sym_b)

    domain_a = _infer_domains(idea_a.get("tags", []), idea_a.get("interfaces", []))
    domain_b = _infer_domains(idea_b.get("tags", []), idea_b.get("interfaces", []))

    set_a = set(domain_a)
    set_b = set(domain_b)
    cross_domain = bool(set_a and set_b and not set_a.issubset(set_b) and not set_b.issubset(set_a))

    threshold = CROSS_DOMAIN_MIN_COHERENCE if cross_domain else MIN_COHERENCE
    if result.coherence < threshold:
        _pair_cache[key] = None  # type: ignore[assignment]
        return None

    pair = ResonancePair(
        idea_id_a=id_a,
        name_a=idea_a.get("name", id_a),
        domain_a=domain_a,
        idea_id_b=id_b,
        name_b=idea_b.get("name", id_b),
        domain_b=domain_b,
        crk_score=result.crk,
        ot_distance=result.d_ot_phi,
        coherence=result.coherence,
        d_codex=result.d_codex,
        cross_domain=cross_domain,
        strong=result.coherence >= STRONG_COHERENCE,
        discovered_at=datetime.now(timezone.utc).isoformat(),
    )
    _pair_cache[key] = pair

    # Log discovery event (deduped: only log first discovery)
    if not any(
        e["idea_id_a"] == id_a and e["idea_id_b"] == id_b
        or e["idea_id_a"] == id_b and e["idea_id_b"] == id_a
        for e in _resonance_events[-50:]  # Check last 50 for performance
    ):
        _resonance_events.append({
            "idea_id_a": id_a,
            "name_a": pair.name_a,
            "idea_id_b": id_b,
            "name_b": pair.name_b,
            "coherence": result.coherence,
            "cross_domain": cross_domain,
            "domain_a": domain_a,
            "domain_b": domain_b,
            "discovered_at": pair.discovered_at,
        })

    return pair


def find_resonant_ideas(
    source_idea: dict,
    all_ideas: list[dict],
    limit: int = 10,
    min_coherence: float = 0.0,
    cross_domain_only: bool = False,
) -> list[ResonancePair]:
    """Find ideas that resonate structurally with source_idea.

    Uses CRK for structural similarity. Unlike keyword matching, this can
    surface connections between ideas from different domains that solve
    analogous problems.
    """
    source_id = source_idea["id"]
    pairs: list[ResonancePair] = []

    effective_min = max(min_coherence, CROSS_DOMAIN_MIN_COHERENCE if cross_domain_only else MIN_COHERENCE)

    for candidate in all_ideas:
        if candidate["id"] == source_id:
            continue

        pair = compute_pair_resonance(source_idea, candidate)
        if pair is None:
            continue
        if pair.coherence < effective_min:
            continue
        if cross_domain_only and not pair.cross_domain:
            continue

        pairs.append(pair)

    # Sort: cross-domain first, then by coherence descending
    pairs.sort(key=lambda p: (p.cross_domain, p.coherence), reverse=True)
    return pairs[:limit]


def get_cross_domain_pairs(
    all_ideas: list[dict],
    limit: int = 20,
    min_coherence: float = 0.0,
) -> list[ResonancePair]:
    """Scan all idea pairs and return cross-domain resonances.

    This is O(n²) but cached. For n=500 ideas with CRK at ~0.1ms/pair,
    a full scan takes ~25s — only run on demand, never in hot paths.
    Cache results per-pair indefinitely (TTL via _pair_cache).
    """
    cross_pairs: list[ResonancePair] = []
    effective_min = max(min_coherence, CROSS_DOMAIN_MIN_COHERENCE)
    n = len(all_ideas)

    for i in range(n):
        for j in range(i + 1, n):
            pair = compute_pair_resonance(all_ideas[i], all_ideas[j])
            if pair and pair.cross_domain and pair.coherence >= effective_min:
                cross_pairs.append(pair)

    cross_pairs.sort(key=lambda p: (p.strong, p.coherence), reverse=True)
    return cross_pairs[:limit]


def get_resonance_proof(all_ideas: list[dict]) -> ResonanceProof:
    """Summarize evidence that structural resonance is working.

    Scans the event log and cached pairs to build a proof object.
    The proof quality grows as more cross-domain connections accumulate.
    """
    # Count events
    total = len(_resonance_events)
    cross_domain = sum(1 for e in _resonance_events if e.get("cross_domain"))
    strong_events = [e for e in _resonance_events if e.get("coherence", 0) >= STRONG_COHERENCE]

    latest: Optional[str] = None
    if _resonance_events:
        latest = _resonance_events[-1].get("discovered_at")

    # Domain bridge counts
    bridge_counts: dict[str, int] = {}
    for event in _resonance_events:
        if not event.get("cross_domain"):
            continue
        for d in event.get("domain_a", []) + event.get("domain_b", []):
            bridge_counts[d] = bridge_counts.get(d, 0) + 1

    # Top pairs from cache
    cached_pairs = [p for p in _pair_cache.values() if p is not None and p.cross_domain]
    cached_pairs.sort(key=lambda p: (p.strong, p.coherence), reverse=True)
    top_pairs = cached_pairs[:5]

    avg_coherence = 0.0
    if _resonance_events:
        avg_coherence = round(
            sum(e.get("coherence", 0) for e in _resonance_events) / len(_resonance_events), 4
        )

    # Proof quality
    if cross_domain == 0:
        quality = "none"
    elif cross_domain < 3:
        quality = "weak"
    elif cross_domain < 10:
        quality = "emerging"
    else:
        quality = "strong"

    return ResonanceProof(
        total_pairs_discovered=total,
        cross_domain_pairs=cross_domain,
        strong_pairs=len(strong_events),
        latest_discovery=latest,
        top_pairs=top_pairs,
        domain_bridge_count=bridge_counts,
        avg_coherence=avg_coherence,
        proof_quality=quality,
    )


def invalidate_idea_cache(idea_id: str) -> None:
    """Remove cached symbol and all pairs involving this idea."""
    _symbol_cache.pop(idea_id, None)
    to_remove = [k for k in _pair_cache if k[0] == idea_id or k[1] == idea_id]
    for k in to_remove:
        _pair_cache.pop(k, None)


def get_event_log(limit: int = 50) -> list[dict]:
    """Return the resonance event log (most recent first)."""
    return list(reversed(_resonance_events[-limit:]))
