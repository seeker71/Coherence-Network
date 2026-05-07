from __future__ import annotations

import json
import re
import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services import field_story_service
from app.services.mcp_tool_registry import TOOL_MAP


client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_encounter_script():
    spec = importlib.util.spec_from_file_location("encounter_script", REPO_ROOT / "scripts" / "encounter.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert "encounter-next-breath-seed" in artifact_ids
    assert "trace-encounter-next-breath" in artifact_ids
    assert "digital-influence-inventory" in artifact_ids
    assert "trace-digital-influence-inventory" in artifact_ids

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

    seed_response = client.get("/api/field-stories/urs-field-story/artifacts/trace-encounter-next-breath")
    assert seed_response.status_code == 200, seed_response.text
    seed = json.loads(seed_response.json()["content"])
    assert seed["schema_version"] == "encounter-next-breath/v1"
    assert len(seed["rows"]) == 8
    assert seed["rows"][0]["input"] == "Mei-lan"
    assert seed["rows"][0]["trace"].startswith("/api/field-stories/urs-field-story/trace/author/")

    seed_file = REPO_ROOT / "docs" / "field" / "urs" / "input" / "encounter_next_breath.txt"
    encounters = _load_encounter_script()._encounters_from_file(seed_file)
    assert len(encounters) == 8
    assert encounters[0][0] == "Mei-lan"
    assert "trace=/api/field-stories/urs-field-story/trace/author/Mei-lan" in encounters[0][1]

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


def test_digital_influence_inventory_registers_full_history_attention():
    report_response = client.get("/api/field-stories/urs-field-story/artifacts/digital-influence-inventory")
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()["content"]
    assert "Watch and listen history are allowed to be public" in report
    assert "2023 YouTube events" in report
    assert "Al Marconi" in report

    trace_response = client.get("/api/field-stories/urs-field-story/artifacts/trace-digital-influence-inventory")
    assert trace_response.status_code == 200, trace_response.text
    trace = json.loads(trace_response.json()["content"])
    assert trace["schema_version"] == "digital-influence-inventory/v1"
    assert trace["youtube"]["history_only_takeout"]["events"] > 60000
    assert trace["youtube"]["published_gap"]["missing_2023_events"] > 10000
    assert trace["youtube"]["published_gap"]["missing_before_2024_05_07_events"] > 30000
    assert trace["publication_boundary"].startswith("This compact artifact publishes")


def test_audible_history_spectrum_registers_captured_history_waves():
    story = field_story_service.get_field_story("urs-field-story", include_story=False)
    artifact_ids = {artifact["artifact_id"] for artifact in story["artifacts"]}

    assert "audible-history-spectrum" in artifact_ids
    assert "trace-audible-history-spectrum" in artifact_ids
    assert "audible-history-spectrum-builder" in artifact_ids

    report_response = client.get("/api/field-stories/urs-field-story/artifacts/audible-history-spectrum")
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()["content"]
    assert "Library holdings: `233` rows" in report
    assert "Visible web listen history: `50` rows" in report
    assert "Ryk Brown: 92" in report

    trace_response = client.get("/api/field-stories/urs-field-story/artifacts/trace-audible-history-spectrum")
    assert trace_response.status_code == 200, trace_response.text
    trace = json.loads(trace_response.json()["content"])
    capture = trace["capture_shape"]
    assert trace["schema_version"] == "audible-history-spectrum/v1"
    assert capture["library_rows"] == 233
    assert capture["purchase_rows"] == 198
    assert capture["visible_listen_history_rows"] == 50
    assert capture["unique_titles_or_asins"] >= 250
    assert len(trace["monthly"]) >= 80

    ryk = next(row for row in trace["author_waves"] if row["value"] == "Ryk Brown")
    assert ryk["events"] == 92
    assert ryk["sources"]["audible-purchase-history"] == 40
    assert ryk["wave_schema"] == ["month", "events", "pressure", "intensity", "inspiration", "insight", "vitality"]
