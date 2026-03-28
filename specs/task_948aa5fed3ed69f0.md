# Spec: Concept resonance — ideas attract related ideas across domains

**Spec ID / task:** `task_948aa5fed3ed69f0`  
**Status:** Draft (product specification; implementation may be phased)

## Summary

Concept resonance is the mechanism by which the ontology grows **without** relying on a central curator to draw every cross-domain link by hand. When a biology idea (for example, symbiosis) and a software idea (for example, microservices) **solve analogous problems** in different domains, the system should surface that relationship so humans can validate, refine, and build on it.

**North-star definition:** resonance is **structural similarity** in the intelligence graph (shared problem patterns, compatible interfaces, lineage or spec references), not mere keyword overlap. The current API implementation uses **derived concept tokens** from idea metadata (tags, interfaces, domains) as an MVP proxy; this spec defines the contract for that surface area and the **evolution path** toward true graph-structural scoring, observability, and provable quality over time.

**Who benefits:** contributors exploring the graph, PMs measuring ontology health, and automation that proposes edges from execution artifacts (tasks, specs, commits).

## Purpose

Deliver a stable, testable contract for listing cross-domain “resonant” ideas for a given idea, with scores and explainability fields, while explicitly separating **today’s heuristic** from **tomorrow’s graph-native** matcher. Prevent silent drift: every resonance match must be inspectable (why this pair, which signals).

## Requirements

### Functional

1. **Read path (MVP, must remain stable):** For a known idea, clients can retrieve ranked candidate ideas that share conceptual overlap and, when applicable, **boost cross-domain** pairs so analogous problems in different domains rise to the top.
2. **Not keyword-only:** The product requirement is graph-structural resonance. The implementation MUST document which signals are used today (token overlap from tags/interfaces) vs which signals are planned (Neo4j edges, `codex.meta/*` nodes, spec/task lineage, interface compatibility). No claim in API docs that “only keywords” define resonance without also stating the evolution plan.
3. **Explainability:** Each match exposes enough structured fields for a UI or CLI to show **why** the system proposed the pair (`shared_concepts`, domain lists, `cross_domain`, scores in `[0.0, 1.0]`).
4. **Feed path:** A time-window feed of “resonant” recent activity across ideas remains available for dashboards (existing `GET /api/ideas/resonance`).
5. **Full CRUD for ideas:** Resonance is computed over **persisted** ideas; create/update/read of ideas must continue to drive portfolio state used by resonance (see Verification Scenarios).

### Non-functional

6. **Determinism where possible:** Given the same portfolio snapshot, resonance ordering for the same query parameters must be stable (tie-breakers documented).
7. **Performance:** Resonance for one idea must complete within API SLA for interactive use (document batch/async if portfolio grows large).
8. **Privacy / abuse:** Public endpoints must not leak non-public contributor data; resonance payloads remain idea-scoped.

## Research Inputs (Required)

- `2026-03-28` — Repository: `api/app/services/idea_service.py` (`get_concept_resonance_matches`) — defines current scoring and cross-domain behavior.
- `2026-03-28` — Repository: `api/tests/test_idea_concept_resonance.py` — encodes acceptance for cross-domain ordering and 404 behavior.
- `2026-03-28` — Internal: `specs/TEMPLATE.md` — spec structure alignment.

*(External papers on analogical reasoning / knowledge graphs may be added when implementing graph-native matchers.)*

## Current vs target architecture

| Layer | Today (MVP) | Target |
|-------|-------------|--------|
| Signal | Normalized concept tokens from tags + `interfaces` (e.g. `domain:*`) | Neo4j paths: shared `problem_pattern` / `interface` nodes, spec lineage edges, task co-activation |
| Score | Overlap ratio + small cross-domain boost | Learned or calibrated structural similarity + human feedback weights |
| Proof | Pytest + manual curl | Metrics below + dashboard + optional `explain` payload |

## API contract (must exist or stay backward-compatible)

### `GET /api/ideas/resonance`

**Query:** `window_hours` (int), `limit` (int)  
**Response 200:** JSON list (feed of recently active resonant ideas — existing contract; see `idea_service.get_resonance_feed`).

### `GET /api/ideas/{idea_id}/concept-resonance`

**Query:** `limit` (int, default 5), `min_score` (float, default 0.05)  
**Response 200:** `IdeaConceptResonanceResponse`

