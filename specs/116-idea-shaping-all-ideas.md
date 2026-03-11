# Idea Shaping: All Ideas — Current State, Manifestation Delta, and Flow Design

Companion to spec 116. Applies the seven-lens Idea Shaping framework to every idea
in the portfolio and identifies what's built vs what's missing. Includes measurable ROI
for every gap and OpenClaw-inspired design principles for reducing friction and increasing
collective rewards.

---

## 1. portfolio-governance

> Unified idea portfolio governance

### Break it apart

**Deconstruct**
- (a) Ideas CRUD API with free energy scoring — **done**
- (b) Structured SQL persistence with bootstrap — **done**
- (c) Portfolio summary aggregation — **done**
- (d) Leading indicator tracking (which metrics predict idea success?) — **not started**
- (e) Idea lifecycle transitions (raw → validated) with evidence — **not started**

**Select** — (a–c) shipped and validated. (d) is the highest-value remaining piece — without leading indicators, the portfolio tracks outputs but can't predict which ideas will succeed. (e) depends on the intake process from this spec.

**Sequence** — (d) depends on runtime telemetry data (spec 049, done). (e) depends on this spec's Idea Shaping guidance being adopted. Both can proceed now.

**Stakes** — The portfolio exists but doesn't learn. Every week without leading indicators is a week where the ranking is static intuition, not measured signal. Owner: whoever governs the idea portfolio.

### Make it actionable

**Context to read** — `specs/053-ideas-prioritization.md`, `api/app/services/idea_service.py`, `api/app/services/idea_registry_service.py`

**Done state** — Portfolio API returns ideas ranked by a score that updates based on measured signals, not just initial estimates. The `actual_value` and `actual_cost` fields reflect real data, not zeros.

**Open questions** — Which leading indicators best represent energy flow to the whole? (Already captured as open_question in the idea itself.)

### Manifestation delta

| Piece | Status | What's missing |
|-------|--------|----------------|
| Ideas CRUD API | done | — |
| SQL persistence | done | — |
| Portfolio summary | done | — |
| Web UI (ideas page) | done | — |
| Leading indicator tracking | not started | Define which runtime/telemetry signals map to `actual_value` updates; automate the feedback loop |
| Idea lifecycle transitions | not started | Wire `intake_status` or equivalent to track idea maturity with evidence |

**Manifestation: partial** → needs (d) and (e) for validated.

---

## 2. oss-interface-alignment

> Align OSS intelligence interfaces with runtime

### Break it apart

**Deconstruct**
- (a) Canonical route registry (machine-readable) — **done**
- (b) Endpoint traceability audit (idea → spec → impl → test) — **done**
- (c) Runtime mapping (deployed routes match declared routes) — **partially done**
- (d) Drift detection (alert when declared ≠ runtime) — **not started**
- (e) Minimum E2E flow proving machine-human interface integrity — **not started**

**Select** — (a–b) shipped. (c) is close. (d) is the payoff — without drift detection, the registry is a snapshot that goes stale. (e) is the proof that the whole chain works end-to-end.

**Sequence** — (d) depends on (a) + runtime telemetry (done). (e) depends on (d) + a defined test flow.

**Stakes** — Every new endpoint added without traceability creates hidden debt. The longer drift goes undetected, the harder reconciliation becomes. Owner: API maintainer.

### Make it actionable

**Context to read** — `specs/050-canonical-route-registry-and-runtime-mapping.md`, `specs/089-endpoint-traceability-coverage.md`, `config/canonical_routes.json`, `api/app/services/route_registry_service.py`

**Done state** — CI runs a drift check that fails if any deployed endpoint isn't in the canonical registry. An E2E test hits the public URL and validates the full chain.

**Open questions** — Which route set is canonical for current milestone? What counts as "minimum" E2E?

### Manifestation delta

| Piece | Status | What's missing |
|-------|--------|----------------|
| Canonical route registry | done | — |
| Endpoint traceability API | done | — |
| Gates UI | done | — |
| Runtime mapping | partial | Default mapping for standard surfaces needs completion |
| Drift detection | not started | CI gate that compares canonical_routes.json to live FastAPI app.routes |
| Minimum E2E flow | not started | Define the flow, write the test, run it against deployed instance |

**Manifestation: partial** → needs (d) and (e) for validated.

---

## 3. coherence-signal-depth

> Increase coherence signal depth with real data

### Break it apart

**Deconstruct**
- (a) Coherence score API with 8 components — **done (stubs)**
- (b) `downstream_impact` from real data — **done**
- (c) `dependency_health` from real data — **done**
- (d) `contributor_diversity` from GitHub data — **not started**
- (e) `activity_cadence` from GitHub data — **not started**
- (f) `community_responsiveness` from GitHub data — **not started**
- (g) `documentation_quality` heuristic — **not started**
- (h) `funding_sustainability` signal — **not started**
- (i) `security_posture` signal — **not started**
- (j) Component weight finalization — **blocked (decision gate)**

