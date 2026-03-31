# Spec: Self-Balancing Graph — Anti-Collapse, Organic Expansion, Entropy Management (PM)

**Spec Ref**: `spec-task_fc3bb95cb540f270`  
**Related implementation contract**: [`specs/fractal-self-balance.md`](./fractal-self-balance.md) (`spec-172`, Idea ID `fractal-self-balance`)  
**Task ID**: `task_fc3bb95cb540f270`  
**Status**: draft  
**Date**: `2026-03-28`

## Summary

Coherence Network’s intelligence graph must **observe its own shape** and steer attention without silently rewriting structure. This product specification defines *what “healthy” means*, how the system **signals** overload (too many children on one concept), fragmentation (orphan clusters), and **concentration risk** (for example when roughly 80% of measured “energy” accrues to a tiny set of ideas), while preserving **genuine convergence** through explicit human or reviewer guardrails. Balance is **dynamic equilibrium**: thresholds and surfacing rules adapt as the network grows; the MVP remains **diagnostic and advisory**—automatic split/merge execution stays out of scope and lives under [`specs/fractal-self-balance.md`](./fractal-self-balance.md).

## Purpose

Operators, contributors, and automation need a shared contract for **graph-shape health** so the network can expand organically without collapsing into a few hubs or shattering into inert fragments. This spec frames the *product intent* and *proof strategy*; the concrete API field names, endpoints, and acceptance tests are aligned with `spec-172` so implementers do not fork two incompatible contracts.

## Open Questions — Resolved for Product Intent

### What metrics signal healthy vs unhealthy graph shape?

| Signal | Healthy (directional) | Unhealthy (directional) | Notes |
|--------|-------------------------|-------------------------|--------|
| **Entropy (diversity)** | Normalized Shannon entropy over engagement-like counts is **not** near zero | Entropy near minimum while node count grows | Low entropy alone is not “bad” if the domain is genuinely convergent; combine with concentration and guards. |
| **Concentration** | Top-*k* share of energy (e.g. top-3) **below** policy threshold (e.g. &lt; 0.8) | Top-3 share **≥ 0.8** sustained across snapshots | Triggers **surface_candidates** for neglected branches per `spec-172`. |
| **Gravity (fan-out)** | No concept stays above `SPLIT_THRESHOLD` children without review | Child count ≥ threshold → **gravity** + **split_signal** (unless guarded) | Prevents “collapse of taxonomy” into one overloaded parent. |
| **Orphans / clusters** | Small components are rare or intentionally isolated | Many tiny disconnected clusters → **merge_signal** | Suggests linking or merge, not auto-execution. |
| **Balance score** | Composite in `[0,1]` stable or improving vs baseline | Monotonic decline with rising concentration | Use `GET /api/graph/health/roi` for **delta** over time. |

### How do we prevent the balance algorithm from suppressing genuine convergence?

1. **Signals, not edits**: No automatic graph mutation in MVP; operators act on advisories.  
2. **Convergence guard**: `POST /api/graph/concepts/{concept_id}/convergence-guard` marks intentional depth; compute runs emit `convergence_ok` instead of `split_signal` for that concept (`spec-172`).  
3. **Temporal stability**: A single snapshot never demotes a concept; repeated computes + reviewer action are required before any future automation (out of scope here).  
4. **Explicit false-positive path**: `DELETE /api/graph/concepts/{concept_id}/convergence-guard` restores normal detection if a guard was wrong.

### How can we improve this idea, show whether it is working, and make proof clearer over time?

| Phase | Proof | Artifact |
|-------|--------|----------|
| **Baseline** | First `POST /api/graph/health/compute` after deploy | Stored snapshot + `computed_at` |
| **Advisory** | Non-empty `signals` when shape is skewed | Logs / monitor on `split_signal`, `merge_signal`, `surface_signal` |
| **Outcome** | `balance_score_delta` and action counters | `GET /api/graph/health/roi` returns `spec_ref: "spec-172"` for traceability |
| **Iteration** | Tune thresholds in config, not in ad hoc code | Documented in implementation task; A/B on `SPLIT_THRESHOLD` optional follow-up |

## Requirements

