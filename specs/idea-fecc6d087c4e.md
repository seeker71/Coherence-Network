# Spec: Self-Balancing Graph — Anti-Collapse, Organic Expansion, Entropy Management

**Idea ID**: `idea-fecc6d087c4e`  
**Task ID**: `task_2bf58d13bf2f0453`, `task_3fbd4783fb612150`
**Related implementation specs**: [`specs/fractal-self-balance.md`](./fractal-self-balance.md) (spec-172), [`specs/172-fractal-self-balance.md`](./172-fractal-self-balance.md)  
**Status**: draft (product specification — consolidates requirements and verification contract)  
**Date**: 2026-03-28

## Summary

Coherence Network’s intelligence graph must **observe its own shape** as it grows: detect when a few concepts absorb disproportionate attention (collapse), when small disconnected clusters drift (fragmentation), and when diversity of engagement drops (entropy loss). The system stays **advisory** in the MVP: it computes metrics, emits **signals** (split, merge, surface neglected branches), and allows **reviewer-protected convergence** so legitimate focus is not treated as pathology. Balance is **dynamic equilibrium**—thresholds and weights may evolve; what is “healthy” is defined by measurable ranges plus human guardrails, not a fixed score forever.

This document is the **product-manager** contract. Implementation details, JSON field names, and router layout are aligned with **spec-172** and the existing API under `/api/graph/*`.

## Purpose

- Give operators and automation a **shared vocabulary** for graph shape (collapse vs convergence vs neglect).
- Ensure **no silent graph mutation**: suggestions and metrics first; actions remain explicit.
- Make **proof of value** possible: snapshots over time, ROI counters, and scenarios that can be run in CI and in production.

## Open Questions — Resolved in This Spec

### 1. What metrics signal healthy vs unhealthy graph shape?

| Signal | Healthy band (indicative) | Unhealthy / review trigger | Notes |
|--------|---------------------------|----------------------------|--------|
| **Normalized entropy** (engagement distribution) | Mid–high; spread across many nodes | Very low entropy with high total activity | Low entropy alone can be OK if guarded convergence (see below). |
| **Concentration ratio** (share of “energy” in top-3 concepts) | Below ~0.65–0.70 for large graphs | **≥ 0.80** sustained | Surfaces **neglected high-potential branches** via `surface_candidates`. |
| **Gravity wells** (concepts with many children) | Few or none above soft threshold | At or above `SPLIT_THRESHOLD` / `SPLIT_CRITICAL` | Emits `split_signal`; severity escalates at critical threshold. |
| **Orphan clusters** (small disconnected components) | None or small count | Clusters ≤ `ORPHAN_CLUSTER_MAX_SIZE` | Emits `merge_signal` for operator decision (link, merge, retire). |
| **`balance_score`** | Higher is “more balanced” in aggregate | Sudden sustained drop vs baseline | Composite; not a sole decision trigger — interpret with raw metrics. |

**Healthy** means: metrics sit in acceptable bands *or* deviations are **explained** (convergence guard, planned roadmap hub, cold-start graph). **Unhealthy** means: multiple red signals align (e.g. high concentration + low entropy + rising gravity wells) without guards or narrative.

### 2. How do we prevent the balance algorithm from suppressing genuine convergence?

- **No automatic splits/merges** in MVP — removes the class of bugs where the algorithm “fixes” intentional structure.
- **`POST /api/graph/concepts/{concept_id}/convergence-guard`** with reviewer `reason` and `set_by`: marks intentional depth; compute runs emit **`convergence_ok`** instead of **`split_signal`** for that concept.
- **`DELETE /api/graph/concepts/{concept_id}/convergence-guard`** restores default detection.
- **Signals are advisory**; ranking, payouts, and deletion must not be driven solely by `balance_score` (see Risks).

### 3. How can we improve the idea, show whether it is working, and make proof clearer over time?

- **`GET /api/graph/health/roi`**: exposes `balance_score_delta`, counts of actioned split/merge/surface signals, and stable `spec_ref` for traceability.
- **Repeated `POST /api/graph/health/compute`**: each success returns fresh `computed_at` — compare snapshots over time (store or log externally if needed).
- **Future (follow-up)**: dashboard page, alerting on threshold breach, calibration of weights in `graph_health_service` — listed under Known Gaps.

## Requirements

