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


def _source_crypto_root() -> str:
    trace_path = REPO_ROOT / "docs" / "field" / "urs" / "trace" / "source_crypto_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    return trace["roots"]["combined_trace_root"]


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
    assert author["volume"]["known_duration_seconds"] > 0
    assert author["volume"]["duration_event_count"] > 0
    assert author["volume"]["backfilled_duration_event_count"] > 0
    assert author["volume"]["axis_energy"] > author["events"]
    assert author["influence_spectrum"]["dominant_frequency"] == "devotional-body"
    assert author["influence_spectrum"]["dominant_axis"] == "vitality"
    assert author["source_mix"]["platforms"]["youtube"] > 0
    assert author["backtrace_samples"]
    sample = author["backtrace_samples"][0]
    assert sample["event_id"].startswith("field-event:")
    assert sample["source_line"] > 0
    assert sample["duration_backfill"]["match_key"].startswith("youtube:")
    assert sample["trace_links"]["author"].endswith("/Mose%20-%20Topic")
    assert sample["trace_links"]["month"].startswith("/api/field-stories/urs-field-story/trace/month/")
    assert sample["trace_links"]["work"].startswith("/api/field-stories/urs-field-story/trace/work/")
    assert author["wave_schema"] == ["month", "events", "pressure", "intensity", "inspiration", "insight", "vitality"]
    assert author["wave"]

    work_id = author["top_works"][0]["id"]
    work_response = client.get(f"/api/field-stories/urs-field-story/trace/work/{work_id}")
    assert work_response.status_code == 200, work_response.text
    work = work_response.json()["result"]
    assert work["id"] == work_id
    assert work["author_id"] == author["id"]
    assert work["volume"]["events"] == work["events"]
    assert work["source_mix"]["evidence"]
    assert work_id.replace(":", "%3A") in work["backtrace_samples"][0]["trace_links"]["work"]
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

    summary_response = client.get("/api/field-stories/urs-field-story/artifacts/trace-influence-breath-cycle")
    assert summary_response.status_code == 200, summary_response.text
    summary = json.loads(summary_response.json()["content"])
    assert summary["source_counts"]["sources"]["youtube-takeout"] > 20000
    assert summary["counts"]["unroomed_author_candidates"] >= 10
    expected_seed = summary["breaths"][2]["result"]["candidates"][0]
    assert expected_seed["plain_name"] in report

    seed_response = client.get("/api/field-stories/urs-field-story/artifacts/trace-encounter-next-breath")
    assert seed_response.status_code == 200, seed_response.text
    seed = json.loads(seed_response.json()["content"])
    assert seed["schema_version"] == "encounter-next-breath/v1"
    assert len(seed["rows"]) == 8
    assert seed["rows"][0]["input"] == expected_seed["plain_name"]
    assert seed["rows"][0]["trace"].startswith("/api/field-stories/urs-field-story/trace/author/")

    seed_file = REPO_ROOT / "docs" / "field" / "urs" / "input" / "encounter_next_breath.txt"
    encounters = _load_encounter_script()._encounters_from_file(seed_file)
    assert len(encounters) == 8
    assert encounters[0][0] == expected_seed["plain_name"]
    assert f"trace={expected_seed['trace']}" in encounters[0][1]

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
    pdf_items = trace["local_source_pdfs"]["items"]
    assert any(item["file_name"] == "Friday Live Channeled Message 5.8.26.pdf" for item in pdf_items)
    friday_pdf = next(item for item in pdf_items if item["file_name"] == "Friday Live Channeled Message 5.8.26.pdf")
    assert friday_pdf["label"] == "channeled-message-pdf"
    assert friday_pdf["ingestion_policy"] == "metadata_hashes_and_summary_only"
    assert friday_pdf["content_type"] == "application/pdf"
    assert trace["publication_boundary"].startswith("This compact artifact publishes")


