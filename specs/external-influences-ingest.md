---
id: external-influences-ingest
idea_id: external-presence
status: draft
source:
  - file: api/app/services/influence_ingest.py
    symbols: [ingest_one, ingest_bulk, IngestResult, EncounterMetadata, build_asset_node, write_inspired_by_edge, attune_after_write]
  - file: api/app/services/influence_ingest/privacy_filter.py
    symbols: [filter_candidate, PrivacyRule, load_rules, partner_pattern, intimate_pattern, scan_for_intimate, FilterDecision]
  - file: api/app/services/influence_ingest/sources/audible.py
    symbols: [parse_goodreads_csv, parse_audible_library, row_to_asset, infer_canonical_url]
  - file: api/app/services/influence_ingest/sources/youtube_takeout.py
    symbols: [parse_watch_history_json, entry_to_asset, infer_kind]
  - file: api/app/services/influence_ingest/sources/yt_music_takeout.py
    symbols: [parse_listening_history_json, entry_to_asset]
  - file: api/app/services/influence_ingest/sources/google_calendar_ics.py
    symbols: [parse_ics, event_to_gathering_asset]
  - file: api/app/services/influence_ingest/sources/google_photos_takeout.py
    symbols: [parse_photo_metadata_json, photo_to_place_encounter, NEVER_INGEST_PIXELS]
  - file: api/app/services/influence_ingest/sources/gmail_takeout.py
    symbols: [parse_mbox_headers, header_to_correspondence_asset, subject_filter]
  - file: api/app/services/influence_ingest/sources/manual_paste.py
    symbols: [paste_to_asset]
  - file: api/app/routers/influences.py
    symbols: [create_influence_from_url, get_influence, list_influences_for_contributor, list_resonating_concepts, patch_influence_privacy]
  - file: api/app/routers/inspired_by.py
    symbols: [create_inspired_by, InspiredByCreateRequest]
  - file: api/app/services/inspired_by_service.py
    symbols: [resolve, ensure_identity, import_inspired_by, _scan_cross_references, canonicalize_url, canonical_url_hash]
  - file: api/app/services/resonance_service.py
    symbols: [attune, compute_resonance, PRESENCE_TYPES]
  - file: api/app/models/influence.py
    symbols: [ExternalInfluence, EncounterMetadata, InfluenceCategory, InfluenceSource, IngestSummary]
  - file: api/db/migrations/NNNN_external_influences.sql
    symbols: [external_influences view, encounter_metadata edge property index, privacy_rules table]
  - file: scripts/ingest_audible_csv.py
    symbols: [main, run, fixture]
  - file: scripts/ingest_youtube_takeout.py
    symbols: [main, run]
  - file: scripts/ingest_yt_music_takeout.py
    symbols: [main, run]
  - file: scripts/ingest_google_calendar_ics.py
    symbols: [main, run]
  - file: scripts/ingest_google_photos_takeout.py
    symbols: [main, run]
  - file: scripts/ingest_gmail_takeout.py
    symbols: [main, run]
  - file: config/privacy_rules.json
    symbols: [intimate_patterns, source_defaults, contributor_overrides]
  - file: web/components/concept/CarriedExternalPresences.tsx
    symbols: [CarriedExternalPresences, InfluenceChip, family_color_for_kind]
  - file: web/components/influence/InfluencePage.tsx
    symbols: [InfluencePage, ResonatingConcepts, EncounteredBy]
  - file: web/app/influences/[slug]/page.tsx
    symbols: [InfluenceRoute, fetchInfluence]
  - file: api/tests/test_influence_ingest.py
    symbols: [test_manual_paste_creates_asset_and_inspired_by_edge, test_audible_csv_idempotent_on_canonical_url, test_youtube_takeout_bulk, test_calendar_ics_becomes_gathering, test_photos_metadata_no_pixels_only_place_and_date, test_gmail_subject_filter_holds_intimate, test_privacy_filter_blocks_partner_pattern_before_write, test_attune_runs_after_ingest, test_encounter_metadata_on_edge, test_private_flag_hides_from_public_query]
