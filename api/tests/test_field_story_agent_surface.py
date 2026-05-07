from __future__ import annotations

import json
import re

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


def test_chronological_story_links_influence_trace_slices():
    story = field_story_service.get_field_story("urs-field-story")["story_markdown"]

    significant_work_paths = [
        "/api/field-stories/urs-field-story/trace/significant-work/Karl%20May%20stories",
        "/api/field-stories/urs-field-story/trace/significant-work/Der%20Lederstrumpf",
        "/api/field-stories/urs-field-story/trace/significant-work/Momo",
        "/api/field-stories/urs-field-story/trace/significant-work/Die%20unendliche%20Geschichte",
        "/api/field-stories/urs-field-story/trace/significant-work/Daemon",
        "/api/field-stories/urs-field-story/trace/significant-work/Ringworld",
        "/api/field-stories/urs-field-story/trace/significant-work/The%20Expanse",
        "/api/field-stories/urs-field-story/trace/significant-work/The%20Viridian%20Gate%20Archives",
        "/api/field-stories/urs-field-story/trace/significant-work/Kingkiller%20Chronicle",
        "/api/field-stories/urs-field-story/trace/significant-work/Sword%20of%20Truth",
        "/api/field-stories/urs-field-story/trace/significant-work/First%20Law%20World",
        "/api/field-stories/urs-field-story/trace/significant-work/Spellmonger",
        "/api/field-stories/urs-field-story/trace/significant-work/Frontiers%20Saga",
        "/api/field-stories/urs-field-story/trace/significant-work/Peter%20F.%20Hamilton%20Systems%20Fiction",
    ]
    author_paths = [
        "/api/field-stories/urs-field-story/trace/author/Mose%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Yaima%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/porangui",
        "/api/field-stories/urs-field-story/trace/author/Liquid%20Bloom%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Ajeet%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Ayla%20Schafer%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Malte%20Marten%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Maneesh%20De%20Moor%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Karunesh%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/East%20Forest%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Parijat%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Alexia%20Chellun%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Alex%20Serra%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Anne%20Tucker",
        "/api/field-stories/urs-field-story/trace/author/Ram%20Dass%20-%20Topic",
        "/api/field-stories/urs-field-story/trace/author/Eckhart%20Tolle",
        "/api/field-stories/urs-field-story/trace/author/Dr%20Joe%20Dispenza",
    ]

    for path in significant_work_paths + author_paths:
        assert path in story
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.text}"


def test_chronological_story_gives_each_known_influence_a_room():
    story = field_story_service.get_field_story("urs-field-story")["story_markdown"]

    required_links = [
        "/people/mose",
        "/people/porangui",
        "/people/lex-fridman",
        "/people/elon-musk",
        "/people/matias-de-stefano",
        "/people/aubrey-marcus",
        "/people/robert-edward-grant",
        "../../../presences/next-level-soul.md",
        "../../../presences/liquid-bloom.md",
        "../../../presences/yaima.md",
        "../../../lineage/urs-contribution-profile.graph.json",
        "../../../lineage/formative-transmissions.md",
        "../../../lineage/grok-verified-lineage.md",
        "../../../vision-kb/concepts/lc-perception-as-interface.md",
        "../anchors/influence_anchors.json",
        "../anchors/event_meeting_anchors.json",
    ]
    required_names = [
        "Veda Austin",
        "MAPS",
        "Tantra",
        "Ecstatic Dance",
        "Contact Improv",
        "Unison",
        "Emergence Conference",
        "Zach Bush",
        "Michael Levin",
        "Donald Hoffman",
        "Next Level Soul",
    ]

    for link in required_links:
        assert link in story
    for name in required_names:
        assert name in story


def test_chronological_story_trace_links_resolve():
    story = field_story_service.get_field_story("urs-field-story")["story_markdown"]
    trace_paths = sorted(
        {
            match.group(1)
            for match in re.finditer(r"\((/api/field-stories/urs-field-story/trace/[^)\s]+)\)", story)
            if "{" not in match.group(1)
        }
    )

    assert len(trace_paths) >= 30
    for path in trace_paths:
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.text}"


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
