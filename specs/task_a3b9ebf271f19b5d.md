# Spec — Concept Resonance Kernel (CRK): Harmonic Similarity Matching

**Spec ID:** `task_a3b9ebf271f19b5d`  
**Related task:** `task_a3b9ebf271f19b5d`  
**Status:** Specification (implementation deferred to follow-on task card)

---

## Summary

The **Concept Resonance Kernel (CRK)** replaces brittle **keyword overlap** (Jaccard-style token sets, phrase boosts) with **harmonic similarity**: each concept (and optionally each idea, news item, or graph node) is represented as a **symbol in a harmonic basis**—carrying **frequency bands**, **k-vectors** (direction in concept space), **phase**, and **amplitude**. Pairwise and set-wise similarity combine a **Gaussian kernel** over band-wise distances with **OT-φ optimal transport** (entropy-regularized Wasserstein with cost tied to the golden-ratio structure φ) to align mass across bands when absolute frequencies differ.

This spec ports the **intent and algorithmic contract** of Living Codex `ConceptResonanceModule` into Coherence Network’s adapter layer, with explicit **APIs**, **data shapes**, **observability**, and **verification** so operators can prove the system is working and improve it over time.

**Strategic outcome:** search, ranking, news–idea matching, geo-tagged resonance, and graph suggestions move from “same words” to “same harmonic shape,” reducing false negatives (synonyms, paraphrases) and false positives (polysemy) relative to pure keyword scoring.

---

## Problem

- Today, multiple services use **keyword extraction + overlap** (e.g. news–idea resonance, local news resonance). This does not capture **graded semantic proximity** or **structural alignment** across modalities.
- There is **no single, testable contract** for “how similar are two concepts?” that is **versioned**, **auditable**, and **comparable** week over week.
- Stakeholders cannot answer: *Is resonance getting better?* without **metrics**, **shadow mode**, and **A/B or cohort proofs**.

---

## Solution Overview

1. **Representation:** Each concept `c` has a fixed-dimensional **harmonic signature** `H(c) = {(band_i, k_i, φ_i, A_i)}` (frequency band index or center, k-vector in ℝᵈ, phase, amplitude). Ideas and text-derived entities map to the same space via an **ingestion projection** (existing embeddings may seed k-vectors; bands partition the spectrum of importance).
2. **Gaussian kernel:** For two symbols, band-wise contributions use a Gaussian on distances between k-vectors and phase-aware terms (implementation may start with magnitude-only + phase cosine, then extend).
3. **OT-φ transport:** Given two **distributions over bands** (amplitudes normalized), compute an optimal transport plan with cost matrix derived from inter-band distances and φ-scaled regularization, yielding a **transport score** in [0, 1].
4. **Composite resonance score:** `α · K_gauss + (1−α) · OT_φ` (α configurable; default conservative toward OT when mass is comparable).
5. **Rollout:** **Shadow scoring** runs CRK alongside legacy keyword scores; **promotion** switches consumers one router at a time when cohort metrics pass gates.

---

## Requirements

### Functional

1. **R1 — Canonical scoring API:** Expose a deterministic HTTP API to score resonance between two entities or between a query signature and a catalog (see API section).
2. **R2 — Persistence of signatures:** Concept harmonic signatures are **stored** (Postgres JSON column or dedicated table) with `schema_version`, `updated_at`, and optional `source` (manual, derived, imported).
3. **R3 — Backward compatibility:** Until CRK is promoted per surface, existing keyword-based endpoints **continue** to return 200 with legacy fields; CRK fields are **additive** (`crk_score`, `crk_components`) where applicable.
4. **R4 — Batch explainability:** For a scored pair, return **decomposable** components: `gaussian_term`, `ot_phi_term`, `band_alignment`, `schema_version`, `model_id` (for proof and debugging).
5. **R5 — CLI parity:** Operators can invoke scoring and **dry-run** catalog stats from `cc` without the HTTP stack.

### Non-functional

6. **R6 — Latency budget:** P95 < 300 ms for pairwise score at N ≤ 10⁴ catalog entries with ANN prefilter (specify in impl); otherwise documented degradation path.
7. **R7 — Determinism:** Same inputs + same `schema_version` ⇒ identical score to within floating-point epsilon documented in tests.
8. **R8 — Observability:** Emit structured events (`crk.score`, `crk.shadow_diff`) for dashboards and the proof loop described below.

---

## API Contract

Base path prefix: **`/api/crk`** (Concept Resonance Kernel). All JSON responses use Pydantic models; errors follow FastAPI `detail` convention.

### `POST /api/crk/signatures`

**Purpose:** Create or replace a harmonic signature for an entity (full create in the CRK namespace).