**Select** — (d), (e), (f) all depend on GitHub API integration and would move 3 of 6 stub components to real data in one effort. That's the 80/20. (g–i) are lower value and harder to source. (j) is a decision, not implementation.

**Sequence** — GitHub API integration (spec 029) must exist first. Then (d–f) can ship together. (j) can happen in parallel — it's a human decision about weights.

**Stakes** — The coherence score is the product's core claim. Every day it returns 0.5 stubs for 6/8 components is a day the score means almost nothing. This is the credibility gap. Owner: algorithm owner.

### Make it actionable

**Context to read** — `specs/018-coherence-algorithm-spec.md`, `specs/020-sprint-2-coherence-api.md`, `specs/029-github-api-integration.md`, `api/app/services/coherence_service.py`

**Done state** — `GET /api/projects/{eco}/{name}/coherence` returns scores where at least 5/8 components use measured data, not stubs. Component weights are documented and justified.

**Open questions** — What minimal GitHub ingestion yields measurable component uplift? Are weights fixed or per-ecosystem?

### Manifestation delta

| Piece | Status | What's missing |
|-------|--------|----------------|
| Coherence API | done (stubs) | — |
| downstream_impact | done (real) | — |
| dependency_health | done (real) | — |
| contributor_diversity | not started | GitHub API integration → contributor count/distribution |
| activity_cadence | not started | GitHub API → commit frequency, recency |
| community_responsiveness | not started | GitHub API → issue/PR response times |
| documentation_quality | not started | Heuristic: README length, docs/ presence, changelog |
| funding_sustainability | not started | Signal source TBD (OpenCollective? GitHub Sponsors?) |
| security_posture | not started | Signal source TBD (Scorecard? advisories?) |
| Weight finalization | blocked | Decision gate — needs human input |

**Manifestation: none** → needs GitHub integration + 3 components + weights for partial. All 8 + weights for validated.

---

## 4. federated-instance-aggregation

> Federated instance aggregation for contributor-owned deployments

### Break it apart

**Deconstruct**
- (a) Federation contract definition (schema for cross-instance data) — **not started**
- (b) Contributor fork telemetry publishing endpoint — **not started**
- (c) Anti-duplication and trust signals — **not started**
- (d) Aggregation service (merge fork telemetry into shared system) — **not started**
- (e) ROI ranking integration (federated data affects portfolio scores) — **not started**

**Select** — (a) is the foundation — everything else depends on it. Highest value is defining the contract so forks know what to publish. (b) is the minimum viable integration. (c–e) are follow-ups.

**Sequence** — (a) first, then (b), then (c) before (d–e). Nothing currently blocks (a) except design effort.

**Stakes** — Highest `potential_value` in the portfolio (128.0) but zero actual. This idea enables contributor scaling without central bottleneck. The longer it waits, the more the system depends on single-instance deployment. Owner: architecture lead.

### Make it actionable

**Context to read** — `api/app/services/runtime_service.py` (telemetry patterns to replicate), `specs/048-value-lineage-and-payout-attribution.md` (contributor model)

**Done state** — A contributor can fork the repo, run their instance, and `POST` telemetry back to the main instance. The main instance merges it with provenance and it appears in the portfolio.

**Open questions** — What is the minimal federation contract? Which trust signals are required before federated data affects ROI ranking?

### Manifestation delta

| Piece | Status | What's missing |
|-------|--------|----------------|
| Federation contract | not started | Design the schema: what data, what format, what provenance |
| Fork telemetry endpoint | not started | `POST /api/federation/telemetry` or similar |
| Anti-duplication/trust | not started | Dedup logic, contributor identity verification |
| Aggregation service | not started | Merge + reconcile fork data into shared state |
| ROI integration | not started | Update scoring to weight federated signals |

**Manifestation: none** → entirely unbuilt. Needs (a) + (b) for partial.

---

## 5. coherence-network-agent-pipeline

> Evolve autonomous task orchestration, validation gates, and failure recovery

### Break it apart

**Deconstruct**
- (a) Task orchestration API (create, claim, complete tasks) — **done**
- (b) Pipeline status and phase tracking — **done**
- (c) Validation gates (pre-merge checks) — **done**
- (d) Failure recovery signals (detect stuck tasks, auto-retry) — **partial**
- (e) A/B testing of prompts/models — **not started**
- (f) Auto-scheduling of improvement tasks — **not started**

**Select** — (a–c) shipped. (d) is partially addressed by spec 046 (debugging stuck tasks). (e–f) are from pipeline observability Phase 2–6 and represent the next leap — the pipeline optimizing itself.

**Sequence** — (d) can proceed now. (e) depends on metrics infrastructure (Phase 1 done). (f) depends on (e) proving variant effectiveness.

**Stakes** — The agent pipeline runs but doesn't improve itself. Manual intervention is still needed for stuck tasks and prompt tuning. Owner: pipeline maintainer.

