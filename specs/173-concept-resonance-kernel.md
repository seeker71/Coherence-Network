# Spec 173 — Concept Resonance Kernel (CRK): Harmonic Similarity Matching

**Status:** Draft
**Author:** agent (product-manager)
**Task ID:** task_c8365ca801bb45d8
**Date:** 2026-03-28

---

## Summary

The Concept Resonance Kernel (CRK) replaces keyword-based similarity matching across the Coherence
Network platform with a **harmonic resonance model** ported from the Living Codex
`ConceptResonanceModule`. Concepts are represented as harmonic symbols — each carrying a frequency
band, k-vector (direction in concept space), phase offset, and amplitude — and compared using a
combination of a **Gaussian resonance kernel** and **OT-phi optimal transport** (Wasserstein-style
mass-flow between frequency distributions). This produces a richer, more semantically honest
similarity score that captures conceptual *alignment* (phase), *depth* (amplitude), *domain
proximity* (frequency band), and *directional coherence* (k-vector).

The CRK becomes the single authoritative similarity primitive for:
- Idea deduplication and clustering
- Cross-concept relevance ranking
- Graph edge weight computation
- Contributor affinity scoring
- Search result ordering on `/ideas`, `/concepts`, and `/projects` endpoints

---

## Problem

The current platform uses naive TF-IDF / keyword overlap to score similarity between ideas and
concepts. This produces three categories of failure:

1. **Synonym blindness** — "neural embedding" and "vector representation" score near zero despite
   identical meaning.
2. **False proximity** — "graph theory" and "graph database" score high because they share a word,
   despite differing in domain depth.
3. **No directionality** — two ideas can be superficially similar while pointing in opposite
   intellectual directions (e.g., "centralise authority" vs "decentralise authority"). Keyword
   matching cannot distinguish them.

The CRK models each concept as a wave packet in a high-dimensional resonance space. Concepts
that are semantically *in-phase* and frequency-matched produce high resonance; out-of-phase or
cross-domain concepts produce destructive interference and low scores — exactly mirroring how
these ideas relate in human cognition.

---

## Theoretical Foundation

### Concept as Harmonic Symbol

Each concept `c` is encoded as a harmonic symbol:

```
c = { f, k, φ, A }
```

| Field | Type | Meaning |
|-------|------|---------|
| `f` | `float[B]` | Frequency band vector (B = 32 bands). Encodes *domain* and *abstraction level*. High-frequency bands = specific/technical; low-frequency = abstract/philosophical. |
| `k` | `float[D]` | k-vector, D-dimensional unit vector. Encodes *intellectual direction* — what the concept points toward. |
| `φ` | `float` | Phase offset in [0, 2π]. Encodes conceptual *polarity* — two concepts with identical frequency and k but φ differing by π are *opposed*. |
| `A` | `float` | Amplitude in [0, 1]. Encodes *strength/maturity* — a fully developed idea has A ≈ 1; a nascent stub has A ≈ 0.1. |

The embedding dimensions are:
- B = 32 frequency bands (log-spaced from 0.5 Hz to 16 kHz metaphorically mapped to abstraction level)
- D = 128 k-vector dimensions (matches the concept embedding space from the graph)

### Gaussian Resonance Kernel

For two concepts `c_i` and `c_j`, the Gaussian kernel computes:

```
K_gauss(c_i, c_j) = A_i · A_j · exp(−||f_i − f_j||² / 2σ_f²) · cos(φ_i − φ_j) · (k_i · k_j)
```

Where:
- `σ_f = 0.25` (bandwidth parameter, tunable)
- `k_i · k_j` is the dot product of unit k-vectors (−1 to 1 cosine similarity)
- `cos(φ_i − φ_j)` is +1 for in-phase, −1 for anti-phase, 0 for quadrature

Result `K_gauss ∈ [−1, 1]`. Negative values indicate *conceptual opposition*, a signal as valuable
as high positive scores.

### OT-phi Optimal Transport Term

The Gaussian kernel operates pointwise. The OT-phi term captures *distributional shape* — how
the entire frequency band distribution of `c_i` can be transported to match `c_j`, penalising
large Earth Mover Distance (EMD):