**Request body**
```json
{
  "entity_type": "concept",
  "entity_id": "formal-verification",
  "bands": [
    { "band_id": "b0", "k": [0.12, -0.4, 0.88], "phase": 0.31, "amplitude": 0.9 },
    { "band_id": "b1", "k": [0.02, 0.15, -0.22], "phase": 1.02, "amplitude": 0.4 }
  ],
  "schema_version": "crk-1"
}
```

**Response 201**
```json
{
  "entity_type": "concept",
  "entity_id": "formal-verification",
  "schema_version": "crk-1",
  "updated_at": "2026-03-28T18:00:00Z",
  "band_count": 2
}
```

**Response 422** — invalid vector length, negative amplitude, empty bands.

---

### `GET /api/crk/signatures/{entity_type}/{entity_id}`

**Purpose:** Read back a stored signature (read).

**Response 200** — body matches stored signature + metadata.

**Response 404** — no signature for that entity.

---

### `PATCH /api/crk/signatures/{entity_type}/{entity_id}`

**Purpose:** Partial update (e.g. single band amplitude adjustment).

**Response 200** — updated resource.

**Response 404** — entity not found.

---

### `POST /api/crk/score`

**Purpose:** Compute resonance between two signatures **or** between one inline signature and one stored id (flexible for tests and pipelines).

**Request body**
```json
{
  "left": { "ref": { "entity_type": "concept", "entity_id": "a" } },
  "right": { "ref": { "entity_type": "concept", "entity_id": "b" } },
  "params": { "alpha": 0.45, "phi_regularization": 0.1 }
}
```

**Response 200**
```json
{
  "score": 0.7821,
  "gaussian_term": 0.81,
  "ot_phi_term": 0.76,
  "components": {
    "band_pairs": 12,
    "transport_sparsity": 0.34
  },
  "schema_version": "crk-1",
  "latency_ms": 4.2
}
```

---

### `POST /api/crk/score/batch`

**Purpose:** Score a **query** ref against up to `limit` targets (default 50, max 200) for ranking.

**Response 200** — `{ "items": [ { "entity_id": "...", "score": 0.71, ... } ], "truncated": false }`

---

### `GET /api/crk/metrics`

**Purpose:** Operator-facing **proof** endpoint: rolling shadow diff (CRK vs keyword), latency histograms, cohort drift. Used to show whether CRK is “working yet.”

**Response 200**
```json
{
  "window_hours": 72,
  "pairwise_scores_total": 18420,
  "shadow_mean_abs_diff": 0.082,
  "promotion_ready": false,
  "schema_version": "crk-1"
}
```

---

### Existing surfaces (integration, not duplicate routes)

These **existing** endpoints gain **optional** CRK-backed behavior behind flags; exact query/header names are fixed at implementation time but **must** be documented in OpenAPI:

| Existing route | Integration |
|----------------|-------------|
| `GET /api/ideas/resonance` | Optional `mode=crk` or header `X-Resonance-Mode: crk` — list ideas ranked by CRK against a profile or window. |
| News / geo resonance services | Internal call to `POST /api/crk/score/batch` when feature flag on. |

---

## Web Pages

| Path | Purpose |
|------|---------|
| `/resonance` | Existing page; add **optional** panel “Harmonic match” when `NEXT_PUBLIC_CRK_UI=1` showing last scores and link to docs (no breaking change to default layout). |
| `/admin/crk` (optional, behind auth) | Metrics dashboard: shadow diff, latency, schema version mix. |

---

## CLI Commands

| Command | Purpose |
|---------|---------|
| `cc crk signature get <type> <id>` | Fetch signature JSON (wraps `GET /api/crk/signatures/...`). |
| `cc crk score <typeA> <idA> <typeB> <idB>` | Pairwise score. |
| `cc crk metrics` | Print `GET /api/crk/metrics` summary. |

---

## Data Model

### Table: `crk_signatures` (logical; may be JSON column on `concepts` in MVP)

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID PK | |
| `entity_type` | string | `concept`, `idea`, … |
| `entity_id` | string | Stable id |
| `schema_version` | string | e.g. `crk-1` |
| `bands` | JSONB | Array of `{band_id, k[], phase, amplitude}` |
| `created_at`, `updated_at` | timestamptz | |

**Constraints:** Unique `(entity_type, entity_id)`; GIN index on `bands` optional for future.

### Event log (observability)

- `crk.score` — `entity_left`, `entity_right`, `score`, `schema_version`, `latency_ms`
- `crk.shadow_diff` — `legacy_score`, `crk_score`, `surface` (e.g. `news_idea`)

---

## Files to Create or Modify (implementation phase)

