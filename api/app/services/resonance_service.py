"""Resonance service — stitches presence nodes to vision concepts.

A presence in the graph (an artist, a sanctuary, a gathering) carries
a frequency spectrum — the words that describe what they make, where
they hold space, what they open. A Living Collective concept (ceremony,
breath, nervous-system, attunement) carries its own spectrum. Where
those overlap, there is resonance, and that resonance — made into a
graph edge — lets a visitor walking either page cross the bridge into
the other.

This first pass computes resonance from **keyword overlap** between a
presence's written signal (name + description + creation titles + note
text) and a concept's written signal (name + story_content). Each
``resonates-with`` edge carries:

  · ``score``         — overlap / concept_keyword_count, 0..1
  · ``shared_tokens`` — the words that aligned
  · ``method``        — "keyword-overlap" (future passes can add
                         "frequency-vector" or "felt-by-human")

Keyword-overlap is a crude approximation. A later pass can compute
cosine similarity on signed frequency profiles (the system already
has the scaffolding for that). When it arrives, the same
``resonates-with`` edge type absorbs the richer score and the
``method`` marker tells us which pass wrote which edge.
"""
from __future__ import annotations

import re
from typing import Any

from app.services import graph_service
from app.services.news_resonance_service import extract_keywords


# Edges for presence-kind nodes (concepts don't need to resonate with
# each other through this service — they have their own concept graph).
PRESENCE_TYPES = frozenset({
    "contributor", "community", "network-org", "asset", "event", "scene",
})

# Resonance threshold — below this the overlap is noise, not signal.
RESONANCE_MIN_SCORE = 0.05

# Cap on edges written per presence so the graph stays readable.
MAX_RESONANCES_PER_PRESENCE = 8


def _presence_keywords(node: dict[str, Any]) -> set[str]:
    """The words that describe what this presence holds or makes.

    Pulls from: name, description, tagline, note (for events), and the
    titles of every creation linked via ``contributes-to``. Dedupes
    via extract_keywords which drops stop words and short tokens.
    """
    text_parts: list[str] = [
        str(node.get("name") or ""),
        str(node.get("description") or ""),
        str(node.get("tagline") or ""),
        str(node.get("note") or ""),
    ]
    # Pull creation titles for richer signal on artists etc.
    edges = graph_service.list_edges(
        from_id=node["id"], edge_type="contributes-to", limit=50,
    ).get("items", [])
    for e in edges:
        to_node = e.get("to_node") or {}
        if to_node.get("type") in ("asset", "event"):
            full = graph_service.get_node(e["to_id"])
            if full:
                text_parts.append(str(full.get("name") or ""))
                text_parts.append(str(full.get("description") or ""))
    text = " ".join(p for p in text_parts if p)
    return extract_keywords(text)


def _concept_keywords(node: dict[str, Any]) -> set[str]:
    """The words that describe what this concept holds.

    Concepts have a rich ``story_content`` (the KB markdown body) in
    their description field, plus the concept name itself. Both feed
    the spectrum.
    """
    text_parts: list[str] = [
        str(node.get("name") or ""),
        str(node.get("description") or ""),
        str(node.get("story_content") or ""),
    ]
    text = " ".join(p for p in text_parts if p)
    return extract_keywords(text)