- [ ] The product exposes **structural health** via `GET /api/graph/health` and refresh via `POST /api/graph/health/compute` (same schema as spec-172; HTTP 200 for empty graph with bounded numeric fields and empty lists).
- [ ] **Split suggestion**: concepts exceeding child-count thresholds appear in `gravity_wells` with `split_signal` unless a convergence guard applies.
- [ ] **Merge suggestion**: small disconnected clusters appear in `orphan_clusters` with `merge_signal`.
- [ ] **Neglected branches**: when concentration is high (e.g. top-3 ≥ 80% of energy), `surface_candidates` lists under-linked but promising concepts.
- [ ] **Convergence protection** is first-class: guard create/delete endpoints behave as in spec-172.
- [ ] **ROI / proof**: `GET /api/graph/health/roi` returns non-negative counters and delta fields per spec-172.
- [ ] **Web (MVP)**: No dedicated page is required for this PM spec; operators validate via API. A future page **`/ops/graph-health`** (read-only dashboard) is listed as a follow-up — not blocking for this contract.
- [ ] **CLI**: Verification uses **`curl`** against `$API_URL` (see scenarios). A future **`cc graph health`** wrapper is optional and not part of MVP acceptance.

## Research Inputs (Required)

- `2026-03-28` — [`specs/fractal-self-balance.md`](./fractal-self-balance.md) — Canonical API and data model for graph health and guards.
- `2026-03-28` — [`api/tests/test_fractal_self_balance.py`](../api/tests/test_fractal_self_balance.py) — Executable acceptance contract for graph health behavior.
- `2026-03-28` — [`specs/169-fractal-node-edge-primitives.md`](./169-fractal-node-edge-primitives.md) — Graph primitives this feature observes.

## Task Card (Reference)

```yaml
goal: Ship advisory self-balancing graph diagnostics with convergence guards and ROI proof per spec-172.
files_allowed:
  - api/app/routers/graph_health.py
  - api/app/services/graph_health_service.py
  - api/app/models/graph_health.py
  - api/app/db/graph_health_repo.py
  - api/tests/test_fractal_self_balance.py
done_when:
  - pytest api/tests/test_fractal_self_balance.py passes
  - production curl verification scenarios below succeed
commands:
  - cd api && pytest -q tests/test_fractal_self_balance.py
constraints:
  - advisory only; no autonomous graph rewrites in MVP
```

## API Contract (Exact Endpoints)

Base path: **`/api`** (FastAPI `include_router(..., prefix="/api")`).

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/graph/health` | Latest snapshot (or baseline if none computed). |
| `POST` | `/api/graph/health/compute` | Recompute snapshot from current graph state. |
| `POST` | `/api/graph/concepts/{concept_id}/convergence-guard` | Set guard (JSON body: `reason`, `set_by`). |
| `DELETE` | `/api/graph/concepts/{concept_id}/convergence-guard` | Remove guard. |
| `GET` | `/api/graph/health/roi` | ROI / proof metrics. |

**404 behavior**: Invalid `concept_id` for guard operations should follow existing router patterns (if concept missing, document **404** with `detail` message — align with implementation).

## Data Model

Aligned with **spec-172** (`GraphHealthSnapshot`, `GravityWell`, `OrphanCluster`, `SurfaceCandidate`, `GraphSignal`, `ConvergenceGuard`, `GraphHealthROI`). See [`specs/fractal-self-balance.md`](./fractal-self-balance.md) § Data model for full YAML.

## Files to Create/Modify (Implementation Track)

When implementing beyond this PM doc, follow **spec-172** file list (routers, service, models, repo, tests). This task **only** adds this spec file unless a separate implementation task is opened.

## Acceptance Tests (Automated)

- `cd api && pytest -q tests/test_fractal_self_balance.py`

## Verification Scenarios (Production-Runnable Contract)

Use `API_URL=https://api.coherencycoin.com` (or local `http://localhost:8000` for dev). Replace `{CONCEPT_ID}` with a real concept id from your graph when testing guards.

### Scenario 1 — Read baseline health (empty or cold graph)

- **Setup**: API is up; graph may be empty or default-seeded.
- **Action**: `curl -sS "$API_URL/api/graph/health" | jq .`
- **Expected**: HTTP **200**; JSON includes numeric `balance_score`, `entropy_score`, `concentration_ratio`, arrays `gravity_wells`, `orphan_clusters`, `surface_candidates`, `signals`, and ISO `computed_at` (or baseline timestamp). No **500**.
- **Edge**: Same request with invalid path `GET /api/graph/healthz` → **404** (not 500).

### Scenario 2 — Full recompute cycle (create-read-update via compute)

