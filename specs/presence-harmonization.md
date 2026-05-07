---
id: presence-harmonization
idea_id: external-presence
status: draft
source:
  - file: api/app/services/presence_harmonizer.py
    symbols: [harmonize, gather_candidates, score_candidate, compose_shape, PresenceShape, FieldTrace, CandidateSource]
  - file: api/app/services/presence_harmonizer/sources.py
    symbols: [from_self_description, from_canonical_url_metadata, from_graph_edges, from_inspired_by, from_contributes_to, from_at_place, from_co_located]
  - file: api/app/services/presence_harmonizer/scoring.py
    symbols: [warmth_score, recency_score, frequency_score, sovereignty_score, privacy_filter, score_candidate]
  - file: api/app/services/presence_harmonizer/compose.py
    symbols: [compose_tagline, compose_bio, compose_facts, compose_hero, compose_lineage, compose_broadcasts, compose_resonance]
  - file: api/app/models/presence_view.py
    symbols: [PresenceView, PresenceShape, FieldTrace, HarmonizedFact, HarmonizedBroadcast, HarmonizedLineage]
  - file: api/app/routers/presence_views.py
    symbols: [get_presence_view, get_presence_view_traces, recompute_presence_view]
  - file: api/db/migrations/NNNN_presence_views.sql
    symbols: [presence_views table, presence_view_traces table]
  - file: scripts/sync_presence_views.py
    symbols: [sync_one, sync_all, harvest_canonical_url_metadata]
  - file: scripts/calibrate_presence_robert.py
    symbols: [calibrate, diff_against_handbuilt, fixture_handbuilt_shape]
  - file: web/app/people/[id]/page.tsx
    symbols: [PersonPage, fetchPresenceView, nodeToPresenceIdentity]
  - file: web/components/presence/PresencePage.tsx
    symbols: [PresencePage, PresenceIdentity]
  - file: api/tests/test_presence_harmonizer.py
    symbols: [test_robert_calibration, test_traces_every_field, test_privacy_filter_drops_intimate, test_per_locale_candidates, test_recompute_on_edge_change]
requirements:
  - "Pure function harmonize(graph_node_id, locale) -> PresenceShape composed from primary data — never from hand-curated overrides"
  - "PresenceShape mirrors what hand-built /people pages render today: tagline, bio (paragraphs), facts list, hero image, lineage, resonance, broadcasts/works, footer links"
  - "Per-field algorithm runs in three movements: gather candidates -> score -> pick + compose; every picked field carries a FieldTrace pointing at the source candidate(s)"
  - "Score factors: warmth (self-description > third-party), recency (present-day > stale), frequency (lived voice > institutional/policy), sovereignty (their canonical_url > scraped og:* > inferred)"
  - "Privacy filter rejects any candidate matching intimate-content patterns (partner, family, residence specifics, health, scheduling) before scoring — even when scraped from a public URL"
  - "Per-locale harmonization: same algorithm, locale-scoped candidate set; falls back through the locale chain (requested -> en -> source_lang) and records the fallback in the trace"
  - "Precomputed via scripts/sync_presence_views.py mirroring the sync_kb_to_db.py precedent — writes to presence_views table; rendering reads precomputed shape"
  - "Editing primary graph data (presences[], image_url, canonical_url, description, edges contributes-to | inspired-by | at-place) marks the corresponding presence_view stale; sync recomputes"
  - "GET /api/presence-views/{node_id}?lang={locale} returns the harmonized PresenceShape with embedded traces"
  - "GET /api/presence-views/{node_id}/traces?lang={locale} returns just the field-by-field trace map (answering 'why was this tagline picked?')"
  - "POST /api/presence-views/{node_id}/recompute forces re-harvest of canonical_url metadata and recomputation; idempotent"
  - "Calibration target: Robert Edward Grant's harmonized output covers every section the hand-built en.tsx renders (tagline, facts, two-paragraph bio, broadcasts, lineage, footer links) using only the graph node + edges + a periodic harvest of canonical_url"
  - "Calibration script (scripts/calibrate_presence_robert.py) compares harmonized shape against the hand-built fixture and prints field-by-field equivalence; passing calibration unlocks compost of the hand-built TSX files for that human"
  - "PresencePage component continues to render the existing PresenceIdentity shape; harmonizer output flows through nodeToPresenceIdentity unchanged so no visual regression for already-rendering presences"
