"""Graph-backed page content for Living Collective vision surfaces."""

from __future__ import annotations

from typing import Any

from app.services import graph_service


ALIGNED_SOURCE_PAGE = "/vision/aligned"
HUB_SOURCE_PAGE = "/vision"
HUB_NODE_TYPES = ("concept", "asset", "scene", "practice", "story", "network-org")
REALIZE_SOURCE_PAGE = "/vision/realize"
REALIZE_NODE_TYPES = ("concept", "asset", "scene", "practice")


def _as_str(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
    try:
        order = int(item.get("sort_order") or 9999)
    except (TypeError, ValueError):
        order = 9999
    return (order, _as_str(item.get("name")))


def _scoped_nodes(node_type: str, *, aligned_kind: str | None = None) -> list[dict[str, Any]]:
    rows = graph_service.list_nodes(type=node_type, limit=500).get("items", [])
    scoped = []
    for row in rows:
        if row.get("source_page") != ALIGNED_SOURCE_PAGE:
            continue
        if aligned_kind is not None and row.get("aligned_kind") != aligned_kind:
            continue
        scoped.append(row)
    return sorted(scoped, key=_sort_key)


def _hub_nodes(domain: str, group: str, *, gallery_group: str | None = None) -> list[dict[str, Any]]:
    scoped: list[dict[str, Any]] = []
    for node_type in HUB_NODE_TYPES:
        rows = graph_service.list_nodes(type=node_type, limit=500).get("items", [])
        for row in rows:
            if row.get("source_page") != HUB_SOURCE_PAGE:
                continue
            if _as_str(row.get("domain")).lower() != domain.lower():
                continue
            if row.get("vision_hub_group") != group:
                continue
            if gallery_group is not None and row.get("gallery_group") != gallery_group:
                continue
            scoped.append(row)
    return sorted(scoped, key=_sort_key)


def _realize_nodes(domain: str, group: str) -> list[dict[str, Any]]:
    scoped: list[dict[str, Any]] = []
    for node_type in REALIZE_NODE_TYPES:
        rows = graph_service.list_nodes(type=node_type, limit=500).get("items", [])
        for row in rows:
            if row.get("source_page") != REALIZE_SOURCE_PAGE:
                continue
            if _as_str(row.get("domain")).lower() != domain.lower():
                continue
            if row.get("realize_group") != group:
                continue
            scoped.append(row)
    return sorted(scoped, key=_sort_key)


def _href(row: dict[str, Any]) -> str:
    return _as_str(row.get("href"), f"/vision/{_as_str(row.get('id'))}")


def _hub_section(row: dict[str, Any]) -> dict[str, Any]:
    concept_id = _as_str(row.get("concept_id"), _as_str(row.get("id")))
    return {
        "id": _as_str(row.get("slug"), concept_id.replace("lc-", "")),
        "concept_id": concept_id,
        "image": _as_str(row.get("image"), _as_str(row.get("visual_path"))),
        "title": _as_str(row.get("title"), _as_str(row.get("name"))),
        "body": _as_str(row.get("body"), _as_str(row.get("description"))),
        "note": _as_str(row.get("note")),
    }


def _gallery_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "image": _as_str(row.get("image"), _as_str(row.get("visual_path"))),
        "label": _as_str(row.get("label"), _as_str(row.get("name"))),
        "href": _href(row),
    }


def _hub_card(row: dict[str, Any]) -> dict[str, Any]:
    concept_id = _as_str(row.get("concept_id"), _as_str(row.get("id")))
    return {
        "id": row.get("id"),
        "title": _as_str(row.get("title"), _as_str(row.get("name"))),
        "concept_id": concept_id,
        "href": _href(row),
        "desc": _as_str(row.get("desc"), _as_str(row.get("description"))),
        "tag": _as_str(row.get("tag")),
    }


def _vocabulary_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "old": _as_str(row.get("old_word")),
        "field": _as_str(row.get("field_word"), _as_str(row.get("name"))),
        "meaning": _as_str(row.get("meaning"), _as_str(row.get("description"))),
    }