- **Setup**: Note prior `computed_at` from Scenario 1 if present.
- **Action**: `curl -sS -X POST "$API_URL/api/graph/health/compute" -H 'Content-Type: application/json' | jq .`
- **Expected**: HTTP **200**; response matches health snapshot schema; `computed_at` is **newer or equal** to previous snapshot time after compute.
- **Edge**: Repeat POST immediately; still **200** and valid schema (idempotent recompute, not error).

### Scenario 3 — Convergence guard create → verify suppression → delete (error handling)

- **Setup**: Pick a `concept_id` that exists in the graph, or use one returned in `gravity_wells` after compute on a stressed fixture graph.
- **Action (create)**:  
  `curl -sS -X POST "$API_URL/api/graph/concepts/{CONCEPT_ID}/convergence-guard" -H 'Content-Type: application/json' -d '{"reason":"Intentional hub","set_by":"reviewer"}' | jq .`
- **Expected**: HTTP **200**; body indicates guard applied (`convergence_guard: true`, echoes `reason` / `set_by` per implementation).
- **Action (read implied)**: `POST /api/graph/health/compute` then inspect `signals` — for guarded concept, expect **`convergence_ok`** or absence of **`split_signal`** per spec-172 tests.
- **Action (delete)**: `curl -sS -X DELETE "$API_URL/api/graph/concepts/{CONCEPT_ID}/convergence-guard" | jq .`
- **Expected**: HTTP **200**; guard cleared.
- **Edge (bad input)**: POST guard with **empty JSON** `{}` → **422** validation error (if required fields missing).
- **Edge (missing resource)**: POST guard for **nonexistent** `concept_id` → **404** if implementation validates existence; must not return **500**.

### Scenario 4 — Concentration / neglected branches

- **Setup**: Test or staging graph where engagement is concentrated in three concepts (or use fixture-backed environment).
- **Action**: `curl -sS -X POST "$API_URL/api/graph/health/compute" | jq '{concentration_ratio, surface_candidates}'`
- **Expected**: When concentration rule fires (e.g. top-3 ≥ 80%), `surface_candidates` is a **non-null array** with at least zero entries; each entry has stable fields (`concept_id`, `reason`, `score` per model).
- **Edge**: If graph too small to compute diversity, still **200** with defined fields (no uncaught exception).

### Scenario 5 — ROI proof endpoint

- **Action**: `curl -sS "$API_URL/api/graph/health/roi" | jq .`
- **Expected**: HTTP **200**; JSON includes `balance_score_delta`, integer-like non-negative `split_signals_actioned`, `merge_signals_actioned`, `surface_signals_actioned`, and `spec_ref` matching **spec-172** string.
- **Edge**: Repeated GETs return consistent schema (no 500 under load).

## Concurrency Behavior

- Health reads are safe; writes (compute, guards) follow **last-write-wins** for guards and snapshot storage unless upgraded with ETags in a future spec.

## Verification (CI / Local)

```bash
cd api && pytest -q tests/test_fractal_self_balance.py
python3 scripts/validate_spec_quality.py --file specs/idea-fecc6d087c4e.md
```

## Out of Scope

- Automatic split/merge/reparent of graph nodes.
- Dedicated Next.js page in this PM deliverable (optional follow-up: `/ops/graph-health`).
- Changing authentication or multi-tenant isolation (separate security spec).

## Risks and Assumptions

- **Risk**: Degree-based and engagement proxies may mis-label a valid strategic hub as a gravity well. **Mitigation**: convergence guard + human review; no auto-rewrite.
- **Risk**: Operators may over-trust `balance_score`. **Mitigation**: document composite nature; require interpreting sub-metrics.
- **Assumption**: Concept and engagement data are available to the service layer; if not, snapshots may be shallow — surface in Known Gaps.

## Known Gaps and Follow-up Tasks

- Public **dashboard** for non-API users (`/ops/graph-health`).
- **`cc graph health`** CLI convenience wrapper and docs.
- **Calibration** task for `SPLIT_THRESHOLD`, concentration bands, and weighting in `balance_score` using production telemetry.
- Optional **historical time series** storage for snapshots (not required for MVP ROI counters).

## Failure/Retry Reflection

- **Failure mode**: Stale snapshot if compute is never called. **Next action**: document operator habit — call `POST .../compute` after bulk imports; optional scheduler in follow-up.
- **Failure mode**: ROI counters not incremented if no resolution workflow. **Next action**: wire signal resolution to ROI increments in implementation tasks.

## See Also

- [`specs/fractal-self-balance.md`](./fractal-self-balance.md)
- [`specs/114-collective-coherence-resonance-flow-friction-health.md`](./114-collective-coherence-resonance-flow-friction-health.md)