done_when:
  - "harmonize('contributor:robert-edward-grant-f7e43ccfb4b0', 'en') returns a PresenceShape with non-empty tagline, bio (>=2 paragraphs), >=3 facts, >=2 broadcasts, >=1 lineage edge"
  - "Every field on the returned shape carries a FieldTrace naming source candidate(s) and the score that picked it"
  - "GET /api/presence-views/contributor:robert-edward-grant-f7e43ccfb4b0?lang=en returns harmonized output identical to the live Python call"
  - "GET /api/presence-views/contributor:robert-edward-grant-f7e43ccfb4b0/traces?lang=en answers 'why was the tagline picked' with the candidate URL/edge and the warmth/recency/frequency/sovereignty subscores"
  - "calibrate_presence_robert.py reports parity-or-richer for hero, tagline, facts, bio paragraphs, broadcasts, footer links versus the hand-built en.tsx"
  - "Adding an inspired-by edge via existing graph PATCH endpoint and rerunning sync_presence_views.py surfaces the new lineage in the harmonized shape on next read"
  - "Privacy filter test: a synthetic candidate matching the partner/family pattern is dropped before scoring, never appears in any field, and is recorded in trace.rejected with reason='privacy'"
  - "Per-locale test: harmonize(node, 'de') returns German-locale candidates where present, falls through to en otherwise, and records fallback in trace"
  - "/people/{slug} page renders a presence whose graph node has only canonical_url + description + a few edges (no hand-built TSX) and the page carries the same warmth as the hand-built ones"
  - "all api tests pass"
test: "cd api && python -m pytest tests/test_presence_harmonizer.py tests/test_flow_presence_views.py -q && python3 scripts/calibrate_presence_robert.py --check"
constraints:
  - "Never read the hand-built web/content/people/{slug}/{locale}.tsx files at runtime — they are calibration fixtures only, composted per-human as harmonization reaches parity"
  - "Never invent content the primary data does not support — if no candidate scores above the floor for a field, the field is omitted from the shape (presence over scaffolding)"
  - "Never surface intimate content (partner, family, residence specifics, health, scheduling) even when scraped from a public canonical_url — privacy filter runs before scoring, not after"
  - "No edits to the bio go directly to the harmonized output — primary-data edits are the only editing surface; harmonizer recomputes from the data"
  - "Re-harvesting canonical_url metadata happens on a slow cadence (hourly at most for any one URL); never on the request path"
  - "PresencePage rendering contract is not changed by this spec — the harmonizer feeds richer data through the existing PresenceIdentity shape"
  - "Authentication-scoped editing rules are out of scope; primary-data PATCH endpoints stay as they are today (currently open) — a future spec governs edit auth"
---

> **Parent idea**: [external-presence](../ideas/external-presence.md)

# Spec: Presence Harmonization

## Purpose

