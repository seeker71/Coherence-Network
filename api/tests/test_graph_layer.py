"""Coverage for the universal node + edge data layer.

The universal-node-edge-layer spec sits at the foundation of the body:
every contributor, asset, concept, gathering, and lineage relation
lives as a Node or Edge in graph_service. Many surfaces depend on
the CRUD contract being stable — /people, /presences, /me,
/people/{slug}/lineage, the inspired-by service, the auto-track
contribution flow.

These tests pin the service-level surface the spec requires:
node CRUD, edge CRUD with upsert idempotency, neighbor traversal,
and the trace-node filtering that keeps anonymous-meeting events
out of presence directories (added in PR #1527 and load-bearing for
the visitor surfaces).

Source under test: api/app/services/graph_service.py
Spec: specs/universal-node-edge-layer.md
"""

from __future__ import annotations

import pytest

from app.services import graph_service


# ── Node CRUD ─────────────────────────────────────────────────────


def test_create_node_round_trip_returns_same_content():
    """The minimal contract: create returns the node, get returns the
    same content. Without this, every downstream caller is guessing."""
    node = graph_service.create_node(
        id="contributor:graph-test-roundtrip",
        type="contributor",
        name="Graph Test Roundtrip",
        description="Pinned for the universal-node-edge-layer spec.",
    )
    assert node["id"] == "contributor:graph-test-roundtrip"
    assert node["type"] == "contributor"
    assert node["name"] == "Graph Test Roundtrip"

    fetched = graph_service.get_node("contributor:graph-test-roundtrip")
    assert fetched is not None
    assert fetched["id"] == node["id"]
    assert fetched["name"] == node["name"]
    assert fetched["description"] == node["description"]


def test_create_node_explicit_id_honored():
    """Callers can provide a stable namespaced id (contributor:slug,
    asset:slug, event:slug). The id flows through unchanged."""
    node = graph_service.create_node(
        id="asset:graph-test-explicit",
        type="asset",
        name="Explicit ID",
    )
    assert node["id"] == "asset:graph-test-explicit"


def test_create_node_idempotent_on_duplicate_id():
    """Posting the same id twice should not raise; the service folds
    the second call into the existing node. This is what /api/graph/nodes
    relies on for upsert semantics (the spec calls it out as R5)."""
    first = graph_service.create_node(
        id="contributor:graph-test-upsert",
        type="contributor",
        name="First Author",
    )
    second = graph_service.create_node(
        id="contributor:graph-test-upsert",
        type="contributor",
        name="Second Author",  # would-be conflict
    )
    # The current contract: returns the existing node (name from first
    # write stays). If a later version implements true upsert with
    # name overwrite, this test will surface the change clearly.
    assert second["id"] == first["id"]
    # Whatever the merge semantics, the call doesn't raise — that's
    # the load-bearing contract for repeat ingestion.


def test_create_node_properties_and_phase():
    """Phase derives from lifecycle_state when not explicit. Properties
    are preserved on the dict returned from create_node.

    Node.to_dict flattens properties into the top-level dict (API
    convenience), so a property like `venue` lives at `node["venue"]`
    rather than `node["properties"]["venue"]`. Edge.to_dict keeps
    them nested under "properties" — different shape, same data, the
    test_create_edge_with_properties test below pins that side.
    """
    node = graph_service.create_node(
        id="event:graph-test-properties",
        type="event",
        name="Properties Test",
        properties={"lifecycle_state": "ice", "venue": "test-room"},
    )
    assert node["phase"] == "ice", (
        "phase should derive from lifecycle_state when not explicitly set"
    )
    # Properties merged flat into the node dict (top-level API shape).
    assert node.get("venue") == "test-room"
    assert node.get("lifecycle_state") == "ice"


def test_get_node_returns_none_for_missing():
    """get_node on an unknown id is a quiet None, not an exception.
    Callers (every /people/{slug} page) rely on this."""
    assert graph_service.get_node("contributor:does-not-exist-anywhere") is None