```
W(c_i, c_j) = EMD(f_i / ||f_i||₁, f_j / ||f_j||₁)
OT-phi(c_i, c_j) = exp(−W(c_i, c_j) / τ)
```

Where `τ = 0.5` is the temperature parameter. `OT-phi ∈ (0, 1]` — 1 when distributions are
identical, approaching 0 for maximally different distributions.

### Combined CRK Score

```
CRK(c_i, c_j) = α · K_gauss(c_i, c_j) · OT-phi(c_i, c_j) + (1 − α) · TF-IDF_fallback(c_i, c_j)
```

Where `α = 0.85` by default (85% harmonic, 15% keyword fallback for robustness during cold-start).

The final score is clamped to `[0.0, 1.0]` by the formula:

```
score = (CRK + 1) / 2  # shift [−1,1] → [0,1]
score = score * OT-phi  # apply transport penalty
```

### Harmonic Encoding Pipeline

Concepts acquire their harmonic encoding via a two-stage pipeline:

1. **Semantic projection**: The concept's text (name + description + tags) is embedded via the
   platform's existing embedding model (currently `text-embedding-ada-002` or equivalent). The
   128-dimensional embedding becomes the k-vector after L2 normalisation.

2. **Frequency decomposition**: The embedding vector is projected onto B=32 frequency bands using
   a learned filterbank matrix `W_filter ∈ R^{32×128}` (initialised as DCT-II basis, then
   fine-tuned). The result is softmax-normalised to form a probability distribution over bands.

3. **Phase assignment**: Phase φ is computed from the *sign pattern* of the embedding using:
   `φ = atan2(sum(embedding[odd indices]), sum(embedding[even indices]))`

4. **Amplitude**: `A = tanh(||embedding||₂ / √128)` — concepts with richer semantic content
   (longer, denser descriptions) get higher amplitude.

---

## Architecture

### New Components

```
api/
  services/
    crk/
      __init__.py
      kernel.py          # CRKernel class: encode(), score(), batch_score()
      harmonic_symbol.py # HarmonicSymbol dataclass + serialisation
      filterbank.py      # W_filter matrix, DCT init, fine-tune hooks
      ot_phi.py          # EMD computation (scipy.stats.wasserstein_distance)
      fallback.py        # TF-IDF fallback wrapper
  routers/
    resonance.py         # New router: /api/resonance/*
  models/
    resonance.py         # Pydantic models for requests/responses
```

### Modified Files

```
api/
  services/
    similarity.py        # Replace keyword logic → delegate to CRKernel
    ideas_service.py     # Use CRK for deduplication
    graph_service.py     # Use CRK for edge weight computation
  routers/
    ideas.py             # /api/ideas?q= uses CRK ranking
    concepts.py          # /api/concepts?similar_to= uses CRK
```

### Database Changes

**PostgreSQL migration** — add `harmonic_encodings` table:

```sql
CREATE TABLE harmonic_encodings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id      TEXT NOT NULL,          -- concept/idea/project ID
    entity_type    TEXT NOT NULL,          -- 'concept' | 'idea' | 'project'
    freq_bands     FLOAT[] NOT NULL,       -- B=32 frequency band values
    k_vector       FLOAT[] NOT NULL,       -- D=128 direction vector
    phase          FLOAT NOT NULL,         -- φ ∈ [0, 2π]
    amplitude      FLOAT NOT NULL,         -- A ∈ [0, 1]
    model_version  TEXT NOT NULL,          -- embedding model version for invalidation
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_harmonic_entity ON harmonic_encodings(entity_id, entity_type);
CREATE INDEX idx_harmonic_updated ON harmonic_encodings(updated_at);
```

**Neo4j migration** — add `crk_score` property to `RELATED_TO` and `SIMILAR_TO` edges:

```cypher
// On all existing RELATED_TO edges:
MATCH ()-[r:RELATED_TO]->()
SET r.crk_score = null  -- null triggers lazy recomputation on first access
```

---

## API Endpoints

### New: Resonance Router

#### `POST /api/resonance/encode`

Encode one or more entities into their harmonic symbols.

**Request:**
```json
{
  "entities": [
    {"id": "idea-abc", "type": "idea", "text": "neural embeddings for concept graphs"}
  ]
}
```

