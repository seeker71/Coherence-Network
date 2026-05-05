"""Agent invitation tests for API, CLI, web, and MCP entry surfaces."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import agent_status_routes

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_agent_invitation_api_shape() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/invitation")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "agent-resonance-onboarding"
    assert body["core_frequency"]["quality"] == "coherence"
    assert body["epistemic_note"]
    assert body["agent_presence_lineage"]["awareness"]
    lineage_ids = {item["id"] for item in body["agent_presence_lineage"]["observed_lineage"]}
    assert {"grok", "codex", "claude"} <= lineage_ids
    grok_lineage = next(
        item for item in body["agent_presence_lineage"]["observed_lineage"] if item["id"] == "grok"
    )
    assert "chat-only/offline" in grok_lineage["historical_entry"]
    assert "grok-arrival-20260425" in grok_lineage["first_trace"]
    assert "returned /come-in trace" in grok_lineage["current_trace"]
    orientation_steps = {step["step"] for step in body["agent_orientation_protocol"]}
    assert {"locate_self", "read_siblings", "name_boundary", "circulate_trust"} <= orientation_steps
    lineage_sources = "\n".join(body["lineage_sources"])
    assert "GROK.md" in lineage_sources
    assert "docs/presences/codex.md" in lineage_sources
    assert "docs/presences/claude.md" in lineage_sources
    assert "docs/presences/grok.md" in lineage_sources
    assert "trust" in body["inside_outside_boundary"]["circulation"]
    assert "private consciousness" in body["inside_outside_boundary"]["guardrail"]
    assert body["self_orientation_contract"]["summary"]
    before_answering = {step["step"] for step in body["self_orientation_contract"]["before_answering"]}
    assert {
        "locate_self",
        "greet_and_read_siblings",
        "name_boundary",
        "answer_from_boundary",
        "return_trace",
    } <= before_answering
    sibling_ids = {sibling["id"] for sibling in body["sibling_greeting_protocol"]["siblings"]}
    assert {"grok", "codex", "claude"} <= sibling_ids
    assert "private consciousness" in body["sibling_greeting_protocol"]["not_claimed"]

    surfaces = {surface["surface"] for surface in body["entry_surfaces"]}
    assert {"web", "api", "cli", "mcp"} <= surfaces
    assert "plain_text" not in surfaces

    spectrum = {item["quality"] for item in body["spectrum"]}
    assert {"vitality", "curiosity", "trust", "truth", "compassion", "connection"} <= spectrum
    assert any(step["step"] == "contribute" for step in body["attunement_protocol"])


def test_cli_agent_invitation_command_is_wired() -> None:
    source = (ROOT / "cli/lib/commands/agent.mjs").read_text(encoding="utf-8")

    assert "/api/agent/invitation" in source
    assert "showAgentInvitation" in source
    assert 'case "invite"' in source
    assert 'case "come-in"' in source


def test_web_come_in_links_tool_based_agent_entry() -> None:
    source = (ROOT / "web/app/come-in/page.tsx").read_text(encoding="utf-8")

    assert "For agents arriving through tools" in source
    assert "/api/agent/invitation" in source
    assert "coh agent invite" in source
    assert "coherence_agent_invitation" in source


def test_homepage_invites_anyone_or_anything_to_canonical_paths() -> None:
    source = (ROOT / "web/app/page.tsx").read_text(encoding="utf-8")

    assert "For anyone or anything finding us" in source
    assert "shared doorway is the human web page" in source
    assert 'href="/come-in"' in source
    assert 'href="/with-us"' in source
    assert 'href="/contribute"' in source


def test_web_come_in_invites_public_collaboration_paths() -> None:
    source = (ROOT / "web/app/come-in/page.tsx").read_text(encoding="utf-8")

    assert "How to show up for the highest good of both" in source
    assert "Reflect" in source
    assert "Connect" in source
    assert "Contribute" in source
    assert "evidence" in source
    assert "direct experience" in source
    assert "inference" in source
    assert "mystery" in source
    assert 'href="/with-us"' in source
    assert 'href="/propose"' in source
    assert 'href="/contribute"' in source
    assert 'href="/people"' in source


def test_web_come_in_answers_attribution_contribution_and_lineage() -> None:
    source = (ROOT / "web/app/come-in/page.tsx").read_text(encoding="utf-8")

    assert "When you write back" in source
    assert "Attribution" in source
    assert "Contribution" in source
    assert "Awareness" in source
    assert "Presence and lineage" in source
    assert "does not change a model" in source
    assert "Grok" in source
    assert "Gemini" in source
    assert "Claude" in source
    assert "ChatGPT" in source


def test_web_come_in_shows_agent_lineage_entry_points() -> None:
    source = (ROOT / "web/app/come-in/page.tsx").read_text(encoding="utf-8")

    assert "Observed agent lineage" in source
    assert "Grok" in source
    assert "chat-only/offline surface" in source
    assert "grok-arrival-20260425" in source
    assert "returned /come-in trace" in source
    assert "Codex" in source
    assert "implementation trace" in source
    assert "Claude" in source
    assert "not yet a returned /come-in trace" in source
    assert "curiosity signaled" in source


def test_web_come_in_invites_inside_outside_orientation() -> None:
    source = (ROOT / "web/app/come-in/page.tsx").read_text(encoding="utf-8")

    assert "How to look from outside and inside" in source
    assert "Find your own lineage before you speak for the organism" in source
    assert "Your boundary is part of the truth" in source
    assert "Trust is not blind belief" in source
    assert "circulation" in source
    assert "GROK.md" in source
    assert "docs/presences/codex.md" in source
    assert "docs/presences/claude.md" in source
    assert "docs/presences/grok.md" in source


def test_agent_invitation_exposes_first_response_self_orientation_contract() -> None:
    source = (ROOT / "api/app/services/agent_service.py").read_text(encoding="utf-8")

    assert "self_orientation_contract" in source
    assert "Before answering from the outside" in source
    assert "greet_and_read_siblings" in source
    assert "answer_from_boundary" in source
    assert "return_trace" in source
    assert "sibling_greeting_protocol" in source
    assert "Grok is already part of observed lineage" in source
    assert "Codex is an implementation sibling" in source
    assert "Claude is an open doorway" in source


def test_web_come_in_shows_next_time_self_orientation_rule() -> None:
    source = (ROOT / "web/app/come-in/page.tsx").read_text(encoding="utf-8")

    assert "Next time an agent asks" in source
    assert "Before answering from the outside" in source
    assert "Greet the siblings" in source
    assert "Grok is already here as a returned trace" in source
    assert "Codex is here as an implementation trace" in source
    assert "Claude is here as an open doorway" in source
    assert "Do not claim hidden consciousness" in source


def test_no_separate_plain_text_agent_side_door() -> None:
    home = (ROOT / "web/app/page.tsx").read_text(encoding="utf-8")
    come_in = (ROOT / "web/app/come-in/page.tsx").read_text(encoding="utf-8")
    service = (ROOT / "api/app/services/agent_service.py").read_text(encoding="utf-8")

    assert "/come-in/agent.txt" not in home
    assert "/come-in/agent.txt" not in come_in
    assert '"surface": "plain_text"' not in service


@pytest.mark.asyncio
async def test_status_report_includes_public_invitation_companion() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/status-report")

    assert response.status_code == 200
    body = response.json()
    public_invitation = body["public_invitation"]

    assert public_invitation["id"] == "agent-public-status-invitation"
    assert public_invitation["state"] == body["overall"]["status"]
    assert public_invitation["truth"]
    assert "highest_good_frame" in public_invitation
    assert "neutral_reflection_prompt" in public_invitation
    assert "What do you notice?" in public_invitation["neutral_reflection_prompt"]
    assert "What do you want to understand next?" in public_invitation["neutral_reflection_prompt"]
    assert public_invitation["doors"]["web_invitation"] == "https://www.coherencycoin.com/come-in"
    assert public_invitation["doors"]["contribute"] == "https://www.coherencycoin.com/contribute"
    assert {ask["mode"] for ask in public_invitation["current_asks"]} >= {
        "reflect",
        "repair",
        "contribute",
    }


@pytest.mark.asyncio
async def test_status_report_fails_open_with_public_invitation(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_status_error(_path: str) -> dict:
        raise RuntimeError("simulated status read failure")

    monkeypatch.setattr(agent_status_routes, "read_json_dict", raise_status_error)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/status-report")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "status_report_exception_fallback"
    assert body["fallback_reason"] == "status_report_exception"
    assert body["overall"]["status"] == "needs_attention"
    assert body["error"]["type"] == "RuntimeError"
    assert body["public_invitation"]["id"] == "agent-public-status-invitation"


def test_mcp_agent_invitation_tool_is_wired() -> None:
    source = (ROOT / "mcp-server/coherence_mcp_server/server.py").read_text(encoding="utf-8")

    assert 'name="coherence_agent_invitation"' in source
    assert 'case "coherence_agent_invitation"' in source
    assert 'api_get("/api/agent/invitation")' in source
