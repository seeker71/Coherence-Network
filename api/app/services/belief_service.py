"""Belief profiles stored on contributor graph nodes (properties.belief_profile)."""

from __future__ import annotations

import re
from typing import Any

from app.models.belief import (
    BeliefProfile,
    BeliefProfileUpdate,
    BeliefResonanceBreakdown,
    BeliefResonanceResponse,
    WORLDVIEW_CHOICES,
    default_axis_values,
)
from app.services import graph_service
from app.services import idea_service

_KEY = "belief_profile"

# Keywords hinting at a worldview (for resonance heuristic)
_WORLDVIEW_HINTS: dict[str, tuple[str, ...]] = {
    "scientific": ("empir", "study", "evidence", "experiment", "hypothesis", "peer", "data"),
    "spiritual": ("spirit", "soul", "sacred", "meaning", "transcend", "faith", "consciousness"),
    "pragmatic": ("pragmatic", "ship", "deliver", "mvp", "workable", "usable", "tool"),
    "holistic": ("whole", "holistic", "ecosystem", "system", "interconnected"),
    "integrative": ("integrat", "bridge", "unify", "synthesis", "combine"),
    "speculative": ("speculat", "future", "novel", "explore", "possible", "maybe"),
}


def _find_contributor_node(contributor_id: str) -> dict[str, Any] | None:
    cid = (contributor_id or "").strip()
    if not cid:
        return None
    node = graph_service.get_node(f"contributor:{cid}")
    if node:
        return node
    result = graph_service.list_nodes(type="contributor", limit=500)
    for n in result.get("items", []):
        if n.get("legacy_id") == str(cid) or n.get("name") == cid:
            return n
    return None


def _node_id(node: dict[str, Any]) -> str:
    raw = node.get("id") or ""
    if raw.startswith("contributor:"):
        return raw.split(":", 1)[1]
    return str(node.get("name") or raw or "")


def _parse_profile_blob(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        import json

        try:
            return dict(json.loads(raw))
        except json.JSONDecodeError:
            return {}
    return {}


def _to_profile(contributor_id: str, blob: dict[str, Any]) -> BeliefProfile:
    axes = default_axis_values()
    merged_axes = blob.get("axis_values") or {}
    if isinstance(merged_axes, dict):
        for k, v in merged_axes.items():
            try:
                axes[str(k).strip().lower().replace(" ", "-")] = max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                pass
    concepts: dict[str, float] = {}
    cw = blob.get("concept_weights") or {}
    if isinstance(cw, dict):
        for k, v in cw.items():
            try:
                key = str(k).strip().lower().replace(" ", "-")
                if key:
                    concepts[key] = max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                pass
    wv = str(blob.get("worldview") or "pragmatic").strip().lower()
    if wv not in WORLDVIEW_CHOICES:
        wv = "pragmatic"
    return BeliefProfile(
        contributor_id=contributor_id,
        worldview=wv,
        concept_weights=concepts,
        axis_values=axes,
    )


def get_belief_profile(contributor_id: str) -> BeliefProfile | None:
    node = _find_contributor_node(contributor_id)
    if not node:
        return None
    props = node.get("properties") or {}
    blob = _parse_profile_blob(props.get(_KEY))
    return _to_profile(_node_id(node), blob)


def patch_belief_profile(contributor_id: str, update: BeliefProfileUpdate) -> BeliefProfile | None:
    node = _find_contributor_node(contributor_id)
    if not node:
        return None
    nid = node.get("id")
    if not nid:
        return None
    current = _to_profile(_node_id(node), _parse_profile_blob((node.get("properties") or {}).get(_KEY)))
    data = current.model_dump()
    if update.worldview is not None:
        wv = update.worldview.strip().lower()
        data["worldview"] = wv if wv in WORLDVIEW_CHOICES else current.worldview
    if update.concept_weights is not None:
        merged = dict(data["concept_weights"])
        for k, v in update.concept_weights.items():
            key = str(k).strip().lower().replace(" ", "-")
            if not key:
                continue
            merged[key] = max(0.0, min(1.0, float(v)))
        data["concept_weights"] = merged
    if update.axis_values is not None:
        merged = dict(data["axis_values"])
        for k, v in update.axis_values.items():
            key = str(k).strip().lower().replace(" ", "-")
            if not key:
                continue
            merged[key] = max(0.0, min(1.0, float(v)))
        data["axis_values"] = merged
    graph_service.update_node(
        nid,
        properties={_KEY: data},
    )
    refreshed = graph_service.get_node(nid)
    if not refreshed:
        return None
    return _to_profile(_node_id(refreshed), _parse_profile_blob((refreshed.get("properties") or {}).get(_KEY)))


def _idea_text_blob(idea: Any) -> str:
    parts = [
        getattr(idea, "name", "") or "",
        getattr(idea, "description", "") or "",
        " ".join(getattr(idea, "interfaces", []) or []),
    ]
    return " ".join(parts).lower()


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9-]*", re.I)


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text)}


