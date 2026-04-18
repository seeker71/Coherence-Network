"""Flow-centric tests for the inspired-by resolver and /api/inspired-by.

The resolver is exercised through the FastAPI app. External HTTP is
patched: we never reach out to the real internet from tests.
"""
from __future__ import annotations

from uuid import uuid4
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import graph_service, inspired_by_service as service

BASE = "http://test"

# Bandcamp-flavored page: rich identity with outbound social links and a
# JSON-LD MusicAlbum payload as a creation.
ARTIST_HTML = """
<html><head>
<meta property="og:site_name" content="Liquid Bloom">
<meta property="og:title" content="Liquid Bloom — Bandcamp">
<meta property="og:description" content="Downtempo and bass for ceremony.">
<meta property="og:image" content="https://example.com/lb.jpg">
<link rel="canonical" href="https://liquidbloom.bandcamp.com/">
<title>Liquid Bloom on Bandcamp</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "MusicAlbum",
  "name": "Deep Roots",
  "url": "https://liquidbloom.bandcamp.com/album/deep-roots",
  "image": "https://example.com/deep-roots.jpg"
}
</script>
</head>
<body>
<a href="https://www.youtube.com/@liquidbloom">YouTube</a>
<a href="https://open.spotify.com/artist/abc123">Spotify</a>
<a href="https://www.instagram.com/liquidbloom/">Instagram</a>
<a href="https://liquidbloom.bandcamp.com/album/deep-roots">Deep Roots</a>
</body></html>
"""

# Event page: eventbrite-flavored, no JSON-LD, OG event type.
EVENT_HTML = """
<html><head>
<meta property="og:title" content="Unison Festival 2026">
<meta property="og:description" content="Music, movement, ceremony.">
<meta property="og:type" content="event">
<title>Unison Festival</title>
</head>
<body>
<a href="https://www.instagram.com/unisonfestival/">Instagram</a>
</body></html>
"""

# Thin page: no OG, no JSON-LD, no outbound links. Baseline weight case.
THIN_HTML = """
<html><head><title>Nobody in particular</title></head></html>
"""


def _fake_fetch(html: str, final_url: str):
    return lambda url: (final_url, html)


async def _create_source(c: AsyncClient) -> str:
    cid = f"contributor:test-source-{uuid4().hex[:8]}"
    payload = {
        "id": cid,
        "type": "contributor",
        "name": cid.split(":", 1)[1],
        "description": "Test source contributor",
        "properties": {
            "contributor_type": "HUMAN",
            "email": f"{cid.split(':', 1)[1]}@test.local",
        },
    }
    r = await c.post("/api/graph/nodes", json=payload)
    assert r.status_code == 200, r.text
    return cid


@pytest.mark.asyncio
async def test_name_resolves_to_identity_with_presences_and_creations():
    """A bare name goes search → URL → fetch. The resolver extracts the
    identity, its cross-platform presences, and its creations. The edge
    weight reflects the richness of what was found."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(service, "_ddg_first_result", lambda q: "https://liquidbloom.bandcamp.com"), \
             patch.object(service, "_fetch", _fake_fetch(ARTIST_HTML, "https://liquidbloom.bandcamp.com/")):
            r = await c.post("/api/inspired-by", json={
                "name": "Liquid Bloom",
                "source_contributor_id": source,
            })
        assert r.status_code == 201, r.text
        body = r.json()

        # Identity — placeholder carries the single claim signal so the
        # contributors directory can render the waiting distinctly from
        # the walked-in.
        identity = body["identity"]
        assert identity["type"] == "contributor"
        assert identity["name"] == "Liquid Bloom"
        assert identity["canonical_url"] == "https://liquidbloom.bandcamp.com"
        assert identity["provider"] == "bandcamp"
        assert identity["claimed"] is False
        assert "claimable" not in identity  # one signal, not two

        # Presences — same-provider links (liquidbloom.bandcamp.com) excluded;
        # cross-provider socials kept.
        providers = {p["provider"] for p in body["presences"]}
        assert {"youtube", "spotify", "instagram"} <= providers
        assert "bandcamp" not in providers  # own provider filtered

        # Creations
        assert len(body["creations"]) == 1
        creation = body["creations"][0]["node"]
        assert creation["type"] == "asset"
        assert creation["name"] == "Deep Roots"
        assert creation["creation_kind"] == "album"

        # Weight emerges: base 0.4 + 3 presences*0.05 + 1 creation*0.05
        # + canonical bandcamp.com bonus 0.1 = 0.7
        assert 0.65 <= body["weight"] <= 0.75


@pytest.mark.asyncio
async def test_weight_is_lower_when_discovery_is_thin():
    """No presences, no creations, obscure host → weight stays near base."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(service, "_fetch", _fake_fetch(THIN_HTML, "https://obscure.example.com/x")):
            r = await c.post("/api/inspired-by", json={
                "name": "https://obscure.example.com/x",
                "source_contributor_id": source,
            })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["weight"] == 0.4
        assert body["presences"] == []
        assert body["creations"] == []