### Make it actionable

**Context to read** — `specs/026-pipeline-observability-and-auto-review.md`, `specs/046-agent-debugging-pipeline-stuck-task-hangs.md`, `api/app/services/metrics_service.py`

**Done state** — Pipeline detects stuck tasks within 5 minutes, retries or escalates. Prompt variants are tracked and the best-performing variant is auto-promoted.

**Open questions** — What defines "stuck"? What's the minimum variant sample size for statistical significance?

### Manifestation delta

| Piece | Status | What's missing |
|-------|--------|----------------|
| Task orchestration API | done | — |
| Pipeline status/phases | done | — |
| Validation gates | done | — |
| Failure recovery | partial | Auto-detection of stuck tasks, retry logic |
| A/B prompt testing | not started | Variant tagging, metrics aggregation by variant |
| Auto-scheduling | not started | Task generation from metric signals |

**Manifestation: partial** → needs (d) complete + (e) for validated.

---

## 6. coherence-network-api-runtime

> Ensure public API behavior, runtime telemetry, and deployment state stay in sync

### Break it apart

**Deconstruct**
- (a) Runtime telemetry middleware (auto-capture API metrics) — **done**
- (b) Runtime events API (ingest + query) — **done**
- (c) Per-endpoint summary aggregation — **done**
- (d) Deployment state sync (Railway/CI state matches API state) — **partial**
- (e) Public E2E contract validation — **partial**

**Select** — (a–c) shipped. (d–e) are the gap — the system captures telemetry but doesn't validate that the deployed version matches what the API declares.

**Sequence** — (d) depends on deployment infrastructure access. (e) depends on canonical routes (done) and a live test runner.

**Stakes** — Runtime parity is how users trust the system. A mismatch between docs and behavior is a bug that erodes confidence silently. Owner: ops/deploy lead.

### Make it actionable

**Context to read** — `specs/055-runtime-intent-and-public-e2e-contract-gate.md`, `api/app/services/runtime_service.py`, `api/app/routers/runtime.py`

**Done state** — CI gate that hits the deployed URL, validates response shapes match spec, and fails the deploy if they don't.

**Open questions** — How to access Railway deployment state programmatically? Which endpoints are public-facing vs internal?

### Manifestation delta

| Piece | Status | What's missing |
|-------|--------|----------------|
| Telemetry middleware | done | — |
| Runtime events API | done | — |
| Endpoint summary | done | — |
| Web views summary | done | — |
| Deployment state sync | partial | Railway/CI state comparison not automated |
| Public E2E validation | partial | Contract test exists but not wired to deploy gate |

**Manifestation: partial** → needs (d) + (e) automated for validated.

---

## 7. coherence-network-value-attribution

> Track value lineage from idea to payout with measurable contribution attribution

### Break it apart

**Deconstruct**
- (a) Value lineage CRUD API — **done**
- (b) Usage event tracking — **done**
- (c) ROI computation (measured_value / estimated_cost) — **done**
- (d) Payout attribution by stage + objective weights — **done**
- (e) Contributor payout UI — **not started**
- (f) Actual payout execution — **not started**

**Select** — (a–d) shipped and tested. (e) is the human-facing piece that makes attribution visible. (f) is a business decision, not engineering.

**Sequence** — (e) depends on (a–d) (done) and web framework (done). Can proceed now. (f) depends on legal/business decisions.

**Stakes** — Attribution exists but is invisible to contributors. Without a UI, the data doesn't create the incentive it's designed to create. Owner: product lead.

### Make it actionable

**Context to read** — `specs/048-value-lineage-and-payout-attribution.md`, `api/app/services/value_lineage_service.py`, `api/app/routers/value_lineage.py`

**Done state** — Contributors can visit a page that shows their attributed value across ideas, with breakdown by stage and objective.

**Open questions** — Is payout in tokens, credits, or real currency? What's the minimum attribution threshold to display?

### Manifestation delta

| Piece | Status | What's missing |
|-------|--------|----------------|
| Value lineage API | done | — |
| Usage event tracking | done | — |
| ROI computation | done | — |
| Payout attribution | done | — |
| Contributor payout UI | not started | Web page showing per-contributor attribution |
| Payout execution | not started | Business/legal decision, then payment integration |

**Manifestation: partial** → needs (e) for validated. (f) is out of scope for MVP.

---

## 8. coherence-network-web-interface

> Keep human-facing navigation and detail views aligned with machine-facing inventory

### Break it apart

**Deconstruct**
- (a) Global navigation aligned with API resources — **done**
- (b) Search-first home page — **done**
- (c) Ideas gallery page — **done**
- (d) Portfolio cockpit with questions — **done**
- (e) Specs browser page — **done**
- (f) Gates/traceability page — **done**
- (g) Live refresh / real-time updates — **partial**
- (h) Detail views for individual ideas/specs — **partial**

