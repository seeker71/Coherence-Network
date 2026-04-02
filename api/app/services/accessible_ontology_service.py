"""In-memory store for contributor-submitted ontology concepts (accessible ontology layer).

Plain-language concepts with domain tags, resonance, and inferred relations. This is the
non-technical extension path; Living Codex core concepts remain on /api/concepts.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Seeded domain vocabulary (labels for slugs contributors use in tags)
# ---------------------------------------------------------------------------

SEEDED_DOMAINS: list[dict[str, str]] = [
    {"slug": "science", "label": "Science"},
    {"slug": "music", "label": "Music"},
    {"slug": "ecology", "label": "Ecology"},
    {"slug": "finance", "label": "Finance"},
    {"slug": "technology", "label": "Technology"},
]

_store: dict[str, dict[str, Any]] = {}
_relations: dict[str, list[dict[str, Any]]] = defaultdict(list)
_resonances: dict[str, set[str]] = defaultdict(set)
_activity: list[dict[str, Any]] = []

# Backward-compatible aliases kept for older tests and internal call sites.
_contributions = _store
_inferred_edges = _relations
_domain_index: dict[str, set[str]] = defaultdict(set)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(event: str, concept_id: str) -> None:
    _activity.append({"date": _now_iso()[:10], "event": event, "concept_id": concept_id})


def reset_for_tests() -> None:
    """Clear all state (tests only)."""
    _store.clear()
    _relations.clear()
    _resonances.clear()
    _activity.clear()


def _domain_label(slug: str) -> str:
    for s in SEEDED_DOMAINS:
        if s["slug"] == slug:
            return s["label"]
    return slug.replace("_", " ").title()


def _web_status(api_status: str) -> str:
    if api_status == "confirmed":
        return "placed"
    if api_status == "deprecated":
        return "orphan"
    return "pending"


def _get_relations(concept_id: str) -> list[dict[str, Any]]:
    return list(_relations.get(concept_id, []))


def create_concept(
    title: str,
    body: str,
    domains: list[str],
    contributor_id: str | None,
) -> dict[str, Any]:
    cid = str(uuid.uuid4())
    now = _now_iso()
    record: dict[str, Any] = {
        "id": cid,
        "title": title,
        "body": body,
        "domains": domains,
        "contributor_id": contributor_id,
        "status": "pending",
        "resonance_score": 0.0,
        "confirmation_count": 0,
        "view_count": 0,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    _store[cid] = record
    _record("submission", cid)
    return {**record, "inferred_relations": []}


def list_concepts(
    domain: str | None,
    status: str | None,
    search: str | None,
) -> list[dict[str, Any]]:
    results = []
    for rec in _store.values():
        if rec["deleted_at"] is not None:
            continue
        if domain and domain not in rec["domains"]:
            continue
        if status and rec["status"] != status:
            continue
        if search and search.lower() not in rec["title"].lower():
            continue
        results.append({**rec, "inferred_relations": _get_relations(rec["id"])})
    return results


def get_concept(concept_id: str) -> dict[str, Any] | None:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        return None
    rec["view_count"] += 1
    return {**rec, "inferred_relations": _get_relations(concept_id)}


def patch_concept(
    concept_id: str,
    title: str | None,
    body: str | None,
    domains: list[str] | None,
    status: str | None,
) -> dict[str, Any] | None:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        return None
    if title is not None:
        rec["title"] = title
    if body is not None:
        rec["body"] = body
    if domains is not None:
        rec["domains"] = domains
    if status is not None:
        rec["status"] = status
        if status == "confirmed":
            rec["confirmation_count"] += 1
            _record("confirmation", concept_id)
    rec["updated_at"] = _now_iso()
    return {**rec, "inferred_relations": _get_relations(concept_id)}


def delete_concept(concept_id: str) -> bool:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        return False
    rec["deleted_at"] = _now_iso()
    return True


def resonate(concept_id: str, contributor_id: str | None) -> dict[str, Any] | None:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        return None
    contributor = contributor_id or "anonymous"
    if contributor not in _resonances[concept_id]:
        _resonances[concept_id].add(contributor)
        rec["resonance_score"] = min(1.0, float(rec["resonance_score"]) + 0.1)
        _record("resonance", concept_id)
    return {**rec, "inferred_relations": _get_relations(concept_id)}


def get_related(concept_id: str, min_confidence: float) -> list[dict[str, Any]] | None:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        return None
    return [r for r in _relations.get(concept_id, []) if r["confidence"] >= min_confidence]


def _to_garden_concept(r: dict[str, Any], idx: int, cluster: str) -> dict[str, Any]:
    rel_count = len(_relations.get(r["id"], []))
    return {
        "id": r["id"],
        "title": r["title"],
        "plain_text": r["body"],
        "domains": r["domains"],
        "status": _web_status(r["status"]),
        "garden_position": {
            "cluster": cluster,
            "x": float(idx % 12),
            "y": float(idx // 12),
        },
        "relationship_count": rel_count,
        "core_concept_match": None,
        "contributor_id": (r["contributor_id"] or "anonymous"),
    }


def get_garden_payload(limit: int = 200) -> dict[str, Any]:
    """Domains (API contract) plus clusters/concepts (web Ontology Garden page)."""
    domain_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in _store.values():
        if rec["deleted_at"] is not None:
            continue
        if rec["domains"]:
            for d in rec["domains"]:
                domain_map[d].append(rec)
        else:
            domain_map["general"].append(rec)

    domains_out: list[dict[str, Any]] = []
    for slug, recs in sorted(domain_map.items()):
        label = _domain_label(slug) if slug != "general" else "General"
        cards = [
            {
                "id": r["id"],
                "title": r["title"],
                "domains": r["domains"],
                "resonance_score": r["resonance_score"],
                "status": r["status"],
            }
            for r in recs[:limit]
        ]
        domains_out.append(
            {"slug": slug, "label": label, "concept_count": len(cards), "concepts": cards}
        )

    clusters: list[dict[str, Any]] = []
    flat_concepts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    idx = 0
    for slug, recs in sorted(domain_map.items()):
        members = [_to_garden_concept(r, idx + i, slug) for i, r in enumerate(recs[:limit])]
        idx += len(members)
        clusters.append({"name": slug, "size": len(members), "members": members})
        for m in members:
            cid = m["id"]
            if cid not in seen_ids and len(flat_concepts) < limit:
                seen_ids.add(cid)
                flat_concepts.append(m)

    contributors = {r["contributor_id"] or "anonymous" for r in _store.values() if r["deleted_at"] is None}
    placed = sum(1 for r in _store.values() if r["deleted_at"] is None and r["status"] == "confirmed")
    total_live = sum(1 for r in _store.values() if r["deleted_at"] is None)
    placement_rate = (placed / total_live) if total_live else 0.0

    return {
        "domains": domains_out,
        "clusters": clusters,
        "concepts": flat_concepts,
        "total": total_live,
        "contributor_count": len(contributors),
        "domain_count": len(domain_map),
        "placement_rate": placement_rate,
    }


def get_domains_list() -> list[dict[str, Any]]:
    domain_map: dict[str, int] = defaultdict(int)
    for rec in _store.values():
        if rec["deleted_at"] is None:
            for d in rec["domains"]:
                domain_map[d] += 1
    result = []
    for seed in SEEDED_DOMAINS:
        result.append(
            {
                "slug": seed["slug"],
                "label": seed["label"],
                "concept_count": domain_map[seed["slug"]],
            }
        )
    return result


def get_activity(since: str | None) -> list[dict[str, Any]]:
    date_buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"submissions": 0, "confirmations": 0, "resonances": 0}
    )
    for ev in _activity:
        if since and ev["date"] < since[:10]:
            continue
        event_type = ev["event"]
        if event_type == "submission":
            date_buckets[ev["date"]]["submissions"] += 1
        elif event_type == "confirmation":
            date_buckets[ev["date"]]["confirmations"] += 1
        elif event_type == "resonance":
            date_buckets[ev["date"]]["resonances"] += 1
    return [{"date": d, **counts} for d, counts in sorted(date_buckets.items())]


def get_stats() -> dict[str, Any]:
    live = [r for r in _store.values() if r["deleted_at"] is None]
    total = len(live)
    placed = sum(1 for r in live if r["status"] == "confirmed")
    pending = sum(1 for r in live if r["status"] == "pending")
    orphan = sum(1 for r in live if r["status"] == "deprecated")
    domain_counts: dict[str, int] = defaultdict(int)
    for r in live:
        for d in r["domains"]:
            domain_counts[d] += 1
    top_domains = sorted(
        [{"domain": k, "count": v} for k, v in domain_counts.items()],
        key=lambda x: (-x["count"], x["domain"]),
    )[:12]
    recent: list[str] = []
    seen_c: set[str] = set()
    for r in sorted(live, key=lambda x: x["created_at"], reverse=True):
        cid = r["contributor_id"] or "anonymous"
        if cid not in seen_c:
            seen_c.add(cid)
            recent.append(cid)
        if len(recent) >= 10:
            break
    inferred_edges = sum(len(_relations[k]) for k in _relations)
    placement_rate = (placed / total) if total else 0.0
    return {
        "total_contributions": total,
        "placed_count": placed,
        "pending_count": pending,
        "orphan_count": orphan,
        "placement_rate": placement_rate,
        "top_domains": top_domains,
        "recent_contributors": recent,
        "inferred_edges_count": inferred_edges,
    }