def test_source_crypto_trace_registers_hash_roots_for_dynamic_access():
    story = field_story_service.get_field_story("urs-field-story", include_story=False)
    artifact_ids = {artifact["artifact_id"] for artifact in story["artifacts"]}

    assert "trace-source-crypto" in artifact_ids
    assert "source-crypto-trace-builder" in artifact_ids

    response = client.get("/api/field-stories/urs-field-story/artifacts/trace-source-crypto")
    assert response.status_code == 200, response.text
    trace = json.loads(response.json()["content"])
    assert trace["schema_version"] == "field-source-crypto-trace/v1"
    assert trace["hash_algorithm"] == "sha256"
    assert trace["normalized_event_trace"]["line_count"] == 69082
    assert trace["normalized_event_trace"]["event_merkle_root"]
    assert trace["roots"]["combined_trace_root"]
    assert len(trace["source_bodies"]) >= 10
    assert any(
        row["label"] == "channeled-message-pdf"
        and row["path"].endswith("Friday Live Channeled Message 5.8.26.pdf")
        and row["content_type"] == "application/pdf"
        for row in trace["source_bodies"]
    )
    assert trace["dynamic_access"]["mcp_tool"] == "get_field_story_trace"
    assert trace["truth_boundary"]["next_precision"].startswith("For exact row-to-source-body proofs")


def test_organism_influence_cc_computes_top_influencers_from_trace_and_agent_time():
    response = client.get("/api/field-stories/urs-field-story/organism-influence-cc?limit=80&cc_pool=1000")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["schema_version"] == "organism-influence-cc/v1"
    assert body["policy_id"] == "organism-influence-cc:v1"
    assert body["source_crypto_root"] == _source_crypto_root()
    assert body["totals"]["total_cc_pool"] == 1000
    assert body["totals"]["distributed_cc"] == 1000
    assert body["truth_boundary"].startswith("Computed sensing allocation")

    pool_ids = {pool["pool_id"] for pool in body["pools"]}
    assert {"stewardship_time", "agent_time", "significant_works", "creators_and_channels", "manual_practices"} <= pool_ids

    rows = body["top_influencers"]
    assert len(rows) >= 20
    assert all(row["computed_cc"] > 0 for row in rows)
    assert any(row["influencer_id"] == "contributor:urs" and row["kind"] == "human_steward" for row in rows)
    assert any(row["kind"] == "agent_time" and row["influencer_id"].startswith("agent:") for row in rows)
    assert any(row["influencer_id"].startswith("significant-work:spellmonger") for row in rows)
    assert any(row["ledger_recipient_id"] == "creator:Terry Mancour" for row in rows)
    assert any("trace/significant_work_index.jsonl" in ref for row in rows for ref in row["trace_refs"])

    mcp_result = TOOL_MAP["get_organism_influence_cc"]["handler"]({"slug": "urs-field-story", "limit": 20})
    assert mcp_result["top_influencers"][0]["computed_cc"] > 0
    assert mcp_result["source_crypto_root"] == body["source_crypto_root"]


