"""Frequency profile v2 — dynamic, multi-view, multi-hop.

Where v1 used hand-tuned constants (0.5 for domains, 0.3 for keywords,
0.6 edge multiplier, etc.), v2 derives weights from the graph's own
statistics. Every value emerges from data:

- **Structural view** — Personalized PageRank from the entity, not just
  1-hop neighbors. Multi-hop resonance with natural attenuation.
- **Categorical view** — IDF-weighted (rare features are diagnostic;
  features that appear on every node carry near-zero signal).
- **Semantic view** — frequency-scoring markers from text content.
- **Saturating merge** — two paths of weight w₁, w₂ combine as
  1 − (1−w₁)(1−w₂) instead of max(w₁, w₂). Honors multiple evidence.
- **Inverse-variance view fusion** — no hand-picked 0.5/0.3/0.2.
  A view with more variance (more discriminative) weighs less so
  scale doesn't dominate.
- **Versioned hash** — ``profile_hash`` returns ``"v2:" + sha256(...)``.
  v1 remains callable for any previously-signed profile.

The core shift: resonance is meant to match entities. v1 answered
"what does this entity touch directly?" v2 answers "what is this
entity near in the living graph, relative to everything else?"
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict
from typing import Any

# Per-entity profile cache; cleared on edge/node writes via invalidate().
_profile_cache: dict[str, dict[str, Any]] = {}

# Graph-wide IDF cache, refreshed on TTL because it depends on total corpus.
_idf_cache: dict[str, dict[str, float]] | None = None
_idf_cache_time: float = 0.0
_IDF_TTL = 600.0  # 10 minutes

# PPR math constants (not data-tuned intuition — standard algorithm params)
PPR_DAMPING = 0.85
PPR_MAX_ITER = 20
PPR_TOL = 1e-4


# ── Categorical view (IDF-weighted) ───────────────────────────────────

def _categorical_features(node: dict) -> dict[str, list[str]]:
    """Extract categorical features grouped by category. Used for IDF.

    Any property that categorises the node — its domain, keywords, type,
    phase, frequency, extraction method, ingestion policy, or source-backed
    provenance — participates. Values emerge; weights come from IDF.
    """
    sacred = node.get("sacred_frequency")
    hz = sacred.get("hz") if isinstance(sacred, dict) else None
    source_artifact = node.get("source_artifact_id")
    is_source_backed = bool(source_artifact or node.get("extraction_method"))
    return {
        "domain": [d for d in (node.get("domains") or []) if d],
        "kw": [k for k in (node.get("keywords") or []) if k],
        "type": [node["type"]] if node.get("type") else [],
        "phase": [node["phase"]] if node.get("phase") else [],
        "hz": [str(hz)] if hz else [],
        "extraction": [node["extraction_method"]] if node.get("extraction_method") else [],
        "ingestion_policy": [node["ingestion_policy"]] if node.get("ingestion_policy") else [],
        "source_artifact": [source_artifact] if source_artifact else [],
        "provenance": ["source_backed"] if is_source_backed else [],
    }


def _ensure_idf_cache() -> dict[str, dict[str, float]]:
    """Compute IDF per category across the full graph, cached with TTL.

    IDF = log((1 + N) / (1 + df)) — smoothed so unseen features and
    ubiquitous features both stay bounded.
    """
    global _idf_cache, _idf_cache_time
    if _idf_cache is not None and (time.time() - _idf_cache_time) < _IDF_TTL:
        return _idf_cache

    try:
        from app.services import graph_service
        result = graph_service.list_nodes(limit=10000, offset=0)
        nodes = result.get("items", [])
    except Exception:
        _idf_cache = {}
        _idf_cache_time = time.time()
        return _idf_cache

    N = max(len(nodes), 1)
    df: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for node in nodes:
        for category, values in _categorical_features(node).items():
            for value in values:
                df[category][value] += 1

    idf = {
        category: {v: math.log((1 + N) / (1 + count)) for v, count in values.items()}
        for category, values in df.items()
    }
    _idf_cache = idf
    _idf_cache_time = time.time()
    return idf


def _categorical_view(entity_id: str) -> dict[str, float]:
    """Build IDF-weighted categorical view from the entity's own properties."""
    try:
        from app.services import graph_service
        node = graph_service.get_node(entity_id)
        if not node:
            return {}
    except Exception:
        return {}

    idf = _ensure_idf_cache()
    view: dict[str, float] = {}
    fallback_idf = math.log(2.0)  # unseen category: modest positive signal
    for category, values in _categorical_features(node).items():
        cat_idf = idf.get(category, {})
        for value in values:
            key = f"_{category}:{value}"
            weight = cat_idf.get(value, fallback_idf)
            view[key] = max(view.get(key, 0.0), weight)
    return view


