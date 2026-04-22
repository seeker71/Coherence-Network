"""Flow-centric tests for the Workspace Vitality + related sensing
endpoints (concept voices, energy invitations, fallback witness,
meeting, explore queue).

Four flows cover the surface:

  · Vitality signals + meeting (signal shape, 0-1 score,
    non-empty health description, combined organism vitality with
    viewer + content sides, first_meeting pulse)
  · Concept voices (add/list, ripen into proposal with back-link,
    idempotent ripen, 400 on empty body, 404 localized on missing
    concept / unknown voice, recent surfaces across concepts)
  · Energy invitations + fallback witness + translator fallback
    (no warnings; frequency-words only; fallback recorded when no
    backend; translator falls back to source text)
  · Explore queue + unsupported-entity localization (queue skips
    already-met entities; unsupported type localizes 400 on both
    /explore and /meeting surfaces)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str = "ws") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_workspace(c: AsyncClient) -> dict:
    wid = _uid()
    r = await c.post("/api/workspaces", json={"id": wid, "name": f"Workspace {wid}"})
    assert r.status_code == 201, r.text
    return r.json()


async def _seed_concept(c: AsyncClient, cid: str) -> None:
    await c.post("/api/graph/nodes", json={
        "id": cid, "type": "concept", "name": f"Concept {cid}",
        "description": "Test concept",
        "properties": {"domains": ["living-collective"]},
    })


@pytest.mark.asyncio
async def test_vitality_and_meeting_flow():
    """Vitality endpoint returns full signal shape + 0-1 score +
    non-empty health description; meeting endpoint returns
    viewer+content+shared pulse, first_meeting flips to false after
    a reaction lifts content vitality."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        # Seed an idea so vitality has something to measure.
        iid = f"vit-idea-{_uid()}"
        await c.post("/api/ideas", json={
            "id": iid, "name": "Vitality idea", "description": "T",
            "potential_value": 100.0, "estimated_cost": 10.0,
        })

        vitality = (await c.get(f"/api/workspaces/{ws_id}/vitality")).json()
        assert vitality["workspace_id"] == ws_id
        for field in ("vitality_score", "signals", "health_description", "generated_at"):
            assert field in vitality
        for signal in ("diversity_index", "resonance_density", "flow_rate",
                       "breath_rhythm", "connection_strength", "activity_pulse"):
            assert signal in vitality["signals"]
        for phase in ("gas", "water", "ice"):
            assert phase in vitality["signals"]["breath_rhythm"]
        assert isinstance(vitality["vitality_score"], (int, float))
        assert 0.0 <= vitality["vitality_score"] <= 1.0
        assert isinstance(vitality["health_description"], str)
        assert len(vitality["health_description"]) > 0

        # Meeting endpoint — first meeting, anonymous viewer.
        cid = "lc-meeting-test"
        await _seed_concept(c, cid)
        first_meeting = (await c.get(f"/api/meeting/concept/{cid}")).json()
        assert first_meeting["content"]["first_meeting"] is True
        assert first_meeting["shared"]["pulse"] == "first_meeting"
        assert first_meeting["viewer"]["is_contributor"] is False

        # After a reaction, content vitality rises and first_meeting flips.
        await c.post(f"/api/reactions/concept/{cid}",
                     json={"author_name": "Meeting friend", "emoji": "💛"})
        after = (await c.get(f"/api/meeting/concept/{cid}")).json()
        assert after["content"]["vitality"] > first_meeting["content"]["vitality"]
        assert after["content"]["first_meeting"] is False