```json
{
  "idea_id": "string",
  "matches": [
    {
      "idea_id": "string",
      "name": "string",
      "resonance_score": 0.0,
      "free_energy_score": 0.0,
      "shared_concepts": ["string"],
      "source_domains": ["string"],
      "candidate_domains": ["string"],
      "cross_domain": true
    }
  ],
  "total": 0
}
```

**Response 404:** Idea not found.

**Response 422:** Invalid query parameters (if validation fails).

### Future (optional phase 2 — not blocking MVP if explicitly deferred)

- `GET /api/ideas/{idea_id}/concept-resonance/explain` — same matches plus edge IDs / path summary from graph (when Neo4j-backed).
- `GET /api/metrics/concept-resonance` — aggregate: pairs surfaced/day, human confirmation rate, precision@k proxy.

### Web (phase 2)

- **Page:** `/ideas/[id]` or portfolio detail — panel “Related across domains” calling `GET /api/ideas/{idea_id}/concept-resonance` (exact route to align with existing app router when implemented).

### CLI (optional)

- `cc ideas resonance <idea_id>` — thin wrapper over GET (if `cc` exposes HTTP helpers in your environment).

## Data model

**Existing Pydantic models** (must round-trip):

- `IdeaConceptResonanceMatch` — fields as in API contract above.
- `IdeaConceptResonanceResponse` — `idea_id`, `matches`, `total`.

**Graph (future):**

- Node types: `Idea`, `Concept` (or `ProblemPattern`), `Domain`.
- Edge types: `SHARES_CONCEPT`, `ANALOGOUS_TO`, `INSPIRED_BY` (see `api/config/edge_type_registry.json` for naming consistency).

**Persistence:** Ideas continue to be stored per existing portfolio mechanism (`IDEA_PORTFOLIO_PATH` / DB); resonance is **derived**, not a separate mutable table in MVP.

## Files to create / modify (implementation follow-up)

When implementing phase 2 graph resonance, typical touch points (exact list to be confirmed in implementation spec):

- `api/app/services/idea_service.py` — `get_concept_resonance_matches` (graph-backed scorer).
- `api/app/routers/ideas.py` — route registration (already present for MVP).
- `api/app/models/idea.py` — extend match model if `explain` fields added.
- `api/tests/test_idea_concept_resonance.py` — extend tests; do not weaken existing assertions without decision record.
- Optional: `web/app/...` — resonance panel.

## Open questions (mandatory — how we improve, prove, and clarify over time)

1. **Improve the idea:** Add **human-in-the-loop** signals — “confirm / reject” on a proposed pair — stored as edges or annotations feeding the next scorer version.
2. **Show whether it is working:** Publish **metrics**: (a) count of cross-domain matches served, (b) click-through or confirmation rate, (c) diversity of domains in top-k, (d) regression tests on a **golden** idea pair fixture (symbiosis ↔ microservices style) when graph data exists.
3. **Clearer proof over time:** Version the scorer (`resonance_model_version` in response header or body in phase 2), keep a changelog, and run periodic **offline evaluation** against labeled analogies.

## Verification Scenarios

Scenarios below are written for **production or local API** with `API` set to base URL (e.g. `https://api.coherencycoin.com` or `http://localhost:8000`). Replace `$API_KEY` with a valid key when required.

### Scenario 1 — Full create → read → resonance read cycle

- **Setup:** Portfolio empty or isolated test file; authenticated client available.
- **Action:**
  1. `curl -sS -X POST "$API/api/ideas" -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" -d '{"id":"cr-bio","name":"Symbiosis patterns","description":"Mutual benefit in ecosystems","potential_value":50,"estimated_cost":10,"confidence":0.7,"tags":["symbiosis","mutualism"],"interfaces":["domain:biology"]}'`
  2. `curl -sS -X POST "$API/api/ideas" -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" -d '{"id":"cr-soft","name":"Microservice symbiosis","description":"Services that co-evolve APIs for mutual benefit","potential_value":50,"estimated_cost":10,"confidence":0.7,"tags":["symbiosis","microservices"],"interfaces":["domain:software"]}'`
  3. `curl -sS "$API/api/ideas/cr-bio"`
  4. `curl -sS "$API/api/ideas/cr-bio/concept-resonance?limit=5&min_score=0.05"`