def _realize_host_space(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "title": _as_str(row.get("title"), _as_str(row.get("name"))),
        "image": _as_str(row.get("image"), _as_str(row.get("visual_path"))),
        "context": _as_str(row.get("context")),
        "energy": _as_str(row.get("energy")),
        "body": _as_str(row.get("body"), _as_str(row.get("description"))),
        "first_move": _as_str(row.get("first_move")),
    }


def _context_pair(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "context": _as_str(row.get("context"), _as_str(row.get("name"))),
        "transformed_image": _as_str(row.get("transformed_image")),
        "transformed_title": _as_str(row.get("transformed_title")),
        "transformed_body": _as_str(row.get("transformed_body")),
        "envisioned_image": _as_str(row.get("envisioned_image")),
        "envisioned_title": _as_str(row.get("envisioned_title")),
        "envisioned_body": _as_str(row.get("envisioned_body")),
    }


def _dual_path(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "label": _as_str(row.get("label"), _as_str(row.get("name"))),
        "title": _as_str(row.get("title"), _as_str(row.get("name"))),
        "image": _as_str(row.get("image"), _as_str(row.get("visual_path"))),
        "body": _as_str(row.get("body"), _as_str(row.get("description"))),
    }


def _realize_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "title": _as_str(row.get("title"), _as_str(row.get("name"))),
        "body": _as_str(row.get("body"), _as_str(row.get("description"))),
    }


def _season(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": _as_str(row.get("name"), _as_str(row.get("title"))),
        "body": _as_str(row.get("body"), _as_str(row.get("description"))),
    }


def _seed(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "body": _as_str(row.get("body"), _as_str(row.get("description"))),
    }


def _community(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": _as_str(row.get("name")),
        "slug": _as_str(row.get("slug"), _as_str(row.get("id"))),
        "location": _as_str(row.get("location")),
        "size": _as_str(row.get("size")),
        "image": _as_str(row.get("image")),
        "url": _as_str(row.get("url")),
        "resonates": _as_str(row.get("resonates"), _as_str(row.get("description"))),
        "learn": _as_str(row.get("learn")),
        "concepts": _as_list(row.get("concepts")),
        "concept_labels": _as_list(row.get("concept_labels")),
    }


def _host_space(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "title": _as_str(row.get("title"), _as_str(row.get("name"))),
        "image": _as_str(row.get("image")),
        "context": _as_str(row.get("context")),
        "energy": _as_str(row.get("energy")),
        "body": _as_str(row.get("body"), _as_str(row.get("description"))),
        "first_move": _as_str(row.get("first_move")),
        "note": _as_str(row.get("note")),
    }


def _gathering(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "title": _as_str(row.get("title"), _as_str(row.get("name"))),
        "image": _as_str(row.get("image")),
        "body": _as_str(row.get("body"), _as_str(row.get("description"))),
        "energy": _as_str(row.get("energy")),
    }


def _practice(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": _as_str(row.get("name")),
        "image": _as_str(row.get("image")),
        "url": _as_str(row.get("url")),
        "what": _as_str(row.get("what"), _as_str(row.get("description"))),
        "concepts": _as_list(row.get("concepts")),
    }


def _network(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": _as_str(row.get("name")),
        "url": _as_str(row.get("url")),
        "scope": _as_str(row.get("scope")),
        "resonates": _as_str(row.get("resonates"), _as_str(row.get("description"))),
    }


def get_aligned_content() -> dict[str, Any]:
    """Return the /vision/aligned catalog from graph nodes."""
    communities = [_community(row) for row in _scoped_nodes("community")]
    host_spaces = [_host_space(row) for row in _scoped_nodes("scene", aligned_kind="host-space")]
    gatherings = [_gathering(row) for row in _scoped_nodes("scene", aligned_kind="gathering")]
    practices = [_practice(row) for row in _scoped_nodes("practice")]
    networks = [_network(row) for row in _scoped_nodes("network-org")]
    return {
        "source": "graph",
        "communities": communities,
        "host_spaces": host_spaces,
        "gatherings": gatherings,
        "practices": practices,
        "networks": networks,
        "counts": {
            "communities": len(communities),
            "host_spaces": len(host_spaces),
            "gatherings": len(gatherings),
            "practices": len(practices),
            "networks": len(networks),
        },
    }