@pytest.mark.asyncio
async def test_concept_voices_flow():
    """Add voice → list carries it; ripen into proposal with
    back-link to concept (idempotent); 400 on empty body; 404
    localized on missing concept + unknown voice; recent endpoint
    surfaces voices across multiple concepts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = "lc-voice-test"
        await _seed_concept(c, cid)

        # Add a voice, confirm it lists.
        add = await c.post(f"/api/concepts/{cid}/voices", json={
            "author_name": "Ana from Bali",
            "body": "We practice this every morning before the rice terraces.",
            "locale": "id", "location": "Ubud, Bali",
        })
        assert add.status_code == 201
        created = add.json()
        assert created["concept_id"] == cid and created["locale"] == "id"
        voices = (await c.get(f"/api/concepts/{cid}/voices")).json()["voices"]
        assert any(v["author_name"] == "Ana from Bali" for v in voices)

        # Ripen a longer voice into a proposal + verify idempotence + back-link.
        ripen_cid = "lc-voice-ripen"
        await _seed_concept(c, ripen_cid)
        voice = (await c.post(f"/api/concepts/{ripen_cid}/voices", json={
            "author_name": "Ana",
            "body": "We should share the rice harvest on Sundays. This weaves us tighter.",
            "locale": "en",
        })).json()
        vid = voice["id"]
        first_ripen = (await c.post(f"/api/concepts/voices/{vid}/propose")).json()
        assert first_ripen["already_ripened"] is False
        prop = first_ripen["proposal"]
        assert prop["title"].startswith("We should share")
        assert prop["linked_entity_type"] == "concept"
        assert prop["linked_entity_id"] == ripen_cid

        # Idempotent re-ripen.
        second_ripen = (await c.post(f"/api/concepts/voices/{vid}/propose")).json()
        assert second_ripen["already_ripened"] is True
        assert second_ripen["proposal_id"] == first_ripen["proposal_id"]

        # Voice now carries the back-pointer.
        ripened_voices = (await c.get(f"/api/concepts/{ripen_cid}/voices")).json()["voices"]
        match = next(v for v in ripened_voices if v["id"] == vid)
        assert match["proposed_as_proposal_id"] == first_ripen["proposal_id"]

        # Ripening an unknown voice → 404.
        assert (await c.post("/api/concepts/voices/no-such-voice/propose")).status_code == 404

        # Empty body → 400.
        empty_cid = "lc-voice-empty"
        await _seed_concept(c, empty_cid)
        reject_empty = await c.post(f"/api/concepts/{empty_cid}/voices",
                                    json={"author_name": "A", "body": "   "})
        assert reject_empty.status_code == 400

        # Voice on missing concept → 404 in the caller's locale.
        r = await c.post("/api/concepts/does-not-exist/voices",
                         json={"author_name": "Anon", "body": "hello"},
                         headers={"accept-language": "de"})
        assert r.status_code == 404 and "nicht gefunden" in r.json()["detail"]

        # Recent voices endpoint surfaces across multiple concepts.
        for rec_cid in ("lc-voice-recent-a", "lc-voice-recent-b"):
            await _seed_concept(c, rec_cid)
            await c.post(f"/api/concepts/{rec_cid}/voices",
                         json={"author_name": "Tester", "body": f"Voice for {rec_cid}"})
        recent = (await c.get("/api/concepts/voices/recent?limit=10")).json()["voices"]
        assert {"lc-voice-recent-a", "lc-voice-recent-b"} <= {v["concept_id"] for v in recent}


@pytest.mark.asyncio
async def test_energy_invitations_and_fallback_witness_flow():
    """Energy recommend returns warm invitations (no ERROR/WARNING
    language); fallback witness records events and reads them back;
    translator falls back to source text when no backend, and the
    fallback is witnessed."""
    from app.services import fallback_witness_service as fw
    from app.services import translator_service as _tsvc

    # Energy recommendations use frequency words, not warnings.
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        rec = (await c.get("/api/energy/recommend")).json()
        assert "invitations" in rec and "count" in rec
        for inv in rec["invitations"]:
            assert "invitation" in inv
            assert inv["felt_as"] in ("tender", "quiet", "dormant", "resting")
            assert "ERROR" not in inv["invitation"].upper()
            assert "WARNING" not in inv["invitation"].upper()

        # Fallback witness records + filters + summarises.
        fw.clear()
        fw.witness(source="test:example", reason="demo", context={"k": "v"})
        fw.witness(source="test:other", reason="second")
        all_fb = (await c.get("/api/fallbacks")).json()
        assert all_fb["count"] >= 2
        assert {"test:example", "test:other"} <= {e["source"] for e in all_fb["events"]}
        filtered = (await c.get("/api/fallbacks?source=test:ex")).json()["events"]
        assert all(e["source"].startswith("test:ex") for e in filtered)
        assert (await c.get("/api/fallbacks/summary")).json()["total"] >= 2

    # Translator with no backend → source text + witness event.
    fw.clear()
    prev = _tsvc._BACKEND
    _tsvc.set_backend(None)
    try:
        translated, _ = _tsvc.translate_snippet(
            "hi", "there", source_lang="en", target_lang="de",
        )
        assert translated == "hi"
        events = fw.recent(limit=10, source_prefix="translator")
        assert any(e["source"] == "translator:no-backend" for e in events)
    finally:
        _tsvc.set_backend(prev)


@pytest.mark.asyncio
async def test_explore_queue_and_localized_errors_flow():
    """Explore queue surfaces entities the viewer hasn't met (reacted
    to) and skips ones they have. Unsupported entity types return
    400 localized on both /explore and /meeting surfaces."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        for cid in ("lc-explore-a", "lc-explore-b"):
            await _seed_concept(c, cid)

        viewer = "walker-one"
        await c.post("/api/reactions/concept/lc-explore-a",
                     json={"author_name": "Walker", "emoji": "💛", "author_id": viewer})
        queue = (await c.get(
            f"/api/explore/concept?limit=20&contributor_id={viewer}",
        )).json()["queue"]
        ids = {q["entity_id"] for q in queue}
        assert "lc-explore-a" not in ids  # already met — skipped
        assert "lc-explore-b" in ids      # still to meet

        # Unsupported types return 400 localized on both surfaces.
        explore_err = await c.get("/api/explore/lobster", headers={"accept-language": "es"})
        assert explore_err.status_code == 400
        assert "tipo de entidad" in explore_err.json()["detail"]

        meeting_err = await c.get("/api/meeting/lobster/soup",
                                  headers={"accept-language": "de"})
        assert meeting_err.status_code == 400
        assert "nicht unterstützt" in meeting_err.json()["detail"]