| File | Action |
|------|--------|
| `api/app/routers/crk.py` | New router: all `/api/crk/*` routes |
| `api/app/services/crk_service.py` | Gaussian + OT-φ core (pure functions + optional numba) |
| `api/app/models/crk.py` | Pydantic request/response models |
| `api/app/main.py` or router registry | Include `crk` router |
| `api/tests/test_crk.py` | Contract tests: determinism, 404, 422, batch limits |
| `docs/` or inline OpenAPI | Document `mode` / headers for legacy routes |
| `web/app/resonance/page.tsx` | Optional panel behind env flag |

*This spec authorizes only planning; implementers must attach an explicit task card with `files_allowed` before merging code.*

---

## Acceptance Criteria (spec quality)

- [ ] OpenAPI-visible routes listed above are **named** and **versioned** via `schema_version`.
- [ ] **Verification Scenarios** below are **executable** against production with `curl` / `cc` (no vague “works”).
- [ ] **Risks** and **Known Gaps** include measurable **mitigations** and **follow-up** tasks.
- [ ] **Proof loop** addresses: improving the idea, showing whether it works, clarifying proof over time (metrics + shadow + promotion gates).

---

## Verification Scenarios

### Scenario 1 — Full signature lifecycle (create → read → update)

**Setup:** API deployed; no signature exists for `concept/e2e-crk-alpha`.  
**Action:**

```bash
API=https://api.coherencycoin.com
curl -sS -X POST "$API/api/crk/signatures" -H "Content-Type: application/json" \
  -d '{"entity_type":"concept","entity_id":"e2e-crk-alpha","bands":[{"band_id":"b0","k":[1,0,0],"phase":0,"amplitude":1}],"schema_version":"crk-1"}'
curl -sS "$API/api/crk/signatures/concept/e2e-crk-alpha"
curl -sS -X PATCH "$API/api/crk/signatures/concept/e2e-crk-alpha" \
  -H "Content-Type: application/json" \
  -d '{"bands":[{"band_id":"b0","k":[1,0,0],"phase":0.5,"amplitude":0.8}]}'
curl -sS "$API/api/crk/signatures/concept/e2e-crk-alpha"
```

**Expected:** `201` on POST with `entity_id` echo; GET returns stored bands; PATCH returns `200` and GET shows **updated** `phase`/`amplitude`.  
**Edge:** POST duplicate same `(entity_type, entity_id)` returns **409** (conflict), not silent overwrite, unless spec implementation chooses idempotent upsert—**must** document one behavior and test it.

---

### Scenario 2 — Pairwise score determinism

**Setup:** Signatures for `concept/crk-a` and `concept/crk-b` exist with fixed vectors.  
**Action:**

```bash
curl -sS -X POST "$API/api/crk/score" -H "Content-Type: application/json" \
  -d '{"left":{"ref":{"entity_type":"concept","entity_id":"crk-a"}},"right":{"ref":{"entity_type":"concept","entity_id":"crk-b"}},"params":{"alpha":0.45}}'
# repeat identical request
```

**Expected:** Two responses with **identical** `score` and `gaussian_term` / `ot_phi_term` to 1e-5 relative tolerance.  
**Edge:** Missing entity ref returns **404** with `detail` mentioning unknown id, not **500**.

---

### Scenario 3 — Batch ranking ceiling

**Setup:** At least 60 concepts with signatures seeded in staging.  
**Action:**

```bash
curl -sS -X POST "$API/api/crk/score/batch" -H "Content-Type: application/json" \
  -d '{"query":{"ref":{"entity_type":"concept","entity_id":"crk-a"}},"limit":300}'
```

**Expected:** HTTP **422** or **400** with message that `limit` exceeds max (200), **or** HTTP 200 with `"truncated": true` and at most 200 items—behavior must match OpenAPI.  
**Edge:** `limit=0` returns **422**.

---

### Scenario 4 — Metrics proof endpoint

**Setup:** Shadow mode enabled for at least 24h in staging with traffic.  
**Action:**

```bash
curl -sS "$API/api/crk/metrics?window_hours=24"
```

**Expected:** HTTP **200**, JSON includes numeric `pairwise_scores_total` ≥ 0, `shadow_mean_abs_diff` in [0, 1] or `null` if shadow inactive, and `schema_version`.  
**Edge:** Invalid `window_hours=-1` returns **422**.

---

### Scenario 5 — Error handling and bad input

**Setup:** None.  
**Action:**

```bash
curl -sS -X POST "$API/api/crk/signatures" -H "Content-Type: application/json" \
  -d '{"entity_type":"concept","entity_id":"bad","bands":[],"schema_version":"crk-1"}'
curl -sS "$API/api/crk/signatures/concept/does-not-exist-xyz"
```