**Select** — (a–f) shipped. (g–h) are polish — the core pages exist but some lack detail drill-down and live data refresh.

**Sequence** — (g) and (h) are independent and can proceed in parallel.

**Stakes** — The web interface is the primary human touchpoint. Incomplete detail views mean operators fall back to API calls or file reads, defeating the purpose of the UI. Owner: frontend contributor.

### Make it actionable

**Context to read** — `specs/076-ui-alignment-overhaul.md`, `specs/091-web-live-refresh-and-link-parity.md`, `specs/092-web-refresh-reliability-and-route-completeness.md`, `web/app/` (all page.tsx files)

**Done state** — Every API resource has a corresponding detail page. Portfolio and ideas pages auto-refresh on a reasonable interval.

**Open questions** — What refresh interval is appropriate? Should detail pages be SSR or client-fetched?

### Manifestation delta

| Piece | Status | What's missing |
|-------|--------|----------------|
| Global navigation | done | — |
| Search-first home | done | — |
| Ideas gallery | done | — |
| Portfolio cockpit | done | — |
| Specs browser | done | — |
| Gates/traceability | done | — |
| Live refresh | partial | Auto-refresh interval not wired on all pages |
| Detail views | partial | Individual idea/spec detail pages incomplete |

**Manifestation: partial** → needs (g) + (h) for validated.

---

## 9. deployment-gate-reliability

> Harden deploy and validation gates so failures are detected quickly and recovered automatically

### Break it apart

**Deconstruct**
- (a) CI pipeline with test + build gates — **done**
- (b) Spec quality validator in CI — **done**
- (c) Public E2E smoke test — **partial**
- (d) Auto-rollback on gate failure — **not started**
- (e) Gate failure alerting — **not started**

**Select** — (a–b) shipped. (c) exists as specs but isn't fully automated. (d) is the highest-value gap — without auto-rollback, a broken deploy stays broken until a human notices.

**Sequence** — (c) depends on deployed URL access (available). (d) depends on Railway/deploy API. (e) can use any notification channel.

**Stakes** — Deploy failures that aren't auto-detected cost contributor trust and user experience. The window between "broken" and "noticed" is the risk. Owner: ops lead.

### Make it actionable

**Context to read** — `specs/004-ci-pipeline.md`, `specs/095-public-e2e-flow-gate-automation.md`, `specs/096-provider-readiness-contract-automation.md`, `specs/051-release-gates.md`

**Done state** — A deploy that breaks a gate is auto-rolled back within 5 minutes. An alert fires to the ops channel.

**Open questions** — Does Railway support programmatic rollback? What's the alerting channel (Slack, Telegram, email)?

### Manifestation delta

| Piece | Status | What's missing |
|-------|--------|----------------|
| CI pipeline | done | — |
| Spec quality validator | done | — |
| Public E2E smoke test | partial | Automated but not wired to deploy gate |
| Auto-rollback | not started | Railway API integration for rollback on failure |
| Gate failure alerting | not started | Notification on gate failure |

**Manifestation: partial** → needs (c) wired + (d) for validated.

---

## Portfolio Summary

| Idea | Manifestation | Built | Remaining | Highest-value next piece |
|------|--------------|-------|-----------|--------------------------|
| portfolio-governance | partial | 4/6 | 2 | Leading indicator tracking |
| oss-interface-alignment | partial | 3/6 | 3 | Drift detection CI gate |
| coherence-signal-depth | none | 3/10 | 7 | GitHub API → 3 components |
| federated-instance-aggregation | none | 0/5 | 5 | Federation contract design |
| coherence-network-agent-pipeline | partial | 3/6 | 3 | Stuck task auto-recovery |
| coherence-network-api-runtime | partial | 4/6 | 2 | Deploy state sync automation |
| coherence-network-value-attribution | partial | 4/6 | 2 | Contributor payout UI |
| coherence-network-web-interface | partial | 6/8 | 2 | Detail views + live refresh |
| deployment-gate-reliability | partial | 2/5 | 3 | Auto-rollback |

---

## Stakes & Measurable ROI

Every idea below has a concrete measurement plan: **what** to measure, **where** the data lives,
**when** to measure it, and **what good looks like**. ROI is expressed as the ratio of
value delivered to effort invested, using signals the system already captures or can capture
with minimal new instrumentation.

---

### 1. portfolio-governance — Stakes & ROI

**What's at stake:** The portfolio ranks ideas by free energy score, but `actual_value` is 0.0 for most ideas. The ranking is based on estimates, not evidence. Every decision made from this ranking carries the risk of being wrong in a way that's invisible.

**Measurable ROI:**

