from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import graph_service


client = TestClient(app)


def test_aligned_content_reads_from_graph_nodes() -> None:
    graph_service.create_node(
        id="community-test-aligned",
        type="community",
        name="Test Aligned Community",
        description="A community record from the graph.",
        properties={
            "source_page": "/vision/aligned",
            "slug": "test-aligned-community",
            "location": "Test Valley",
            "size": "42 people",
            "image": "/visuals/test-community.png",
            "url": "https://example.test/community",
            "resonates": "Carries a real graph-backed signal.",
            "learn": "Shows that the page is reading from DB data.",
            "concepts": ["lc-sensing"],
            "concept_labels": ["Sensing"],
        },
    )
    graph_service.create_node(
        id="host-space-test-aligned",
        type="scene",
        name="Test Host Space",
        description="A host-space record from the graph.",
        properties={
            "source_page": "/vision/aligned",
            "aligned_kind": "host-space",
            "image": "/visuals/test-host.png",
            "context": "urban",
            "energy": "light-touch",
            "body": "The existing shell becomes a host.",
            "first_move": "Open one common room.",
            "note": "The DB supplies the invitation.",
        },
    )
    graph_service.create_node(
        id="gathering-test-aligned",
        type="scene",
        name="Test Gathering",
        description="A gathering record from the graph.",
        properties={
            "source_page": "/vision/aligned",
            "aligned_kind": "gathering",
            "image": "/visuals/test-gathering.png",
            "body": "The field travels as a gathering.",
            "energy": "Belonging becomes visible.",
        },
    )
    graph_service.create_node(
        id="practice-test-aligned",
        type="practice",
        name="Test Practice",
        description="A practice record from the graph.",
        properties={
            "source_page": "/vision/aligned",
            "image": "/visuals/test-practice.png",
            "url": "https://example.test/practice",
            "what": "A practice that tunes the place.",
            "concepts": ["lc-v-harmonizing"],
        },
    )
    graph_service.create_node(
        id="network-test-aligned",
        type="network-org",
        name="Test Network",
        description="A network record from the graph.",
        properties={
            "source_page": "/vision/aligned",
            "url": "https://example.test/network",
            "scope": "Global test network",
            "resonates": "Links hosts through DB-backed data.",
        },
    )

    res = client.get("/api/vision/aligned")

    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "graph"
    assert body["counts"] == {
        "communities": 1,
        "host_spaces": 1,
        "gatherings": 1,
        "practices": 1,
        "networks": 1,
    }
    assert body["communities"][0]["name"] == "Test Aligned Community"
    assert body["communities"][0]["slug"] == "test-aligned-community"
    assert body["host_spaces"][0]["title"] == "Test Host Space"
    assert body["gatherings"][0]["title"] == "Test Gathering"
    assert body["practices"][0]["name"] == "Test Practice"
    assert body["networks"][0]["name"] == "Test Network"


def test_aligned_content_does_not_emit_unscoped_nodes() -> None:
    graph_service.create_node(
        id="community-test-unscoped",
        type="community",
        name="Unscoped Community",
        description="This should not appear on /vision/aligned.",
        properties={"source_page": "/other-page"},
    )

    res = client.get("/api/vision/aligned")

    assert res.status_code == 200
    body = res.json()
    assert body["counts"]["communities"] == 0
    assert body["communities"] == []


