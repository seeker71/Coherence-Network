"""Edge navigation — typed relationships (Living Codex ontology + universal graph).

This module encodes the **verification contract** for browsing the graph through
the 46 ontology relationship types (``resonates-with``, ``emerges-from``,
``implements``, ``transcends``, ``fractal-scaling``, ``paradox-resolution``, etc.),
plus operational edge kinds stored in ``graph_edges``.

**Canonical API surfaces**

- ``GET /api/edges/types`` — ontology relationship definitions (same payload as
  ``GET /api/concepts/relationships``).
- ``GET /api/edges`` — paginated list of edges; optional ``type`` filter.
- ``POST /api/edges`` and ``POST /api/graph/edges`` — create an edge.
- ``GET /api/entities/{id}/edges`` — edges for a node (alias of
  ``GET /api/graph/nodes/{id}/edges``); supports ``direction`` and ``type``.
- ``GET /api/graph/path`` — shortest path between two nodes.

**Verification scenarios (reviewer / production)**

1. **Setup:** ontology file ``config/ontology/core-relationships.json`` present.
   **Action:** ``curl -s "$API/api/edges/types" | jq length``
   **Expected:** Count matches ``len(json.load(open(...))["relationships"])`` (46).
   **Edge:** Empty DB does not change type count.

2. **Setup:** Two nodes ``idea`` A and ``spec`` B created via ``POST /api/graph/nodes``.
   **Action:** ``POST /api/edges`` with body
   ``{"from_id":A,"to_id":B,"type":"resonates-with","strength":0.9}``
   **Expected:** HTTP 200; response includes ``id``, ``from_id``, ``to_id``, ``type``.
   **Then:** ``GET /api/entities/{A}/edges?type=resonates-with`` returns that edge.
   **Edge:** ``GET ...?type=does-not-exist`` returns ``[]``.

3. **Duplicate edge:** Repeat the same POST (same from, to, type).
   **Expected:** 200 and strength updated (unique constraint on triple).

4. **Missing edge:** ``DELETE /api/graph/edges/not-a-real-id`` → 404.

5. **Navigation:** With the edge above, ``GET /api/graph/path?from_id=A&to_id=B``
   returns a non-empty ``path`` list.

Open questions (product): surface "proof over time" by logging edge counts in
runtime events or a metrics card — out of scope for this test file.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_RELATIONSHIPS = REPO_ROOT / "config" / "ontology" / "core-relationships.json"

client = TestClient(app)


def _ontology_relationship_count() -> int:
    data = json.loads(ONTOLOGY_RELATIONSHIPS.read_text(encoding="utf-8"))
    return len(data["relationships"])


def test_edges_types_matches_ontology_file_and_concepts_endpoint() -> None:
    """Living Codex relationship catalog is stable and exposed at /api/edges/types."""
    expected = _ontology_relationship_count()
    assert expected == 46, "Ontology must define 46 relationship types for Living Codex parity"

    edges_types = client.get("/api/edges/types")
    assert edges_types.status_code == 200
    via_edges = edges_types.json()
    assert isinstance(via_edges, list)
    assert len(via_edges) == expected

    concepts_rel = client.get("/api/concepts/relationships")
    assert concepts_rel.status_code == 200
    assert concepts_rel.json() == via_edges

    ids = {r["id"] for r in via_edges}
    assert "resonates-with" in ids
    assert "emerges-from" in ids


def test_full_create_read_filter_path_and_duplicate_strength() -> None:
    """Create nodes → typed edge → list/filter → path → duplicate updates strength."""
    a = client.post(
        "/api/graph/nodes",
        json={
            "id": "edge-nav-test-a",
            "type": "idea",
            "name": "Edge Nav Idea",
            "description": "test",
            "phase": "water",
        },
    )
    b = client.post(
        "/api/graph/nodes",
        json={
            "id": "edge-nav-test-b",
            "type": "spec",
            "name": "Edge Nav Spec",
            "description": "test",
            "phase": "water",
        },
    )
    assert a.status_code == 200
    assert b.status_code == 200

    created = client.post(
        "/api/edges",
        json={
            "from_id": "edge-nav-test-a",
            "to_id": "edge-nav-test-b",
            "type": "resonates-with",
            "strength": 0.5,
            "created_by": "pytest",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["from_id"] == "edge-nav-test-a"
    assert body["to_id"] == "edge-nav-test-b"
    assert body["type"] == "resonates-with"
    assert body["strength"] == 0.5
    edge_id = body["id"]

    # Read via entity alias + graph route + direction filter
    ent = client.get(
        "/api/entities/edge-nav-test-a/edges",
        params={"type": "resonates-with", "direction": "outgoing"},
    )
    assert ent.status_code == 200
    assert len(ent.json()) == 1
    assert ent.json()[0]["id"] == edge_id

    graph_same = client.get(
        "/api/graph/nodes/edge-nav-test-a/edges",
        params={"type": "resonates-with"},
    )
    assert graph_same.status_code == 200
    assert len(graph_same.json()) == 1

    listed = client.get("/api/edges", params={"type": "resonates-with", "limit": 10})
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] >= 1
    assert any(e["id"] == edge_id for e in payload["items"])

    path = client.get(
        "/api/graph/path",
        params={"from_id": "edge-nav-test-a", "to_id": "edge-nav-test-b"},
    )
    assert path.status_code == 200
    path_body = path.json()
    assert path_body["path"] is not None
    assert len(path_body["path"]) >= 1

    dup = client.post(
        "/api/graph/edges",
        json={
            "from_id": "edge-nav-test-a",
            "to_id": "edge-nav-test-b",
            "type": "resonates-with",
            "strength": 0.99,
            "created_by": "pytest-dup",
        },
    )
    assert dup.status_code == 200
    assert dup.json()["id"] == edge_id
    assert dup.json()["strength"] == 0.99


def test_edge_type_filter_empty_and_delete_unknown() -> None:
    """Unknown type filter returns empty list; DELETE missing edge is 404."""
    isolated = client.post(
        "/api/graph/nodes",
        json={
            "id": "edge-nav-isolated",
            "type": "idea",
            "name": "Isolated",
            "description": "test",
        },
    )
    assert isolated.status_code == 200

    ghost = client.get(
        "/api/entities/edge-nav-isolated/edges",
        params={"type": "no-such-relationship-type-xyz"},
    )
    assert ghost.status_code == 200
    assert ghost.json() == []

    missing = client.delete("/api/graph/edges/__does_not_exist__")
    assert missing.status_code == 404


def test_graph_stats_include_edges_by_type() -> None:
    """Graph stats remain usable for observability of typed edge distribution."""
    stats = client.get("/api/graph/stats")
    assert stats.status_code == 200
    data = stats.json()
    assert "total_edges" in data
    assert "edges_by_type" in data


def test_create_edge_validation_error_on_missing_fields() -> None:
    """Bad input returns 422 (validation), not 500."""
    bad = client.post("/api/edges", json={"from_id": "only-one-field"})
    assert bad.status_code == 422