- [ ] The product narrative above is implemented **only** through the API and data contracts in [`specs/fractal-self-balance.md`](./fractal-self-balance.md) until a superseding spec is approved.
- [ ] **Health read path**: `GET /api/graph/health` always returns HTTP 200 with bounded metrics and lists (empty graph allowed).
- [ ] **Recompute path**: `POST /api/graph/health/compute` refreshes metrics and `computed_at` from current graph state.
- [ ] **Anti-collapse**: Concepts with child count ≥ threshold generate **gravity** / **split_signal** unless a **convergence guard** is set.
- [ ] **Organic expansion**: When concentration is high, **surface_candidates** lists neglected high-potential branches (per `spec-172` heuristic).
- [ ] **Entropy management**: Response includes normalized entropy and concentration ratio so the “80% to three ideas” condition is observable.
- [ ] **Convergence preservation**: `POST` and `DELETE` convergence-guard endpoints round-trip and affect the next compute.
- [ ] **Proof over time**: `GET /api/graph/health/roi` exposes deltas and action counts with stable `spec_ref`.

## API Changes (authoritative)

All endpoints below are **required** for this feature; field-level JSON is defined in `specs/fractal-self-balance.md`.

| Method | Path | Role |
|--------|------|------|
| `GET` | `/api/graph/health` | Latest snapshot (read) |
| `POST` | `/api/graph/health/compute` | Recompute metrics (create snapshot) |
| `POST` | `/api/graph/concepts/{concept_id}/convergence-guard` | Create guard (override split signals) |
| `DELETE` | `/api/graph/concepts/{concept_id}/convergence-guard` | Remove guard |
| `GET` | `/api/graph/health/roi` | ROI / proof-over-time metrics |

**Graph CRUD (supporting data for tests and seeds)** — full create-read-update cycle for concepts as nodes uses the universal graph API:

| Method | Path |
|--------|------|
| `POST` | `/api/graph/nodes` |
| `GET` | `/api/graph/nodes/{id}` |
| `PATCH` | `/api/graph/nodes/{id}` |

**Web (optional / future)**: A dashboard at **`/graph/balance`** (or **`/admin/graph-health`**) may visualize the same JSON; **not** required for MVP acceptance in `spec-172`.

**CLI (optional / future)**: **`cc graph health`** (read-only snapshot) and **`cc graph compute`** may wrap the HTTP API; verification in production **must** remain possible via `curl` without the CLI.

## Data Model

Authoritative YAML and enums: see **Data model** in [`specs/fractal-self-balance.md`](./fractal-self-balance.md) (`GraphHealthSnapshot`, `GraphSignal`, `ConvergenceGuard`, `GraphHealthROI`, etc.).

## Files to Create / Modify (when implementing)

Per `spec-172` (not in scope for this PM-only task unless a separate implementation card is opened):

- `api/app/routers/graph_health.py`
- `api/app/services/graph_health_service.py`
- `api/app/models/graph_health.py`
- `api/app/db/graph_health_repo.py`
- `api/tests/test_fractal_self_balance.py`

## Verification Scenarios

Use **`API_BASE=https://api.coherencycoin.com`** (or `http://localhost:8000` for local). Replace `<concept_id>` with a real node id from your environment.

### Scenario 1 — Read health on empty or cold graph

- **Setup**: API is up; graph may be empty or never computed.
- **Action**: `curl -sS -o /tmp/gh.json -w "%{http_code}" "$API_BASE/api/graph/health"`
- **Expected**: HTTP status **200**; body parses as JSON; keys include `balance_score`, `entropy_score`, `concentration_ratio`, `gravity_wells`, `orphan_clusters`, `surface_candidates`, `signals`, `computed_at` (arrays may be empty).
- **Edge**: Malformed `API_BASE` (wrong host) returns connection error — **not** a 500 from our API.

### Scenario 2 — Full recompute cycle (create snapshot)

- **Setup**: Valid bearer/session not required for public read paths in this contract (if auth is added later, use test token).
- **Action**: `curl -sS -X POST "$API_BASE/api/graph/health/compute" -H 'Content-Type: application/json' -d '{}'`
- **Expected**: HTTP **200**; `computed_at` is **ISO 8601** string; numeric scores bounded in `[0,1]` where specified in `spec-172`.
- **Edge**: Second immediate POST returns **200** with a **new** `computed_at` timestamp (monotonic wall-clock).

### Scenario 3 — Convergence guard create → read → delete (CRUD on guard)

- **Setup**: Known existing `concept_id` (from `GET /api/graph/nodes?limit=5` or seed data).
- **Action (create)**:  
  `curl -sS -X POST "$API_BASE/api/graph/concepts/<concept_id>/convergence-guard" -H 'Content-Type: application/json' -d '{"reason":"test guard","set_by":"verifier"}'`