| Metric | Where to measure | When | Target | Current |
|--------|-----------------|------|--------|---------|
| Ideas with `actual_value > 0` | `GET /api/ideas` → count where `actual_value > 0` | Weekly | ≥6 of 9 | 2 of 9 |
| Ranking accuracy | Compare free_energy_score ranking to actual outcome ranking after 30 days | Monthly | Spearman ρ ≥ 0.6 | Unmeasured |
| Portfolio value gap trend | `GET /api/ideas` → `summary.total_value_gap` | Weekly | Decreasing week-over-week | Static |
| Time from idea to first `actual_value` update | Timestamp of idea creation vs first PATCH with `actual_value > 0` | Per idea | ≤14 days | Unknown |

**How to measure ranking accuracy:**
1. Snapshot the free_energy_score ranking on day 0
2. After 30 days, rank ideas by actual value delivered (commits, runtime events, value-lineage usage)
3. Compute Spearman rank correlation between predicted and actual
4. Data sources: `GET /api/ideas` (scores), `GET /api/runtime/ideas/summary` (actual usage), `GET /api/value-lineage/links` (value events)

**ROI estimate:** If leading indicators move 2 ideas from wrong-priority to right-priority per month, and each idea's `potential_value` averages 85, the redirected value is ~170 points per month vs ~4 hours of instrumentation work.

---

### 2. oss-interface-alignment — Stakes & ROI

**What's at stake:** Every new endpoint added without traceability is invisible technical debt. The canonical registry is a snapshot — without drift detection, it decays silently until something breaks in production.

**Measurable ROI:**

| Metric | Where to measure | When | Target | Current |
|--------|-----------------|------|--------|---------|
| Endpoint traceability coverage | `GET /api/inventory/endpoint-traceability` → `summary.fully_traced / summary.total_endpoints` | Per deploy | 100% | Check current |
| Drift incidents | Count of times deployed routes ≠ canonical_routes.json | Per deploy (CI) | 0 | Unmeasured |
| Mean time to detect drift | Timestamp of deploy vs timestamp of drift alert | Per incident | ≤5 min | No alerting |
| E2E flow pass rate | Public E2E test result | Per deploy | 100% | Not wired |

**How to measure drift:**
1. In CI, after deploy: `python -c "from app.main import app; print([r.path for r in app.routes])"` → compare to `canonical_routes.json`
2. Any mismatch = drift incident. Log the diff.
3. Data source: CI logs + `canonical_routes.json`

**ROI estimate:** One undetected drift bug costs 2–8 hours of debugging (based on typical incident). Drift detection CI gate costs ~2 hours to build. Pays for itself on first prevented incident.

---

### 3. coherence-signal-depth — Stakes & ROI

**What's at stake:** The coherence score is the product's core value proposition. 6 of 8 components return 0.5 (stub). The score is currently 75% fiction. Every user who sees it and acts on it is making decisions based on fabricated data.

**Measurable ROI:**

| Metric | Where to measure | When | Target | Current |
|--------|-----------------|------|--------|---------|
| Components with real data | `GET /api/projects/{eco}/{name}/coherence` → count non-0.5 components | Per release | ≥5 of 8 | 2 of 8 |
| Score variance across projects | Std dev of coherence scores across all tracked projects | Weekly | σ ≥ 0.15 | σ ≈ 0 (all ~0.5) |
| GitHub API call success rate | Log GitHub API responses | Per fetch | ≥95% | N/A |
| User trust signal | Do users return to check scores? `GET /api/runtime/endpoints/summary` for `/api/projects/*/coherence` | Weekly | Increasing calls/week | Baseline TBD |

**How to measure score variance:**
1. Query coherence for 10+ projects
2. Compute standard deviation of `overall_score`
3. If σ < 0.05, the score doesn't differentiate — it's noise, not signal
4. Data source: batch query to coherence endpoint, store in metrics

**ROI estimate:** GitHub API integration (spec 029) enables 3 components at once. Estimated cost: 16 hours. Moves score from 25% real to 62.5% real. The credibility gain is existential — without it, the core product claim is hollow.

---

### 4. federated-instance-aggregation — Stakes & ROI

**What's at stake:** Highest potential_value (128.0) and zero actual. The system is single-instance. Every contributor must use the central deployment. This limits throughput to one team's infrastructure and creates a single point of failure.

**Measurable ROI:**

| Metric | Where to measure | When | Target | Current |
|--------|-----------------|------|--------|---------|
| Fork count (contributors running own instances) | GitHub forks with activity + federation telemetry POSTs | Monthly | ≥3 active forks | 0 |
| Federated telemetry events received | `POST /api/federation/telemetry` count | Weekly | ≥10 events/week | Endpoint doesn't exist |
| Contributor throughput (tasks completed/week) | `GET /api/agent/metrics` → tasks per week | Weekly | 2x current after federation | Baseline TBD |
| Data duplication rate | Dedup logic rejection rate | Per event | ≤5% duplicates | N/A |

**How to measure contributor throughput impact:**
1. Baseline: tasks completed per week for 4 weeks before federation
2. After federation: same metric
3. Compare. If throughput doesn't increase, federation isn't creating value.
4. Data source: `GET /api/agent/metrics` → `success_rate.completed_count` over time