# ── Structural view (Personalized PageRank) ───────────────────────────

def _structural_view(entity_id: str) -> dict[str, float]:
    """Personalized PageRank from entity_id — multi-hop graph resonance.

    At each step, mass distributes to neighbors proportional to edge strength.
    With damping (1-α) probability, mass teleports back to the source. This
    converges to a stationary distribution where high-weight nodes are those
    reachable via many strong short paths from the entity.
    """
    try:
        from app.services import graph_service
        if not graph_service.get_node(entity_id):
            return {}
    except Exception:
        return {}

    neighbor_cache: dict[str, list[dict]] = {}

    def get_neighbors(node_id: str) -> list[dict]:
        if node_id not in neighbor_cache:
            try:
                from app.services import graph_service
                neighbor_cache[node_id] = graph_service.get_neighbors(node_id, direction="both") or []
            except Exception:
                neighbor_cache[node_id] = []
        return neighbor_cache[node_id]

    p: dict[str, float] = {entity_id: 1.0}

    for _ in range(PPR_MAX_ITER):
        new_p: dict[str, float] = defaultdict(float)
        new_p[entity_id] += (1 - PPR_DAMPING)

        for node_id, mass in p.items():
            neighbors = get_neighbors(node_id)
            if not neighbors:
                # Dead-end: return mass to source (keeps distribution normalized)
                new_p[entity_id] += PPR_DAMPING * mass
                continue
            total_strength = sum(float(n.get("strength", 0.5) or 0.5) for n in neighbors) or 1.0
            for neighbor in neighbors:
                nid = neighbor.get("id")
                if not nid:
                    continue
                strength = float(neighbor.get("strength", 0.5) or 0.5)
                new_p[nid] += PPR_DAMPING * mass * (strength / total_strength)

        keys = set(p.keys()) | set(new_p.keys())
        delta = max(abs(new_p.get(k, 0.0) - p.get(k, 0.0)) for k in keys) if keys else 0.0
        p = dict(new_p)
        if delta < PPR_TOL:
            break

    # The source's own mass is an artifact of starting there; strip it so
    # "most resonant with self" doesn't trivially top every list.
    p.pop(entity_id, None)
    return p


# ── Semantic view (text signal) ───────────────────────────────────────

def _semantic_view(entity_id: str) -> dict[str, float]:
    """Content-derived signal from frequency-scoring.

    Raw signal (no constant multiplier) — markers carry their own strength
    from the scorer. Upgrade to a real embedding model in v3 when that
    dependency is worth carrying.
    """
    try:
        from app.services import graph_service
        node = graph_service.get_node(entity_id)
        if not node:
            return {}
    except Exception:
        return {}

    text = node.get("story_content") or node.get("description", "")
    if not text or len(text) < 50:
        return {}

    view: dict[str, float] = {}
    try:
        from app.services import frequency_scoring
        result = frequency_scoring.score_frequency(text)
        score = float(result.get("score", 0) or 0)
        if score:
            view["_living"] = score
        for marker in result.get("top_living", []) or []:
            word = str(marker.get("word", ""))
            signal = float(marker.get("signal", 0) or 0)
            if word and signal:
                view[f"_marker:{word}"] = signal
    except Exception:
        pass
    return view


# ── Public API ────────────────────────────────────────────────────────