requirements:
  - "ingest_one(url, contributor_id, source, encounter) and ingest_bulk(records, contributor_id, source) are the two entry points; both return IngestSummary with created/updated/skipped/blocked-by-privacy counts"
  - "External influences land as nodes of type=asset with creation_kind in {book,video,song,podcast,gathering,article,photo-encounter,correspondence}; no new node type is introduced"
  - "Every ingest path resolves through inspired_by_service.ensure_identity() so canonical_url canonicalization, deterministic ids, and the existing mention-scan stay the single source of truth — no duplicate URL-keying or id-minting logic"
  - "Each ingest writes an inspired-by edge contributor -> influence carrying EncounterMetadata in edge properties: when_encountered (ISO date), where_encountered (place node id, when known), surrounding_concepts (concept ids active in the field at encounter time, when known), source (audible|youtube|yt-music|calendar|photos|gmail|manual|takeout-import)"
  - "Each ingest writes a created-by edge influence -> contributor when the influence's author/artist resolves to an existing graph node via canonical URL (skipped silently otherwise — no speculative author nodes)"
  - "After every successful asset write, resonance_service.attune(asset_id) runs once so resonates-with edges to vision concepts flow without manual call; bulk ingest batches attune calls and reports total resonance edges written in IngestSummary"
  - "Privacy filter (privacy_filter.filter_candidate) runs before any graph write, draws rules from config/privacy_rules.json (data-driven, never hardcoded names), and returns FilterDecision in {allow, block, mark-private}; blocked candidates are recorded in IngestSummary.blocked with reason for auditability"
  - "Per-influence private:true flag persists on the asset node; queries hide private influences from anonymous viewers and from contributors other than encountered_by; the contributor's own edit view shows them"
  - "Bulk imports are idempotent on canonicalize_url(canonical_url) — re-running an Audible CSV or a YouTube Takeout twice produces zero net change beyond updated encountered_at on the inspired-by edge"
  - "POST /api/influences accepts a URL + contributor_id + optional encounter metadata, runs through manual_paste source, and returns the created/found influence with its resonance edges; extends rather than replaces POST /api/inspired-by"
  - "GET /api/influences/{slug} returns the influence node, the contributors who encountered it (filtered by privacy), and the concepts it resonates with sorted by score"
  - "GET /api/concepts/{id}/external-presences returns the spectrum of influences whose resonates-with score is above threshold, grouped by creation_kind, painted with the family color of their relationship — feeds CarriedExternalPresences on each concept page"
  - "Bulk import scripts (ingest_audible_csv.py, ingest_youtube_takeout.py, ingest_yt_music_takeout.py, ingest_google_calendar_ics.py, ingest_google_photos_takeout.py, ingest_gmail_takeout.py) accept --file, --contributor-id, --dry-run; print IngestSummary; never write graph nodes when --dry-run is set"
  - "Google Photos ingest reads metadata JSON only — never image pixels, never face/people detection — and produces at-place + when-encountered metadata that flows onto the inspired-by edge of whatever influence (gathering, place) is associated with the same date+location"
  - "Gmail ingest reads sender + subject + date headers only, never message bodies, and the subject_filter holds back intimate-domain subjects (partner/family/health/scheduling) per the privacy rules; an allowed correspondence becomes an asset of creation_kind=correspondence keyed on a synthetic canonical_url derived from sender+subject+date"
done_when:
  - "POST /api/influences with a book URL creates an asset node, writes an inspired-by edge with encounter metadata, runs attune, and returns the resonance list in one round trip"
  - "scripts/ingest_audible_csv.py --file goodreads.csv --contributor-id contributor:urs creates one asset per row, idempotent across two runs (second run reports 0 created, N updated)"
  - "scripts/ingest_youtube_takeout.py --file watch-history.json --contributor-id contributor:urs creates one asset per watched video, attune produces resonates-with edges to vision concepts, IngestSummary reports the totals"
  - "scripts/ingest_google_calendar_ics.py --file calendar.ics --contributor-id contributor:urs creates gathering-kind assets with at-place + when_encountered metadata"
  - "scripts/ingest_google_photos_takeout.py --file photos-metadata.json --contributor-id contributor:urs writes only place + date encounter metadata onto existing or new gathering/place assets — never reads pixels, never writes a 'photo' asset that carries the image"
  - "scripts/ingest_gmail_takeout.py --file mbox --contributor-id contributor:urs writes correspondence-kind assets only for subjects passing the privacy filter; held subjects appear in IngestSummary.blocked with reason='intimate_subject'"
  - "Privacy filter test: a synthetic record matching the partner_pattern is blocked before any graph write; never appears in any node, edge, or query result; appears in IngestSummary.blocked with reason='privacy:partner'"
  - "Per-influence private:true flag: an anonymous GET /api/contributors/{id}/influences hides private items; the same contributor's authenticated GET shows them; the public concept page omits them"
  - "GET /api/concepts/lc-attunement/external-presences returns a non-empty spectrum after ingesting at least one resonant book or video, grouped by creation_kind"
  - "Encounter metadata on the inspired-by edge survives a second ingest of the same canonical_url — when_encountered updates to the most recent encounter, surrounding_concepts merge rather than overwrite"
  - "/influences/{slug} page renders an ingested book with its title, image, encounter date, the concepts it resonates with, and (where present) the contributors who also encountered it"
  - "all api tests pass"