- **Expected**: HTTP **200**; JSON includes `convergence_guard: true` and matching `concept_id`.
- **Action (delete)**:  
  `curl -sS -X DELETE "$API_BASE/api/graph/concepts/<concept_id>/convergence-guard"`
- **Expected**: HTTP **200**; `convergence_guard: false`.
- **Edge**: `DELETE` on a concept **without** a guard returns **404** or documented empty state (not **500**).

### Scenario 4 — ROI proof endpoint

- **Action**: `curl -sS "$API_BASE/api/graph/health/roi"`
- **Expected**: HTTP **200**; JSON includes `balance_score_delta`, `split_signals_actioned`, `merge_signals_actioned`, `surface_signals_actioned`, `"spec_ref": "spec-172"`.
- **Edge**: Before any actioning, counters may be **0** but must be **non-negative integers**.

### Scenario 5 — Error handling (bad input / missing resource)

- **Setup**: Random non-existent `concept_id` string.
- **Action**: `curl -sS -X POST "$API_BASE/api/graph/concepts/does-not-exist-00000000/convergence-guard" -H 'Content-Type: application/json' -d '{"reason":"x","set_by":"y"}'`
- **Expected**: HTTP **404** or **422** with JSON `detail` explaining missing concept — **not** HTTP 500.
- **Edge**: POST with **invalid JSON** body to `/api/graph/health/compute` returns **422** Unprocessable Entity (if body is sent malformed).

## Research Inputs (Required)

- `2026-03-28` — [`specs/fractal-self-balance.md`](./fractal-self-balance.md) — Canonical API contract and metrics for this feature.
- `2026-03-28` — [`specs/166-universal-node-edge-layer.md`](./166-universal-node-edge-layer.md) — Graph vocabulary and node/edge semantics the health pass observes.
- `2026-03-28` — [`specs/172-fractal-self-balance.md`](./172-fractal-self-balance.md) — Alternate numbered spec line; keep cross-links consistent when consolidating.

## Task Card

```yaml
goal: Ship diagnostic self-balancing graph signals (health, compute, guards, ROI) per spec-172 without autonomous graph edits.
files_allowed:
  - api/app/routers/graph_health.py
  - api/app/services/graph_health_service.py
  - api/app/models/graph_health.py
  - api/app/db/graph_health_repo.py
  - api/tests/test_fractal_self_balance.py
done_when:
  - All Verification Scenarios in this document pass against staging or production
  - pytest api/tests/test_fractal_self_balance.py passes
commands:
  - curl -sS "$API_BASE/api/graph/health"
  - curl -sS -X POST "$API_BASE/api/graph/health/compute" -H 'Content-Type: application/json' -d '{}'
  - cd api && pytest -q tests/test_fractal_self_balance.py
constraints:
  - No automatic split/merge graph mutations in MVP
  - Do not modify tests to force green; fix implementation
```

## Verification

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
# When implementing:
cd api && pytest -q tests/test_fractal_self_balance.py
```

## Out of Scope

- Autonomous restructuring (split/merge/reparent) without human approval.
- Scheduled background recompute (may be added later; explicit `POST` is the MVP refresh).
- Web UI required for acceptance (optional follow-up).

## Risks and Assumptions

- **Assumption**: Engagement-like weights used for entropy/concentration correlate with “energy” in the product sense; if not, metrics may look noisy. **Mitigation**: document weight source in implementation; allow config tuning.
- **Risk**: Thresholds (`SPLIT_THRESHOLD`, concentration) may be wrong for small graphs. **Mitigation**: ship with conservative defaults; minimum graph size gates in service layer.
- **Risk**: Reviewers may overuse convergence guards. **Mitigation**: audit trail fields (`set_by`, `reason`) and ROI counters.

## Known Gaps and Follow-up Tasks

- CLI commands `cc graph health` / `cc graph compute` — not yet standardized; add under CLI spec when HTTP is stable.
- Web dashboard `/graph/balance` — design task when API usage patterns are known.
- Consolidate `spec-172`, `172-fractal-self-balance.md`, and `fractal-self-balance.md` into a single canonical file if duplicate drift appears.

## Failure / Retry Reflection

- **Failure mode**: Production returns 404 for `/api/graph/*` if deploy not rolled out. **Next action**: verify OpenAPI inventory and deploy order per `docs/DEPLOY.md`.
- **Failure mode**: `compute` is slow on large graphs. **Next action**: add pagination or sampled subgraph option in a follow-up spec (not MVP).