**Expected:** Empty `bands` → **422**; GET missing id → **404**.  
**Edge:** Malformed JSON body → **422** with validation detail.

---

## How We Improve the Idea, Show It Works, and Make Proof Clearer Over Time

1. **Shadow mode (always-on in staging):** For every legacy keyword score, compute CRK in parallel; log `crk.shadow_diff`. **Promotion gate:** rolling `shadow_mean_abs_diff` below threshold **and** no regression on human-labeled set (small golden file in repo).
2. **Cohort dashboards:** `/api/crk/metrics` + optional `/admin/crk` chart **click-through** to example pairs (anonymized) where CRK and keyword disagree most—feeds dataset curation.
3. **Versioned schemas:** `schema_version` bumps when bands or OT regularization change; **A/B** by version header for safe experiments.
4. **Golden vectors:** Checked-in JSON of 20 concept pairs with **expected score ranges** in CI; drift fails the build.
5. **Public narrative:** Release notes tie **metric deltas** to product outcomes (e.g. “median news–idea relevance +0.08”).

---

## Research Inputs

| Date | Source | Relevance |
|------|--------|-----------|
| 2026-03-28 | Internal — Living Codex `ConceptResonanceModule` (reference repo, read-only) | Algorithmic intent: harmonic symbols, OT-φ; port must preserve mathematical separations (Gaussian vs transport). |
| 2026-03-28 | Project — `api/app/services/news_resonance_service.py` | Current keyword baseline to replace incrementally. |
| 2018-2019 | Cuturi et al. — entropy-regularized optimal transport (literature) | OT-φ implementation reference for sinkhorn-style solvers. |

*Implementers should attach primary papers and version pins for any library (e.g. POT, geomloss) in the implementation PR.*

---

## Task Card (for implementation follow-up)

```yaml
goal: Ship CRK scoring API with stored signatures, shadow metrics vs keyword baseline, and CLI wrappers.
files_allowed:
  - api/app/routers/crk.py
  - api/app/services/crk_service.py
  - api/app/models/crk.py
  - api/app/main.py
  - api/tests/test_crk.py
done_when:
  - pytest api/tests/test_crk.py passes
  - POST /api/crk/score returns stable scores for golden fixtures
  - GET /api/crk/metrics returns non-empty counters in staging with shadow enabled
commands:
  - cd api && pytest -q tests/test_crk.py
  - curl -s https://api.coherencycoin.com/api/crk/metrics
constraints:
  - Do not remove keyword paths until promotion gate passes
  - No mocks in golden tests — use fixed numerical fixtures
```

---

## Out of Scope (this spec)

- Full replacement of all keyword paths in one release.
- GPU training of embeddings from scratch (may use existing embedding service as projection).
- Neo4j-native vector index (optional optimization phase).

---

## Risks and Assumptions

| Risk | Mitigation |
|------|------------|
| OT-φ too slow at scale | Prefilter with band histogram intersection; cap batch size; cache transport plans for repeated pairs. |
| Living Codex source not bit-identical in this worktree | Treat reference as **behavioral spec**; golden tests lock Python implementation. |
| Overfitting to golden pairs | Expand golden set quarterly from shadow disagreements + human labels. |

**Assumption:** Concepts can be assigned stable k-vectors; if not, first phase uses **random orthogonal projections** of text embeddings with documented seed.

---

## Known Gaps and Follow-up Tasks

- **Gap:** Exact φ-regularization tie-in to cost matrix must be validated against reference module math during implementation.
- **Follow-up:** ANN index for k-vectors when catalog > 10⁵ signatures.
- **Follow-up:** Wire `GET /api/ideas/resonance?mode=crk` after `/api/crk` is stable in staging.

---

## Verification (developer checklist)

```bash
cd api && pytest -q tests/test_crk.py
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD  # when spec metadata required
curl -s https://api.coherencycoin.com/api/crk/metrics | python3 -m json.tool
```

---

## Failure / Retry Reflection

- **Failure mode:** Sinkhorn OT fails to converge for pathological amplitudes.  
- **Blind spot:** Near-zero mass on all bands.  
- **Next action:** Return **422** with code `ot_non_convergent` and require minimum amplitude floor in validation.

---

## Decision Gates

1. Product approval to enable **shadow** on production traffic (read-only side effects).
2. Security review if signatures may contain PII in `entity_id` or embedded text.

---

## Concurrency Behavior

- Signature writes: **optimistic** on `updated_at` or last-write-wins for MVP (document chosen semantics in OpenAPI).
- Scoring: **read-only**, horizontally scalable.