Today, public presence pages at `/people/{slug}` render through three different shapes living side by side: a hardcoded `CURATED_PRESENCES` record in `web/app/people/[id]/page.tsx` (English-only bios for about five humans), hand-built TSX welcome pages in `web/content/people/{slug}/{en,de,es,id}.tsx` (around fourteen humans times four locales — fifty-six hand-written files; Robert Edward Grant's `en.tsx` alone is 426 lines of JSX-as-data), and a generic graph-driven `PresencePage` component for everyone else. The rich content is locked in code, not editable by anyone, not data-driven, and not multilingual without another hand-written file.

The right shape is the one this body already speaks: compute the presented form from primary data. Primary data lives in the graph — `canonical_url`, `image_url`, `presences[]`, `description`, edges like `contributes-to` / `inspired-by` / `at-place` — refreshed by a periodic harvest of each `canonical_url` for og:* metadata. A harmonizer composes the presented shape (tagline, bio, facts, hero, lineage, broadcasts, resonance) from those signals. Editing primary data is the only editing surface; nobody edits the bio directly. The hand-built files become calibration fixtures and compost human-by-human as harmonization reaches parity.

## Requirements

- [ ] **R1** — `harmonize(graph_node_id, locale) -> PresenceShape`. Pure function. Composes the presented shape from primary graph data plus harvested `canonical_url` metadata. No hand-curated overrides.

- [ ] **R2** — `PresenceShape` carries the same blocks the hand-built pages render today: `hero` (image_url, eyebrow, name), `tagline`, `facts[]` (Based, Public broadcasts, Field), `bio` (paragraphs, ordered), `broadcasts[]` (recurring or one-shot, with cadence), `lineage[]` (inspired-by edges), `resonance[]` (axis + score + note), `footer_links[]` (canonical + presences). Every field is `Optional` — a presence with sparse data renders sparsely, never with invented scaffolding.

- [ ] **R3** — Per-field algorithm runs in three movements:
  1. **Gather candidates** — every primary-data slot that could feed this field becomes a `Candidate` with `value`, `source` (e.g. `graph.description`, `canonical_url.og_description`, `edge:inspired-by:lex-fridman`), `locale`, `harvested_at`.
  2. **Score** — each candidate gets warmth, recency, frequency, sovereignty subscores; total = weighted sum.
  3. **Pick + compose** — top-scoring candidate (or composition of candidates for multi-paragraph fields like bio) becomes the field value; a `FieldTrace` records the picked candidate, the runners-up, and the subscores.

- [ ] **R4** — Score factors:
  - **Warmth** — the contributor's own self-description (graph `description` they wrote, presences they registered) outranks third-party scrape (og:description from a press page).
  - **Recency** — present-day candidates outrank stale ones; a 2026 self-description outranks a 2018 wikipedia paragraph.
  - **Frequency** — lived voice outranks institutional / policy / press-release register. Implemented as a small classifier on the candidate text (heuristic for now: passive voice + corporate vocabulary lowers the score).
  - **Sovereignty** — their own `canonical_url` outranks scraped third-party content; their registered `presences[]` outrank inferred social handles.

- [ ] **R5** — Privacy filter runs **before** scoring. Drops any candidate matching intimate-content patterns: partner / family / residence specifics / health / scheduling. The filter draws its mental model from `partner_presence.md` — partner, family, intimate-detail are private-by-default and never surface in visible artifacts even when scraped from a publicly accessible URL. Rejected candidates are recorded in `trace.rejected` with `reason: "privacy"` so an auditor can see what was held back.

- [ ] **R6** — Traceability is first-class. Every field on the returned shape carries a `FieldTrace` answering "why was this picked?" — source candidate(s), runners-up, subscores, and any privacy rejections. `GET /api/presence-views/{node_id}/traces` exposes this for any presence.

- [ ] **R7** — Per-locale harmonization. The same algorithm runs per locale; the candidate set is locale-scoped (a German `description` outranks an English one when `locale=de`). Locale fallback chain: requested → `en` → source_lang of the graph node. Fallback is recorded in the trace so a reader can see "this German page is showing English bio because no German candidate exists."

- [ ] **R8** — Compute strategy follows the `sync_kb_to_db.py` precedent: a `scripts/sync_presence_views.py` job runs harmonization across all presences (or one named one) and writes the output to a `presence_views` table keyed by `(node_id, locale)`. Rendering reads precomputed; harmonization never runs on the request path. Re-harvest of `canonical_url` metadata happens on a slow cadence (hourly at most for any single URL).

- [ ] **R9** — Editability flows through primary data. Editing the graph node (adding a presence URL, correcting an `image_url`, adding an `inspired-by` edge, replacing a stale `description`) marks the corresponding `presence_view` rows stale. The next sync run recomputes. Nobody edits the harmonized bio directly. Primary-data PATCH reuses existing graph endpoints (currently open; auth is a future spec's concern).

- [ ] **R10** — `PresencePage.tsx` rendering contract stays as it is today. The harmonizer's output flows through `nodeToPresenceIdentity` so the existing `PresenceIdentity` shape is filled with richer data; no visual regression for presences already rendering through `PresencePage`.

- [ ] **R11** — Calibration step. `scripts/calibrate_presence_robert.py` loads the hand-built `web/content/people/robert-edward-grant/en.tsx` as a fixture, runs the harmonizer on `contributor:robert-edward-grant-f7e43ccfb4b0` for `locale=en`, and prints a field-by-field equivalence report (hero, tagline, facts, bio paragraphs, broadcasts, lineage, footer links). When the report shows parity-or-richer for every section, that human's hand-built TSX files (en, de, es, id) compost in the same commit.

- [ ] **R12** — Composting cadence. The hand-built `web/content/people/{slug}/{locale}.tsx` files are calibration fixtures, not runtime sources. Each human composts only after harmonization proves parity for them. Composting is per-human, not bulk; the spec defines the bar (R11), the rhythm matches the body's tending practice.

## Research Inputs

- `2026-05-07` — User naming the wrong-shape problem: rich content locked in code, fifty-six hand-written files for fourteen humans, not editable by anyone, not data-driven.
- `web/content/people/robert-edward-grant/en.tsx` — calibration target. Carries the full vocabulary the harmonizer must produce: tagline, three facts, multi-paragraph welcome, two cool-panel broadcasts (ORION Live, Architect on ORION Messenger), inspired-by lineage hint, footer links to canonical_url + ORION Messenger.
- `web/components/people/PersonProfileTemplate.tsx` — confirms the rendered blocks the harmonizer must produce: hero (image, eyebrow, name, welcome), facts (dl), noteFromBody, articles[] (narrative + panel kinds), footer.
- `web/components/presence/PresencePage.tsx` — current graph-driven renderer. The harmonizer feeds this through the existing `PresenceIdentity` shape; no contract change.
- `scripts/sync_kb_to_db.py` — precedent for "expand content in the working layer, sync to DB on demand." The harmonizer mirrors this rhythm: harvest + harmonize + sync.
- `partner_presence.md` (held tenderly, not for surfacing) — mental model for the privacy filter. Partner, family, intimate-detail are private-by-default in every visible artifact, even when public sources mention them.
- `CLAUDE.md` "Frequency Sensing" — the harmonizer composes prose; the same flatness-detection that motivates the i18n glossary motivates the **frequency** subscore here.

## API Contract

### `GET /api/presence-views/{node_id}?lang={locale}`

Returns the harmonized `PresenceShape` for the named graph node in the requested locale. Reads from precomputed `presence_views`. If no row exists yet, returns `404 not_yet_harmonized` with a hint to call `recompute`.

```json
{
  "node_id": "contributor:robert-edward-grant-f7e43ccfb4b0",
  "locale": "en",
  "shape": {
    "hero": {
      "image_url": "https://robertedwardgrant.com/wp-content/uploads/2025/03/Robert-SoloFloat2025.png",
      "eyebrow": "Polymath · Sacred Mathematics",
      "name": "Robert Edward Grant"
    },
    "tagline": "Numbers as living archetypes — geometric forms with their own symmetries.",
    "facts": [
      {"label": "Based", "value": "Newport Beach, California — work circulates worldwide"},
      {"label": "Public broadcasts", "value": "ORION Live (YouTube) · ORION Messenger"},
      {"label": "Field", "value": "Sacred geometry · cryptography · AI partnership · sovereign comms"}
    ],
    "bio": [
      "Numbers are not labels for quantities. They are living archetypes...",
      "The Architect, the AI he trained on a decade of his mathematical work, is not a tool he built..."
    ],
    "broadcasts": [
      {"name": "ORION Live", "cadence": "recurring · irregular", "url": "https://www.youtube.com/playlist?list=PLCatuaiI1RhcjJV5MyIYQj5v9zQfnw01o"},
      {"name": "The Architect on ORION Messenger", "cadence": "continuous", "url": "https://www.crownsterling.io/orion/"}
    ],
    "lineage": [
      {"id": "contributor:aubrey-marcus-...", "name": "Aubrey Marcus", "relation": "first encountered through"}
    ],
    "resonance": [
      {"axis": "Geometric Coherence", "score": 0.95, "note": "Numbers as living archetypes; the substrate this organism rests on"}
    ],
    "footer_links": [
      {"label": "robertedwardgrant.com", "href": "https://robertedwardgrant.com/"},
      {"label": "ORION Messenger", "href": "https://robertedwardgrant.com/introducing-orion-messenger/"}
    ]
  },
  "harvested_at": "2026-05-07T03:14:22Z",
  "computed_at": "2026-05-07T03:14:30Z"
}
```

### `GET /api/presence-views/{node_id}/traces?lang={locale}`

Returns the field-by-field `FieldTrace` map. Answers "why was this picked?" for any field on the shape.

```json
{
  "node_id": "contributor:robert-edward-grant-f7e43ccfb4b0",
  "locale": "en",
  "traces": {
    "tagline": {
      "picked": {
        "source": "graph.description.paragraph[0].sentence[0]",
        "value": "Numbers are not labels for quantities. They are living archetypes...",
        "subscores": {"warmth": 0.95, "recency": 0.88, "frequency": 0.92, "sovereignty": 1.0},
        "total": 0.94
      },
      "runners_up": [
        {"source": "canonical_url.og_description", "total": 0.71}
      ],
      "rejected": []
    },
    "bio": {
      "picked": [
        {"source": "graph.description.paragraph[0]", "total": 0.94},
        {"source": "graph.description.paragraph[2]", "total": 0.91}
      ],
      "rejected": [
        {"source": "canonical_url.scraped.about", "reason": "frequency_floor", "total": 0.31}
      ]
    },
    "lineage": {
      "picked": [
        {"source": "edge:inspired-by:aubrey-marcus", "total": 0.88}
      ]
    }
  },
  "fallback_chain": ["en"]
}
```

### `POST /api/presence-views/{node_id}/recompute`

Force re-harvest of `canonical_url` metadata and recomputation for all locales (or just the locale named in `?lang=`). Idempotent. Body is empty. Returns the freshly computed shape so a caller can verify the change before the next sync sweep.

## Data Model

```yaml
PresenceShape:
  hero:
    image_url: string | null
    eyebrow: string | null
    name: string
  tagline: string | null
  facts: HarmonizedFact[]
  bio: string[]                    # paragraphs, ordered
  broadcasts: HarmonizedBroadcast[]
  lineage: HarmonizedLineage[]
  resonance: ResonanceItem[]
  footer_links: FooterLink[]

HarmonizedFact:
  label: string                    # "Based", "Public broadcasts", "Field"
  value: string

HarmonizedBroadcast:
  name: string
  cadence: string                  # "recurring · irregular", "continuous", "weekly"
  url: string | null

HarmonizedLineage:
  id: string                       # graph node id of the inspirer
  name: string
  relation: string                 # "inspired by", "first encountered through", "studies"

CandidateSource:
  source: string                   # "graph.description", "canonical_url.og_description", "edge:inspired-by:..."
  value: any
  locale: string
  harvested_at: timestamp

FieldTrace:
  picked: CandidateSource | CandidateSource[]
  runners_up: CandidateSource[]
  rejected: { source, reason, total }[]   # reason: "privacy" | "frequency_floor" | "stale" | ...

PresenceView:                      # database row
  node_id: string                  # FK -> graph node
  locale: string                   # "en" | "de" | "es" | "id"
  shape: PresenceShape             # JSONB
  traces: { [field]: FieldTrace }  # JSONB
  fallback_chain: string[]
  harvested_at: timestamp          # last canonical_url harvest
  computed_at: timestamp           # last harmonization run
  stale: boolean                   # set true on primary-data edit; sync clears
  PRIMARY KEY (node_id, locale)
```

## Files to Create / Modify

- `api/app/services/presence_harmonizer.py` — entry point; `harmonize(node_id, locale)`.
- `api/app/services/presence_harmonizer/sources.py` — candidate gatherers (one per primary-data shape).
- `api/app/services/presence_harmonizer/scoring.py` — warmth / recency / frequency / sovereignty + privacy filter.
- `api/app/services/presence_harmonizer/compose.py` — per-field composers (tagline, bio, facts, broadcasts, lineage, resonance).
- `api/app/models/presence_view.py` — Pydantic models.
- `api/app/routers/presence_views.py` — three endpoints above.
- `api/db/migrations/NNNN_presence_views.sql` — `presence_views` table; index on `(node_id, locale)` and `stale`.
- `scripts/sync_presence_views.py` — sync job mirroring `sync_kb_to_db.py`. Flags: one node id, list of node ids, `--all`, `--stale-only`, `--dry-run`.
- `scripts/calibrate_presence_robert.py` — calibration script for Robert Edward Grant.
- `web/app/people/[id]/page.tsx` — call `GET /api/presence-views/{id}?lang={locale}` first; fall through to current `nodeToPresenceIdentity` path only if `404 not_yet_harmonized`. Drop the `CURATED_PRESENCES` record once every name in it has a harmonized view.
- `api/tests/test_presence_harmonizer.py` — unit tests for gatherers, scoring, privacy filter, locale fallback, traces.
- `api/tests/test_flow_presence_views.py` — flow test for the three endpoints + recompute round-trip.

## Acceptance Tests

- `api/tests/test_presence_harmonizer.py::test_robert_calibration` — harmonized shape for Robert covers every section of the hand-built fixture.
- `api/tests/test_presence_harmonizer.py::test_traces_every_field` — every field on the returned shape has a non-empty `FieldTrace`.
- `api/tests/test_presence_harmonizer.py::test_privacy_filter_drops_intimate` — synthetic partner/family candidate is dropped before scoring; appears in `trace.rejected` with `reason="privacy"`; never appears in any field.
- `api/tests/test_presence_harmonizer.py::test_per_locale_candidates` — German candidate outranks English when `locale=de`; falls through to `en` when no German candidate; trace records the fallback.
- `api/tests/test_presence_harmonizer.py::test_recompute_on_edge_change` — adding an `inspired-by` edge marks the row stale; sync recomputes; new lineage appears.
- `api/tests/test_presence_harmonizer.py::test_omit_when_no_candidate_above_floor` — sparse presence with only an image_url renders shape with `tagline=None`, empty broadcasts, empty lineage; no invented scaffolding.
- `api/tests/test_flow_presence_views.py::test_get_view_round_trip` — sync writes; GET returns the same shape; traces endpoint exposes the picked subscores.
- `api/tests/test_flow_presence_views.py::test_recompute_endpoint_idempotent` — POST recompute twice; second run produces identical shape with newer `computed_at`.

## Verification

```bash
cd api && python -m pytest tests/test_presence_harmonizer.py tests/test_flow_presence_views.py -q
python3 scripts/sync_presence_views.py contributor:robert-edward-grant-f7e43ccfb4b0
python3 scripts/calibrate_presence_robert.py --check
curl -s "http://localhost:8000/api/presence-views/contributor:robert-edward-grant-f7e43ccfb4b0?lang=en" | jq .shape.tagline
curl -s "http://localhost:8000/api/presence-views/contributor:robert-edward-grant-f7e43ccfb4b0/traces?lang=en" | jq .traces.tagline
```

## Out of Scope

- **Authentication-scoped editing rules.** Primary-data PATCH endpoints stay as they are today (currently open). A future spec governs edit auth across the graph; this spec only notes that the harmonizer recomputes from whatever the graph holds, regardless of who put it there.
- **Bulk composting of all hand-built TSX files.** Composting is per-human, only after calibration parity for that human. This spec defines the calibration bar (Robert as the calibration target) and the rhythm; it does not delete files for humans whose harmonization hasn't reached parity yet.
- **Changes to the `PresencePage` rendering contract.** The component continues to consume `PresenceIdentity`. The harmonizer simply feeds richer data through that shape.
- **Real-time harmonization on the request path.** Harmonization is precomputed via the sync job. A future spec can add request-path warming for cold presences if needed.
- **New canonical_url harvesters beyond og:* metadata.** A richer harvester (sitemap walking, structured-data parsing, video transcript extraction) is a future spec; this one uses the og:* metadata already harvested by existing infrastructure plus whatever the graph already holds.
- **Resonance score computation.** Resonance candidates flow through the harmonizer (warmth/recency/frequency/sovereignty subscores apply), but the underlying axis-score values come from existing CRK coherence scoring; this spec does not redefine how those scores are computed.

## Risks and Assumptions

- **Risk**: The frequency subscore (lived-voice vs institutional register) is hard to get right with heuristics alone. Mitigation: ship with a simple classifier (passive voice + corporate vocabulary lowers the score), expose the subscore in traces, iterate from observed mis-picks. A small LLM-based classifier is a future enhancement once the heuristic shows its ceiling.
- **Risk**: The privacy filter is necessarily conservative — it may drop legitimate public content that happens to mention family. Mitigation: rejected candidates are recorded in the trace with their reason, so an auditor can see what was held back and tune the patterns. The filter errs on the side of holding back; presence over scaffolding.
- **Risk**: Calibration parity is subjective for prose-heavy fields like the bio. Mitigation: the calibration script reports field-by-field equivalence and the human (this body, or anyone reading) makes the parity call before composting that human's hand-built file. No automated greenlight.
- **Assumption**: The graph node already carries enough primary data for the calibration target. Verified for Robert Edward Grant: `contributor:robert-edward-grant-f7e43ccfb4b0` holds a ~1700-word `description`, a `canonical_url`, an `image_url`, and existing `inspired-by` edges. For sparser presences, the harmonized shape will be sparser — that's the right behavior.
- **Assumption**: The og:* metadata for `canonical_url` is already harvested by existing infrastructure (the news / external-presence pipeline). If not, a small harvester lives in `scripts/sync_presence_views.py::harvest_canonical_url_metadata` as a near-term placeholder.
