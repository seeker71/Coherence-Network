"""Extended edge navigation tests — covers spec acceptance criteria not in test_edge_navigation.py.

Spec: task_fbceb79ee5d481d5 (Spec 162 — Edge Navigation: Browse the Graph Through 46 Typed Relationships)

Additional coverage:
  - Response payload shapes (from_id, to_id, strength, created_by, created_at, canonical fields)
  - Node stub shape in edge responses (id, type, name)
  - Filter by to_id in GET /api/edges
  - Pagination via limit/offset (GET /api/edges, GET /api/entities/{id}/edges)
  - node_type filter on GET /api/entities/{id}/neighbors
  - Direction field in via_edge for neighbors
  - via_edge.id field in neighbors response
  - Delete non-existent edge returns 404
  - Edge type registry structure (slug, description, canonical fields on each type)
  - All 7 canonical families are present with expected type counts
  - Strength field validation (boundary values)
  - created_by field on edge creation
  - properties field on edge creation
  - List response envelope (items, total, limit, offset)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}


# ── helpers ────────────────────────────────────────────────────────────────────


async def _node(client: AsyncClient, node_id: str, name: str, node_type: str = "idea") -> dict:
    r = await client.post(
        "/api/graph/nodes",
        json={"id": node_id, "type": node_type, "name": name},
        headers=AUTH,
    )
    assert r.status_code in (200, 201, 409), f"create_node failed: {r.text}"
    return r.json()


async def _edge(
    client: AsyncClient,
    from_id: str,
    edge_type: str,
    to_id: str,
    strength: float = 1.0,
    created_by: str = "system",
    properties: dict | None = None,
) -> dict:
    body: dict = {"from_id": from_id, "to_id": to_id, "type": edge_type, "strength": strength, "created_by": created_by}
    if properties is not None:
        body["properties"] = properties
    r = await client.post("/api/edges", json=body, headers=AUTH)
    assert r.status_code in (200, 201), f"create_edge failed: {r.text}"
    return r.json()


# ── Edge type registry structure ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edge_types_each_type_has_slug_description_canonical() -> None:
    """Every type object must have slug, description, and canonical=true."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges/types")

    assert r.status_code == 200
    for family in r.json()["families"]:
        for t in family["types"]:
            assert "slug" in t, f"type missing slug: {t}"
            assert "description" in t, f"type missing description: {t}"
            assert t.get("canonical") is True, f"type not canonical: {t}"


@pytest.mark.asyncio
async def test_edge_types_7_families_with_correct_counts() -> None:
    """7 families must be present and their type counts must sum to 46."""
    expected = {
        "ontological": 6,
        "process": 7,
        "knowledge": 7,
        "scale": 5,
        "temporal": 6,
        "tension": 5,
        "attribution": 10,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges/types")

    assert r.status_code == 200
    families = {f["slug"]: len(f["types"]) for f in r.json()["families"]}
    for slug, count in expected.items():
        assert families.get(slug) == count, f"family {slug}: expected {count} types, got {families.get(slug)}"


@pytest.mark.asyncio
async def test_edge_types_process_family_filter() -> None:
    """Filter by 'process' family returns exactly that family with 7 types."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges/types", params={"family": "process"})

    assert r.status_code == 200
    data = r.json()
    assert len(data["families"]) == 1
    assert data["families"][0]["slug"] == "process"
    assert data["total"] == 7


@pytest.mark.asyncio
async def test_edge_types_attribution_family_contains_contributes_to() -> None:
    """Attribution family must contain 'contributes-to'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges/types", params={"family": "attribution"})

    slugs = {t["slug"] for f in r.json()["families"] for t in f["types"]}
    assert "contributes-to" in slugs
    assert "funded-by" in slugs
    assert "precondition-of" in slugs


# ── Edge creation response shape ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_edge_response_includes_required_fields() -> None:
    """Created edge response must include id, from_id, to_id, type, strength, canonical, from_node, to_node."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-src-shape", "SrcShape")
        await _node(c, "ext-dst-shape", "DstShape")
        created = await _edge(c, "ext-src-shape", "enables", "ext-dst-shape", strength=0.75)

    assert "id" in created
    assert created["from_id"] == "ext-src-shape"
    assert created["to_id"] == "ext-dst-shape"
    assert created["type"] == "enables"
    assert abs(created["strength"] - 0.75) < 0.001
    assert created["canonical"] is True
    assert "from_node" in created
    assert "to_node" in created


@pytest.mark.asyncio
async def test_create_edge_node_stub_has_id_type_name() -> None:
    """Node stubs in edge response must have id, type, name."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-stub-a", "StubA", node_type="concept")
        await _node(c, "ext-stub-b", "StubB", node_type="spec")
        created = await _edge(c, "ext-stub-a", "implements", "ext-stub-b")

    fn = created["from_node"]
    tn = created["to_node"]
    assert fn["id"] == "ext-stub-a"
    assert fn["type"] == "concept"
    assert fn["name"] == "StubA"
    assert tn["id"] == "ext-stub-b"
    assert tn["type"] == "spec"
    assert tn["name"] == "StubB"


