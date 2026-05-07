from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import field_story_service
from app.services.mcp_tool_registry import TOOL_MAP


client = TestClient(app)


def test_field_story_manifest_loads_published_artifacts():
    stories = field_story_service.list_field_stories()
    slugs = {story["slug"] for story in stories}
    assert "urs-field-story" in slugs

    story = field_story_service.get_field_story("urs-field-story")
    assert story["slug"] == "urs-field-story"
    assert story["canonical_story"]["artifact_id"] == "chronological-story"
    assert "Around 1988: Ramtha" in story["story_markdown"]
    assert any(a["artifact_id"] == "influence-anchors" for a in story["artifacts"])
    assert story["agent_use"]["read_api"] == "/api/field-stories/urs-field-story"


def test_field_story_artifact_endpoint_returns_json_and_markdown():
    anchor = client.get("/api/field-stories/urs-field-story/artifacts/influence-anchors")
    assert anchor.status_code == 200, anchor.text
    anchor_body = anchor.json()
    assert anchor_body["artifact"]["content_type"] == "application/json"
    parsed = json.loads(anchor_body["content"])
    ramtha = next(item for item in parsed["consciousness_threshold"] if item["name"] == "Ramtha")
    assert ramtha["first_evidence"] == "circa 1988"

    story = client.get("/api/field-stories/urs-field-story/artifacts/chronological-story")
    assert story.status_code == 200, story.text
    assert "2002: Xbox Live Beta and TheSeeker" in story.json()["content"]


def test_field_story_contribution_records_attribution():
    response = client.post(
        "/api/field-stories/urs-field-story/contributions",
        json={
            "contributor_id": "agent:codex-test",
            "artifact_id": "chronological-story",
            "contribution_type": "correction",
            "summary": "Clarify one formative anchor.",
            "content_markdown": "Ramtha first entered around age 17, not through the 2008 Gmail trace.",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_contribution_id"].startswith("clr_")
    assert body["story_slug"] == "urs-field-story"
    assert body["artifact_id"] == "chronological-story"


def test_field_story_mcp_registry_exposes_agent_tools():
    assert "get_field_story" in TOOL_MAP
    assert "get_field_story_artifact" in TOOL_MAP
    assert "contribute_field_story" in TOOL_MAP

    result = TOOL_MAP["get_field_story"]["handler"]({"slug": "urs-field-story"})
    assert result["slug"] == "urs-field-story"
    assert "story_markdown" in result
