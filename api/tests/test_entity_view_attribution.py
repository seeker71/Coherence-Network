"""Entity-view attribution and attention credit tests."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _entity_id(prefix: str = "lc-attribution") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _post_translation(entity_id: str, author_id: str) -> dict:
    response = client.post(
        "/api/translations",
        json={
            "entity_type": "concept",
            "entity_id": entity_id,
            "lang": "en",
            "content_title": f"Title {entity_id}",
            "content_description": "A contributed content view.",
            "content_markdown": "# Contributed\n\nThis view was edited through the API.",
            "author_type": "original_human",
            "author_id": author_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_translation_write_records_source_contribution():
    author_id = f"author-{uuid.uuid4().hex[:8]}"
    entity_id = _entity_id()

    body = _post_translation(entity_id, author_id)

    assert body["source_contribution_id"].startswith("clr_")

    ledger = client.get(f"/api/contributions/ledger/{author_id}").json()
    matching = [
        rec for rec in ledger["history"]
        if rec["id"] == body["source_contribution_id"]
    ]
    assert matching
    metadata = json.loads(matching[0]["metadata_json"])
    assert matching[0]["contribution_type"] == "content_view"
    assert metadata["entity_type"] == "concept"
    assert metadata["entity_id"] == entity_id
    assert metadata["view_id"] == body["id"]
    assert metadata["content_hash"] == body["content_hash"]


def test_view_ping_credits_latest_source_contribution():
    author_id = f"source-author-{uuid.uuid4().hex[:8]}"
    viewer_id = f"viewer-{uuid.uuid4().hex[:8]}"
    entity_id = _entity_id("lc-credit")
    written = _post_translation(entity_id, author_id)

    ping = client.post(
        "/api/views/ping",
        json={"asset_id": entity_id, "source_page": f"/vision/{entity_id}"},
        headers={"X-Contributor-Id": viewer_id},
    )

    assert ping.status_code == 200, ping.text
    ping_body = ping.json()
    assert ping_body["credited_source_contribution_id"] == written["source_contribution_id"]

    ledger = client.get(f"/api/contributions/ledger/{author_id}").json()
    attention = [
        rec for rec in ledger["history"]
        if rec["contribution_type"] == "attention"
    ]
    assert attention
    metadata = json.loads(attention[0]["metadata_json"])
    assert metadata["source_contribution_id"] == written["source_contribution_id"]
    assert metadata["view_event_id"] == ping_body["event_id"]
    assert metadata["viewer_contributor_id"] == viewer_id
    assert attention[0]["amount_cc"] > 0


def test_concept_view_endpoint_records_source_contribution():
    concept_id = _entity_id("lc-concept-view")
    author_id = f"concept-author-{uuid.uuid4().hex[:8]}"
    create = client.post(
        "/api/graph/nodes",
        json={
            "id": concept_id,
            "type": "concept",
            "name": "Concept view test",
            "description": "Base description",
        },
    )
    assert create.status_code == 200, create.text

    response = client.post(
        f"/api/concepts/{concept_id}/views",
        json={
            "lang": "en",
            "content_title": "Attributed concept title",
            "content_description": "Attributed concept description",
            "content_markdown": "# Attributed concept",
            "author_type": "original_human",
            "author_id": author_id,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_contribution_id"].startswith("clr_")


def test_idea_detail_projects_canonical_content_view():
    idea_id = f"idea-attribution-{uuid.uuid4().hex[:8]}"
    author_id = f"idea-author-{uuid.uuid4().hex[:8]}"
    create = client.post(
        "/api/ideas",
        json={
            "id": idea_id,
            "name": "Base idea title",
            "description": "Base idea description",
            "potential_value": 10,
            "estimated_cost": 2,
        },
    )
    assert create.status_code == 201, create.text

    view = client.post(
        f"/api/entity-views/idea/{idea_id}",
        json={
            "lang": "en",
            "content_title": "Projected idea title",
            "content_description": "Projected idea description",
            "content_markdown": "# Projected idea",
            "author_type": "original_human",
            "author_id": author_id,
        },
    )
    assert view.status_code == 200, view.text
    assert view.json()["source_contribution_id"].startswith("clr_")

    detail = client.get(f"/api/ideas/{idea_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["name"] == "Projected idea title"
    assert body["description"] == "Projected idea description"


def test_page_entity_view_records_source_and_attention():
    page_id = f"with-us-{uuid.uuid4().hex[:8]}"
    author_id = f"page-author-{uuid.uuid4().hex[:8]}"
    viewer_id = f"page-viewer-{uuid.uuid4().hex[:8]}"

    view = client.post(
        f"/api/entity-views/page/{page_id}",
        json={
            "lang": "en",
            "content_title": "Attributed page title",
            "content_description": "Attributed page description",
            "content_markdown": "## Page body\n\nThis page copy came from the content API.",
            "author_type": "original_human",
            "author_id": author_id,
        },
    )
    assert view.status_code == 200, view.text
    source_contribution_id = view.json()["source_contribution_id"]
    assert source_contribution_id.startswith("clr_")

    listed = client.get(f"/api/translations/page/{page_id}")
    assert listed.status_code == 200, listed.text
    item = listed.json()["items"][0]
    assert item["content_title"] == "Attributed page title"
    assert item["content_markdown"].startswith("## Page body")

    ping = client.post(
        "/api/views/ping",
        json={
            "asset_id": f"page:{page_id}",
            "entity_type": "page",
            "entity_id": page_id,
            "source_page": f"/{page_id}",
        },
        headers={"X-Contributor-Id": viewer_id},
    )

    assert ping.status_code == 200, ping.text
    ping_body = ping.json()
    assert ping_body["credited_source_contribution_id"] == source_contribution_id
    assert ping_body["attention_contribution_id"].startswith("clr_")


def test_external_asset_click_credits_seeded_source():
    asset_id = f"npm:coherence-cli-{uuid.uuid4().hex[:8]}"
    author_id = f"asset-author-{uuid.uuid4().hex[:8]}"
    viewer_id = f"asset-viewer-{uuid.uuid4().hex[:8]}"

    view = client.post(
        f"/api/entity-views/asset/{asset_id}",
        json={
            "lang": "en",
            "content_title": "Coherence CLI package",
            "content_description": "Published developer package.",
            "content_markdown": "CLI package source contribution.",
            "author_type": "original_human",
            "author_id": author_id,
        },
    )
    assert view.status_code == 200, view.text
    source_contribution_id = view.json()["source_contribution_id"]
    assert source_contribution_id.startswith("clr_")

    ping = client.post(
        "/api/views/ping",
        json={
            "asset_id": asset_id,
            "entity_type": "asset",
            "entity_id": asset_id,
            "source_page": "/",
        },
        headers={"X-Contributor-Id": viewer_id},
    )

    assert ping.status_code == 200, ping.text
    ping_body = ping.json()
    assert ping_body["credited_source_contribution_id"] == source_contribution_id
    assert ping_body["attention_contribution_id"].startswith("clr_")