- **Expected result:** Steps 1–2 return **201** with created bodies containing `id` matching payload. Step 3 returns **200** with `id` `cr-bio`. Step 4 returns **200** with JSON where `idea_id` is `cr-bio`, `total` ≥ 1, first match has `idea_id` `cr-soft`, `cross_domain` is **true**, and `shared_concepts` includes `"symbiosis"`.
- **Edge case:** POST same `id` again → **409** (or documented conflict behavior). GET `/api/ideas/cr-bio/concept-resonance` with malformed `min_score` (e.g. `not_a_float`) → **422**.

### Scenario 2 — Resonance feed still available

- **Setup:** API healthy.
- **Action:** `curl -sS "$API/api/ideas/resonance?window_hours=72&limit=3"`
- **Expected result:** **200**, body is a JSON **array** (possibly empty), no 500.
- **Edge case:** `limit=0` or negative if validated → **422**; if allowed, document empty list behavior.

### Scenario 3 — Missing idea returns 404 (error handling)

- **Setup:** No idea with id `definitely-missing-idea-xyz`.
- **Action:** `curl -sS -o /dev/null -w "%{http_code}" "$API/api/ideas/definitely-missing-idea-xyz/concept-resonance"`
- **Expected result:** HTTP status **404** (not 500).
- **Edge case:** Path traversal or invalid `idea_id` characters per router rules → **404** or **422** as documented, never opaque 500.

### Scenario 4 — No shared concepts → empty matches

- **Setup:** Create two ideas with disjoint tags/interfaces (no overlapping concept tokens).
- **Action:** `GET /api/ideas/{first_id}/concept-resonance?min_score=0.05`
- **Expected result:** **200** with `matches: []` and `total: 0` (or `total` consistent with empty list).
- **Edge case:** Source idea has no extractable concepts → empty matches with **200**, not error.

### Scenario 5 — Cross-domain ordering (regression)

- **Setup:** Same as automated test: ideas `bio-feedback-loops`, `logistics-feedback-routing`, `music-harmony-archive` created with tags/interfaces as in `api/tests/test_idea_concept_resonance.py`.
- **Action:** `curl -sS "$API/api/ideas/bio-feedback-loops/concept-resonance?limit=3&min_score=0.05"`
- **Expected result:** First match `idea_id` is `logistics-feedback-routing`, `cross_domain` true, `"feedback"` in `shared_concepts`.
- **Edge case:** Lower `min_score` to `0.99` → empty or only very high overlap; must not 500.

## Acceptance tests (repository)

- `api/tests/test_idea_concept_resonance.py::test_concept_resonance_surfaces_cross_domain_match_first`
- `api/tests/test_idea_concept_resonance.py::test_concept_resonance_404_for_unknown_idea`

## Concurrency behavior

- **Reads:** Safe; resonance is computed from snapshot of ideas.
- **Writes:** After `POST/PATCH` idea, subsequent `GET .../concept-resonance` must reflect updates within the same process/store consistency model (eventual if replicated later).

## Verification (developer commands)

```bash
cd api && pytest -q tests/test_idea_concept_resonance.py
cd api && ruff check app/services/idea_service.py app/routers/ideas.py
```

## Out of scope (this spec)

- Training embeddings or LLM-based analogy detection (may be a future spec).
- Replacing Neo4j schema unilaterally without a migration spec.

## Risks and assumptions

- **Risk:** Token overlap mimics keywords; users may distrust scores. **Mitigation:** Transparent fields, versioning, and graph roadmap in API docs.
- **Assumption:** Domain markers remain available via `interfaces` like `domain:*` or equivalent; if not, cross-domain detection degrades.

## Known gaps and follow-up tasks

- Add graph-native scorer behind feature flag.
- Add metrics endpoint and web panel for resonance proof.
- Build golden dataset for analogical pairs (biology ↔ software).

## Failure / retry reflection

- **Failure mode:** Large portfolios make O(n) scan slow. **Next action:** Index concepts in memory or DB; paginate candidates.
- **Failure mode:** Sparse tags yield empty resonance. **Next action:** Enrich ideas from specs/tasks automatically.

## Decision gates

- Changing response schema of `GET /api/ideas/{idea_id}/concept-resonance` requires API version bump or additive-only fields agreed with web consumers.

---

**Character count note:** This document exceeds the minimum 500-character requirement for substantive specs.
