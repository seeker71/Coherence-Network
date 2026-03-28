import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services import graph_service

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    # Setup test entities
    graph_service.create_node(id="idea_001", type="idea", name="Edge Navigation")
    graph_service.create_node(id="concept_resonance", type="concept", name="Resonance")
    yield
    # No easy way to reset DB in tests without affecting others if not using mock, 
    # but for now let's assume a clean slate or unique IDs.

def test_get_edge_types():
    response = client.get("/api/edges/types")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 46
    assert len(data["families"]) == 7
    
    # Check for a specific type
    found = False
    for family in data["families"]:
        if family["name"] == "Ontological / Being":
            for t in family["types"]:
                if t["slug"] == "resonates-with":
                    found = True
                    assert t["canonical"] is True
    assert found

def test_create_and_get_edge():
    # Create
    payload = {
        "from_id": "idea_001",
        "to_id": "concept_resonance",
        "type": "resonates-with",
        "strength": 0.85
    }
    response = client.post("/api/edges", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "resonates-with"
    assert data["canonical"] is True
    assert data["strength"] == 0.85
    edge_id = data["id"]

    # Get by entity
    response = client.get("/api/entities/idea_001/edges?type=resonates-with")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["from_id"] == "idea_001"
    assert item["to_id"] == "concept_resonance"
    assert "from_node" in item
    assert item["from_node"]["name"] == "Edge Navigation"

    # Get neighbors
    response = client.get("/api/entities/idea_001/neighbors?type=resonates-with")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["neighbors"][0]["node"]["id"] == "concept_resonance"
    assert data["neighbors"][0]["via_edge"]["type"] == "resonates-with"

def test_create_duplicate_edge():
    payload = {
        "from_id": "idea_001",
        "to_id": "concept_resonance",
        "type": "resonates-with"
    }
    # First one might already exist from previous test if DB persists
    client.post("/api/edges", json=payload)
    
    # Second one
    response = client.post("/api/edges", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

def test_create_unknown_type():
    payload = {
        "from_id": "idea_001",
        "to_id": "concept_resonance",
        "type": "not-a-real-type"
    }
    # Default: success, canonical: False
    response = client.post("/api/edges", json=payload)
    assert response.status_code == 201
    assert response.json()["canonical"] is False

    # Strict mode: failure
    response = client.post("/api/edges?strict=true", json=payload)
    assert response.status_code == 400
    assert "Unknown edge type" in response.json()["detail"]

def test_delete_edge():
    # Create one to delete
    payload = {
        "from_id": "idea_001",
        "to_id": "concept_resonance",
        "type": "implements"
    }
    res = client.post("/api/edges", json=payload)
    edge_id = res.json()["id"]

    # Delete
    response = client.delete(f"/api/edges/{edge_id}")
    assert response.status_code == 200
    assert response.json()["deleted"] == edge_id

    # Confirm gone
    response = client.get(f"/api/edges/{edge_id}")
    assert response.status_code == 404
