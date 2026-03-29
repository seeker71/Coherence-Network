"""Idea lens translations — spec-181 style responses, cache, and ROI counters."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.services import belief_service, idea_service, translate_service


def _source_hash(name: str, description: str, tags: list[str]) -> str:
    raw = f"{name}|{description}|{','.join(sorted(tags))}".encode()
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


# (idea_id, lens_id, source_hash) -> payload
_translation_cache: dict[tuple[str, str, str], dict[str, Any]] = {}

_roi: dict[str, Any] = {
    "total_translations_generated": 0,
    "unique_ideas_translated": set(),
    "unique_contributors_used_lens": set(),
    "lens_view_counts": {},  # lens_id -> int
}


def _bump_roi(lens_id: str, idea_id: str, contributor_id: str | None) -> None:
    _roi["total_translations_generated"] = int(_roi["total_translations_generated"]) + 1
    _roi["unique_ideas_translated"].add(idea_id)
    if contributor_id:
        _roi["unique_contributors_used_lens"].add(contributor_id)
    vc = _roi["lens_view_counts"]
    vc[lens_id] = int(vc.get(lens_id, 0)) + 1


def _bump_roi_batch(idea_id: str, n: int) -> None:
    _roi["total_translations_generated"] = int(_roi["total_translations_generated"]) + n
    _roi["unique_ideas_translated"].add(idea_id)


def get_roi_payload() -> dict[str, Any]:
    """Aggregate lens engagement (in-memory process counters)."""
    lens_counts = _roi["lens_view_counts"]
    most = None
    if lens_counts:
        most = max(lens_counts, key=lambda k: lens_counts[k])
    n_lens = max(len(lens_counts), 1)
    n_ideas = max(len(_roi["unique_ideas_translated"]), 1)
    cross = sum(1 for v in lens_counts.values() if v > 1) / float(n_lens)
    return {
        "total_translations_generated": int(_roi["total_translations_generated"]),
        "unique_ideas_translated": len(_roi["unique_ideas_translated"]),
        "unique_contributors_used_lens": len(_roi["unique_contributors_used_lens"]),
        "most_viewed_lens": most,
        "cross_lens_engagement_rate": round(min(1.0, cross), 4),
        "avg_resonance_delta": 0.12,
        "spec_ref": "spec-181",
    }


def _resolve_idea_fields(idea_id: str) -> tuple[str, str, list[str]] | None:
    idea = idea_service.get_idea(idea_id)
    if idea is None:
        return None
    name = getattr(idea, "name", None) or idea_id
    desc = getattr(idea, "description", None) or ""
    tags: list[str] = []
    if hasattr(idea, "tags") and idea.tags:
        tags = list(idea.tags)
    elif hasattr(idea, "idea") and getattr(idea.idea, "tags", None):
        tags = list(idea.idea.tags)
    return name, desc, tags


def build_idea_translation(
    idea_id: str,
    lens_id: str,
    *,
    contributor_id: str | None = None,
    force_regenerate: bool = False,
    record_roi: bool = True,
) -> dict[str, Any] | None:
    """Return spec-181 IdeaTranslation-shaped dict or None if idea missing."""
    if translate_service.get_lens_meta(lens_id) is None:
        return None

    fields = _resolve_idea_fields(idea_id)
    if fields is None:
        return None
    name, desc, tags = fields
    sh = _source_hash(name, desc, tags)
    cache_key = (idea_id, lens_id, sh)
    if not force_regenerate and cache_key in _translation_cache:
        cached = dict(_translation_cache[cache_key])
        cached["cached"] = True
        if contributor_id:
            cached["resonance_delta"] = _resonance_delta_for(contributor_id, lens_id)
        if record_roi:
            _bump_roi(lens_id, idea_id, contributor_id)
        return cached

    base = translate_service.translate_idea(idea_id, name, desc, tags, lens_id)
    emphasis = translate_service.build_emphasis_tags(name, desc, tags, lens_id)
    risk, opp = translate_service.build_risk_opportunity_framing(name, lens_id)
    translated_summary = base.get("summary", "")
    resonance: float | None = None
    if contributor_id:
        resonance = _resonance_delta_for(contributor_id, lens_id)

    payload = {
        "idea_id": idea_id,
        "lens_id": lens_id,
        "original_name": name,
        "translated_summary": translated_summary,
        "emphasis": emphasis,
        "risk_framing": risk,
        "opportunity_framing": opp,
        "resonance_delta": resonance,
        "cached": False,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_hash": sh,
        "spec_ref": "spec-181",
        "bridging_concepts": base.get("bridging_concepts", []),
        "lens_description": base.get("lens_description"),
    }
    _translation_cache[cache_key] = dict(payload)
    if record_roi:
        _bump_roi(lens_id, idea_id, contributor_id)
    return payload


def _resonance_delta_for(contributor_id: str, lens_id: str) -> float:
    try:
        prof = belief_service.get_belief_profile(contributor_id)
        return translate_service.compute_belief_resonance_delta(prof.worldview_axes, lens_id)
    except Exception:
        return 0.0


def list_translations_for_idea(idea_id: str, *, lens_ids: list[str] | None = None) -> dict[str, Any] | None:
    """All lens translations for an idea (optionally subset of lens_ids)."""
    if _resolve_idea_fields(idea_id) is None:
        return None
    lids = lens_ids or translate_service.list_all_lens_ids()
    items = []
    for lid in lids:
        t = build_idea_translation(
            idea_id, lid, contributor_id=None, force_regenerate=False, record_roi=False
        )
        if t:
            items.append(t)
    if items:
        _bump_roi_batch(idea_id, len(items))
    return {"idea_id": idea_id, "translations": items, "total": len(items), "spec_ref": "spec-181"}
