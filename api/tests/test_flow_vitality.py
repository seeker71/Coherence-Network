"""Flow-centric tests for the Workspace Vitality API.

Tests the vitality endpoint as a user would experience it:
HTTP requests in, JSON out.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str = "ws") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_workspace(c: AsyncClient, ws_id: str | None = None) -> dict:
    """Create a workspace and return response JSON."""
    wid = ws_id or _uid()
    r = await c.post("/api/workspaces", json={"id": wid, "name": f"Workspace {wid}"})
    assert r.status_code == 201, r.text
    return r.json()


async def _seed_idea(c: AsyncClient, idea_id: str, name: str, phase: str = "gas") -> dict:
    """Seed an idea."""
    r = await c.post(
        "/api/ideas",
        json={
            "id": idea_id,
            "name": name,
            "description": f"Test idea: {name}",
            "potential_value": 100.0,
            "estimated_cost": 10.0,
        },
    )
    assert r.status_code in (200, 201, 409), r.text
    return r.json()


# ---------------------------------------------------------------------------
# Test 1: Vitality returns all signals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vitality_returns_all_signals():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        # Seed some data so vitality has something to measure
        await _seed_idea(c, f"vit-idea-{_uid()}", "Vitality Test Idea")

        r = await c.get(f"/api/workspaces/{ws_id}/vitality")
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["workspace_id"] == ws_id
        assert "vitality_score" in body
        assert "signals" in body
        assert "health_description" in body
        assert "generated_at" in body

        signals = body["signals"]
        assert "diversity_index" in signals
        assert "resonance_density" in signals
        assert "flow_rate" in signals
        assert "breath_rhythm" in signals
        assert "connection_strength" in signals
        assert "activity_pulse" in signals

        # Breath rhythm has sub-keys
        br = signals["breath_rhythm"]
        assert "gas" in br
        assert "water" in br
        assert "ice" in br


# ---------------------------------------------------------------------------
# Test 2: Vitality score is 0.0-1.0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vitality_score_range():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        r = await c.get(f"/api/workspaces/{ws_id}/vitality")
        assert r.status_code == 200, r.text
        body = r.json()

        score = body["vitality_score"]
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Test 3: Health description is non-empty
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_description_non_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        r = await c.get(f"/api/workspaces/{ws_id}/vitality")
        assert r.status_code == 200, r.text
        body = r.json()

        desc = body["health_description"]
        assert isinstance(desc, str)
        assert len(desc) > 0


# ---------------------------------------------------------------------------
# Community voices — lived experience on concepts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_and_list_concept_voice():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = "lc-voice-test"
        r = await c.post(
            "/api/graph/nodes",
            json={
                "id": cid,
                "type": "concept",
                "name": "Voice test concept",
                "description": "A concept to attach a voice to.",
                "properties": {"domains": ["living-collective"]},
            },
        )
        assert r.status_code == 200, r.text

        r = await c.post(
            f"/api/concepts/{cid}/voices",
            json={
                "author_name": "Ana from Bali",
                "body": "We practice this every morning before the rice terraces.",
                "locale": "id",
                "location": "Ubud, Bali",
            },
        )
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["concept_id"] == cid
        assert created["locale"] == "id"

        r = await c.get(f"/api/concepts/{cid}/voices")
        assert r.status_code == 200
        assert any(v["author_name"] == "Ana from Bali" for v in r.json()["voices"])


@pytest.mark.asyncio
async def test_voice_on_missing_concept_returns_404_localized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/concepts/does-not-exist/voices",
            json={"author_name": "Anon", "body": "hello"},
            headers={"accept-language": "de"},
        )
        assert r.status_code == 404
        assert "nicht gefunden" in r.json()["detail"]


@pytest.mark.asyncio
async def test_voice_rejects_empty_body():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = "lc-voice-empty"
        await c.post(
            "/api/graph/nodes",
            json={
                "id": cid, "type": "concept", "name": "Empty",
                "description": "T", "properties": {"domains": ["living-collective"]},
            },
        )
        r = await c.post(
            f"/api/concepts/{cid}/voices",
            json={"author_name": "A", "body": "   "},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_recent_voices_surface_across_concepts():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        for cid in ("lc-voice-recent-a", "lc-voice-recent-b"):
            await c.post(
                "/api/graph/nodes",
                json={
                    "id": cid, "type": "concept", "name": f"Recent {cid}",
                    "description": "T", "properties": {"domains": ["living-collective"]},
                },
            )
            await c.post(
                f"/api/concepts/{cid}/voices",
                json={"author_name": "Tester", "body": f"Voice for {cid}"},
            )
        r = await c.get("/api/concepts/voices/recent?limit=10")
        assert r.status_code == 200
        ids = {v["concept_id"] for v in r.json()["voices"]}
        assert {"lc-voice-recent-a", "lc-voice-recent-b"}.issubset(ids)


# ---------------------------------------------------------------------------
# /api/energy/recommend — warm invitations from sensing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_energy_recommend_returns_invitations_not_warnings():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/energy/recommend")
        assert r.status_code == 200
        body = r.json()
        assert "invitations" in body and "count" in body
        for inv in body["invitations"]:
            assert "invitation" in inv
            assert inv["felt_as"] in ("tender", "quiet", "dormant", "resting")
            assert "ERROR" not in inv["invitation"].upper()
            assert "WARNING" not in inv["invitation"].upper()


# ---------------------------------------------------------------------------
# /api/fallbacks — honest record of silent degradation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fallback_witness_records_and_reads():
    from app.services import fallback_witness_service as fw
    fw.clear()
    fw.witness(source="test:example", reason="demo reason", context={"k": "v"})
    fw.witness(source="test:other", reason="second reason")

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/fallbacks")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 2
        sources = {e["source"] for e in body["events"]}
        assert {"test:example", "test:other"}.issubset(sources)

        r = await c.get("/api/fallbacks?source=test:ex")
        assert all(e["source"].startswith("test:ex") for e in r.json()["events"])

        r = await c.get("/api/fallbacks/summary")
        assert r.json()["total"] >= 2


@pytest.mark.asyncio
async def test_meeting_returns_combined_organism_vitality():
    """The /api/meeting endpoint returns viewer+content vitalities and a
    qualitative shared pulse so full-screen surfaces can render both sides
    of the encounter."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = "lc-meeting-test"
        await c.post(
            "/api/graph/nodes",
            json={
                "id": cid, "type": "concept", "name": "Meeting test",
                "description": "T", "properties": {"domains": ["living-collective"]},
            },
        )
        # First meeting — no prior reactions, anonymous viewer
        r = await c.get(f"/api/meeting/concept/{cid}")
        assert r.status_code == 200
        body = r.json()
        assert body["content"]["first_meeting"] is True
        assert body["shared"]["pulse"] == "first_meeting"
        assert body["viewer"]["is_contributor"] is False

        # After a reaction, content vitality rises
        await c.post(
            f"/api/reactions/concept/{cid}",
            json={"author_name": "Meeting friend", "emoji": "💛"},
        )
        r = await c.get(f"/api/meeting/concept/{cid}")
        body2 = r.json()
        assert body2["content"]["vitality"] > body["content"]["vitality"]
        assert body2["content"]["first_meeting"] is False