**ROI estimate:** This is a multiplier, not an increment. If 3 contributors each run a fork and produce 5 tasks/week, that's 15 tasks/week from infrastructure that costs them, not you. Estimated design cost: 20 hours. The ROI scales with adoption.

---

### 5. coherence-network-agent-pipeline — Stakes & ROI

**What's at stake:** The pipeline runs tasks but doesn't recover from failures or optimize itself. Stuck tasks require manual intervention. Prompt quality is static — no experimentation, no learning.

**Measurable ROI:**

| Metric | Where to measure | When | Target | Current |
|--------|-----------------|------|--------|---------|
| Stuck task detection time | Time from task hang to detection alert | Per incident | ≤5 min | Manual (hours?) |
| Task success rate | `GET /api/agent/metrics` → `success_rate` | Weekly | ≥85% | Check current |
| Mean task duration | `GET /api/agent/metrics` → `execution_time.p50` | Weekly | Decreasing trend | Baseline TBD |
| Manual interventions per week | Count of human-triggered task retries or fixes | Weekly | ≤1 | Unknown |
| Prompt variant win rate | A/B metrics: variant success rate vs baseline | Per experiment | Statistically significant (p<0.05) | No experiments |

**How to measure stuck task cost:**
1. Tag each manual intervention with timestamp and duration
2. Sum hours/week spent on manual pipeline fixes
3. That's the current cost of not having auto-recovery
4. Data source: ops log or `POST /api/runtime/events` with type `manual_intervention`

**ROI estimate:** If manual intervention takes 1 hour/week and auto-recovery eliminates 80% of cases, that's 40 hours/year saved. Build cost: ~8 hours. 5x return in year one.

---

### 6. coherence-network-api-runtime — Stakes & ROI

**What's at stake:** The API captures telemetry but doesn't validate that the deployed version matches what it declares. A mismatch means the docs lie, and users calling the API get unexpected behavior.

**Measurable ROI:**

| Metric | Where to measure | When | Target | Current |
|--------|-----------------|------|--------|---------|
| Deploy-to-contract match rate | E2E contract test pass/fail per deploy | Per deploy | 100% | Not automated |
| API uptime | `GET /api/health` success rate from external monitor | Continuous | ≥99.5% | Unmeasured externally |
| Response shape violations | Contract test: response JSON matches Pydantic model | Per deploy | 0 violations | Not tested |
| Telemetry coverage | `GET /api/runtime/endpoints/summary` → endpoints with ≥1 event / total endpoints | Weekly | 100% | Check current |

**How to measure deploy-to-contract match:**
1. After each deploy, run: `pytest api/tests/ -k "contract or e2e"` against the live URL
2. Any failure = contract violation. Log the diff between expected and actual response.
3. Data source: CI pipeline output

**ROI estimate:** One contract violation caught in CI vs production saves 1–4 hours of incident response. Gate costs ~3 hours to build. Pays for itself immediately.

---

### 7. coherence-network-value-attribution — Stakes & ROI

**What's at stake:** Attribution math exists but contributors can't see it. Invisible attribution creates no incentive. The whole payout system is inert until humans can see their contributions.

**Measurable ROI:**

| Metric | Where to measure | When | Target | Current |
|--------|-----------------|------|--------|---------|
| Contributors viewing their attribution | `GET /api/runtime/web/views/summary` for `/contributors/*` | Weekly | ≥3 unique viewers/week | 0 (no page) |
| Value lineage links created | `GET /api/value-lineage/links` count | Weekly | ≥1 new link/week | Check current |
| Attribution disputes | Manual reports of "my contribution isn't shown" | Monthly | ≤1 | N/A |
| Contributor retention | Contributors active in week N who are also active in week N+4 | Monthly | ≥60% | Baseline TBD |

**How to measure attribution visibility impact:**
1. Before UI: count contributor return rate (4-week retention)
2. After UI: same metric
3. Hypothesis: visibility increases retention by ≥20%
4. Data source: `GET /api/runtime/web/views/summary`, contributor activity logs

**ROI estimate:** UI build cost: ~8 hours. If it retains even 1 additional contributor who produces 3 tasks/week, the value far exceeds the build cost within a month.

---

### 8. coherence-network-web-interface — Stakes & ROI

**What's at stake:** The web interface is the primary human touchpoint. Missing detail views force operators back to API calls or file reads. Stale data (no live refresh) means decisions based on old information.

**Measurable ROI:**

| Metric | Where to measure | When | Target | Current |
|--------|-----------------|------|--------|---------|
| Pages with detail view | Count of routes with `/{id}` detail pages vs API resources | Per release | 100% coverage | Check current |
| Page views per session | `GET /api/runtime/web/views/summary` → avg views per unique session | Weekly | ≥3 pages/session | Baseline TBD |
| Bounce rate (single-page sessions) | Sessions with exactly 1 page view / total sessions | Weekly | ≤40% | Baseline TBD |
| Data freshness | Max age of displayed data (time since last fetch) | Per page | ≤60 seconds | No auto-refresh |