**Response (200):**
```json
{
  "encodings": [
    {
      "id": "idea-abc",
      "type": "idea",
      "freq_bands": [0.02, 0.15, ...],   // 32 values, sum to 1.0
      "k_vector": [0.03, -0.12, ...],     // 128 values, L2 norm = 1.0
      "phase": 1.47,
      "amplitude": 0.82,
      "model_version": "crk-v1"
    }
  ]
}
```

**Errors:** 422 if `entities` is empty or `text` is blank.

---

#### `POST /api/resonance/score`

Compute pairwise CRK scores between a query entity and a list of candidates.

**Request:**
```json
{
  "query": {"id": "idea-abc", "type": "idea"},
  "candidates": [
    {"id": "idea-xyz", "type": "idea"},
    {"id": "concept-123", "type": "concept"}
  ],
  "alpha": 0.85
}
```

**Response (200):**
```json
{
  "scores": [
    {"id": "idea-xyz", "type": "idea", "crk_score": 0.87, "k_gauss": 0.92, "ot_phi": 0.95, "tfidf_fallback": 0.44},
    {"id": "concept-123", "type": "concept", "crk_score": 0.23, "k_gauss": 0.18, "ot_phi": 0.61, "tfidf_fallback": 0.11}
  ],
  "query_id": "idea-abc",
  "alpha_used": 0.85
}
```

**Errors:** 404 if query entity not found; 422 if candidates list empty.

---

#### `GET /api/resonance/similar/{entity_type}/{entity_id}`

Return top-K most resonant entities for a given entity.

**Query params:**
- `k` (int, default 10, max 50) — number of results
- `entity_types` (comma-separated, default `idea,concept`) — types to search
- `min_score` (float, default 0.3) — minimum CRK score threshold
- `alpha` (float, default 0.85) — harmonic weight

**Response (200):**
```json
{
  "entity_id": "idea-abc",
  "entity_type": "idea",
  "similar": [
    {"id": "idea-xyz", "type": "idea", "crk_score": 0.87, "name": "Graph embedding methods"},
    ...
  ],
  "total": 3
}
```

**Errors:** 404 if entity not found.

---

#### `GET /api/resonance/health`

Return CRK subsystem health: coverage (fraction of entities with encodings), average amplitude,
last recomputation timestamp.

**Response (200):**
```json
{
  "coverage_pct": 94.2,
  "total_entities": 1204,
  "encoded_entities": 1134,
  "avg_amplitude": 0.71,
  "model_version": "crk-v1",
  "last_encode_run": "2026-03-28T07:00:00Z"
}
```

---

### Modified Existing Endpoints

#### `GET /api/ideas?q={query}`

When `q` is present, results are ranked by CRK score against the query string (encoded on-the-fly)
instead of keyword match. Response unchanged; adds optional `crk_score` field per idea when
`include_scores=true` query param is set.

#### `GET /api/concepts?similar_to={concept_id}`

CRK-ranked results instead of tag overlap. Existing response shape preserved.

---

## Configuration

All CRK parameters are configurable via `api/config/crk_config.json`:

```json
{
  "alpha": 0.85,
  "sigma_f": 0.25,
  "tau": 0.5,
  "freq_bands": 32,
  "k_vector_dims": 128,
  "model_version": "crk-v1",
  "batch_encode_cron": "0 3 * * *",
  "min_amplitude_threshold": 0.05,
  "max_similar_k": 50
}
```

---

## Observability and Proof of Correctness

A core open question: **how do we prove CRK is working, and show that proof clearly over time?**

### Proof Layer 1 — Regression Test Suite

A deterministic test suite (see Verification Scenarios) encodes known-good pairs:
- Synonyms must score > 0.75
- Antonyms must score < 0.25 (and K_gauss should be negative)
- Unrelated cross-domain pairs must score < 0.35

These tests run in CI on every merge and emit a JSON report to `api/tests/crk_regression.json`.

### Proof Layer 2 — A/B Similarity Audit Endpoint

`GET /api/resonance/audit` returns a sampled comparison of CRK vs legacy TF-IDF on the same
pairs — exposing both scores side-by-side with a `winner` field (`crk` | `tfidf` | `tie`).
Human reviewers can spot-check whether CRK winners are intuitively correct.

### Proof Layer 3 — Coverage Drift Metric