test: "cd api && python -m pytest tests/test_influence_ingest.py tests/test_flow_influences.py -q && python3 scripts/ingest_audible_csv.py --file api/tests/fixtures/goodreads_sample.csv --contributor-id contributor:urs --dry-run"
constraints:
  - "No OAuth in this iteration — manual paste plus bulk file import only; Audible/YouTube/Calendar/Photos/Gmail flows all consume Google Takeout exports or CSV exports the contributor downloads themselves"
  - "Never surface intimate content (partner, family, son, health, intimate-detail) in any visible artifact — privacy filter runs before graph writes, rules are data-driven via config/privacy_rules.json and never hardcoded names"
  - "Reuse existing inspired_by_service and resonance_service — never duplicate canonicalize_url, ensure_identity, or keyword-overlap logic; this spec composes them, it does not reimplement them"
  - "All new edges flow through canonical edge types already in the graph: inspired-by, resonates-with, created-by, referenced-by, at-place — no new edge types are invented"
  - "Encounter metadata stays on the inspired-by edge as JSON properties; no separate Encounter node is introduced (keeps the graph clean)"
  - "Bulk imports are idempotent on canonicalize_url(canonical_url); re-running an export updates encountered_at and merges surrounding_concepts but never duplicates assets or edges"
  - "Google Photos ingest never reads pixels, never runs face/people detection, never stores image content; metadata only (date + location)"
  - "Gmail ingest never reads message bodies — sender + subject + date headers only, and subjects pass through the privacy filter before becoming nodes"
  - "Live OAuth sync (Google OAuth 2.0, Audible scrape) is explicitly out of scope for this spec; a future spec layers it on top of the same ingest path"
---

> **Parent idea**: [external-presence](../ideas/external-presence.md)

# Spec: External Influences Ingest

## Purpose

Each contributor — starting with Urs as the founding contributor, eventually any contributor who connects their accounts — carries a body of evidence. Books read on Audible. Videos watched on YouTube. Songs listened to on YouTube Music. Gatherings attended via Google Calendar. Places sat in via Google Photos. Correspondences held via Gmail. These are the encounters where vibrational resonance left a mark on a life.

