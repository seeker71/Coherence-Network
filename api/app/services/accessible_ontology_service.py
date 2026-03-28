"""Accessible ontology service — lets non-technical contributors extend the ontology
in plain language.  The system infers relationships, finds placements, and surfaces
concepts as gardens/cards rather than raw graph nodes.

Storage: in-memory (session-scoped).  A future migration to PostgreSQL is tracked
under the 'ontology-persistence' follow-up task.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_contributions: dict[str, dict[str, Any]] = {}   # id -> record
_inferred_edges: list[dict[str, Any]] = []        # relationship records
_domain_index: dict[str, list[str]] = {}          # domain -> [concept_id]


# ---------------------------------------------------------------------------
# Keyword → relationship-type heuristics
# (used when a full LLM is not available in the request path)
# ---------------------------------------------------------------------------

_REL_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\b(part of|within|inside|component of|member of)\b", re.I),
     "part-of", "lexical part-of signal"),
    (re.compile(r"\b(causes?|leads? to|results? in|produces?|creates?)\b", re.I),
     "causes", "lexical causation signal"),
    (re.compile(r"\b(like|similar to|resembles?|analogous to)\b", re.I),
     "similar-to", "lexical similarity signal"),
    (re.compile(r"\b(opposite of|contrary to|contrast with|versus)\b", re.I),
     "opposes", "lexical opposition signal"),
    (re.compile(r"\b(depends? on|requires?|needs?|relies? on)\b", re.I),
     "depends-on", "lexical dependency signal"),
    (re.compile(r"\b(extends?|builds? on|evolves? from|derived from)\b", re.I),
     "extends", "lexical extension signal"),
    (re.compile(r"\b(enables?|allows?|supports?|facilitates?)\b", re.I),
     "enables", "lexical enablement signal"),
]

# Core concept keywords for placement (simplified without live DB)
_CORE_CONCEPT_KEYWORDS: dict[str, list[str]] = {
    "coherence": ["coherence", "alignment", "harmony", "consistency", "resonance"],
    "flow": ["flow", "stream", "movement", "current", "transition"],
    "emergence": ["emergence", "emerges", "arising", "spontaneous", "complex"],
    "identity": ["identity", "self", "who", "personal", "unique"],
    "structure": ["structure", "form", "pattern", "organisation", "architecture"],
    "value": ["value", "worth", "meaning", "importance", "significance"],
    "relationship": ["relationship", "connection", "link", "bond", "tie"],
    "knowledge": ["knowledge", "understanding", "wisdom", "learning", "insight"],
    "change": ["change", "transform", "evolve", "shift", "transition"],
    "balance": ["balance", "equilibrium", "stability", "harmony", "homeostasis"],
    "creativity": ["creativity", "create", "invent", "imagine", "novel"],
    "community": ["community", "collective", "together", "shared", "social"],
    "growth": ["growth", "grow", "expand", "develop", "progress"],
    "perception": ["perceive", "observe", "notice", "sense", "aware"],
    "time": ["time", "temporal", "duration", "moment", "sequence"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    """Convert free text to a short slug suitable for use as an id."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text[:40].strip("-")


def _infer_title(plain_text: str) -> str:
    """Extract a short title (first sentence or first 60 chars)."""
    sentence = re.split(r"[.!?]", plain_text)[0].strip()
    if len(sentence) <= 60:
        return sentence or plain_text[:60]
    # Capitalise significant words up to 8 words
    words = sentence.split()[:8]
    return " ".join(w.capitalize() if i == 0 else w for i, w in enumerate(words))


def _find_core_concept_match(plain_text: str) -> str | None:
    """Return the core concept id that best matches the plain_text, or None."""
    lower = plain_text.lower()
    best_id, best_score = None, 0
    for concept_id, keywords in _CORE_CONCEPT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > best_score:
            best_score, best_id = score, concept_id
    return best_id if best_score > 0 else None