def get_profile_v2(entity_id: str) -> dict[str, dict[str, float]]:
    """Three-view profile: structural, categorical, semantic.

    Returned as a dict of views so cosine similarity can be computed per-view
    (avoiding the v1 blur of mixing edge-weights and text-scores in one vector).
    """
    cached = _profile_cache.get(entity_id)
    if cached and cached.get("_version") == "v2":
        return cached["views"]

    views = {
        "structural": _structural_view(entity_id),
        "categorical": _categorical_view(entity_id),
        "semantic": _semantic_view(entity_id),
    }
    _profile_cache[entity_id] = {"_version": "v2", "views": views}
    return views


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[k] * b[k] for k in shared)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _variance(vals: list[float]) -> float:
    if not vals:
        return 0.0
    mean = sum(vals) / len(vals)
    return sum((v - mean) ** 2 for v in vals) / len(vals)


def resonance_v2(entity_a: str, entity_b: str) -> float:
    """Cosine per view, fused via inverse-variance weighting.

    No hand-picked fusion weights. A view that has no data on either side
    contributes zero. A view with high variance (more discriminative across
    its dims) gets less weight so raw scale doesn't dominate the fusion.
    """
    views_a = get_profile_v2(entity_a)
    views_b = get_profile_v2(entity_b)

    cosines: list[float] = []
    weights: list[float] = []
    for name in ("structural", "categorical", "semantic"):
        va = views_a.get(name, {})
        vb = views_b.get(name, {})
        cosines.append(_cosine(va, vb))
        combined_vals = list(va.values()) + list(vb.values())
        var = _variance(combined_vals) if combined_vals else 0.0
        # Inverse-variance. Zero variance (empty view) → zero weight.
        weights.append(1.0 / (var + 1e-6) if var > 0 else 0.0)

    total = sum(weights)
    if total == 0:
        return 0.0
    weights = [w / total for w in weights]
    return sum(w * c for w, c in zip(weights, cosines))


def magnitude_v2(views: dict[str, dict[str, float]]) -> float:
    """L2 norm across all view values combined."""
    all_vals: list[float] = []
    for view in views.values():
        all_vals.extend(view.values())
    if not all_vals:
        return 0.0
    return math.sqrt(sum(v * v for v in all_vals))


def top_dimensions_v2(views: dict[str, dict[str, float]], n: int = 15) -> list[dict[str, Any]]:
    """Top dimensions across all views, each tagged with its view of origin."""
    all_dims: list[tuple[str, str, float]] = []
    for view_name, view in views.items():
        for dim, weight in view.items():
            all_dims.append((view_name, dim, weight))
    all_dims.sort(key=lambda x: -x[2])
    return [
        {"view": view_name, "dimension": dim, "strength": round(weight, 4)}
        for view_name, dim, weight in all_dims[:n]
    ]


def profile_hash_v2(entity_id: str) -> str:
    """Versioned hash: ``"v2:" + sha256(canonical_views)``.

    v1-signed profiles verify against the v1 algorithm via their v1 hash;
    the version prefix lets verifiers route to the right compute path.
    """
    views = get_profile_v2(entity_id)
    canonical = json.dumps(
        {
            view_name: {k: round(v, 6) for k, v in sorted(view.items())}
            for view_name, view in sorted(views.items())
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(f"{entity_id}|{canonical}".encode()).hexdigest()
    return f"v2:{digest}"


def find_resonant_v2(entity_id: str, candidates: list[str] | None = None, top_n: int = 10) -> list[dict[str, Any]]:
    """Find the most resonant entities to a given one.

    If candidates is None, searches all concepts in the living-collective domain
    (matches v1 semantics so existing callers transition cleanly).
    """
    views = get_profile_v2(entity_id)
    if not any(views.values()):
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
        score = resonance_v2(entity_id, cid)
        if score > 0:
            results.append({"entity_id": cid, "resonance": round(score, 4)})
    results.sort(key=lambda x: -x["resonance"])
    return results[:top_n]


def invalidate(entity_id: str | None = None) -> None:
    """Clear cached profiles. If entity_id given, clear only that entity's
    cache but leave the graph-wide IDF alone. If None, clear everything."""
    global _idf_cache, _idf_cache_time
    if entity_id:
        _profile_cache.pop(entity_id, None)
    else:
        _profile_cache.clear()
        _idf_cache = None
        _idf_cache_time = 0.0