@pytest.mark.asyncio
async def test_create_edge_custom_created_by() -> None:
    """created_by field is stored and reflected in the response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-cb-a", "CbA")
        await _node(c, "ext-cb-b", "CbB")
        created = await _edge(c, "ext-cb-a", "blocks", "ext-cb-b", created_by="agent_test")

    assert created.get("created_by") == "agent_test"


@pytest.mark.asyncio
async def test_create_edge_properties_stored() -> None:
    """properties dict is accepted and does not cause an error."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-prop-a", "PropA")
        await _node(c, "ext-prop-b", "PropB")
        created = await _edge(c, "ext-prop-a", "catalyzes", "ext-prop-b", properties={"note": "test property"})

    assert created["type"] == "catalyzes"
    assert created["canonical"] is True


@pytest.mark.asyncio
async def test_create_edge_min_strength() -> None:
    """Strength of 0.0 is accepted."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-str0-a", "Str0A")
        await _node(c, "ext-str0-b", "Str0B")
        created = await _edge(c, "ext-str0-a", "dampens", "ext-str0-b", strength=0.0)

    assert abs(created["strength"] - 0.0) < 0.001


@pytest.mark.asyncio
async def test_create_edge_max_strength() -> None:
    """Strength of 1.0 is accepted."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-str1-a", "Str1A")
        await _node(c, "ext-str1-b", "Str1B")
        created = await _edge(c, "ext-str1-a", "amplifies", "ext-str1-b", strength=1.0)

    assert abs(created["strength"] - 1.0) < 0.001


@pytest.mark.asyncio
async def test_create_edge_invalid_strength_rejected() -> None:
    """Strength > 1.0 must be rejected with 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-strbad-a", "StrBadA")
        await _node(c, "ext-strbad-b", "StrBadB")
        r = await c.post(
            "/api/edges",
            json={"from_id": "ext-strbad-a", "to_id": "ext-strbad-b", "type": "enables", "strength": 2.5},
            headers=AUTH,
        )
    assert r.status_code == 422


# ── List edges — response envelope and filters ─────────────────────────────────


@pytest.mark.asyncio
async def test_list_edges_response_envelope() -> None:
    """GET /api/edges must return items, total, limit, offset in response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges")

    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


@pytest.mark.asyncio
async def test_list_edges_filter_by_to_id() -> None:
    """?to_id=X filters edges where to_id matches X."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-toid-a", "ToIdA")
        await _node(c, "ext-toid-b", "ToIdB")
        await _node(c, "ext-toid-c", "ToIdC")

        await _edge(c, "ext-toid-a", "precedes", "ext-toid-b")
        await _edge(c, "ext-toid-c", "precedes", "ext-toid-b")

        r = await c.get("/api/edges", params={"to_id": "ext-toid-b"})

    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) >= 2
    assert all(e["to_id"] == "ext-toid-b" for e in data["items"])


@pytest.mark.asyncio
async def test_list_edges_pagination_limit() -> None:
    """limit parameter restricts the number of returned items."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-pg-hub", "PgHub")
        for i in range(5):
            await _node(c, f"ext-pg-{i}", f"PgNode{i}")
            await _edge(c, "ext-pg-hub", "follows", f"ext-pg-{i}", strength=0.5)

        r = await c.get("/api/edges", params={"from_id": "ext-pg-hub", "limit": 3})

    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 3
    assert data["limit"] == 3
    assert data["total"] >= 5


