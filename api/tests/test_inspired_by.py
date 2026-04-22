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

# Bandcamp album landing — Bandcamp redirects an artist's subdomain root
# to a featured album; og:description is generic "N track album" chrome,
# not the bio. The resolver should pivot to the /music artist page.
BANDCAMP_ALBUM_LANDING_HTML = """
<html><head>
<meta property="og:site_name" content="Liquid Bloom">
<meta property="og:title" content="Deep Roots, by Liquid Bloom">
<meta property="og:description" content="8 track album">
<meta property="og:type" content="album">
<meta property="og:url" content="https://liquidbloom.bandcamp.com/album/deep-roots">
<meta property="og:image" content="https://f4.bcbits.com/img/a111_23.jpg">
<title>Deep Roots | Liquid Bloom</title>
</head><body></body></html>
"""

# The /music artist page: real bio in og:description (prefixed with
# booking boilerplate the cleaner must strip), artist portrait as
# og:image, no JSON-LD — the discography lives in a static album grid.
BANDCAMP_MUSIC_HTML = """
<html><head>
<meta property="og:site_name" content="Liquid Bloom">
<meta property="og:title" content="Liquid Bloom">
<meta property="og:type" content="band">
<meta property="og:url" content="https://liquidbloom.bandcamp.com">
<meta property="og:description" content="Bookings: setesh@pivotal-agency.com

Liquid Bloom is a music project led by Amani Friend of Desert Dwellers. It combines ambient, world, and psychedelic elements.">
<meta property="og:image" content="https://f4.bcbits.com/img/0041296343_23.jpg">
<link rel="canonical" href="https://liquidbloom.bandcamp.com">
</head><body>
<ol id="music-grid">
    <li class="music-grid-item square first-four">
        <a href="/album/embers-of-a-forgotten-prayer-revibed">
            <div class="art">
                <img src="https://f4.bcbits.com/img/a3661285281_2.jpg" alt="" />
            </div>
            <p class="title">
                Embers of a Forgotten Prayer Revibed
                <br><span class="artist-override">Liquid Bloom, Bloomurian</span>
            </p>
        </a>
    </li>
    <li class="music-grid-item square">
        <a href="/album/reimagined-legacies-liquid-bloom-remixes">
            <div class="art">
                <img class="lazy" src="/img/0.gif"
                    data-original="https://f4.bcbits.com/img/a0374030033_2.jpg" alt="">
            </div>
            <p class="title">
                Reimagined Legacies (Liquid Bloom Remixes)
                <br><span class="artist-override">Various Artists</span>
            </p>
        </a>
    </li>
</ol>
</body></html>
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
    """No presences, no creations, obscure host → weight stays near base.

    With auto-enrichment enabled, a sparse page triggers a name search;
    this test stubs the search + verify paths to empty so we're still
    measuring "thin discovery stays thin" rather than the enrichment
    behaviour (which is covered separately)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(service, "_fetch", _fake_fetch(THIN_HTML, "https://obscure.example.com/x")), \
             patch.object(service, "_ddg_search_urls", lambda q, limit=40: []), \
             patch.object(service, "_url_verified_against_name", lambda u, n: False):
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
async def test_bandcamp_pivots_from_album_landing_to_artist_music_page():
    """Bandcamp redirects `artist.bandcamp.com/` to a featured album.
    That page is a single-work view with admin-generic copy, not a
    presence. The resolver must pivot to `/music` — where the artist's
    bio, portrait, and full discography live — and use that as the
    identity. Albums are pulled from the grid when no JSON-LD is
    present, and lazy-loaded covers come from `data-original`.
    """
    fetches: list[str] = []

    def _routed_fetch(url: str):
        fetches.append(url)
        if url.endswith("/music"):
            return (url, BANDCAMP_MUSIC_HTML)
        return (url, BANDCAMP_ALBUM_LANDING_HTML)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(service, "_fetch", _routed_fetch):
            r = await c.post("/api/inspired-by", json={
                "name": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
        assert r.status_code == 201, r.text
        body = r.json()
        identity = body["identity"]

        # The pivot fired: we fetched the root then the /music page.
        assert any(u.endswith("/music") for u in fetches), fetches

        # Canonical anchors on the artist, not the album.
        assert identity["canonical_url"] == "https://liquidbloom.bandcamp.com"

        # Tagline starts empty — scraped third-party bios never fill
        # the hero slot. That space is held open for the identity's own
        # voice to arrive (via claim) or for a visitor who knows them
        # to type a welcome (via inline edit). The raw og:description
        # still lives on node.description for search/audit; it just
        # doesn't masquerade as the person's voice.
        assert identity["tagline"] == ""
        # The longer-form description field still carries the cleaned
        # bio — useful for search and for any future first-person
        # detector, but explicitly not rendered as the tagline.
        assert identity["description"].startswith("Liquid Bloom is a music project")

        # Two albums pulled from the grid (JSON-LD absent). Names carry
        # the full title; lazy-loaded cover is picked up from
        # data-original and upscaled to Bandcamp's 1200px format.
        creations = body["creations"]
        names = [c["node"]["name"] for c in creations]
        assert "Embers of a Forgotten Prayer Revibed" in names
        assert "Reimagined Legacies (Liquid Bloom Remixes)" in names
        for c in creations:
            assert c["node"]["creation_kind"] == "album"
            img = c["node"]["image_url"] or ""
            assert "/img/0.gif" not in img  # lazy-load placeholder never lands in the grid
            assert "_10." in img  # upscaled from thumb to full-size


@pytest.mark.asyncio
async def test_gathering_stitches_primary_added_by_and_held_open_names():
    """Adding a gathering to a presence threads multiple real edges into
    the graph and keeps unverified names honest.

    The flow: a provisional visitor opens Amani's page and adds a
    gathering. They include a hosting collective (URL) and two co-
    leaders: one as a URL and one as a bare first name. After the
    call, the graph holds:

      · the event node with when/where/note/added_by
      · a contributes-to edge from Amani (role=primary)
      · a contributes-to edge from the hosting collective's real
        node (resolved via URL → inspired-by service)
      · a contributes-to edge from the URL-named co-leader's real
        node (same resolver path)
      · a contributes-to edge from the bare-name co-leader, but
        their node is a held-open placeholder — no canonical_url,
        claimed:false, name equal to what was typed
      · a contributes-to edge from the provisional visitor (added-by)
        so their footprint mirrors what they've placed

    The single URL we need to reach online is stubbed.
    """
    host_url = "https://ecstaticdance.example.org/boulder"
    host_html = """
    <html><head>
    <meta property="og:site_name" content="Ecstatic Dance">
    <meta property="og:title" content="Boulder Ecstatic Dance">
    <link rel="canonical" href="https://ecstaticdance.example.org/boulder">
    </head><body></body></html>
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Primary identity — a minted artist page the gathering is added to.
        source = await _create_source(c)
        with patch.object(service, "_fetch", _fake_fetch(ARTIST_HTML, "https://liquidbloom.bandcamp.com/")):
            created = await c.post("/api/inspired-by", json={
                "name": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
        artist_id = created.json()["identity"]["id"]

        # Provisional visitor — a wanderer with no name, created by
        # the client's ensureVisitorContributor helper.
        wanderer_id = "contributor:wanderer-test-abc"
        r = await c.post("/api/graph/nodes", json={
            "id": wanderer_id,
            "type": "contributor",
            "name": wanderer_id.split(":", 1)[1],
            "description": "",
            "properties": {"claimed": False, "contributor_type": "HUMAN", "provisional": True},
        })
        assert r.status_code == 200

        # Route _fetch: primary identity was already memoized as an
        # existing node, so only the hosting-collective fetch needs
        # to succeed for this case.
        def _routed_fetch(url: str):
            if "ecstaticdance.example.org" in url:
                return (host_url, host_html)
            return None

        with patch.object(service, "_fetch", _routed_fetch):
            r = await c.post(
                f"/api/presences/{artist_id}/gatherings",
                json={
                    "title": "Breathwork with Liquid Bloom",
                    "when": "summer 2026",
                    "where": "Boulder, CO",
                    "note": "a charged one",
                    "added_by": wanderer_id,
                    "hosted_by": host_url,
                    "co_led_with": [
                        "https://artist.example.com",  # URL — would resolve
                        "Robin",                       # bare name — placeholder
                    ],
                },
            )
        # The URL co-leader's fetch returns None above, so that path
        # falls through to placeholder too. That's intentional: both
        # unresolvable URLs and bare names become held-open placeholders
        # with no canonical_url, never speculative online identities.
        assert r.status_code == 201, r.text
        body = r.json()
        event_id = body["event"]["id"]

        # All the contributes-to edges pointing AT the event.
        incoming = graph_service.list_edges(
            to_id=event_id, edge_type="contributes-to", limit=50,
        ).get("items", [])
        roles = {(e["from_id"], (e.get("properties") or {}).get("role")) for e in incoming}

        # Primary host = the identity whose page this was added from.
        assert (artist_id, "primary") in roles

        # Added-by edge from the provisional wanderer — their footprint
        # now carries this event.
        assert (wanderer_id, "added-by") in roles

        # Hosting collective — the node was created from the stubbed fetch,
        # and links back with role=hosting.
        hosting_ids = [fid for (fid, role) in roles if role == "hosting"]
        assert len(hosting_ids) == 1
        hosting_node = graph_service.get_node(hosting_ids[0])
        assert hosting_node is not None
        assert hosting_node["canonical_url"] == host_url

        # Co-leaders — both became held-open placeholders (no
        # canonical_url, claimed:false, names match what was typed).
        co_leader_ids = [fid for (fid, role) in roles if role == "co-leading"]
        assert len(co_leader_ids) == 2
        co_leaders = [graph_service.get_node(cid) for cid in co_leader_ids]
        co_names = {n["name"] for n in co_leaders if n}
        assert "Robin" in co_names
        for n in co_leaders:
            assert n["claimed"] is False
            # Placeholders carry no canonical_url — the graph never
            # pretends they resolved to an online identity.
            assert not n.get("canonical_url")


@pytest.mark.asyncio
async def test_sparse_resolve_auto_enriches_from_name_search():
    """When an entity's home page surfaces only 0-1 outbound presence
    links (Bandcamp artist page → Facebook only), the resolver's
    auto-enrichment runs a name search and picks up the rest of the
    constellation. Slug-match URLs are accepted directly; opaque-ID
    URLs (Spotify's /artist/{hash}, YouTube's /channel/{id}) get a
    cheap og:title verification pass. Both paths are stubbed here so
    the test doesn't reach the live web."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)

        # Thin bandcamp-like page: only one social link (Facebook).
        thin_artist_html = """
        <html><head>
        <meta property="og:site_name" content="Desert Seeker">
        <meta property="og:title" content="Desert Seeker">
        <meta property="og:description" content="Ambient journey music">
        <link rel="canonical" href="https://desertseeker.bandcamp.com/">
        </head><body>
        <a href="https://www.facebook.com/desertseeker">Facebook</a>
        </body></html>
        """

        # What DDG "returns" for the name search. Mix of slug-matches
        # and opaque IDs.
        search_hits = [
            "https://soundcloud.com/desertseeker",             # slug-match
            "https://www.instagram.com/desertseeker",          # slug-match
            "https://open.spotify.com/artist/abc123hash",       # opaque, verified
            "https://www.facebook.com/desertseeker",            # dup with initial
            "https://open.spotify.com/artist/otherartist",      # opaque, NOT verified
            "https://www.example.com/random-match-desertseeker", # no provider
        ]

        # Opaque-ID verification: only the first Spotify URL matches name.
        def fake_verify(url, name):
            return url == "https://open.spotify.com/artist/abc123hash"

        with patch.object(service, "_fetch", _fake_fetch(thin_artist_html, "https://desertseeker.bandcamp.com/")), \
             patch.object(service, "_ddg_search_urls", lambda q, limit=40: search_hits), \
             patch.object(service, "_url_verified_against_name", fake_verify):
            r = await c.post("/api/inspired-by", json={
                "name": "https://desertseeker.bandcamp.com",
                "source_contributor_id": source,
            })
        assert r.status_code == 201, r.text
        body = r.json()
        providers = {p["provider"] for p in body["presences"]}
        # Facebook from the page; SoundCloud + Instagram via slug match;
        # Spotify via opaque-ID fetch-verify. Second Spotify (different
        # artist) was rejected by verify.
        assert "facebook" in providers
        assert "soundcloud" in providers
        assert "instagram" in providers
        assert "spotify" in providers
        # Only one spotify link — the verified one
        spotify_urls = [p["url"] for p in body["presences"] if p["provider"] == "spotify"]
        assert spotify_urls == ["https://open.spotify.com/artist/abc123hash"]


@pytest.mark.asyncio
async def test_resonance_attune_stitches_presence_into_vision_concepts():
    """A presence's keyword spectrum aligned against a concept's keyword
    spectrum becomes a ``resonates-with`` edge. Each edge carries the
    score + the shared tokens that explain why the link is there, so
    a later deeper-frequency pass can refresh or disambiguate. Also
    verifies the read endpoint surfaces them back in score order."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        # Seed a tiny concept universe — enough to exercise the match
        # logic without requiring the full KB sync.
        for cid, name, story in (
            ("concept:ceremony", "Ceremony",
             "Sacred fire, ritual, slow music, the gathering around a circle, "
             "elders holding space, breath and bass and stillness."),
            ("concept:nervous-system", "Nervous System",
             "Breathwork regulates the nervous system. Calm, co-regulation, "
             "somatic grounding, heartbeat, subtle tuning."),
            ("concept:unrelated", "Spreadsheets",
             "Rows, columns, pivot tables, accounting, quarterly reports."),
        ):
            r = await c.post("/api/graph/nodes", json={
                "id": cid, "type": "concept", "name": name,
                "description": story, "properties": {},
            })
            assert r.status_code == 200

        # Mint an artist presence with ceremony-flavoured signal.
        with patch.object(service, "_fetch", _fake_fetch(ARTIST_HTML, "https://liquidbloom.bandcamp.com/")):
            created = await c.post("/api/inspired-by", json={
                "name": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
        identity_id = created.json()["identity"]["id"]

        # Layer on a ceremonial note so the resonance has real overlap
        # against the ceremony concept's story words.
        await c.patch(
            f"/api/graph/nodes/{identity_id}",
            json={
                "description": (
                    "Liquid Bloom holds sacred music for ritual — slow bass, "
                    "ceremony-bass, breath-paced. The fire circle filled with "
                    "sound."
                ),
            },
        )

        attune = await c.post(f"/api/presences/{identity_id}/resonances/attune")
        assert attune.status_code == 200, attune.text
        body = attune.json()

        # Ceremony should emerge as the top resonance; spreadsheet noise
        # shouldn't. Edges may live in either ``written`` (first time
        # seen by this attune call) or ``existed`` (already laid by the
        # auto-attune-on-update hook the graph PATCH triggered just
        # above). Either placement counts as "the edge is there."
        all_concept_ids = [r["concept_id"] for r in body["written"] + body["existed"]]
        assert "concept:ceremony" in all_concept_ids
        assert "concept:unrelated" not in all_concept_ids

        # Read-back endpoint surfaces the same edges in score order,
        # with the shared tokens that explain each thread.
        listed = await c.get(f"/api/presences/{identity_id}/resonances")
        assert listed.status_code == 200
        items = listed.json()["items"]
        scores = [it["score"] for it in items]
        assert scores == sorted(scores, reverse=True)
        assert items[0]["concept_id"] == "concept:ceremony"
        assert items[0]["method"] == "keyword-overlap"
        assert items[0]["shared_tokens"]

        # Re-attuning is idempotent — existing edges stay put, nothing
        # duplicates.
        again = await c.post(f"/api/presences/{identity_id}/resonances/attune")
        assert len(again.json()["written"]) == 0


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