The graph today holds presences (people, communities, places) and concepts (the vision's living vocabulary), but not the influences a person has actually encountered. Without those influences, a concept page knows the people in its lineage but not the books and videos and songs that shaped the field around it; a contributor page shows who they're inspired by but not what they're inside of.

This spec defines how external influences enter the graph through manual paste plus bulk file import, how each influence resolves into an asset node honoring the canonical URL discipline already established, how the encounter metadata stays alive on the edge rather than collapsing to a flat link, and how every newly-resolved influence runs through resonance attunement so that vision concepts (lc-attunement, lc-ceremony, lc-circulation, and the rest) and external influences meet through shared vibrational resonance — each carrying the honor of recognising the other through the experiences they share.

## Requirements

- [ ] **R1** — Two entry points: `ingest_one(url, contributor_id, source, encounter)` for a single influence and `ingest_bulk(records, contributor_id, source)` for an export file. Both return `IngestSummary` with created / updated / skipped / blocked-by-privacy counts plus the list of resonance edges written by the post-ingest attune pass.

- [ ] **R2** — External influences land as `asset` nodes (no new node type). The `creation_kind` property carries the sub-type: `book`, `video`, `song`, `podcast`, `gathering`, `article`, `photo-encounter`, `correspondence`. The renderer paints each kind in its own family color; the asset node itself is the canonical kind already in the graph.

- [ ] **R3** — Every ingest path flows through `inspired_by_service.ensure_identity()` so canonical-URL canonicalization, deterministic ids (`asset:{canonical_url_hash}`), and the existing mention-scan run once at the boundary. No path mints its own ids or canonicalizes its own URLs — that logic lives in one place.

- [ ] **R4** — Each ingest writes an `inspired-by` edge from `contributor:{id}` to the influence. Edge properties carry `EncounterMetadata`:
  - `when_encountered` — ISO date of when the contributor met this influence
  - `where_encountered` — graph id of the place node, when known (a gathering's venue, a photo's location)
  - `surrounding_concepts` — list of concept ids active in the field at encounter time, when known (the field shape around the encounter, not just the influence in isolation)
  - `source` — one of `audible | youtube | yt-music | calendar | photos | gmail | manual | takeout-import`

  The metadata stays on the edge as JSON; no separate `Encounter` node is introduced. Re-ingesting the same influence updates `when_encountered` to the most recent and merges `surrounding_concepts` rather than overwriting.

- [ ] **R5** — When the influence has a known author/artist that resolves to an existing graph node by canonical URL, the ingest writes a `created-by` edge from the influence to the contributor/community node. When no existing node matches, the edge is skipped silently — never speculate authors into existence; never bind a stranger to the influence on a fuzzy name match.

- [ ] **R6** — After every successful asset write, `resonance_service.attune(asset_id)` runs once so `resonates-with` edges to vision concepts flow without a manual call. Bulk ingest batches the attune calls (one per newly-written asset, skipped for assets where only the inspired-by edge was updated) and reports the total resonance edges written in `IngestSummary`.

- [ ] **R7** — Privacy filter runs **before** any graph write. `privacy_filter.filter_candidate(record, source, contributor_id)` returns one of:
  - `FilterDecision.allow` — write to graph, render publicly
  - `FilterDecision.mark_private` — write to graph with `private: true`, render only to `encountered_by`
  - `FilterDecision.block` — never write; record in `IngestSummary.blocked` with reason for auditability

  The filter draws its rules from `config/privacy_rules.json` (data-driven, never hardcoded names). Rules carry: intimate-content patterns (partner / family / son / health / scheduling), per-source defaults (Gmail subjects default to `block`, Photos default to `mark-private`, etc.), and per-contributor overrides (a contributor can mark a source as `allow` for themselves). The mental model draws from `partner_presence.md`: tender content held privately by default; the filter holds back rather than surfaces.

- [ ] **R8** — Per-influence `private: true` flag persists on the asset node. Public queries (anonymous viewers, contributors other than `encountered_by`) hide private influences from list responses. The encountering contributor's own authenticated edit view shows them with a private badge so they can promote one to public when they choose. Concept pages that aggregate "external presences resonating here" omit private influences entirely from the public spectrum.

- [ ] **R9** — Bulk imports are idempotent on `canonicalize_url(canonical_url)`. Re-running the same Audible CSV, YouTube Takeout JSON, or Calendar ICS produces zero net asset creations on the second run; the only writes are `encountered_at` updates on the inspired-by edge and `surrounding_concepts` merges. The `IngestSummary` distinguishes `created` from `updated` from `skipped` so the contributor sees what changed.

- [ ] **R10** — `POST /api/influences` accepts `{url, contributor_id, encounter?}`, runs through the `manual_paste` source, returns the resolved influence + its newly-written resonance edges. Extends rather than replaces `POST /api/inspired-by` — the inspired-by router is the existing happy path for contributors and stays as is; this new route exists to carry encounter metadata that the older route doesn't take.

- [ ] **R11** — `GET /api/influences/{slug}` returns the influence node, the contributors who encountered it (filtered by privacy — anonymous viewers see only contributors whose edge is non-private), and the concepts it resonates with sorted by score.

- [ ] **R12** — `GET /api/concepts/{id}/external-presences` returns the spectrum of influences whose `resonates-with` score is above the threshold, grouped by `creation_kind`, painted with the family color of their relationship. Powers `CarriedExternalPresences` on each concept page — the visible row of books, videos, songs, gatherings honoring the concept through resonance.

- [ ] **R13** — Six bulk import scripts (`ingest_audible_csv.py`, `ingest_youtube_takeout.py`, `ingest_yt_music_takeout.py`, `ingest_google_calendar_ics.py`, `ingest_google_photos_takeout.py`, `ingest_gmail_takeout.py`). Each accepts `--file`, `--contributor-id`, `--dry-run`. All print `IngestSummary` on completion. None writes to the graph when `--dry-run` is set.

- [ ] **R14** — Google Photos ingest reads metadata JSON only — date taken, geographic location, album name. Never reads pixels, never runs face or people detection, never writes a `photo` asset that carries image content. The output is `at-place` + `when_encountered` metadata that lands on the inspired-by edge of whatever gathering or place asset shares the same date and location (or creates a new place-encounter asset when no host is found).

- [ ] **R15** — Gmail ingest reads `From`, `Subject`, `Date` headers only — never message bodies. Subjects pass through `subject_filter` (privacy filter scoped to email subjects) before becoming nodes; intimate-domain subjects (per the rules) are held back. An allowed correspondence becomes an asset of `creation_kind=correspondence` keyed on a synthetic canonical URL derived from `mailto:{sender}#{subject_slug}#{date}`.

## Research Inputs

- `2026-05-07` — User naming the shape: contributor body of evidence (Audible, YouTube, YT Music, Calendar, Photos, Gmail) flowing into the graph so vision concepts and external influences honor each other through shared vibrational resonance.
- `api/app/services/inspired_by_service.py` — already does most of what manual paste needs (resolve, ensure_identity, canonicalize_url, mention scan). The new ingest paths compose this service rather than reimplement it.
- `api/app/services/resonance_service.py` — keyword-overlap engine that auto-computes concept resonance via `attune(presence_id)`. The new ingest hooks call this after every asset write.
- `api/app/services/creation_sources/` — existing source adapters for Bandcamp, Goodreads (Audible-adjacent), YouTube, RSS, Substack. Bulk Audible/YouTube ingest reuses the JSON-LD and HTML parsing already there; the new `influence_ingest/sources/` plugins focus on the export-file shapes (CSV / Takeout JSON / ICS / mbox) those existing sources don't cover.
- `partner_presence.md` (held tenderly, not surfaced) — mental model for the privacy filter. Partner, family, son, intimate-detail are private-by-default in every visible artifact, even when the source export contains them. The filter holds back rather than surfaces.
- `specs/presence-harmonization.md` — companion spec; same idea_id (`external-presence`); same privacy stance; same data-driven, never-hardcoded approach. Where presence-harmonization composes the presented shape of an existing presence, this spec brings new presences (external influences) into the graph in the first place.

## API Contract

### `POST /api/influences`

Resolve a URL into an external-influence asset, write the inspired-by edge with encounter metadata, attune for concept resonance.

**Request**
```json
{
  "url": "https://www.audible.com/pd/Becoming-Supernatural-Audiobook/B0791WT8K6",
  "contributor_id": "contributor:urs",
  "source": "audible",
  "encounter": {
    "when_encountered": "2024-09-12",
    "where_encountered": null,
    "surrounding_concepts": ["lc-attunement", "lc-coherence"]
  }
}
```

**Response 201**
```json
{
  "influence": {
    "id": "asset:9f2a...",
    "name": "Becoming Supernatural",
    "creation_kind": "book",
    "canonical_url": "https://audible.com/pd/becoming-supernatural-audiobook/b0791wt8k6",
    "image_url": "https://...",
    "private": false
  },
  "inspired_by_edge": {
    "id": "edge:...",
    "from_id": "contributor:urs",
    "to_id": "asset:9f2a...",
    "type": "inspired-by",
    "properties": {
      "when_encountered": "2024-09-12",
      "source": "audible",
      "surrounding_concepts": ["lc-attunement", "lc-coherence"]
    }
  },
  "resonance": [
    {"concept_id": "lc-attunement", "score": 0.42, "shared_tokens": ["frequency", "field", "coherence"]},
    {"concept_id": "lc-ceremony", "score": 0.18, "shared_tokens": ["practice", "embodiment"]}
  ],
  "summary": {"created": 1, "updated": 0, "skipped": 0, "blocked": 0, "resonance_edges_written": 2}
}
```

### `GET /api/influences/{slug}`

Return the influence + the contributors who encountered it (filtered by privacy) + concepts it resonates with.

```json
{
  "influence": { "id": "asset:9f2a...", "name": "Becoming Supernatural", "creation_kind": "book" },
  "encountered_by": [
    {"contributor_id": "contributor:urs", "when_encountered": "2024-09-12", "where_encountered": null}
  ],
  "resonates_with": [
    {"concept_id": "lc-attunement", "score": 0.42},
    {"concept_id": "lc-ceremony", "score": 0.18}
  ],
  "created_by": {"contributor_id": "contributor:joe-dispenza-...", "name": "Joe Dispenza"}
}
```

### `GET /api/concepts/{concept_id}/external-presences`

Return the spectrum of influences resonating with this concept, grouped by `creation_kind`. Feeds `CarriedExternalPresences` on `/vision/{id}`.

```json
{
  "concept_id": "lc-attunement",
  "groups": [
    {"creation_kind": "book", "family_color": "#8b6f47", "items": [
      {"id": "asset:9f2a...", "name": "Becoming Supernatural", "score": 0.42, "image_url": "..."}
    ]},
    {"creation_kind": "video", "family_color": "#3b6dac", "items": [...]},
    {"creation_kind": "gathering", "family_color": "#7a5fb8", "items": [...]}
  ]
}
```

### `PATCH /api/influences/{slug}/privacy`

Flip an influence between public and private (only the `encountered_by` contributor can call).

```json
{ "private": true }
```

## Data Model

```yaml
ExternalInfluence:                  # rendered as asset node, type=asset
  id: string                        # asset:{canonical_url_hash}
  type: "asset"
  name: string
  description: string | null
  canonical_url: string
  image_url: string | null
  creation_kind: "book" | "video" | "song" | "podcast" | "gathering" | "article" | "photo-encounter" | "correspondence"
  private: boolean                  # default false
  source: "audible" | "youtube" | "yt-music" | "calendar" | "photos" | "gmail" | "manual" | "takeout-import"
  ingested_at: timestamp

EncounterMetadata:                  # JSON properties on the inspired-by edge
  when_encountered: string          # ISO date
  where_encountered: string | null  # place node id
  surrounding_concepts: string[]    # concept ids
  source: string

InfluenceCategory:
  enum: ["book", "video", "song", "podcast", "gathering", "article", "photo-encounter", "correspondence"]

InfluenceSource:
  enum: ["audible", "youtube", "yt-music", "calendar", "photos", "gmail", "manual", "takeout-import"]

IngestSummary:
  created: int
  updated: int
  skipped: int
  blocked:                          # privacy filter rejections, with reasons
    - record_id: string
      reason: "privacy:partner" | "privacy:family" | "privacy:son" | "privacy:intimate_subject" | ...
  resonance_edges_written: int
  errors: { record_id, message }[]

PrivacyRule:                        # config/privacy_rules.json
  pattern: string                   # regex, case-insensitive
  domains: ["partner", "family", "son", "health", "scheduling", ...]
  default_decision: "block" | "mark-private" | "allow"
  applies_to_sources: string[]      # which ingest sources the rule binds to

FilterDecision:
  enum: ["allow", "mark-private", "block"]
```

## Files to Create / Modify

- `api/app/services/influence_ingest.py` — `ingest_one`, `ingest_bulk`, `IngestSummary`, post-ingest attune wiring.
- `api/app/services/influence_ingest/privacy_filter.py` — `filter_candidate`, rule loader, `FilterDecision`.
- `api/app/services/influence_ingest/sources/audible.py` — Goodreads CSV / Audible library export parser.
- `api/app/services/influence_ingest/sources/youtube_takeout.py` — Google Takeout `watch-history.json` parser.
- `api/app/services/influence_ingest/sources/yt_music_takeout.py` — Google Takeout YT Music history parser.
- `api/app/services/influence_ingest/sources/google_calendar_ics.py` — ICS feed parser → gathering assets.
- `api/app/services/influence_ingest/sources/google_photos_takeout.py` — Photos metadata JSON parser (place + date only).
- `api/app/services/influence_ingest/sources/gmail_takeout.py` — mbox header parser (sender + subject + date only).
- `api/app/services/influence_ingest/sources/manual_paste.py` — single-URL passthrough wrapping `inspired_by_service.resolve`.
- `api/app/routers/influences.py` — `POST /api/influences`, `GET /api/influences/{slug}`, `PATCH /api/influences/{slug}/privacy`, `GET /api/contributors/{id}/influences`, `GET /api/concepts/{id}/external-presences`.
- `api/app/models/influence.py` — Pydantic shapes.
- `api/db/migrations/NNNN_external_influences.sql` — index on `(creation_kind, private)`, `privacy_rules` table mirror.
- `config/privacy_rules.json` — data-driven rule set; never hardcoded names.
- `scripts/ingest_audible_csv.py`, `scripts/ingest_youtube_takeout.py`, `scripts/ingest_yt_music_takeout.py`, `scripts/ingest_google_calendar_ics.py`, `scripts/ingest_google_photos_takeout.py`, `scripts/ingest_gmail_takeout.py` — CLI wrappers.
- `web/components/concept/CarriedExternalPresences.tsx` — spectrum-row component on each concept page.
- `web/components/influence/InfluencePage.tsx` — influence detail page (resonating concepts + encountered-by list).
- `web/app/influences/[slug]/page.tsx` — `/influences/{slug}` route.
- `web/components/concept/StoryContent.tsx` (touch only) — slot the `CarriedExternalPresences` row into the existing concept page render.
- `api/tests/test_influence_ingest.py` — unit tests (one per source, privacy filter, idempotency, attune wiring, encounter metadata, private flag).
- `api/tests/test_flow_influences.py` — flow test for the new routes + concept aggregation.
- `api/tests/fixtures/goodreads_sample.csv`, `youtube_watch_history_sample.json`, `calendar_sample.ics`, `photos_metadata_sample.json`, `gmail_sample.mbox` — small fixtures.

## Acceptance Tests

- `api/tests/test_influence_ingest.py::test_manual_paste_creates_asset_and_inspired_by_edge` — single URL ingest writes one asset + one inspired-by edge with encounter metadata; attune runs.
- `api/tests/test_influence_ingest.py::test_audible_csv_idempotent_on_canonical_url` — two runs of the same CSV → second produces 0 created, N updated.
- `api/tests/test_influence_ingest.py::test_youtube_takeout_bulk` — sample watch-history.json → one asset per video, attune produces resonates-with edges, IngestSummary totals match.
- `api/tests/test_influence_ingest.py::test_calendar_ics_becomes_gathering` — one event → one asset of `creation_kind=gathering` with `at-place` + `when_encountered`.
- `api/tests/test_influence_ingest.py::test_photos_metadata_no_pixels_only_place_and_date` — Photos ingest never reads pixels; output is encounter metadata on existing or new place-encounter assets.
- `api/tests/test_influence_ingest.py::test_gmail_subject_filter_holds_intimate` — sample mbox containing a subject matching the partner/family pattern → the subject is blocked; `IngestSummary.blocked` records it with reason; no asset is written.
- `api/tests/test_influence_ingest.py::test_privacy_filter_blocks_partner_pattern_before_write` — synthetic record matching the partner pattern is blocked before any graph write; never appears in any node, edge, or query.
- `api/tests/test_influence_ingest.py::test_attune_runs_after_ingest` — newly-written asset has `resonates-with` edges to vision concepts after `ingest_one`.
- `api/tests/test_influence_ingest.py::test_encounter_metadata_on_edge` — edge properties carry `when_encountered`, `where_encountered`, `surrounding_concepts`, `source`; second ingest merges rather than overwrites `surrounding_concepts`.
- `api/tests/test_influence_ingest.py::test_private_flag_hides_from_public_query` — `private: true` asset is hidden from anonymous `GET /api/contributors/{id}/influences` and from `GET /api/concepts/{id}/external-presences`; the encountering contributor's authenticated view shows it.
- `api/tests/test_flow_influences.py::test_post_get_round_trip` — POST creates, GET returns the same shape with resonance.
- `api/tests/test_flow_influences.py::test_concept_external_presences_grouped_by_kind` — after ingesting a book + a video + a gathering, `GET /api/concepts/{id}/external-presences` returns three groups.

## Verification

```bash
cd api && python -m pytest tests/test_influence_ingest.py tests/test_flow_influences.py -q
python3 scripts/ingest_audible_csv.py --file api/tests/fixtures/goodreads_sample.csv --contributor-id contributor:urs --dry-run
python3 scripts/ingest_youtube_takeout.py --file api/tests/fixtures/youtube_watch_history_sample.json --contributor-id contributor:urs --dry-run
curl -s "http://localhost:8000/api/concepts/lc-attunement/external-presences" | jq '.groups[].creation_kind'
curl -s -X POST "http://localhost:8000/api/influences" -H 'content-type: application/json' \
  -d '{"url":"https://www.audible.com/pd/Becoming-Supernatural-Audiobook/B0791WT8K6","contributor_id":"contributor:urs","source":"audible","encounter":{"when_encountered":"2024-09-12"}}' | jq .resonance
```

## Out of Scope

- **Live OAuth sync.** Google OAuth 2.0 + Audible scrape (ongoing live mirror) are explicitly out of this iteration. A future spec layers OAuth-driven ingest on top of the same `ingest_one` / `ingest_bulk` entry points; the source plugins this spec creates already carry the per-source parsing logic.
- **Pixel-level image analysis from Google Photos.** Photos ingest reads metadata only. A future spec can add an opt-in image-tagging path; this one stays at place + date.
- **Gmail body content.** Headers only. A future spec governs whether body content can ever be ingested; this one says no.
- **New edge types.** All connectivity flows through `inspired-by`, `resonates-with`, `created-by`, `referenced-by`, `at-place`. If a future ingest pattern needs richer connectivity, that's a separate spec.
- **Encounter as its own node.** Encounter metadata stays on the inspired-by edge. A future spec could promote it to a node if encounters become first-class for analytics, but the graph stays clean for now.
- **Cross-contributor encounter aggregation** (e.g. "every contributor who encountered this book on the same day"). The data model supports this via the inspired-by edges; the read API and rendering are left to a follow-up spec.
- **Authentication-scoped editing rules** beyond the `private` flag's encountered-by check. A broader edit-auth spec governs the graph; this spec only carves out the privacy-flag behaviour the ingest path needs.

## Risks and Assumptions

- **Risk**: The privacy filter is necessarily conservative — it may hold back legitimate public influences whose subject happens to match an intimate pattern. Mitigation: blocked records appear in `IngestSummary.blocked` with the matched reason; the contributor can review and either refine the rule (data-driven) or override per-record. The filter errs on the side of holding back; presence over surfacing.
- **Risk**: Goodreads CSV is an Audible adjacency, not the canonical Audible export — some books in an Audible library don't appear in Goodreads. Mitigation: this spec ships the Goodreads path as the first buildable Audible-adjacent flow; a richer Audible parser is a future enhancement once OAuth sync is in scope.
- **Risk**: YouTube Takeout exports are large (tens of thousands of entries for long-time users); naive ingest could overwhelm the resonance attune step. Mitigation: bulk ingest batches attune calls and reports total resonance edges written; if performance becomes a concern, attune can be deferred to an off-line sweep without changing the API contract.
- **Risk**: Google Photos location data carries privacy weight even without pixels (a home address pattern across many photos exposes residence). Mitigation: the privacy filter applies to Photos metadata too; residence-pattern detection (multiple encounters at the same private location) can flow `mark-private` rather than `allow`.
- **Assumption**: `inspired_by_service.ensure_identity()` handles the `asset` node type as well as the contributor types it was originally written for. If the asset path needs additional defaults (e.g. `claimable: true` already in `_ensure_creation_nodes`), this spec extends `ensure_identity` rather than forking.
- **Assumption**: The vision concepts already in the graph carry enough story_content for `resonance_service.attune` to produce meaningful overlap with influence keywords. Verified for the existing lc-* concepts; sparse concepts will produce sparse resonance, which is the right behaviour.