`GET /api/resonance/health` tracks `coverage_pct` over time. A Prometheus/Grafana gauge
`crk_encoding_coverage` emits this value. A drop below 80% triggers an alert. The nightly
batch re-encoder (`batch_encode_cron`) keeps coverage near 100%.

### Proof Layer 4 — Amplitude Distribution

A concept with very low amplitude (A < 0.1) is a stub with insufficient semantic content to
resonante meaningfully. `GET /api/resonance/health` exposes `avg_amplitude`. A healthy system
has avg_amplitude > 0.5. Declining amplitude signals data quality issues (empty descriptions,
no tags).

### Proof Layer 5 — Live Score Drift Tracking

When the CRK score for a pair changes > 0.1 between two encoder runs, the change is logged to
`resonance_drift` events (stored in PostgreSQL). `GET /api/resonance/drift?days=7` returns the
top-20 most-drifted pairs, indicating concepts undergoing significant semantic evolution —
a useful editorial signal.

---

## Verification Scenarios

### Scenario 1 — Encode and retrieve a harmonic symbol (create-read cycle)

**Setup:** A concept exists: `concept-001` with name "Graph Neural Network" and description
"Machine learning on graph-structured data using message passing".

**Action:**
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/encode \
  -H "Content-Type: application/json" \
  -d '{"entities":[{"id":"concept-001","type":"concept","text":"Graph Neural Network — machine learning on graph-structured data using message passing"}]}'
```

**Expected result:**
- HTTP 200
- Response contains `encodings[0].id == "concept-001"`
- `freq_bands` is an array of 32 floats summing to 1.0 (±0.001)
- `k_vector` is an array of 128 floats with L2 norm = 1.0 (±0.001)
- `phase` is a float in [0, 2π]
- `amplitude` is a float in [0.05, 1.0]

**Verify persistence:**
```bash
curl -s https://api.coherencycoin.com/api/resonance/similar/concept/concept-001
```
Returns HTTP 200 with `similar` array (may be empty if no other concepts encoded yet).

**Edge case:** POST with empty `text`:
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/encode \
  -d '{"entities":[{"id":"concept-001","type":"concept","text":""}]}'
```
Returns HTTP 422, response body contains `"detail"` with message about blank text.

---

### Scenario 2 — Synonym pair scores high (semantic correctness)

**Setup:** Two concepts encoded:
- `crk-test-syn-a`: "neural embeddings" — "Dense vector representations learned by neural networks"
- `crk-test-syn-b`: "vector representations" — "Numerical encodings of concepts as points in high-dimensional space"

**Action:**
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/score \
  -H "Content-Type: application/json" \
  -d '{
    "query": {"id":"crk-test-syn-a","type":"concept"},
    "candidates": [{"id":"crk-test-syn-b","type":"concept"}],
    "alpha": 0.85
  }'
```

**Expected result:**
- HTTP 200
- `scores[0].crk_score >= 0.70`
- `scores[0].k_gauss > 0` (not anti-phase)

**Edge case:** Same concept scored against itself:
```bash
# query = crk-test-syn-a, candidates = [crk-test-syn-a]
```
Returns `crk_score = 1.0` (±0.001).

---

### Scenario 3 — Antonym pair scores low with negative K_gauss (opposition detection)

**Setup:** Two concepts encoded:
- `crk-test-ant-a`: "decentralisation" — "Distributing authority and control away from a central point"
- `crk-test-ant-b`: "centralisation" — "Concentrating authority and decision-making in a single centre"

**Action:**
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/score \
  -H "Content-Type: application/json" \
  -d '{
    "query": {"id":"crk-test-ant-a","type":"concept"},
    "candidates": [{"id":"crk-test-ant-b","type":"concept"}],
    "alpha": 0.85
  }'
```

**Expected result:**
- HTTP 200
- `scores[0].crk_score <= 0.35`
- `scores[0].k_gauss < 0.2` (ideally negative, indicating phase opposition)

**Edge case:** Request with non-existent query ID:
```bash
curl -s -X POST https://api.coherencycoin.com/api/resonance/score \
  -d '{"query":{"id":"nonexistent-xxx","type":"concept"},"candidates":[{"id":"crk-test-ant-b","type":"concept"}]}'
```
Returns HTTP 404 with `{"detail": "Entity not found: nonexistent-xxx"}`.