@pytest.mark.asyncio
async def test_list_edges_pagination_offset() -> None:
    """offset parameter skips the first N items."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-off-hub", "OffHub")
        for i in range(4):
            await _node(c, f"ext-off-{i}", f"OffNode{i}")
            await _edge(c, "ext-off-hub", "triggers", f"ext-off-{i}")

        r_all = await c.get("/api/edges", params={"from_id": "ext-off-hub", "limit": 100})
        r_paged = await c.get("/api/edges", params={"from_id": "ext-off-hub", "limit": 2, "offset": 2})

    data_all = r_all.json()
    data_paged = r_paged.json()
    # Total should be the same
    assert data_paged["total"] == data_all["total"]
    # The paged items should be a subset with different ids
    all_ids = [e["id"] for e in data_all["items"]]
    paged_ids = [e["id"] for e in data_paged["items"]]
    assert len(paged_ids) == 2
    # Paged items must differ from first 2
    assert paged_ids != all_ids[:2]


# ── Entity-scoped edges pagination ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_entity_edges_response_envelope() -> None:
    """GET /api/entities/{id}/edges response must include items, total, limit, offset."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-env-hub", "EnvHub")
        await _node(c, "ext-env-a", "EnvA")
        await _edge(c, "ext-env-hub", "resonates-with", "ext-env-a")

        r = await c.get("/api/entities/ext-env-hub/edges")

    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


@pytest.mark.asyncio
async def test_entity_edges_pagination_limit() -> None:
    """limit parameter on entity edges restricts returned items."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-epg-hub", "EPgHub")
        for i in range(5):
            await _node(c, f"ext-epg-{i}", f"EPgNode{i}")
            await _edge(c, "ext-epg-hub", "iterates", f"ext-epg-{i}")

        r = await c.get("/api/entities/ext-epg-hub/edges", params={"limit": 2})

    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 5


# ── Neighbor navigation — node_type filter and response shape ─────────────────


@pytest.mark.asyncio
async def test_neighbors_node_type_filter() -> None:
    """?node_type=X filters neighbors to only those with matching type."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-nt-hub", "NtHub")
        await _node(c, "ext-nt-idea", "NtIdea", node_type="idea")
        await _node(c, "ext-nt-spec", "NtSpec", node_type="spec")

        await _edge(c, "ext-nt-hub", "implements", "ext-nt-idea")
        await _edge(c, "ext-nt-hub", "implements", "ext-nt-spec")

        r = await c.get("/api/entities/ext-nt-hub/neighbors", params={"node_type": "spec"})

    assert r.status_code == 200
    data = r.json()
    assert all(n["node"]["type"] == "spec" for n in data["neighbors"])
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_neighbors_via_edge_has_id_field() -> None:
    """Each neighbor's via_edge must include an 'id' field."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-vid-hub", "VidHub")
        await _node(c, "ext-vid-peer", "VidPeer")
        await _edge(c, "ext-vid-hub", "integrates", "ext-vid-peer")

        r = await c.get("/api/entities/ext-vid-hub/neighbors")

    assert r.status_code == 200
    neighbors = r.json()["neighbors"]
    assert len(neighbors) >= 1
    assert "id" in neighbors[0]["via_edge"]


@pytest.mark.asyncio
async def test_neighbors_via_edge_direction_outgoing() -> None:
    """Outgoing edge sets direction='outgoing' in via_edge."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-dir-hub", "DirHub")
        await _node(c, "ext-dir-out", "DirOut")
        await _edge(c, "ext-dir-hub", "depends-on", "ext-dir-out")

        r = await c.get("/api/entities/ext-dir-hub/neighbors")

    assert r.status_code == 200
    neighbors = r.json()["neighbors"]
    outgoing = [n for n in neighbors if n["node"]["id"] == "ext-dir-out"]
    assert len(outgoing) == 1
    assert outgoing[0]["via_edge"]["direction"] == "outgoing"