**How to measure UI completeness:**
1. List all API resources: ideas, specs, projects, contributors, assets, lineage, etc.
2. Check which have a `/resource/{id}` detail page in `web/app/`
3. Coverage = detail pages / API resources
4. Data source: file system scan of `web/app/*/[id]/page.tsx` vs `api/app/routers/*.py`

**ROI estimate:** Each missing detail view costs ~5 minutes per operator lookup (falling back to curl). If operators do 10 lookups/week across missing pages, that's ~50 min/week. Detail pages cost ~3 hours each to build. Break-even in ~4 weeks per page.

---

### 9. deployment-gate-reliability — Stakes & ROI

**What's at stake:** A broken deploy stays broken until a human notices. The window between "broken" and "noticed" is pure downtime risk. For an OSS intelligence platform, downtime means stale data and lost trust.

**Measurable ROI:**

| Metric | Where to measure | When | Target | Current |
|--------|-----------------|------|--------|---------|
| Mean time to detect failure (MTTD) | Timestamp of failed deploy vs first alert | Per incident | ≤5 min | Manual (unknown) |
| Mean time to recover (MTTR) | Timestamp of alert vs successful rollback | Per incident | ≤10 min | Manual (unknown) |
| Deploys with passing E2E gate | E2E test pass count / total deploys | Per deploy | 100% | Not gated |
| Rollback count | Auto-rollbacks triggered / total deploys | Monthly | ≤5% of deploys | 0 (no auto-rollback) |

**How to measure MTTD and MTTR:**
1. Log every deploy with timestamp: `deploy_started_at`, `gate_checked_at`, `alert_sent_at`, `rollback_completed_at`
2. MTTD = `alert_sent_at - deploy_started_at`
3. MTTR = `rollback_completed_at - alert_sent_at`
4. Data source: CI/deploy pipeline logs, Railway API events

**ROI estimate:** Average downtime incident costs 1–3 hours of engineering attention + lost user trust. Auto-rollback eliminates ~80% of incidents. Build cost: ~6 hours. Pays for itself on the first prevented outage.

---

## Portfolio ROI Summary

| Idea | Est. build cost (hrs) | Value unlocked | Payback | Priority signal |
|------|----------------------|----------------|---------|-----------------|
| coherence-signal-depth | 16 | Core product credibility | Existential | **Do first** — score is 75% fiction |
| deployment-gate-reliability | 6 | Downtime prevention | 1 incident | **Do first** — cheap, high safety |
| oss-interface-alignment | 2 | Invisible debt prevention | 1 incident | Quick win |
| coherence-network-api-runtime | 3 | Contract trust | 1 incident | Quick win |
| coherence-network-agent-pipeline | 8 | 40 hrs/year saved | ~10 weeks | Medium-term |
| coherence-network-value-attribution | 8 | Contributor retention | ~4 weeks | Medium-term |
| portfolio-governance | 4 | Decision accuracy | ~4 weeks | Medium-term |
| coherence-network-web-interface | 6 | Operator efficiency | ~4 weeks/page | Ongoing |
| federated-instance-aggregation | 20 | Throughput multiplier | Scales with adoption | Long-term bet |

---

## Learning from OpenClaw: Reducing Friction, Increasing Flow, Rewarding the Collective