def test_delete_node_round_trip():
    graph_service.create_node(
        id="contributor:graph-test-delete",
        type="contributor",
        name="Goodbye",
    )
    assert graph_service.get_node("contributor:graph-test-delete") is not None
    assert graph_service.delete_node("contributor:graph-test-delete") is True
    assert graph_service.get_node("contributor:graph-test-delete") is None


# ── list_nodes — what /presences and /people walk ─────────────────


def test_list_nodes_filters_by_type():
    """The /presences directory walks /api/graph/nodes?type=contributor.
    A type filter that didn't restrict would crash the visitor surface."""
    graph_service.create_node(id="contributor:list-a", type="contributor", name="A")
    graph_service.create_node(id="asset:list-b", type="asset", name="B")
    graph_service.create_node(id="contributor:list-c", type="contributor", name="C")

    result = graph_service.list_nodes(type="contributor", limit=100)
    items = result.get("items", [])
    ids = {n["id"] for n in items}
    assert "contributor:list-a" in ids
    assert "contributor:list-c" in ids
    assert "asset:list-b" not in ids, "type filter must exclude other types"


def test_list_nodes_excludes_anonymous_meeting_traces():
    """Anonymous-meeting traces share the "event" type with real
    gatherings but are circulation data, not presences. PR #1527 added
    an id-prefix exclusion so they don't leak into the directory. This
    test pins it so a future refactor can't silently re-leak them."""
    graph_service.create_node(
        id="event:real-gathering",
        type="event",
        name="Real Gathering",
    )
    graph_service.create_node(
        id="anonymous-meeting:abc123:def456",
        type="event",
        name="trace not a gathering",
        properties={"anonymous_meeting_trace": True},
    )

    result = graph_service.list_nodes(type="event", limit=100)
    ids = {n["id"] for n in result.get("items", [])}
    assert "event:real-gathering" in ids
    assert "anonymous-meeting:abc123:def456" not in ids, (
        "anonymous-meeting traces must not surface in list_nodes — they "
        "pollute /presences gathering cards"
    )


def test_count_nodes_excludes_anonymous_meeting_traces():
    """Mirror the list filter so counts match the rendered directory."""
    graph_service.create_node(
        id="event:counted-gathering",
        type="event",
        name="Counted",
    )
    graph_service.create_node(
        id="anonymous-meeting:trace-xyz:session-1",
        type="event",
        name="trace",
    )

    info = graph_service.count_nodes(type="event")
    # Only the real gathering counts.
    assert info["total"] == 1


# ── Edge CRUD ─────────────────────────────────────────────────────


def test_create_edge_round_trip():
    """Edge create + get_edges returns the edge. The /api/graph/nodes/{id}/edges
    surface (used by every InfluenceLineageStrip on /people pages)
    rests on this."""
    graph_service.create_node(id="contributor:edge-from", type="contributor", name="From")
    graph_service.create_node(id="asset:edge-to", type="asset", name="To")

    edge = graph_service.create_edge(
        from_id="contributor:edge-from",
        to_id="asset:edge-to",
        type="contributes-to",
        strength=0.8,
    )
    assert edge["from_id"] == "contributor:edge-from"
    assert edge["to_id"] == "asset:edge-to"
    assert edge["type"] == "contributes-to"
    assert abs(edge["strength"] - 0.8) < 1e-9

    edges = graph_service.get_edges(node_id="contributor:edge-from")
    assert any(e["to_id"] == "asset:edge-to" for e in edges)


