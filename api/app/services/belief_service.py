"""Belief profiles stored on contributor graph node properties."""

from __future__ import annotations

import re
from typing import Any

from app.models.belief import (
    DEFAULT_AXIS_KEYS,
    BeliefProfile,
    BeliefProfileUpdate,
    BeliefResonanceResponse,
    BeliefResonanceScores,
)
from app.services import graph_service, idea_service

BELIEF_KEY = "belief_profile"

_ALLOWED_WORLDVIEWS = frozenset(
    {"scientific", "spiritual", "pragmatic", "holistic", "artistic", "systems"}
)

_WORLDVIEW_KEYWORDS: dict[str, list[str]] = {
    "scientific": ("experiment", "hypothesis", "evidence", "peer", "study", "data", "empirical", "research"),
    "spiritual": ("meaning", "consciousness", "soul", "faith", "meditation", "wisdom", "transcend"),
    "pragmatic": ("ship", "deliver", "mvp", "practical", "constraint", "budget", "deadline", "tool"),
    "holistic": ("whole", "ecosystem", "balance", "integrat", "wellbeing", "context", "interconnect"),
    "artistic": ("design", "aesthetic", "creative", "story", "express", "beauty", "craft"),
    "systems": ("feedback", "invariant", "architecture", "graph", "node", "emergent", "complex"),
}


def _resolve_contributor_node(contributor_id: str) -> dict[str, Any] | None:
    """Find contributor graph node by stable id or legacy UUID."""
    cid = (contributor_id or "").strip()
    if not cid:
        return None
    node = graph_service.get_node(f"contributor:{cid}")
    if node:
        return node
    result = graph_service.list_nodes(type="contributor", limit=500)
    for n in result.get("items", []):
        if n.get("legacy_id") == cid or n.get("name") == cid:
            return n
    return None


def _node_id_from_node(node: dict[str, Any]) -> str:
    raw = node.get("id") or ""
    if raw.startswith("contributor:"):
        return raw[len("contributor:") :]
    return raw or ""


def _default_axes() -> dict[str, float]:
    return {k: 0.5 for k in DEFAULT_AXIS_KEYS}


def _normalize_profile_dict(raw: dict[str, Any] | None) -> dict[str, Any]:
    if raw is None or not isinstance(raw, dict):
        raw = {}
    axes = raw.get("axes") if isinstance(raw.get("axes"), dict) else {}
    concepts = raw.get("concepts") if isinstance(raw.get("concepts"), dict) else {}
    wv = raw.get("worldview")
    if isinstance(wv, str) and wv.strip():
        worldview = wv.strip() if wv.strip() in _ALLOWED_WORLDVIEWS else "pragmatic"
    else:
        worldview = "pragmatic"
    merged_axes = dict(_default_axes())
    for k, v in axes.items():
        if not isinstance(k, str):
            continue
        try:
            merged_axes[k] = float(v)
        except (TypeError, ValueError):
            continue
    for k in list(merged_axes.keys()):
        merged_axes[k] = max(0.0, min(1.0, float(merged_axes[k])))
    clean_concepts: dict[str, float] = {}
    for k, v in concepts.items():
        if not isinstance(k, str) or not k.strip():
            continue
        try:
            clean_concepts[k.strip().lower()] = max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            continue
    return {"worldview": worldview, "axes": merged_axes, "concepts": clean_concepts}


def get_beliefs(contributor_id: str) -> BeliefProfile | None:
    node = _resolve_contributor_node(contributor_id)
    if not node:
        return None
    props = node.get("properties") or {}
    raw = props.get(BELIEF_KEY)
    merged = _normalize_profile_dict(raw if isinstance(raw, dict) else {})
    legacy = props.get("legacy_id") or ""
    cid_out = str(legacy) if legacy else _node_id_from_node(node)
    wv = merged["worldview"]
    if wv not in _ALLOWED_WORLDVIEWS:
        wv = "pragmatic"
    return BeliefProfile(
        contributor_id=cid_out or contributor_id,
        worldview=wv,  # type: ignore[arg-type]
        axes=merged["axes"],
        concepts=merged["concepts"],
    )