def test_influence_teaching_translator_links_lessons_to_frequency_shape_and_cc():
    artifact_response = client.get("/api/field-stories/urs-field-story/artifacts/trace-influence-teaching-translator")
    assert artifact_response.status_code == 200, artifact_response.text
    artifact = json.loads(artifact_response.json()["content"])
    assert artifact["schema_version"] == "influence-teaching-translator/v1"
    assert len(artifact["rows"]) >= 35

    response = client.get("/api/field-stories/urs-field-story/influence-teaching-translator?limit=80")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == "influence-teaching-translator/v1"
    assert body["source_crypto_root"] == _source_crypto_root()
    assert body["totals"]["joined_cc_rows"] >= 25
    assert {
        "physical_book_reading",
        "music",
        "podcast_longform",
        "podcast_research",
        "practice_teaching",
        "embodied_practice",
        "embodied_gathering",
        "retreat_gathering",
        "ritual",
        "formative_technical_work",
    } <= set(body["totals"]["coverage_kinds"])

    rows_by_name = {row["name"]: row for row in body["rows"]}
    frontiers = rows_by_name["Frontiers Saga"]
    assert frontiers["current_cc"] > 40
    assert "distributed-resilience" in frontiers["frequency_translation"]
    assert "lc-network" in frontiers["concept_ids"]
    assert frontiers["trace_refs"][0].endswith("/Frontiers%20Saga")

    spellmonger = rows_by_name["Spellmonger Universe"]
    assert "living-infrastructure" in spellmonger["frequency_translation"]
    assert "guild-like contribution paths" in spellmonger["network_shape"]
    assert spellmonger["ledger_recipient_id"] == "work:spellmonger-universe"

    goodkind = rows_by_name["Sword of Truth / Goodkind Universe"]
    assert "truth-discernment" in goodkind["frequency_translation"]
    assert "source-rooted receipts" in goodkind["network_shape"]

    karl_may = rows_by_name["Karl May stories"]
    assert karl_may["kind"] == "physical_book_reading"
    assert "frontier" in karl_may["frequency_translation"]
    assert karl_may["current_cc"] > 15

    mose = rows_by_name["Mose / Mose - Topic"]
    assert mose["kind"] == "music"
    assert "devotional-body" in mose["frequency_translation"]
    assert mose["current_cc"] > 1

    lex = rows_by_name["Lex Fridman"]
    assert lex["kind"] == "podcast_longform"
    assert "long-form-dialogue" in lex["frequency_translation"]
    assert lex["current_cc"] > 0

    ecstatic_dance = rows_by_name["Ecstatic Dance"]
    assert ecstatic_dance["kind"] == "embodied_gathering"
    assert "nonverbal-integration" in ecstatic_dance["frequency_translation"]
    assert ecstatic_dance["current_cc"] > 7

    starhouse = rows_by_name["StarHouse New Moon ceremonies"]
    assert starhouse["kind"] == "ritual"
    assert "ritual-cycle" in starhouse["frequency_translation"]
    assert starhouse["current_cc"] == 0

    mcp_result = TOOL_MAP["get_influence_teaching_translator"]["handler"]({"slug": "urs-field-story", "limit": 3})
    assert mcp_result["rows"][0]["name"] == "Frontiers Saga"
    assert mcp_result["rows"][0]["current_cc"] > 40