def test_create_edge_upsert_refreshes_strength():
    """Posting the same (from, to, type) twice should not duplicate —
    it refreshes the strength on the existing edge. This is what
    POST /api/inspired-by/manual relies on for idempotent re-runs of
    the Ubud-cluster connect script (#1555)."""
    graph_service.create_node(id="contributor:edge-up-from", type="contributor", name="UpFrom")
    graph_service.create_node(id="contributor:edge-up-to", type="contributor", name="UpTo")

    first = graph_service.create_edge(
        from_id="contributor:edge-up-from",
        to_id="contributor:edge-up-to",
        type="inspired-by",
        strength=0.5,
    )
    second = graph_service.create_edge(
        from_id="contributor:edge-up-from",
        to_id="contributor:edge-up-to",
        type="inspired-by",
        strength=0.85,
    )
    # Either we got back the same edge (refreshed) or the upsert
    # collapsed cleanly — but not two duplicate rows.
    edges = graph_service.get_edges(node_id="contributor:edge-up-from")
    matching = [e for e in edges if e["to_id"] == "contributor:edge-up-to" and e["type"] == "inspired-by"]
    assert len(matching) == 1, (
        f"upsert must collapse duplicates; got {len(matching)} rows for the same (from, to, type)"
    )
    # Strength should be the most recent value.
    assert abs(matching[0]["strength"] - 0.85) < 1e-9
    # Sanity: the two return dicts reference the same edge id.
    assert first["id"] == second["id"]


def test_create_edge_with_properties():
    """Properties (manual=True flag, role hints, era labels) flow
    through the dict. /api/inspired-by/manual sets properties.manual."""
    graph_service.create_node(id="contributor:props-a", type="contributor", name="A")
    graph_service.create_node(id="contributor:props-b", type="contributor", name="B")

    edge = graph_service.create_edge(
        from_id="contributor:props-a",
        to_id="contributor:props-b",
        type="inspired-by",
        properties={"manual": True, "note": "lineage figure"},
        strength=0.75,
    )
    props = edge.get("properties") or {}
    assert props.get("manual") is True
    assert props.get("note") == "lineage figure"


def test_delete_edge_round_trip():
    graph_service.create_node(id="contributor:del-edge-a", type="contributor", name="A")
    graph_service.create_node(id="contributor:del-edge-b", type="contributor", name="B")
    edge = graph_service.create_edge(
        from_id="contributor:del-edge-a",
        to_id="contributor:del-edge-b",
        type="inspired-by",
        strength=1.0,
    )
    assert graph_service.delete_edge(edge["id"]) is True
    # Edge no longer reachable
    edges = graph_service.get_edges(node_id="contributor:del-edge-a")
    assert not any(e["to_id"] == "contributor:del-edge-b" for e in edges)


# ── Neighbors traversal ───────────────────────────────────────────


def test_get_neighbors_returns_connected_nodes():
    """First-degree neighbors with edge metadata. The spec calls this
    out explicitly (R7); /api/graph/nodes/{id}/neighbors uses it for
    the lineage strip + body-of-evidence renders."""
    graph_service.create_node(id="contributor:hub", type="contributor", name="Hub")
    graph_service.create_node(id="asset:spoke-1", type="asset", name="Spoke1")
    graph_service.create_node(id="asset:spoke-2", type="asset", name="Spoke2")
    graph_service.create_edge(
        from_id="contributor:hub",
        to_id="asset:spoke-1",
        type="contributes-to",
        strength=1.0,
    )
    graph_service.create_edge(
        from_id="contributor:hub",
        to_id="asset:spoke-2",
        type="contributes-to",
        strength=1.0,
    )

    result = graph_service.get_neighbors("contributor:hub", depth=1)
    # Shape varies by implementation; what's load-bearing is that the
    # two connected assets are reachable from the hub's neighbors.
    # Accept either a flat list of node dicts or a dict with "nodes".
    nodes = result.get("nodes") if isinstance(result, dict) else result
    if nodes is None:
        # Fallback: maybe the function returns a different envelope —
        # walk for any presence of the spoke ids in any value.
        flat = repr(result)
        assert "asset:spoke-1" in flat
        assert "asset:spoke-2" in flat
    else:
        ids = {n["id"] for n in nodes if isinstance(n, dict) and "id" in n}
        assert "asset:spoke-1" in ids
        assert "asset:spoke-2" in ids