def compute_resonance(presence_id: str) -> list[dict[str, Any]]:
    """Return the ranked list of concepts this presence resonates with.

    Each entry: {concept_id, concept_name, score, shared_tokens}. Sorted
    by score descending, filtered by RESONANCE_MIN_SCORE. Doesn't write
    anything — that's the attune step.
    """
    presence = graph_service.get_node(presence_id)
    if not presence:
        return []
    if presence.get("type") not in PRESENCE_TYPES:
        return []

    p_kw = _presence_keywords(presence)
    if not p_kw:
        return []

    concepts = graph_service.list_nodes(type="concept", limit=500).get("items", [])
    scored: list[dict[str, Any]] = []
    for concept in concepts:
        c_kw = _concept_keywords(concept)
        if not c_kw:
            continue
        shared = p_kw & c_kw
        if not shared:
            continue
        # How much of the presence's spectrum echoes inside the concept.
        # Normalizing by the presence (not the concept) means a concept
        # with a long story_content doesn't drown out real signal — and
        # a presence with many keywords needs more overlap to score
        # high, which matches intuition ("a lot of what describes this
        # presence shows up over there too").
        score = round(len(shared) / max(len(p_kw), 1), 3)
        if score < RESONANCE_MIN_SCORE:
            continue
        scored.append({
            "concept_id": concept["id"],
            "concept_name": concept.get("name") or concept["id"],
            "score": score,
            "shared_tokens": sorted(shared)[:12],
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:MAX_RESONANCES_PER_PRESENCE]


def resolve_query(query: str, limit: int = 12) -> dict[str, Any]:
    """Treat free-text as a spectrum and return the graph that resonates.

    Rather than exact-match word lookup, this extracts keywords from
    the query and scores every concept and every presence node against
    that spectrum — what the network already carries that overlaps.
    Returns a connected web the caller can confirm and integrate:

      · concepts     — vision concepts whose story overlaps the query
      · presences    — contributors / communities / events / practices
                        whose spectrum overlaps the query
      · existing_edges — which of the returned items are already
                        linked to each other (so a UI can draw
                        the weave, not just the nodes)

    Each scored item carries its shared_tokens so the reason for
    inclusion is transparent. Nothing is written — this is the
    "preview the weave" call. A separate integrate step laid on
    top can make the inspired-by edges from the viewer real.
    """
    keywords = extract_keywords(query or "")
    if not keywords:
        return {"query": query, "concepts": [], "presences": [], "existing_edges": []}

    # Score concepts
    concepts_scored: list[dict[str, Any]] = []
    for c in graph_service.list_nodes(type="concept", limit=500).get("items", []):
        c_kw = _concept_keywords(c)
        if not c_kw:
            continue
        shared = keywords & c_kw
        if len(shared) < 2:
            continue
        # Normalise by query-keyword count so we ask "how much of the
        # query's frequency this concept carries" — matches the intuition.
        score = round(len(shared) / max(len(keywords), 1), 3)
        concepts_scored.append({
            "id": c["id"],
            "name": c.get("name") or c["id"],
            "type": "concept",
            "hz": (c.get("sacred_frequency") or {}).get("hz")
                  if isinstance(c.get("sacred_frequency"), dict)
                  else c.get("sacred_frequency"),
            "score": score,
            "shared_tokens": sorted(shared)[:12],
        })
    concepts_scored.sort(key=lambda x: x["score"], reverse=True)
    concepts_top = concepts_scored[:limit]

    # Score presences (contributor, community, event, etc.)
    presences_scored: list[dict[str, Any]] = []
    for ntype in PRESENCE_TYPES:
        for n in graph_service.list_nodes(type=ntype, limit=500).get("items", []):
            p_kw = _presence_keywords(n)
            if not p_kw:
                continue
            shared = keywords & p_kw
            if len(shared) < 2:
                continue
            score = round(len(shared) / max(len(keywords), 1), 3)
            presences_scored.append({
                "id": n["id"],
                "name": n.get("name") or n["id"],
                "type": n.get("type", "contributor"),
                "image_url": n.get("image_url"),
                "canonical_url": n.get("canonical_url"),
                "score": score,
                "shared_tokens": sorted(shared)[:12],
            })
    presences_scored.sort(key=lambda x: x["score"], reverse=True)
    presences_top = presences_scored[:limit]

    # Existing edges between the returned nodes — so a UI can draw the
    # already-woven threads between what the query surfaced.
    returned_ids = {c["id"] for c in concepts_top} | {p["id"] for p in presences_top}
    edges_out: list[dict[str, Any]] = []
    if len(returned_ids) > 1:
        for nid in returned_ids:
            for e in graph_service.list_edges(from_id=nid, limit=200).get("items", []):
                if e["to_id"] in returned_ids and e["to_id"] != nid:
                    edges_out.append({
                        "from_id": nid,
                        "to_id": e["to_id"],
                        "type": e["type"],
                        "role": (e.get("properties") or {}).get("role"),
                    })

    return {
        "query": query,
        "concepts": concepts_top,
        "presences": presences_top,
        "existing_edges": edges_out,
    }


def attune(presence_id: str) -> dict[str, Any]:
    """Compute + write ``resonates-with`` edges for a presence.

    Idempotent: already-present edges are kept (score isn't updated;
    future passes can refresh). Returns a summary of what was written
    and what was found.
    """
    scored = compute_resonance(presence_id)
    written: list[dict[str, Any]] = []
    existed: list[dict[str, Any]] = []
    for item in scored:
        existing = graph_service.list_edges(
            from_id=presence_id,
            to_id=item["concept_id"],
            edge_type="resonates-with",
            limit=1,
        ).get("items", [])
        if existing:
            existed.append(item)
            continue
        r = graph_service.create_edge_strict(
            from_id=presence_id,
            to_id=item["concept_id"],
            type="resonates-with",
            properties={
                "score": item["score"],
                "shared_tokens": item["shared_tokens"],
                "method": "keyword-overlap",
            },
            strength=item["score"],
            created_by="resonance_service",
        )
        if r.get("id"):
            written.append(item)
    return {
        "presence_id": presence_id,
        "scored_count": len(scored),
        "written": written,
        "existed": existed,
    }