def test_vision_hub_reads_scoped_graph_nodes() -> None:
    graph_service.create_node(
        id="hub-section-pulse",
        type="concept",
        name="Hub Pulse",
        description="The hub section comes from the graph.",
        properties={
            "source_page": "/vision",
            "domain": "living-collective",
            "vision_hub_group": "sections",
            "sort_order": 1,
            "image": "/visuals/hub-pulse.png",
            "body": "A graph-backed section body.",
            "note": "A graph-backed section note.",
        },
    )
    graph_service.create_node(
        id="hub-gallery-space",
        type="asset",
        name="Graph Hearth",
        description="A graph-backed gallery item.",
        properties={
            "source_page": "/vision",
            "domain": "living-collective",
            "vision_hub_group": "gallery",
            "gallery_group": "spaces",
            "sort_order": 2,
            "image": "/visuals/hub-hearth.png",
            "href": "/vision/lc-nourishment",
        },
    )
    graph_service.create_node(
        id="hub-blueprint-space",
        type="concept",
        name="Graph Space Blueprint",
        description="A graph-backed blueprint card.",
        properties={
            "source_page": "/vision",
            "domain": "living-collective",
            "vision_hub_group": "blueprints",
            "href": "/vision/lc-space",
            "tag": "7 resources",
        },
    )
    graph_service.create_node(
        id="hub-emerging-ceremony",
        type="concept",
        name="Graph Ceremony",
        description="A graph-backed emerging vision.",
        properties={
            "source_page": "/vision",
            "domain": "living-collective",
            "vision_hub_group": "emerging",
            "href": "/vision/lc-v-ceremony",
        },
    )
    graph_service.create_node(
        id="hub-orientation-joy",
        type="concept",
        name="Graph Joy",
        description="A graph-backed orientation word.",
        properties={
            "source_page": "/vision",
            "domain": "living-collective",
            "vision_hub_group": "orientation_words",
            "label": "Joy",
        },
    )

    res = client.get("/api/vision/living-collective/hub")

    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "graph"
    assert body["domain"] == "living-collective"
    assert body["counts"] == {
        "sections": 1,
        "gallery_items": 1,
        "blueprints": 1,
        "emerging": 1,
        "orientation_words": 1,
    }
    assert body["sections"][0]["title"] == "Hub Pulse"
    assert body["galleries"]["spaces"][0]["label"] == "Graph Hearth"
    assert body["blueprints"][0]["title"] == "Graph Space Blueprint"
    assert body["emerging"][0]["title"] == "Graph Ceremony"
    assert body["orientation_words"] == ["Joy"]


def test_vision_hub_filters_domain_and_source_page() -> None:
    graph_service.create_node(
        id="hub-wrong-domain",
        type="concept",
        name="Wrong Domain",
        description="This should not appear.",
        properties={
            "source_page": "/vision",
            "domain": "other-domain",
            "vision_hub_group": "sections",
        },
    )
    graph_service.create_node(
        id="hub-wrong-page",
        type="concept",
        name="Wrong Page",
        description="This should not appear.",
        properties={
            "source_page": "/vision/other",
            "domain": "living-collective",
            "vision_hub_group": "sections",
        },
    )

    res = client.get("/api/vision/living-collective/hub")

    assert res.status_code == 200
    body = res.json()
    assert body["sections"] == []
    assert body["counts"]["sections"] == 0


def test_vision_realize_reads_scoped_graph_nodes() -> None:
    graph_service.create_node(
        id="realize-vocab-work",
        type="concept",
        name="Offering",
        description="Vocabulary row from the graph.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "vocabulary",
            "sort_order": 1,
            "old_word": "Work",
            "field_word": "Offering",
            "meaning": "What flows from your natural frequency.",
        },
    )
    graph_service.create_node(
        id="realize-host-city",
        type="scene",
        name="Graph City Host",
        description="A graph-backed host-space pattern.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "host_spaces",
            "image": "/visuals/graph-city.png",
            "context": "city",
            "energy": "light-touch",
            "body": "The city shell becomes a host.",
            "first_move": "Open one shared landing.",
        },
    )
    graph_service.create_node(
        id="realize-context-city",
        type="scene",
        name="City",
        description="A graph-backed context pair.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "context_pairs",
            "context": "City",
            "transformed_image": "/visuals/graph-transform.png",
            "transformed_title": "Transform what is here",
            "transformed_body": "The shell already exists.",
            "envisioned_image": "/visuals/graph-new.png",
            "envisioned_title": "Build what follows",
            "envisioned_body": "The future form follows coherence.",
        },
    )
    graph_service.create_node(
        id="realize-dual-repurpose",
        type="scene",
        name="Repurposed now",
        description="A graph-backed dual path.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "dual_paths",
            "label": "Repurposed now",
            "title": "Keep the shell",
            "image": "/visuals/graph-dual.png",
            "body": "Change the field before the walls.",
        },
    )

    res = client.get("/api/vision/living-collective/realize")

    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "graph"
    assert body["domain"] == "living-collective"
    assert body["counts"] == {
        "vocabulary": 1,
        "host_spaces": 1,
        "context_pairs": 1,
        "dual_paths": 1,
        "fastest_opportunities": 0,
        "shell_transformations": 0,
        "seasons": 0,
        "abundance_flows": 0,
        "existing_structures": 0,
        "seeds": 0,
    }
    assert body["vocabulary"][0] == {
        "old": "Work",
        "field": "Offering",
        "meaning": "What flows from your natural frequency.",
    }
    assert body["host_spaces"][0]["title"] == "Graph City Host"
    assert body["context_pairs"][0]["context"] == "City"
    assert body["dual_paths"][0]["title"] == "Keep the shell"