---

### Scenario 4 — Top-K similar retrieval with score filtering

**Setup:** At least 5 concepts encoded in the system, including `concept-001` ("Graph Neural Network").

**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/resonance/similar/concept/concept-001?k=5&min_score=0.4"
```

**Expected result:**
- HTTP 200
- `similar` array contains 0–5 entries (depends on corpus)
- Every entry has `crk_score >= 0.4`
- Results are sorted descending by `crk_score`
- Response includes `entity_id == "concept-001"` and `entity_type == "concept"`

**Edge case:** `k=0` or `k=51`:
```bash
curl -s "https://api.coherencycoin.com/api/resonance/similar/concept/concept-001?k=0"
```
Returns HTTP 422 (k must be 1–50).

---

### Scenario 5 — Health endpoint reflects coverage and detects staleness

**Setup:** System has encoded at least 1 entity.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/resonance/health
```

**Expected result:**
- HTTP 200
- `coverage_pct` is a float in [0.0, 100.0]
- `total_entities >= 1`
- `encoded_entities <= total_entities`
- `avg_amplitude` is a float in [0.0, 1.0]
- `model_version == "crk-v1"`
- `last_encode_run` is an ISO 8601 UTC timestamp or `null` if no run yet

**Edge case:** No entities in system (clean install):
Returns HTTP 200 with `{"coverage_pct": 100.0, "total_entities": 0, "encoded_entities": 0, ...}`.
(0/0 coverage is defined as 100% — nothing to encode.)

---

### Scenario 6 — Ideas search endpoint uses CRK ranking (integration)

**Setup:** At least 3 ideas exist in the system.