@pytest.mark.asyncio
async def test_neighbors_via_edge_direction_incoming() -> None:
    """Incoming edge sets direction='incoming' in via_edge."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-inc-hub", "IncHub")
        await _node(c, "ext-inc-src", "IncSrc")
        await _edge(c, "ext-inc-src", "validates", "ext-inc-hub")

        r = await c.get("/api/entities/ext-inc-hub/neighbors")

    assert r.status_code == 200
    neighbors = r.json()["neighbors"]
    incoming = [n for n in neighbors if n["node"]["id"] == "ext-inc-src"]
    assert len(incoming) == 1
    assert incoming[0]["via_edge"]["direction"] == "incoming"


@pytest.mark.asyncio
async def test_neighbors_response_includes_entity_id_and_total() -> None:
    """Neighbors response must include entity_id and total fields."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-tot-hub", "TotHub")
        await _node(c, "ext-tot-a", "TotA")
        await _node(c, "ext-tot-b", "TotB")
        await _edge(c, "ext-tot-hub", "bridges", "ext-tot-a")
        await _edge(c, "ext-tot-hub", "bridges", "ext-tot-b")

        r = await c.get("/api/entities/ext-tot-hub/neighbors")

    assert r.status_code == 200
    data = r.json()
    assert data["entity_id"] == "ext-tot-hub"
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_neighbors_empty_entity_returns_empty_list() -> None:
    """Entity with no edges returns empty neighbors list, not 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-empty-hub", "EmptyHub")
        r = await c.get("/api/entities/ext-empty-hub/neighbors")

    assert r.status_code == 200
    data = r.json()
    assert data["neighbors"] == []
    assert data["total"] == 0


# ── Delete edge edge cases ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_non_existent_edge_returns_404() -> None:
    """DELETE on a non-existent edge must return 404, not 500."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.delete("/api/edges/edge-does-not-exist-abc-xyz-123")

    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_edge_twice_returns_404_second_time() -> None:
    """Deleting an edge a second time after it's gone must return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-del2-a", "Del2A")
        await _node(c, "ext-del2-b", "Del2B")
        edge = await _edge(c, "ext-del2-a", "stabilizes", "ext-del2-b")
        edge_id = edge["id"]

        r1 = await c.delete(f"/api/edges/{edge_id}")
        assert r1.status_code == 200

        r2 = await c.delete(f"/api/edges/{edge_id}")
        assert r2.status_code == 404


# ── GET /api/edges/{edge_id} response shape ───────────────────────────────────


@pytest.mark.asyncio
async def test_get_edge_response_shape() -> None:
    """GET /api/edges/{id} returns edge with from_node/to_node stubs and canonical flag."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-get-a", "GetA", node_type="concept")
        await _node(c, "ext-get-b", "GetB", node_type="task")
        created = await _edge(c, "ext-get-a", "paradox-resolution", "ext-get-b", strength=0.6)
        edge_id = created["id"]

        r = await c.get(f"/api/edges/{edge_id}")

    assert r.status_code == 200
    edge = r.json()
    assert edge["id"] == edge_id
    assert edge["type"] == "paradox-resolution"
    assert edge["canonical"] is True
    assert abs(edge["strength"] - 0.6) < 0.001
    assert "from_node" in edge
    assert "to_node" in edge


# ── Backward-compatible alias routes ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_graph_nodes_route_still_works_for_backward_compat() -> None:
    """GET /api/graph/nodes/{id} (old route) still works — backward compatibility."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _node(c, "ext-bk-node", "BkNode")
        r = await c.get("/api/graph/nodes/ext-bk-node")

    assert r.status_code == 200