@pytest.mark.asyncio
async def test_event_resolves_to_community_identity():
    """Hostname inference maps eventbrite-style pages to community nodes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(service, "_ddg_first_result", lambda q: "https://www.eventbrite.com/e/unison-festival-123"), \
             patch.object(service, "_fetch", _fake_fetch(EVENT_HTML, "https://www.eventbrite.com/e/unison-festival-123")):
            r = await c.post("/api/inspired-by", json={
                "name": "Unison Festival",
                "source_contributor_id": source,
            })
        assert r.status_code == 201, r.text
        identity = r.json()["identity"]
        assert identity["type"] == "community"
        assert identity["provider"] == "eventbrite"
        # A festival is not a HUMAN contributor — it's a community node.
        # No contributor_type + no placeholder email should be forced on
        # it, so nothing pollutes /api/contributors.
        assert "contributor_type" not in identity
        assert "email" not in identity


@pytest.mark.asyncio
async def test_idempotent_on_canonical_url():
    """Re-adding the same identity reuses the node and reports edge_existed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(service, "_fetch", _fake_fetch(ARTIST_HTML, "https://liquidbloom.bandcamp.com/")):
            first = await c.post("/api/inspired-by", json={
                "name": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
            second = await c.post("/api/inspired-by", json={
                "name": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
        assert first.json()["identity_created"] is True
        assert second.json()["identity_created"] is False
        assert second.json()["edge_existed"] is True
        assert first.json()["identity"]["id"] == second.json()["identity"]["id"]


def test_fetch_refuses_internal_addresses():
    """SSRF guard: the resolver must not reach loopback, private, or
    link-local addresses even if a user posts one directly. This is
    tested at the ``_fetch`` level — if it returns None for these
    URLs, the rest of the resolver can't accidentally fetch them."""
    # Loopback, private, link-local (AWS metadata), reserved.
    assert service._fetch("http://127.0.0.1/admin") is None
    assert service._fetch("http://10.0.0.1/") is None
    assert service._fetch("http://192.168.1.1/") is None
    assert service._fetch("http://169.254.169.254/latest/meta-data/") is None
    assert service._fetch("http://localhost/") is None


@pytest.mark.asyncio
async def test_unresolvable_is_soft_failure_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(service, "_ddg_first_result", lambda q: None):
            r = await c.post("/api/inspired-by", json={
                "name": "xxxxx nothing here xxxxx",
                "source_contributor_id": source,
            })
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_viewer_id_marks_shared_threads():
    """When a viewer contributor id is supplied, each subject item carries
    ``shared_with_viewer``. Kinship surfaces automatically wherever the
    viewer and the subject are both inspired-by the same identity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        subject = await _create_source(c)
        viewer = await _create_source(c)
        stranger = await _create_source(c)

        with patch.object(service, "_fetch", _fake_fetch(ARTIST_HTML, "https://liquidbloom.bandcamp.com/")):
            await c.post("/api/inspired-by", json={
                "name": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": subject,
            })
            await c.post("/api/inspired-by", json={
                "name": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": viewer,
            })
        # Subject has an additional inspiration the viewer does not.
        with patch.object(service, "_fetch", _fake_fetch(EVENT_HTML, "https://eventbrite.com/e/unison-festival")):
            await c.post("/api/inspired-by", json={
                "name": "https://eventbrite.com/e/unison-festival",
                "source_contributor_id": subject,
            })

        # Viewer → shared flag set on the one they both carry.
        listed = await c.get(
            f"/api/inspired-by?contributor_id={subject}&viewer_id={viewer}"
        )
        body = listed.json()
        assert body["shared_count"] == 1
        shared = [it for it in body["items"] if it.get("shared_with_viewer")]
        assert len(shared) == 1
        assert shared[0]["node"]["name"] == "Liquid Bloom"

        # Stranger (no inspirations) → shared flag present and all False.
        stranger_view = await c.get(
            f"/api/inspired-by?contributor_id={subject}&viewer_id={stranger}"
        )
        assert stranger_view.json()["shared_count"] == 0


@pytest.mark.asyncio
async def test_list_and_delete_leaves_identity_and_creations_intact():
    """Deleting the inspired-by edge leaves the identity and its
    creation edges in the graph — still claimable, still connected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(service, "_fetch", _fake_fetch(ARTIST_HTML, "https://liquidbloom.bandcamp.com/")):
            created = await c.post("/api/inspired-by", json={
                "name": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
        identity_id = created.json()["identity"]["id"]
        creation_id = created.json()["creations"][0]["node"]["id"]

        listed = await c.get(f"/api/inspired-by?contributor_id={source}")
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["node"]["id"] == identity_id
        assert 0.0 < items[0]["weight"] <= 1.0
        edge_id = items[0]["edge_id"]

        deleted = await c.delete(f"/api/inspired-by/{edge_id}")
        assert deleted.status_code == 200

        relisted = await c.get(f"/api/inspired-by?contributor_id={source}")
        assert relisted.json()["count"] == 0
        # Identity and creation both still present; the contributes-to
        # edge between them also survives.
        assert graph_service.get_node(identity_id) is not None
        assert graph_service.get_node(creation_id) is not None
        identity_edges = graph_service.list_edges(from_id=identity_id, edge_type="contributes-to")
        assert any(e["to_id"] == creation_id for e in identity_edges.get("items", []))