def test_field_story_view_attribution_records_compact_receipt_and_cc_flow():
    response = client.post(
        "/api/field-stories/urs-field-story/view-attribution",
        json={
            "surface": "/field/urs",
            "presence_id": "concept:lc-network",
            "target_selector": "significant-work",
            "target_value": "Spellmonger",
            "session_hash": "anon:test-session-field-view-flow",
            "viewer_contributor_id": "viewer:test-field-view-flow",
            "cc_amount": 1.0,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()

    receipt = body["receipt"]
    assert receipt["event_hash"].startswith("sha256:")
    assert receipt["presence"] == "concept:lc-network"
    assert receipt["target_id"] == "significant-work:spellmonger-universe-45f3b507"
    assert receipt["creator"] == "creator:Terry Mancour"
    assert receipt["root"] == _source_crypto_root()
    assert body["storage_shape"]["receipt_bytes"] < 900
    assert body["storage_shape"]["flow_rows"] == 6
    assert sum(row["amount_cc"] for row in body["flows"]) == 1.0

    fetched = client.get(f"/api/field-stories/urs-field-story/view-attribution/{receipt['event_hash']}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["receipt"]["event_hash"] == receipt["event_hash"]

    ledger = client.get("/api/contributions/ledger/creator:Terry%20Mancour?limit=20")
    assert ledger.status_code == 200, ledger.text
    creator_rows = [
        row for row in ledger.json()["history"]
        if row["contribution_type"] == "field_view_flow"
        and json.loads(row["metadata_json"]).get("event_hash") == receipt["event_hash"]
    ]
    assert creator_rows
    assert creator_rows[0]["amount_cc"] == 0.4

    summary = client.get("/api/field-stories/urs-field-story/view-attribution-circulation")
    assert summary.status_code == 200, summary.text
    circulation = summary.json()
    assert circulation["flow_row_count"] >= 6
    assert circulation["sensing"]["circulation"] == "flowing"
    assert circulation["sensing"]["vitality"] >= 1.0
    assert any(row["recipient_id"] == "creator:Terry Mancour" for row in circulation["top_recipients"])


def test_field_story_view_attribution_allows_living_append_only_adjustments():
    view = client.post(
        "/api/field-stories/urs-field-story/view-attribution",
        json={
            "surface": "/field/urs",
            "presence_id": "concept:lc-network",
            "target_selector": "significant-work",
            "target_value": "Spellmonger",
            "session_hash": "anon:test-session-field-view-adjustment",
            "viewer_contributor_id": "viewer:test-field-view-adjustment",
            "cc_amount": 1.0,
        },
    )
    assert view.status_code == 201, view.text
    event_hash = view.json()["receipt"]["event_hash"]

    policy = client.get("/api/field-stories/urs-field-story/view-attribution-policy")
    assert policy.status_code == 200, policy.text
    assert policy.json()["living_policy"]["conservation"].startswith("each adjustment")

    adjustment = client.post(
        "/api/field-stories/urs-field-story/view-attribution-adjustments",
        json={
            "event_hash": event_hash,
            "from_recipient_id": "viewer-session",
            "to_recipient_id": "creator:Terry Mancour",
            "amount_cc": 0.05,
            "reason_code": "viewer-gratitude",
            "attested_by": "contributor:urs",
            "attestation_type": "steward-attestation",
            "note": "Spellmonger deserves more visible creator nutrition for this concept view.",
        },
    )
    assert adjustment.status_code == 201, adjustment.text
    adjusted = adjustment.json()
    assert adjusted["adjustment"]["policy_id"] == "cc-flow-policy:presence-work-view-adjustment:v1"

    effective = {row["recipient_id"]: row["amount_cc"] for row in adjusted["effective_flows"]}
    assert effective["creator:Terry Mancour"] == 0.45
    assert effective["viewer-session"] == 0.03

    fetched = client.get(f"/api/field-stories/urs-field-story/view-attribution/{event_hash}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["adjustments"][0]["reason_code"] == "viewer-gratitude"

    creator_ledger = client.get("/api/contributions/ledger/creator:Terry%20Mancour?limit=20")
    assert creator_ledger.status_code == 200, creator_ledger.text
    creator_adjustments = [
        row for row in creator_ledger.json()["history"]
        if row["contribution_type"] == "field_view_flow_adjustment"
        and json.loads(row["metadata_json"]).get("event_hash") == event_hash
        and json.loads(row["metadata_json"]).get("direction") == "to"
    ]
    assert creator_adjustments
    assert creator_adjustments[0]["amount_cc"] == 0.05

    summary = client.get("/api/field-stories/urs-field-story/view-attribution-circulation")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["adjustment_count"] >= 1
    assert body["sensing"]["living_adjustment"] == "active"


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
    assert trace["schema_version"] == "audible-history-spectrum/v2"
    assert capture["library_rows"] == 233
    assert capture["purchase_rows"] == 198
    assert capture["visible_listen_history_rows"] == 50
    assert capture["unique_titles_or_asins"] >= 250
    assert len(trace["monthly"]) >= 80

    ryk = next(row for row in trace["author_waves"] if row["value"] == "Ryk Brown")
    assert ryk["events"] == 92
    assert ryk["sources"]["audible-purchase-history"] == 40
    assert ryk["wave_schema"] == ["month", "events", "pressure", "intensity", "inspiration", "insight", "vitality"]