[OpenClaw](https://github.com/openclaw/clawhub) grew to 160K+ GitHub stars and 300K+ users
in months by making contribution nearly frictionless: a skill is a single SKILL.md file with
YAML frontmatter and natural language instructions. No compilation, no SDK, no approval queue.
But OpenClaw's explosive growth also exposed a critical gap: **no governance framework, no
contributor reward system, and a security crisis** (800+ malicious skills, 42K exposed gateways).

Coherence Network can learn from both the success and the failure.

### What OpenClaw got right (adopt)

| OpenClaw pattern | Coherence equivalent | Current state | Gap |
|-----------------|---------------------|---------------|-----|
| **SKILL.md** — single file, YAML + markdown, zero friction to contribute | **Spec template** — single file, structured markdown | Template exists but 13 required sections is high friction | Simplify: the Idea Shaping section already reduces cognitive load; consider a "light spec" format for small changes |
| **ClawHub** — centralized discovery, decentralized contribution | **Ideas API + specs/** — centralized prioritization, anyone can submit | Ideas API exists but no public submission flow | Add `POST /api/ideas` for external contributors to propose ideas |
| **Embedding-based search** — find skills by meaning, not keywords | **Search-first home page** — search across projects | Search exists but doesn't search specs/ideas | Extend search to cover `specs/` and `GET /api/ideas` content |
| **One-line install** — `npx openclaw` and you're running | **Quick start** — `docker compose up` or manual setup | Setup documented but multi-step | Reduce to single command for contributor onboarding |

### What OpenClaw got wrong (avoid)

| OpenClaw failure | Root cause | Coherence safeguard |
|-----------------|------------|---------------------|
| 800+ malicious skills in ClawHub | No review gate, no trust scoring | Spec quality validator + CI gates already enforce structure |
| 42K exposed gateways | No deployment governance | Railway deploy gates + E2E validation (partially built) |
| No contributor rewards | No value tracking | **Value lineage + payout attribution already exists** — this is Coherence's structural advantage |
| Shadow AI proliferation | No audit trail | Runtime telemetry + commit evidence already captures provenance |

### Coherence's advantage: the reward loop OpenClaw is missing

OpenClaw has contributors but no way to reward them. Coherence has:

1. **Value lineage** (`POST /api/value-lineage/links`) — traces value from idea → spec → implementation → usage
2. **Payout attribution** (`POST /api/value-lineage/links/{id}/payout-preview`) — splits credit by stage (idea 10%, research 20%, spec 20%, implementation 50%, review 20%) and by objective (coherence 35%, energy flow 20%, awareness 20%, friction relief 15%, balance 10%)
3. **Free energy scoring** — prioritizes ideas by `(value × confidence) / (cost + risk)`

The gap: **this loop is invisible**. Contributors can't see their attribution. The math exists but the feedback doesn't flow.

### Design principles for flow (from both frameworks)

**1. Contribution should take less time than deciding to contribute.**
- Light spec format: Purpose + 3 requirements + done state. Skip the other 10 sections for small changes.
- Idea submission: one API call or one markdown file, not a full spec.
- Remove friction: if a contributor has to ask "where do I start?", the onboarding failed.

**2. Every contribution should be immediately visible.**
- Contributor payout UI (gap in `coherence-network-value-attribution`)
- Real-time portfolio dashboard showing contribution flow
- Runtime telemetry showing which contributions are being used

**3. Governance should accelerate flow, not block it.**
- Gates say "yes, and here's what to fix" not "no, go away"
- Validator warnings, not errors, for advisory sections
- Auto-fix suggestions: if a spec fails validation, show exactly what's missing
- Trust scoring: contributors who pass gates consistently earn faster review

**4. Rewards should be proportional, transparent, and timely.**
- Attribution visible within 24 hours of merge
- Stage weights public and auditable
- Value gap visible per idea — contributors can see where the opportunity is
- Standing question on every idea: "how can this measurement be improved?"

**5. The system should learn from its own friction.**
- Measure: time from idea submission to first spec draft
- Measure: time from spec draft to passing tests
- Measure: number of review cycles before merge
- Friction report: `GET /api/friction` or `specs/050-friction-analysis.md` already specced
- Auto-generate tasks from friction signals (pipeline observability Phase 6)

### Concrete next actions from this analysis

| Action | Idea it serves | Effort | Impact on flow |
|--------|---------------|--------|----------------|
| Build contributor payout UI | value-attribution | 8 hrs | Makes the reward loop visible — existential for contributor retention |
| Add `POST /api/ideas` for public submission | portfolio-governance | 4 hrs | Removes the biggest contribution barrier |
| Create "light spec" format (3-section minimum) | all | 2 hrs | Cuts spec authoring time by 60% for small changes |
| Extend search to specs/ideas | web-interface | 4 hrs | Contributors find where to help without browsing 100+ files |
| Publish stage weights in UI | value-attribution | 2 hrs | Transparency → trust → more contributions |
| Auto-suggest spec fixes on validation failure | portfolio-governance | 4 hrs | Gate becomes a guide, not a wall |
| Measure contribution cycle time (idea → merge) | agent-pipeline | 3 hrs | First friction metric — baseline for improvement |

### Branch cleanup needed

55 unmerged branches were audited. 7 clean branches merged into this PR.
44 branches have merge conflicts (most are 700+ commits behind main).
4 remaining clean branches are stale duplicates or bot artifacts.

**Branches merged in this PR:**
- `cursor/development-environment-setup-2cf2` — docs update
- `codex/disable-vercel-pr-deploys` — Vercel deploy policy
- `codex/fix-external-tools-audit` — audit stability
- `codex/fix-runtime-persistence-ready` — runtime telemetry DB fix
- `codex/20260217-endpoint-usage-metrics-complete` — route registry loading
- `codex/runner-validation-artifact-20260219c` — validation artifacts
- `codex/runner-soak-validation-20260219b` — soak test artifacts

**Branches recommended for deletion** (conflicted, stale, superseded):

The remaining 48 branches are all from Feb 13–20 and 700+ commits behind main.
Most represent work that was either:
- Superseded by later branches (e.g., `ci-unblock-workflows` vs `ci-unblock-workflows-v2`)
- Completed via different PRs on main
- Bot checkpoint artifacts with no mergeable value

Recommended: delete all `codex/*` branches older than 2026-02-20 that have merge conflicts.
This reduces branch noise from 55 to ~3 active branches.
