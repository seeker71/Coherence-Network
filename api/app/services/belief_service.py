"""Belief profiles on contributor nodes + resonance vs ideas."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any

from app.services import graph_service, idea_service

BELIEF_KEY = "belief_profile"

CANONICAL_AXES: tuple[str, ...] = (
    "empirical",
    "collaborative",
    "strategic",
    "technical",
    "ethical",
)

WORLDVIEWS: frozenset[str] = frozenset(
    {"scientific", "spiritual", "pragmatic", "holistic", "artistic", "systems"},
)

WORLDVIEW_KEYWORDS: dict[str, frozenset[str]] = {
    "scientific": frozenset(
        {"science", "experiment", "data", "measure", "hypothesis", "evidence", "empirical"},
    ),
    "spiritual": frozenset({"meaning", "purpose", "consciousness", "wisdom", "values", "care"}),
    "pragmatic": frozenset({"ship", "deliver", "practical", "cost", "roi", "implementation"}),
    "holistic": frozenset({"system", "whole", "ecosystem", "integrate", "network", "graph"}),
    "artistic": frozenset({"design", "experience", "aesthetic", "narrative", "ux", "interface"}),
    "systems": frozenset({"architecture", "layer", "dependency", "pipeline", "service"}),
}


def _default_axis_weights() -> dict[str, float]:
    return {a: 0.5 for a in CANONICAL_AXES}


def resolve_contributor_node(contributor_id: str) -> tuple[str, dict[str, Any]] | None:
    node = graph_service.get_node(f"contributor:{contributor_id}")
    if node:
        return f"contributor:{contributor_id}", node
    result = graph_service.list_nodes(type="contributor", limit=500)
    for n in result.get("items", []):
        if n.get("legacy_id") == str(contributor_id) or n.get("name") == contributor_id:
            nid = n.get("id")
            if nid:
                return str(nid), n
    return None


def _parse_stored_profile(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return raw


def _normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "worldview": "pragmatic",
        "axis_weights": _default_axis_weights(),
        "concept_weights": {},
    }
    ws = str(raw.get("worldview", "pragmatic")).lower()
    base["worldview"] = ws if ws in WORLDVIEWS else "pragmatic"
    axes = _default_axis_weights()
    aw = raw.get("axis_weights")
    if isinstance(aw, dict):
        for k, v in aw.items():
            if k in CANONICAL_AXES and isinstance(v, (int, float)):
                axes[k] = max(0.0, min(1.0, float(v)))
    base["axis_weights"] = axes
    concepts: dict[str, float] = {}
    cw = raw.get("concept_weights")
    if isinstance(cw, dict):
        for k, v in cw.items():
            if not isinstance(k, str) or not k.strip():
                continue
            if isinstance(v, (int, float)):
                concepts[k.strip().lower()] = max(0.0, min(1.0, float(v)))
    base["concept_weights"] = concepts
    return base


def get_belief_profile_dict(contributor_id: str) -> dict[str, Any] | None:
    resolved = resolve_contributor_node(contributor_id)
    if not resolved:
        return None
    _, node = resolved
    props = node.get("properties") or {}
    raw = _parse_stored_profile(props.get(BELIEF_KEY))
    merged = _normalize_profile(raw)
    ts = props.get("belief_profile_updated_at")
    merged["updated_at"] = ts
    return merged


def save_belief_profile(contributor_id: str, update: dict[str, Any]) -> dict[str, Any] | None:
    resolved = resolve_contributor_node(contributor_id)
    if not resolved:
        return None
    node_id, node = resolved
    props = dict(node.get("properties") or {})
    raw = _parse_stored_profile(props.get(BELIEF_KEY))
    current = _normalize_profile(raw)
    if update.get("worldview") is not None:
        w = str(update["worldview"]).lower()
        if w in WORLDVIEWS:
            current["worldview"] = w
    aw = update.get("axis_weights")
    if isinstance(aw, dict):
        for k, v in aw.items():
            if k in CANONICAL_AXES and isinstance(v, (int, float)):
                current["axis_weights"][k] = max(0.0, min(1.0, float(v)))
    cw = update.get("concept_weights")
    if isinstance(cw, dict):
        for k, v in cw.items():
            if not isinstance(k, str) or not k.strip():
                continue
            if isinstance(v, (int, float)):
                current["concept_weights"][k.strip().lower()] = max(0.0, min(1.0, float(v)))
    now = datetime.now(timezone.utc).isoformat()
    props[BELIEF_KEY] = current
    props["belief_profile_updated_at"] = now
    graph_service.update_node(node_id, properties=props)
    current["updated_at"] = now
    return current


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.lower()))


def _idea_text(idea: Any) -> str:
    parts = [idea.name, idea.description]
    if getattr(idea, "interfaces", None):
        parts.extend(idea.interfaces)
    return " ".join(parts)


def _idea_axis_vector(tokens: set[str]) -> dict[str, float]:
    empirical_hits = len(
        tokens & {"data", "measure", "test", "evidence", "metric", "validate", "empirical"},
    )
    collaborative_hits = len(
        tokens & {"community", "contributor", "share", "collaborate", "team", "human"},
    )
    strategic_hits = len(
        tokens & {"goal", "roadmap", "priority", "portfolio", "governance", "strategy"},
    )
    technical_hits = len(
        tokens & {"api", "code", "build", "deploy", "implementation", "graph", "runtime"},
    )
    ethical_hits = len(tokens & {"trust", "security", "privacy", "fair", "value", "ethical"})

    def norm(x: float) -> float:
        return max(0.0, min(1.0, x / 5.0))

    return {
        "empirical": norm(float(empirical_hits) + 0.1),
        "collaborative": norm(float(collaborative_hits) + 0.1),
        "strategic": norm(float(strategic_hits) + 0.1),
        "technical": norm(float(technical_hits) + 0.2),
        "ethical": norm(float(ethical_hits) + 0.1),
    }


def _cosine_sim(
    a: dict[str, float],
    b: dict[str, float],
    keys: tuple[str, ...],
) -> float:
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(a.get(k, 0.0) ** 2 for k in keys))
    nb = math.sqrt(sum(b.get(k, 0.0) ** 2 for k in keys))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


def _concept_match_score(tokens: set[str], text_lower: str, contrib_concepts: dict[str, float]) -> tuple[float, list[str]]:
    if not contrib_concepts:
        return 0.35, []
    matches: list[str] = []
    weights: list[float] = []
    for concept, weight in contrib_concepts.items():
        c = concept.lower()
        hit = c in tokens or c in text_lower
        if not hit and len(c) > 3:
            hit = any(c in t or t in c for t in tokens)
        if hit:
            matches.append(concept)
            weights.append(weight)
    if not matches:
        return 0.12, []
    avg_w = sum(weights) / len(weights)
    cover = len(matches) / max(len(contrib_concepts), 1)
    return max(0.0, min(1.0, avg_w * (cover**0.5))), sorted(set(matches))[:20]


def compute_resonance(contributor_id: str, idea_id: str) -> dict[str, Any] | None:
    prof = get_belief_profile_dict(contributor_id)
    if prof is None:
        return None
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        return None
    text = _idea_text(idea)
    text_lower = text.lower()
    tokens = _tokenize(text)
    contrib_concepts = prof.get("concept_weights") or {}
    concept_part, match_list = _concept_match_score(tokens, text_lower, contrib_concepts)

    idea_axes = _idea_axis_vector(tokens)
    user_axes = prof.get("axis_weights") or _default_axis_weights()
    axis_align = _cosine_sim(user_axes, idea_axes, CANONICAL_AXES)

    w_scores: dict[str, float] = {}
    for w, kws in WORLDVIEW_KEYWORDS.items():
        w_scores[w] = float(len(tokens & kws))
    best_w = max(w_scores.keys(), key=lambda x: w_scores[x]) if w_scores else "pragmatic"
    user_w = str(prof.get("worldview", "pragmatic"))
    best_score = w_scores.get(best_w, 0.0)
    user_score = w_scores.get(user_w, 0.0)
    if best_score < 1e-9:
        w_align = 0.5
    elif best_w == user_w:
        w_align = 1.0
    else:
        w_align = 0.25 + 0.75 * min(1.0, user_score / max(best_score, 0.01))

    resonance = 0.35 * concept_part + 0.45 * axis_align + 0.20 * w_align
    resonance = max(0.0, min(1.0, resonance))

    return {
        "contributor_id": contributor_id,
        "idea_id": idea_id,
        "resonance_score": round(resonance, 4),
        "concept_overlap": round(concept_part, 4),
        "axis_alignment": round(axis_align, 4),
        "worldview_alignment": round(min(1.0, w_align), 4),
        "matching_concepts": match_list,
        "idea_worldview_signal": best_w,
    }
