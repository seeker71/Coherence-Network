from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import field_story_service
from app.services.mcp_tool_registry import TOOL_MAP


client = TestClient(app)


def test_trace_index_artifacts_are_registered_and_queryable():
    story = field_story_service.get_field_story("urs-field-story", include_story=False)
    artifact_ids = {artifact["artifact_id"] for artifact in story["artifacts"]}

    assert "trace-monthly-spectrum" in artifact_ids
    assert "trace-author-index" in artifact_ids
    assert "trace-work-index" in artifact_ids

    month = field_story_service.get_field_story_trace_slice("urs-field-story", "month", "2026-04")
    assert month["selector"] == "month"
    assert month["value"] == "2026-04"
    assert month["result"]["events"] > 1000
    assert month["result"]["primary_influence"]["frequency"]
    assert month["result"]["top_authors"][0]["id"].startswith("author:")


def test_trace_index_api_returns_author_and_work_waves():
    author_response = client.get("/api/field-stories/urs-field-story/trace/author/Mose%20-%20Topic")
    assert author_response.status_code == 200, author_response.text
    author = author_response.json()["result"]
    assert author["id"].startswith("author:")
    assert author["events"] > 1000
    assert author["wave_schema"] == ["month", "events", "pressure", "intensity", "inspiration", "insight", "vitality"]
    assert author["wave"]

    work_id = author["top_works"][0]["id"]
    work_response = client.get(f"/api/field-stories/urs-field-story/trace/work/{work_id}")
    assert work_response.status_code == 200, work_response.text
    work = work_response.json()["result"]
    assert work["id"] == work_id
    assert work["author_id"] == author["id"]
    assert work["wave"]


def test_trace_index_mcp_tool_exposes_small_slices():
    assert "get_field_story_trace" in TOOL_MAP
    result = TOOL_MAP["get_field_story_trace"]["handler"](
        {"slug": "urs-field-story", "selector": "month", "value": "2026-04"}
    )
    assert result["result"]["month"] == "2026-04"
    assert result["result"]["primary_influence"]["frequency"]