def test_vision_realize_filters_domain_and_source_page() -> None:
    graph_service.create_node(
        id="realize-wrong-domain",
        type="scene",
        name="Wrong Domain",
        description="This should not appear.",
        properties={
            "source_page": "/vision/realize",
            "domain": "other-domain",
            "realize_group": "dual_paths",
        },
    )
    graph_service.create_node(
        id="realize-wrong-page",
        type="scene",
        name="Wrong Page",
        description="This should not appear.",
        properties={
            "source_page": "/vision/other",
            "domain": "living-collective",
            "realize_group": "dual_paths",
        },
    )

    res = client.get("/api/vision/living-collective/realize")

    assert res.status_code == 200
    body = res.json()
    assert body["dual_paths"] == []
    assert body["counts"]["dual_paths"] == 0


def test_vision_realize_reads_expansion_graph_nodes() -> None:
    graph_service.create_node(
        id="realize-fastest-room",
        type="concept",
        name="Open one commons room",
        description="A graph-backed fastest opportunity.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "fastest_opportunities",
            "sort_order": 1,
            "title": "Open one commons room",
            "body": "Start with one room that can hold tea.",
        },
    )
    graph_service.create_node(
        id="realize-shell-office",
        type="scene",
        name="Office floor",
        description="A graph-backed shell transformation.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "shell_transformations",
            "title": "Office floor -> vertical neighborhood",
            "body": "Private desks give way to commons bands.",
        },
    )
    graph_service.create_node(
        id="realize-season-spring",
        type="scene",
        name="Spring",
        description="A graph-backed season.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "seasons",
            "body": "Everything wakes.",
        },
    )
    graph_service.create_node(
        id="realize-abundance-land",
        type="concept",
        name="The land overflows",
        description="A graph-backed abundance flow.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "abundance_flows",
            "title": "The land overflows",
            "body": "The overflow flows to neighbors.",
        },
    )
    graph_service.create_node(
        id="realize-existing-apartment",
        type="scene",
        name="Apartment",
        description="A graph-backed existing-structure meaning.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "existing_structures",
            "title": "Apartment -> Coherent cell",
            "body": "A small room becomes a quiet cell.",
        },
    )
    graph_service.create_node(
        id="realize-seed-do-no-harm",
        type="practice",
        name="Do no harm",
        description="A graph-backed seed.",
        properties={
            "source_page": "/vision/realize",
            "domain": "living-collective",
            "realize_group": "seeds",
            "body": "Do no harm. Live in accordance with nature.",
        },
    )

    res = client.get("/api/vision/living-collective/realize")

    assert res.status_code == 200
    body = res.json()
    assert body["counts"]["fastest_opportunities"] == 1
    assert body["counts"]["shell_transformations"] == 1
    assert body["counts"]["seasons"] == 1
    assert body["counts"]["abundance_flows"] == 1
    assert body["counts"]["existing_structures"] == 1
    assert body["counts"]["seeds"] == 1
    assert body["fastest_opportunities"][0]["title"] == "Open one commons room"
    assert body["shell_transformations"][0]["body"] == "Private desks give way to commons bands."
    assert body["seasons"][0] == {"id": "realize-season-spring", "name": "Spring", "body": "Everything wakes."}
    assert body["abundance_flows"][0]["title"] == "The land overflows"
    assert body["existing_structures"][0]["title"] == "Apartment -> Coherent cell"
    assert body["seeds"][0] == {
        "id": "realize-seed-do-no-harm",
        "body": "Do no harm. Live in accordance with nature.",
    }