@pytest.mark.asyncio
async def test_explore_queue_returns_entities_viewer_has_not_met():
    """Explore queue returns entities filtered by the viewer's prior
    reactions — so a walk never repeats someone the viewer already met."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Seed two concepts
        for cid in ("lc-explore-a", "lc-explore-b"):
            await c.post(
                "/api/graph/nodes",
                json={
                    "id": cid, "type": "concept", "name": f"Explore {cid}",
                    "description": "T", "properties": {"domains": ["living-collective"]},
                },
            )
        # A viewer reacts to one
        viewer = "walker-one"
        await c.post(
            "/api/reactions/concept/lc-explore-a",
            json={"author_name": "Walker", "emoji": "💛", "author_id": viewer},
        )
        r = await c.get(f"/api/explore/concept?limit=20&contributor_id={viewer}")
        assert r.status_code == 200
        body = r.json()
        ids = {q["entity_id"] for q in body["queue"]}
        assert "lc-explore-a" not in ids  # already met — skipped
        assert "lc-explore-b" in ids      # still to meet


@pytest.mark.asyncio
async def test_explore_unsupported_entity_type_localized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/explore/lobster", headers={"accept-language": "es"})
        assert r.status_code == 400
        assert "tipo de entidad" in r.json()["detail"]


@pytest.mark.asyncio
async def test_meeting_unsupported_entity_localized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/meeting/lobster/soup", headers={"accept-language": "de"})
        assert r.status_code == 400
        assert "nicht unterstützt" in r.json()["detail"]


@pytest.mark.asyncio
async def test_translator_fallback_is_witnessed():
    """No backend → witness records it, source text returned."""
    from app.services import translator_service as _tsvc
    from app.services import fallback_witness_service as fw
    fw.clear()
    prev = _tsvc._BACKEND
    _tsvc.set_backend(None)
    try:
        t, d = _tsvc.translate_snippet("hi", "there", source_lang="en", target_lang="de")
        assert t == "hi"
        events = fw.recent(limit=10, source_prefix="translator")
        assert any(e["source"] == "translator:no-backend" for e in events)
    finally:
        _tsvc.set_backend(prev)