def _implied_axis_vector(blob: str) -> dict[str, float]:
    """Rough axis scores from idea text (keyword families)."""
    axes = default_axis_values()
    families: dict[str, tuple[str, ...]] = {
        "empirical": ("evidence", "measure", "metric", "data", "experiment", "validate", "test"),
        "systemic": ("system", "graph", "network", "flow", "pipeline", "architecture"),
        "humanistic": ("human", "people", "community", "care", "experience", "usability"),
        "technical": ("api", "code", "implement", "build", "deploy", "stack", "type"),
        "intuitive": ("intuitive", "feel", "sense", "discovery", "serendipity"),
        "pragmatic": ("ship", "mvp", "fast", "pragmatic", "usable", "tool"),
    }
    for axis, words in families.items():
        hit = sum(1 for w in words if w in blob)
        if hit:
            axes[axis] = min(1.0, 0.35 + 0.12 * hit)
    return axes


def compute_resonance(contributor_id: str, idea_id: str) -> BeliefResonanceResponse | None:
    prof = get_belief_profile(contributor_id)
    if not prof:
        return None
    idea = idea_service.get_idea(idea_id)
    if not idea:
        return None
    blob = _idea_text_blob(idea)
    toks = _tokens(blob)

    matched: list[str] = []
    for tag in prof.concept_weights:
        if tag in toks or tag in blob.replace("-", " "):
            matched.append(tag)
            continue
        sub = tag.replace("-", "")
        if sub and sub in blob.replace("-", ""):
            matched.append(tag)

    if prof.concept_weights:
        if matched:
            overlap = sum(prof.concept_weights[t] for t in matched)
            total = sum(prof.concept_weights.values()) or 1.0
            concept_al = min(1.0, overlap / total)
        else:
            concept_al = 0.2
    else:
        concept_al = 0.5

    wv = prof.worldview
    hints = _WORLDVIEW_HINTS.get(wv, ())
    wv_hits = sum(1 for h in hints if h in blob)
    worldview_al = min(1.0, 0.25 + 0.15 * wv_hits) if hints else 0.5

    implied = _implied_axis_vector(blob)
    user_axes = prof.axis_values
    num = 0.0
    den = 0.0
    for k, uv in user_axes.items():
        iv = implied.get(k, 0.5)
        num += uv * iv
        den += max(uv * uv, 1e-6)
    axis_al = num / den if den > 0 else 0.5
    axis_al = max(0.0, min(1.0, axis_al))

    score = 0.35 * concept_al + 0.25 * worldview_al + 0.40 * axis_al
    score = max(0.0, min(1.0, score))

    return BeliefResonanceResponse(
        contributor_id=prof.contributor_id,
        idea_id=idea_id,
        resonance_score=score,
        breakdown=BeliefResonanceBreakdown(
            concept_alignment=concept_al,
            worldview_alignment=worldview_al,
            axis_alignment=axis_al,
        ),
        matched_concepts=matched,
    )
