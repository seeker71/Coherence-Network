from __future__ import annotations

import json
import re

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
    assert "trace-significant-work-index" in artifact_ids
    assert "trace-concept-work-map" in artifact_ids

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


def test_trace_index_returns_significant_work_deep_discovery():
    response = client.get("/api/field-stories/urs-field-story/trace/significant-work/Spellmonger")
    assert response.status_code == 200, response.text
    record = response.json()["result"]

    assert record["title"] == "Spellmonger Universe"
    assert record["impact_score"] >= 90
    assert any(link["concept_id"] == "lc-network" for link in record["concept_links"])
    assert record["deep_discovery"]["chapter_precision"] == "not-yet-evidence-backed"
    assert "chapter_probe_terms" in record["concept_links"][0]
    assert any(child["title"] == "Preceptor" for child in record["children"])


def test_trace_index_includes_childhood_frontier_works():
    karl_may = client.get("/api/field-stories/urs-field-story/trace/significant-work/Karl%20May%20stories")
    assert karl_may.status_code == 200, karl_may.text
    assert karl_may.json()["result"]["authors"] == ["Karl May"]

    lederstrumpf = client.get("/api/field-stories/urs-field-story/trace/significant-work/Der%20Lederstrumpf")
    assert lederstrumpf.status_code == 200, lederstrumpf.text
    record = lederstrumpf.json()["result"]
    assert record["authors"] == ["James Fenimore Cooper"]
    assert any(link["concept_id"] == "lc-field-edge" for link in record["concept_links"])


def test_trace_index_returns_concept_to_significant_work_map():
    response = client.get("/api/field-stories/urs-field-story/trace/concept/lc-network")
    assert response.status_code == 200, response.text
    concept = response.json()["result"]

    titles = {item["title"] for item in concept["related_significant_works"]}
    assert "Spellmonger Universe" in titles
    spellmonger = next(item for item in concept["related_significant_works"] if item["title"] == "Spellmonger Universe")
    assert "Sevendor" in spellmonger["chapter_probe_terms"]

    mcp_result = TOOL_MAP["get_field_story_trace"]["handler"](
        {"slug": "urs-field-story", "selector": "concept", "value": "lc-network"}
    )
    assert any(item["title"] == "Spellmonger Universe" for item in mcp_result["result"]["related_significant_works"])


def test_influence_breath_cycle_registers_youtube_discovery_loop():
    story = field_story_service.get_field_story("urs-field-story", include_story=False)
    artifact_ids = {artifact["artifact_id"] for artifact in story["artifacts"]}

    assert "influence-breath-cycle" in artifact_ids
    assert "trace-influence-breath-cycle" in artifact_ids

    report_response = client.get("/api/field-stories/urs-field-story/artifacts/influence-breath-cycle")
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()["content"]
    assert "## Unroomed Author Candidates" in report
    assert "youtube-takeout" in report
    assert "Mei-lan" in report

    summary_response = client.get("/api/field-stories/urs-field-story/artifacts/trace-influence-breath-cycle")
    assert summary_response.status_code == 200, summary_response.text
    summary = json.loads(summary_response.json()["content"])
    assert summary["source_counts"]["sources"]["youtube-takeout"] > 20000
    assert summary["counts"]["unroomed_author_candidates"] >= 10

    trace_paths = sorted(
        {
            match.group(1)
            for match in re.finditer(r"\((/api/field-stories/urs-field-story/trace/[^)\s]+)\)", report)
        }
    )
    assert len(trace_paths) >= 40
    for path in trace_paths:
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.text}"