def get_hub_content(domain: str) -> dict[str, Any]:
    """Return the /vision hub content for a domain from graph nodes."""
    sections = [_hub_section(row) for row in _hub_nodes(domain, "sections")]
    gallery_groups = {
        "spaces": [_gallery_item(row) for row in _hub_nodes(domain, "gallery", gallery_group="spaces")],
        "practices": [_gallery_item(row) for row in _hub_nodes(domain, "gallery", gallery_group="practices")],
        "people": [_gallery_item(row) for row in _hub_nodes(domain, "gallery", gallery_group="people")],
        "network": [_gallery_item(row) for row in _hub_nodes(domain, "gallery", gallery_group="network")],
    }
    blueprints = [_hub_card(row) for row in _hub_nodes(domain, "blueprints")]
    emerging = [_hub_card(row) for row in _hub_nodes(domain, "emerging")]
    orientation_words = [
        _as_str(row.get("label"), _as_str(row.get("name")))
        for row in _hub_nodes(domain, "orientation_words")
    ]
    gallery_count = sum(len(items) for items in gallery_groups.values())
    return {
        "source": "graph",
        "domain": domain,
        "sections": sections,
        "galleries": gallery_groups,
        "blueprints": blueprints,
        "emerging": emerging,
        "orientation_words": orientation_words,
        "counts": {
            "sections": len(sections),
            "gallery_items": gallery_count,
            "blueprints": len(blueprints),
            "emerging": len(emerging),
            "orientation_words": len(orientation_words),
        },
    }


def get_realize_content(domain: str) -> dict[str, Any]:
    """Return the /vision/realize content for a domain from graph nodes."""
    vocabulary = [_vocabulary_item(row) for row in _realize_nodes(domain, "vocabulary")]
    host_spaces = [_realize_host_space(row) for row in _realize_nodes(domain, "host_spaces")]
    context_pairs = [_context_pair(row) for row in _realize_nodes(domain, "context_pairs")]
    dual_paths = [_dual_path(row) for row in _realize_nodes(domain, "dual_paths")]
    fastest_opportunities = [
        _realize_card(row) for row in _realize_nodes(domain, "fastest_opportunities")
    ]
    shell_transformations = [
        _realize_card(row) for row in _realize_nodes(domain, "shell_transformations")
    ]
    seasons = [_season(row) for row in _realize_nodes(domain, "seasons")]
    abundance_flows = [_realize_card(row) for row in _realize_nodes(domain, "abundance_flows")]
    existing_structures = [
        _realize_card(row) for row in _realize_nodes(domain, "existing_structures")
    ]
    seeds = [_seed(row) for row in _realize_nodes(domain, "seeds")]
    return {
        "source": "graph",
        "domain": domain,
        "vocabulary": vocabulary,
        "host_spaces": host_spaces,
        "context_pairs": context_pairs,
        "dual_paths": dual_paths,
        "fastest_opportunities": fastest_opportunities,
        "shell_transformations": shell_transformations,
        "seasons": seasons,
        "abundance_flows": abundance_flows,
        "existing_structures": existing_structures,
        "seeds": seeds,
        "counts": {
            "vocabulary": len(vocabulary),
            "host_spaces": len(host_spaces),
            "context_pairs": len(context_pairs),
            "dual_paths": len(dual_paths),
            "fastest_opportunities": len(fastest_opportunities),
            "shell_transformations": len(shell_transformations),
            "seasons": len(seasons),
            "abundance_flows": len(abundance_flows),
            "existing_structures": len(existing_structures),
            "seeds": len(seeds),
        },
    }