**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/ideas?q=graph+embeddings&include_scores=true"
```

**Expected result:**
- HTTP 200
- Response is a list of ideas (same shape as without `q`)
- Results are ordered: idea with highest CRK match to "graph embeddings" is first
- Each idea object contains `"crk_score": <float>` when `include_scores=true`

**Edge case:** Query string with no matching ideas (very obscure term):
Returns HTTP 200 with empty list `[]` — not 404 or 500.

---

## Files to Create / Modify

### Create

| File | Purpose |
|------|---------|
| `specs/173-concept-resonance-kernel.md` | This spec |
| `api/services/crk/__init__.py` | Package init |
| `api/services/crk/harmonic_symbol.py` | `HarmonicSymbol` dataclass |
| `api/services/crk/filterbank.py` | DCT-II filterbank, W_filter matrix |
| `api/services/crk/ot_phi.py` | EMD/Wasserstein wrapper |
| `api/services/crk/kernel.py` | `CRKernel`: encode, score, batch_score |
| `api/services/crk/fallback.py` | TF-IDF fallback adapter |
| `api/routers/resonance.py` | FastAPI router for /api/resonance/* |
| `api/models/resonance.py` | Pydantic request/response models |
| `api/config/crk_config.json` | Default CRK configuration |
| `api/migrations/0XX_harmonic_encodings.sql` | PostgreSQL table migration |
| `api/tests/test_crk_kernel.py` | Unit tests for kernel math |
| `api/tests/test_resonance_router.py` | Integration tests for new endpoints |
| `api/tests/crk_regression_pairs.json` | Known-good synonym/antonym pairs |

### Modify

| File | Change |
|------|--------|
| `api/services/similarity.py` | Delegate to CRKernel; keep TF-IDF as fallback |
| `api/services/ideas_service.py` | Use CRK for deduplication |
| `api/routers/ideas.py` | Support `include_scores` param; CRK-rank `?q=` results |
| `api/routers/concepts.py` | `?similar_to=` uses CRK |
| `api/main.py` | Register `resonance` router |

---

## Acceptance Criteria

- [ ] `POST /api/resonance/encode` returns valid harmonic symbol (freq_bands sum 1.0, k_vector unit) for any non-empty text
- [ ] `POST /api/resonance/score` returns `crk_score ∈ [0.0, 1.0]` with component breakdown
- [ ] Known synonym pair scores ≥ 0.70 (regression test `test_synonym_pair_high_score`)
- [ ] Known antonym pair scores ≤ 0.35 (regression test `test_antonym_pair_low_score`)
- [ ] Self-score = 1.0 (regression test `test_self_score_identity`)
- [ ] `GET /api/resonance/similar/{type}/{id}` returns results sorted descending by `crk_score`
- [ ] `GET /api/resonance/health` returns valid JSON with all required fields
- [ ] `GET /api/ideas?q=...` returns CRK-ranked results in descending order
- [ ] 404 returned for non-existent entity in score/similar endpoints
- [ ] 422 returned for empty text in encode, empty candidates in score, k out-of-range
- [ ] Harmonic encodings persisted in PostgreSQL `harmonic_encodings` table
- [ ] CRK scores stored as `crk_score` property on Neo4j edges
- [ ] Full CI test suite passes (pytest, no mocks on DB layer per spec 084)
- [ ] `GET /api/resonance/health` shows `coverage_pct > 0` after encoding at least one entity

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Embedding model unavailable / cold-start | Medium | TF-IDF fallback (`alpha` param; graceful degradation to `alpha=0`) |
| EMD computation too slow for large batches | Medium | Batch via numpy vectorisation; cap at B=32 bands keeps cost O(B log B) |
| Harmonic encoding parameters need tuning | High | All parameters in `crk_config.json`; regression tests serve as tuning signal |
| Phase/amplitude encoding is domain-specific | Medium | Phase and amplitude are computed from the embedding, not handcrafted; accuracy tracks embedding quality |
| Negative CRK scores confuse consumers | Low | Final score clamped to [0,1] via shift; raw K_gauss exposed separately for power users |
| PostgreSQL `FLOAT[]` column performance | Low | GIN index not needed for similarity search (handled in-memory); index on entity_id sufficient |

---

## Known Gaps and Follow-up Tasks

1. **Fine-tuned filterbank**: The `W_filter` matrix is initialised as DCT-II and is not trained.
   A follow-up task should fine-tune it on concept pair feedback (thumbs-up/down on similarity
   results) to improve frequency decomposition accuracy.

2. **Approximate nearest-neighbour (ANN) index**: For large corpora (> 10,000 concepts), linear
   scan in `GET /api/resonance/similar` will be too slow. Follow-up: integrate FAISS or pgvector
   for sub-linear k-vector retrieval, then apply CRK re-scoring to the top-M candidates.

3. **Multi-hop resonance**: CRK currently scores pairs. A future spec should define *resonance
   paths* — chains of concepts where each consecutive pair has high CRK, forming semantic corridors
   through the graph.

4. **Contributor resonance**: Map contributor contribution vectors (using their idea/concept
   interaction history) to harmonic symbols and compute contributor-concept resonance for
   personalised relevance ranking.

5. **Living Codex `ConceptResonanceModule` full port**: The Living Codex module includes a
   breath-state modulation of phase (phase shifts with the contributor's current engagement
   state). This integration should be spec'd as a separate feature once basic CRK is stable.

---

## Task Card

```yaml
goal: >
  Port and implement the Concept Resonance Kernel from Living Codex ConceptResonanceModule.
  Replace keyword-based similarity with harmonic matching across the Coherence Network platform.
files_allowed:
  - api/services/crk/
  - api/routers/resonance.py
  - api/models/resonance.py
  - api/config/crk_config.json
  - api/migrations/0XX_harmonic_encodings.sql
  - api/services/similarity.py
  - api/services/ideas_service.py
  - api/routers/ideas.py
  - api/routers/concepts.py
  - api/main.py
  - api/tests/test_crk_kernel.py
  - api/tests/test_resonance_router.py
  - api/tests/crk_regression_pairs.json
  - specs/173-concept-resonance-kernel.md
done_when:
  - All acceptance criteria above are checked
  - All 6 verification scenarios pass against production
  - CI green
commands:
  - python3 -m pytest api/tests/test_crk_kernel.py -x -v
  - python3 -m pytest api/tests/test_resonance_router.py -x -v
  - curl -s https://api.coherencycoin.com/api/resonance/health
constraints:
  - Do not modify tests to force passing
  - Do not remove TF-IDF fallback — it is the cold-start safety net
  - alpha parameter must remain configurable, not hardcoded
  - No schema migrations without running migration scripts through the established migration path
  - CRK scores must be stored, not recomputed on every request (performance requirement)
```