def _infer_relationships(
    concept_id: str,
    plain_text: str,
    domains: list[str],
    all_contributions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Infer relationships to existing contributions and core concepts."""
    rels: list[dict[str, Any]] = []
    lower = plain_text.lower()

    # 1. Pattern-based relationships from text
    for pattern, rel_type, reason in _REL_PATTERNS:
        if pattern.search(plain_text):
            # Find the best matching other contribution
            for other_id, other in all_contributions.items():
                if other_id == concept_id:
                    continue
                other_lower = other["plain_text"].lower()
                # Shared domain signals relevance
                shared_domains = set(domains) & set(other.get("domains", []))
                if shared_domains or _token_overlap(lower, other_lower) > 0.2:
                    rels.append({
                        "concept_id": other_id,
                        "concept_name": other["title"],
                        "relationship_type": rel_type,
                        "confidence": min(0.4 + 0.3 * len(shared_domains), 0.9),
                        "reason": reason + (
                            f" (shared domains: {', '.join(shared_domains)})"
                            if shared_domains else ""
                        ),
                    })

    # 2. Domain-cohort relationship (other contributions in same domain)
    for domain in domains:
        cohort = _domain_index.get(domain, [])
        for other_id in cohort[:5]:  # cap at 5 per domain
            if other_id == concept_id:
                continue
            if not any(r["concept_id"] == other_id for r in rels):
                other = all_contributions.get(other_id)
                if other:
                    rels.append({
                        "concept_id": other_id,
                        "concept_name": other["title"],
                        "relationship_type": "same-domain",
                        "confidence": 0.6,
                        "reason": f"both tagged with domain '{domain}'",
                    })

    # Deduplicate by concept_id, keeping highest confidence
    seen: dict[str, dict[str, Any]] = {}
    for r in rels:
        cid = r["concept_id"]
        if cid not in seen or r["confidence"] > seen[cid]["confidence"]:
            seen[cid] = r

    return list(seen.values())[:10]  # cap total inferred rels


def _token_overlap(a: str, b: str) -> float:
    """Jaccard similarity of word token sets."""
    tokens_a = set(re.findall(r"\w+", a))
    tokens_b = set(re.findall(r"\w+", b))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    # Remove very common words
    stop = {"the", "a", "an", "is", "are", "of", "and", "or", "in", "it", "to"}
    intersection -= stop
    if not intersection:
        return 0.0
    return len(intersection) / len(tokens_a | tokens_b)


def _garden_position(concept_id: str, domains: list[str], idx: int) -> dict[str, Any]:
    """Deterministic garden x/y position + cluster assignment."""
    # Cluster by first domain if available, else by hash
    cluster = domains[0] if domains else "general"
    # Spread items in a pseudo-random but deterministic grid
    h = int(hashlib.md5(concept_id.encode()).hexdigest()[:8], 16)
    angle = (h % 360) * math.pi / 180
    radius = 100 + (h % 200)
    return {
        "cluster": cluster,
        "x": round(math.cos(angle) * radius, 2),
        "y": round(math.sin(angle) * radius, 2),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def submit_plain_language(
    plain_text: str,
    contributor_id: str = "anonymous",
    domains: list[str] | None = None,
    title: str | None = None,
    view_preference: str = "garden",
) -> dict[str, Any]:
    """Accept a plain-language description and place it in the ontology."""
    domains = [d.lower().strip() for d in (domains or [])]
    title = title or _infer_title(plain_text)

    # Generate stable id from contributor + title
    raw = f"{contributor_id}:{title}:{plain_text[:40]}"
    concept_id = _slugify(title) + "-" + hashlib.md5(raw.encode()).hexdigest()[:6]

    if concept_id in _contributions:
        # Return existing record with 409 handled by caller
        return _contributions[concept_id]

    core_match = _find_core_concept_match(plain_text)
    status = "placed" if core_match else "pending"

    record: dict[str, Any] = {
        "id": concept_id,
        "title": title,
        "plain_text": plain_text,
        "contributor_id": contributor_id,
        "domains": domains,
        "status": status,
        "core_concept_match": core_match,
        "view_preference": view_preference,
        "garden_position": _garden_position(concept_id, domains, len(_contributions)),
        "inferred_relationships": [],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }

    _contributions[concept_id] = record

    # Update domain index
    for domain in domains:
        _domain_index.setdefault(domain, []).append(concept_id)

    # Infer relationships (runs after insertion so self-reference is excluded)
    rels = _infer_relationships(concept_id, plain_text, domains, _contributions)
    record["inferred_relationships"] = rels

    # Persist inferred edges globally
    for rel in rels:
        edge = {
            "id": str(uuid.uuid4())[:12],
            "from": concept_id,
            "to": rel["concept_id"],
            "type": rel["relationship_type"],
            "confidence": rel["confidence"],
            "reason": rel["reason"],
            "created_at": _now_iso(),
        }
        _inferred_edges.append(edge)

    log.info(
        "Accessible ontology: new concept '%s' (id=%s, status=%s, rels=%d)",
        title, concept_id, status, len(rels),
    )
    return record


def get_contribution(concept_id: str) -> dict[str, Any] | None:
    return _contributions.get(concept_id)


def list_contributions(
    limit: int = 50,
    offset: int = 0,
    domain: str | None = None,
    status: str | None = None,
    contributor_id: str | None = None,
) -> dict[str, Any]:
    items = list(_contributions.values())

    if domain:
        items = [c for c in items if domain.lower() in c["domains"]]
    if status:
        items = [c for c in items if c["status"] == status]
    if contributor_id:
        items = [c for c in items if c["contributor_id"] == contributor_id]

    # Newest first
    items.sort(key=lambda c: c["created_at"], reverse=True)
    total = len(items)
    return {
        "items": items[offset : offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def patch_contribution(
    concept_id: str, patch: dict[str, Any]
) -> dict[str, Any] | None:
    record = _contributions.get(concept_id)
    if not record:
        return None
    for key, val in patch.items():
        if val is not None and key in ("title", "plain_text", "domains", "status"):
            record[key] = val
    record["updated_at"] = _now_iso()
    # Re-infer if text changed
    if "plain_text" in patch and patch["plain_text"]:
        rels = _infer_relationships(
            concept_id, record["plain_text"], record["domains"], _contributions
        )
        record["inferred_relationships"] = rels
    return record


def delete_contribution(concept_id: str) -> bool:
    if concept_id not in _contributions:
        return False
    record = _contributions.pop(concept_id)
    for domain in record.get("domains", []):
        if domain in _domain_index:
            _domain_index[domain] = [
                cid for cid in _domain_index[domain] if cid != concept_id
            ]
    # Remove associated edges
    global _inferred_edges
    _inferred_edges = [
        e for e in _inferred_edges
        if e["from"] != concept_id and e["to"] != concept_id
    ]
    return True


def garden_view(limit: int = 200) -> dict[str, Any]:
    """Return garden-view data: clusters of concepts for non-technical UI."""
    items = list(_contributions.values())[:limit]

    # Build cluster map
    clusters: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        cluster = item["garden_position"]["cluster"]
        clusters.setdefault(cluster, []).append({
            "id": item["id"],
            "title": item["title"],
            "domains": item["domains"],
            "status": item["status"],
            "x": item["garden_position"]["x"],
            "y": item["garden_position"]["y"],
            "contributor_id": item["contributor_id"],
            "relationship_count": len(item["inferred_relationships"]),
        })

    cluster_list = [
        {
            "name": name,
            "size": len(members),
            "members": members,
        }
        for name, members in sorted(clusters.items(), key=lambda kv: -len(kv[1]))
    ]

    placed = sum(1 for c in items if c["status"] == "placed")
    contributors = {c["contributor_id"] for c in items}
    domains = set()
    for c in items:
        domains.update(c["domains"])

    return {
        "clusters": cluster_list,
        "concepts": [
            {
                "id": c["id"],
                "title": c["title"],
                "plain_text": c["plain_text"],
                "domains": c["domains"],
                "status": c["status"],
                "garden_position": c["garden_position"],
                "relationship_count": len(c["inferred_relationships"]),
                "core_concept_match": c["core_concept_match"],
                "contributor_id": c["contributor_id"],
            }
            for c in items
        ],
        "total": len(items),
        "contributor_count": len(contributors),
        "domain_count": len(domains),
        "placement_rate": round(placed / len(items), 3) if items else 0.0,
    }


def get_stats() -> dict[str, Any]:
    """Return statistics for observability / proof the feature is working."""
    items = list(_contributions.values())
    if not items:
        return {
            "total_contributions": 0,
            "placed_count": 0,
            "pending_count": 0,
            "orphan_count": 0,
            "placement_rate": 0.0,
            "top_domains": [],
            "recent_contributors": [],
            "inferred_edges_count": 0,
        }

    placed = sum(1 for c in items if c["status"] == "placed")
    pending = sum(1 for c in items if c["status"] == "pending")
    orphan = sum(1 for c in items if c["status"] == "orphan")

    # Domain counts
    domain_counts: dict[str, int] = {}
    for c in items:
        for d in c["domains"]:
            domain_counts[d] = domain_counts.get(d, 0) + 1
    top_domains = sorted(
        [{"domain": d, "count": n} for d, n in domain_counts.items()],
        key=lambda x: -x["count"],
    )[:10]

    recent = sorted(items, key=lambda c: c["created_at"], reverse=True)[:5]
    recent_contributors = list({c["contributor_id"] for c in recent})[:5]

    return {
        "total_contributions": len(items),
        "placed_count": placed,
        "pending_count": pending,
        "orphan_count": orphan,
        "placement_rate": round(placed / len(items), 3),
        "top_domains": top_domains,
        "recent_contributors": recent_contributors,
        "inferred_edges_count": len(_inferred_edges),
    }


def get_inferred_edges(
    concept_id: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    """Return inferred edges, optionally filtered to a concept."""
    edges = _inferred_edges
    if concept_id:
        edges = [e for e in edges if e["from"] == concept_id or e["to"] == concept_id]
    return edges[:limit]
