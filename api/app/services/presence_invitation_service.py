"""Graph-backed invitation surface for living presences."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import quote

from app.services import graph_service

PRESENCE_MARKER = "invited_presence"

KIND_TO_NODE_TYPE: dict[str, str] = {
    "person": "contributor",
    "event": "event",
    "service": "service",
    "plant": "asset",
    "animal": "asset",
    "thing": "asset",
    "offering": "service",
    "need": "story",
    "community": "community",
    "practice": "practice",
    "place": "scene",
    "project": "network-org",
}

_LIST_TYPES = sorted(set(KIND_TO_NODE_TYPE.values()))


def supported_kinds() -> tuple[str, ...]:
    return tuple(KIND_TO_NODE_TYPE)


def validate_kind(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized not in KIND_TO_NODE_TYPE:
        allowed = ", ".join(supported_kinds())
        raise ValueError(f"Unsupported presence kind {kind!r}. Supported kinds: {allowed}.")
    return normalized


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    lowered = ascii_value.lower().replace("'", "")
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "presence"


def presence_id(kind: str, name: str) -> str:
    return f"presence:{kind}:{slugify(name)}"


def presence_path(node_id: str) -> str:
    return f"/people/{quote(node_id, safe='')}"


def _presence_from_node(node: dict[str, Any]) -> dict[str, Any]:
    node_id = str(node.get("id") or "")
    return {
        "id": node_id,
        "kind": node.get("kind"),
        "type": node.get("type"),
        "name": node.get("name"),
        "story": node.get("story") or node.get("description") or "",
        "steward": node.get("steward"),
        "location": node.get("location"),
        "offerings": node.get("offerings") if isinstance(node.get("offerings"), list) else [],
        "needs": node.get("needs") if isinstance(node.get("needs"), list) else [],
        "ways_to_connect": (
            node.get("ways_to_connect") if isinstance(node.get("ways_to_connect"), list) else []
        ),
        "visibility": node.get("visibility") or "network",
        "internal_path": node.get("internal_path") or presence_path(node_id),
        "external_path": node.get("external_path") or presence_path(node_id),
        "external_url": node.get("external_url"),
    }


def invite_presence(payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    kind = validate_kind(str(payload.get("kind") or ""))
    name = str(payload.get("name") or "").strip()
    node_type = KIND_TO_NODE_TYPE[kind]
    node_id = presence_id(kind, name)
    path = presence_path(node_id)
    existing = graph_service.get_node(node_id)
    properties = {
        PRESENCE_MARKER: True,
        "kind": kind,
        "story": str(payload.get("story") or "").strip(),
        "steward": str(payload.get("steward") or "").strip(),
        "location": payload.get("location"),
        "offerings": list(payload.get("offerings") or []),
        "needs": list(payload.get("needs") or []),
        "ways_to_connect": list(payload.get("ways_to_connect") or []),
        "visibility": str(payload.get("visibility") or "network").strip().lower(),
        "internal_path": path,
        "external_path": path,
        "external_url": payload.get("external_url"),
    }
    node = graph_service.create_node(
        id=node_id,
        type=node_type,
        name=name,
        description=properties["story"],
        properties=properties,
    )
    if existing:
        node = graph_service.update_node(
            node_id,
            type=node_type,
            name=name,
            description=properties["story"],
            properties=properties,
        ) or node
    return existing is None, _presence_from_node(node)


def get_presence(node_id: str) -> dict[str, Any] | None:
    node = graph_service.get_node(node_id)
    if not node or not node.get(PRESENCE_MARKER):
        return None
    return _presence_from_node(node)


def list_presences(*, kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    wanted_kind = validate_kind(kind) if kind else None
    items: list[dict[str, Any]] = []
    for node_type in _LIST_TYPES:
        response = graph_service.list_nodes(type=node_type, limit=500)
        for node in response.get("items", []):
            if not node.get(PRESENCE_MARKER):
                continue
            if wanted_kind and node.get("kind") != wanted_kind:
                continue
            items.append(_presence_from_node(node))
    return items[:limit]