def patch_beliefs(contributor_id: str, update: BeliefProfileUpdate) -> BeliefProfile | None:
    node = _resolve_contributor_node(contributor_id)
    if not node:
        return None
    node_id = node.get("id")
    if not node_id:
        return None
    current = get_beliefs(contributor_id)
    if not current:
        return None
    new_worldview = update.worldview if update.worldview is not None else current.worldview
    new_axes = dict(current.axes)
    if update.axes is not None:
        new_axes.update(update.axes)
    new_concepts = dict(current.concepts)
    if update.concepts is not None:
        new_concepts.update(update.concepts)
    payload = _normalize_profile_dict(
        {"worldview": new_worldview, "axes": new_axes, "concepts": new_concepts}
    )
    graph_service.update_node(node_id, properties={BELIEF_KEY: payload})
    return get_beliefs(contributor_id)


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]{3,}", text.lower())
    return set(words)


def _idea_text_blob(idea: Any) -> str:
    parts = [idea.name or "", idea.description or ""]
    if getattr(idea, "interfaces", None):
        parts.extend(str(x) for x in idea.interfaces if x)
    return "\n".join(parts)


def _infer_axes_from_text(text: str) -> dict[str, float]:
    low = text.lower()
    scores = {k: 0.5 for k in DEFAULT_AXIS_KEYS}
    buckets: dict[str, list[str]] = {
        "rigor": ("proof", "test", "verify", "formal", "spec", "invariant", "metric"),
        "empathy": ("user", "people", "community", "care", "inclusive", "access"),
        "speed": ("fast", "quick", "latency", "ship", "mvp", "iterate"),
        "creativity": ("novel", "creative", "design", "explore", "idea"),
        "collaboration": ("team", "together", "review", "share", "open", "contrib"),
        "systems": ("graph", "pipeline", "architecture", "scale", "network", "node"),
    }
    for axis, keys in buckets.items():
        hit = sum(1 for k in keys if k in low)
        if hit:
            scores[axis] = min(1.0, 0.5 + 0.1 * hit)
    return scores


def _worldview_fit(worldview: str, text: str) -> float:
    low = text.lower()
    keys = _WORLDVIEW_KEYWORDS.get(worldview, ())
    if any(k in low for k in keys):
        return 1.0
    # soft match: any worldview keyword from other lenses still gives partial signal
    any_hit = any(k in low for ks in _WORLDVIEW_KEYWORDS.values() for k in ks)
    return 0.45 if any_hit else 0.35


def compute_resonance(contributor_id: str, idea_id: str) -> BeliefResonanceResponse | None:
    beliefs = get_beliefs(contributor_id)
    if not beliefs:
        return None
    idea = idea_service.get_idea(idea_id)
    if not idea:
        return None
    text = _idea_text_blob(idea)
    tokens = _tokenize(text)
    concept_tags = list(beliefs.concepts.keys())
    matched = [t for t in concept_tags if t in tokens or any(t in tok or tok in t for tok in tokens)]
    if concept_tags:
        jacc = len(set(concept_tags) & tokens) / max(1, len(set(concept_tags) | tokens))
        overlap = min(1.0, 0.5 * jacc + 0.5 * (len(matched) / max(1, len(concept_tags))))
    else:
        overlap = 0.4

    wv_fit = _worldview_fit(str(beliefs.worldview), text)

    inferred = _infer_axes_from_text(text)
    axis_sum = 0.0
    n = 0
    for k, v in beliefs.axes.items():
        if k in inferred:
            axis_sum += 1.0 - abs(float(v) - float(inferred[k]))
            n += 1
    axis_align = axis_sum / n if n else 0.5

    overall = 0.38 * overlap + 0.32 * wv_fit + 0.30 * axis_align
    overall = max(0.0, min(1.0, overall))

    return BeliefResonanceResponse(
        contributor_id=beliefs.contributor_id,
        idea_id=idea.id,
        idea_name=idea.name,
        scores=BeliefResonanceScores(
            overall=round(overall, 4),
            concept_overlap=round(overlap, 4),
            worldview_fit=round(wv_fit, 4),
            axis_alignment=round(axis_align, 4),
        ),
        matched_concepts=sorted(set(matched))[:32],
        notes="Heuristic overlap from idea text vs belief tags, worldview keywords, and axis inference.",
    )
