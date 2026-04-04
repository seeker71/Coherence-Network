# Spec Index

59 active specs across 4 domains. 150+ archived in `docs/specs-archive/`.

## How to find what you need

1. Find the spec number/slug below
2. Read `specs/{slug}.md` — frontmatter has `idea_id`, `status`, `source:` (files + symbols)
3. Query `GET /api/spec-registry/{slug}` for value/cost/ROI data
4. Find parent idea via `GET /api/ideas/{idea_id}` or `ideas/{idea_id}.md`

---

## 1. Idea Realization (Core Mission)

The system that tracks ideas from inception to measurable impact.

### Idea Lifecycle

| Spec | Title | Status |
|------|-------|--------|
| 053 | [Ideas Prioritization (free energy scoring)](053-ideas-prioritization.md) | done |
| 138 | [Idea Lifecycle Management (stages: none→specced→implementing→testing→reviewing→complete)](138-idea-lifecycle-management.md) | active |
| 176 | [Idea Lifecycle Closure (exit task-generation pool on complete)](176-idea-lifecycle-closure.md) | active |
| 117 | [Idea Hierarchy — Super/Child Ideas](117-idea-hierarchy-super-child.md) | in progress |
| 120 | [Super-Idea Rollup Criteria](120-super-idea-rollup-criteria.md) | active |
| 158 | [Idea Right-Sizing (split bloated / merge nano ideas)](158-idea-right-sizing.md) | active |
| 181 | [Idea Dual Identity (UUID + human slug)](181-idea-dual-identity.md) | active |

### Contributions and Value

| Spec | Title | Status |
|------|-------|--------|
| 048 | [Contributions API (time, effort, code tracking)](048-contributions-api.md) | done |
| 048 | [Value Lineage and Payout Attribution (idea→spec→impl→usage→payout chain)](048-value-lineage-and-payout-attribution.md) | active |
| 049 | [Distribution Engine (fair value distribution by coherence scores)](049-distribution-engine.md) | done |
| 052 | [Assets API (code, models, content, data)](052-assets-api.md) | done |
| 083 | [Task Claim Tracking and ROI De-duplication](083-task-claim-tracking-and-roi-dedupe.md) | done |
| 086 | [Normalize GitHub Commit Cost Estimation](086-normalize-github-commit-cost-estimation.md) | done |
| 094 | [Contributor Onboarding and Governed Change Flow](094-contributor-onboarding-and-governed-change-flow.md) | active |

### Economics and Measurement

| Spec | Title | Status |
|------|-------|--------|
| 119 | [Coherence Credit (CC) — Internal Currency](119-coherence-credit-internal-currency.md) | done |
| 124 | [CC Economics and Value Coherence](124-cc-economics-and-value-coherence.md) | in progress |
| 114 | [MVP Cost Tracking and Acceptance Proof](114-mvp-cost-and-acceptance-proof.md) | active |
| 115 | [Grounded Cost and Value Measurement (real signals → A/B ROI)](115-grounded-cost-value-measurement.md) | done |
| 116 | [Grounded Idea Portfolio Metrics](116-grounded-idea-portfolio-metrics.md) | done |
| 126 | [Portfolio Governance Effectiveness](126-portfolio-governance-effectiveness.md) | active |

---

## 2. Agent Pipeline (Execution Engine)

The engine that turns ideas into working software.

### Core Pipeline

| Spec | Title | Status |
|------|-------|--------|
| 002 | [Agent Orchestration API (task submission, routing, status)](002-agent-orchestration-api.md) | done |
| 005 | [Project Manager Pipeline (spec→impl→test→review cycle)](005-project-manager-pipeline.md) | done |
| 139 | [Agent Pipeline — umbrella spec](139-coherence-network-agent-pipeline.md) | active |
| 026 | [Pipeline Observability and Auto-Review](026-pipeline-observability-and-auto-review.md) | partial |
| 032 | [Attention Heuristics in Pipeline Status](032-attention-heuristics-pipeline-status.md) | done |
| 159 | [Split Review/Deploy/Verify Phases](159-split-review-deploy-verify-phases.md) | active |

### Reliability and Self-Healing

| Spec | Title | Status |
|------|-------|--------|
| 113 | [Failed Task Diagnostics Contract (error_summary + error_category)](113-failed-task-diagnostics-contract.md) | done |
| 114 | [Auto-Heal from Diagnostics](114-auto-heal-from-diagnostics.md) | done |
| 125 | [Incident Response and Self-Healing](125-incident-response-and-self-healing.md) | active |
| 169 | [Smart Reap (diagnose/resume stuck tasks)](169-smart-reap.md) | active |
| 186 | [Data-Driven Timeout and Resume](186-data-driven-timeout-resume.md) | active |
| 047 | [Heal Completion and Issue Resolution](047-heal-completion-issue-resolution.md) | partial |
| stale-task-reaper | [Stale Task Reaper](stale-task-reaper.md) | active |
| task-deduplication | [Task Deduplication](task-deduplication.md) | active |

### Optimization

| Spec | Title | Status |
|------|-------|--------|
| 074 | [Tool Failure Awareness (cost without gain)](074-tool-failure-awareness.md) | active |
| 112 | [Prompt A/B ROI Measurement](112-prompt-ab-roi-measurement.md) | done |
| 113 | [Provider Usage Coalescing + Timeout Resilience](113-provider-usage-coalescing-timeout-resilience.md) | active |
| 127 | [Cross-Task Outcome Correlation](127-cross-task-outcome-correlation.md) | active |
| 135 | [Provider Health Alerting](135-provider-health-alerting.md) | active |
| runner-auto-contribution | [Runner Auto-Contribution](runner-auto-contribution.md) | active |

### Agent CLI

| Spec | Title | Status |
|------|-------|--------|
| 108 | [Unified Agent CLI Flow (patch on fail)](108-unified-agent-cli-flow-patch-on-fail.md) | active |
| 111 | [Agent Execution Lifecycle Hooks](111-agent-execution-lifecycle-hooks.md) | active |

---

## 3. Infrastructure (Foundations)

### Data and Storage

| Spec | Title | Status |
|------|-------|--------|
| 018 | [Coherence Algorithm Formal Spec (0.0–1.0 scores)](018-coherence-algorithm-spec.md) | done |
| 054 | [PostgreSQL Migration](054-postgresql-migration.md) | active |
| 118 | [Unified SQLite Store](118-unified-sqlite-store.md) | in progress |
| 166 | [Universal Node + Edge Layer](166-universal-node-edge-layer.md) | active |
| 050 | [Canonical Route Registry and Runtime Mapping](050-canonical-route-registry-and-runtime-mapping.md) | active |
| 107 | [Runtime Telemetry DB Precedence](107-runtime-telemetry-db-precedence.md) | active |
| 130 | [API Request Logging Middleware](130-api-request-logging-middleware.md) | active |
| 051 | [Release Gates API](051-release-gates.md) | done |

### Surfaces

| Spec | Title | Status |
|------|-------|--------|
| 148 | [Coherence CLI (comprehensive, 35+ commands)](148-coherence-cli-comprehensive.md) | partial |
| 075 | [Web Ideas/Specs/Usage Pages](075-web-ideas-specs-usage-pages.md) | active |
| 161 | [Node and Task Visibility](161-node-task-visibility.md) | active |
| 162 | [Metadata and Self-Discovery](162-meta-self-discovery.md) | active |
| 165 | [UX Homepage Readability (WCAG AA)](165-ux-homepage-readability.md) | active |
| 180 | [MCP Skill Registry Submission](180-mcp-skill-registry-submission.md) | active |

---

## 4. Phase 2 (Multi-User)

Not active until core idea lifecycle is proven reliable.

| Spec | Title | Status |
|------|-------|--------|
| 168 | [Identity-Driven Onboarding (TOFU)](168-identity-driven-onboarding-tofu.md) | active |
| 157 | [Investment UX — Stake CC on Ideas](157-investment-ux-stake-cc-on-ideas.md) | active |

---

## What We Are NOT Building Yet

Archived in `docs/specs-archive/` (150+ specs). Key categories:

- **Federation** (120, 121, 131–134, 137, 143, 149, 156) — no second node exists
- **Social bots** (164, 167) — no user base to broadcast to
- **Crypto treasury** (122) — no users to transact with
- **Garden/resonance/fractal UX** (163, 169, 181, 182, 186) — polish before core works
- **Belief systems** (169) — philosophical, not practical for MVP
- **Meta-process specs** (054-commit, 055-runtime, 056-traceability, 072, 073, 088, 095, 096) — internal validation, not user-facing
- **Architecture research** (109, 110, 111-greenfield) — speculative
- **Completed plumbing** (001, 009, 010, 011, 014, 016) — code is the spec now

---

## Roadmap

### Phase 1 (NOW): Core Idea Lifecycle + Pipeline Reliability

1. Ideas tracked with lifecycle, hierarchy, and right-sizing
2. Contributions attributed with value lineage
3. CC as unit of account with grounded cost/value measurement
4. Agent pipeline: reliable execution, diagnostics, auto-heal, smart reap
5. CLI and web: functional surfaces for idea and pipeline management
6. PostgreSQL migration for production persistence

### Phase 2 (NEXT): Multi-User + Attribution

1. Contributor onboarding and identity (TOFU)
2. Investment UX: stake CC on ideas
3. Portfolio governance and effectiveness measurement

### Phase 3 (LATER): Federation + Ecosystem

1. Federation layer: node identity, sync, aggregated visibility
2. OpenClaw marketplace for cross-instance idea trading
3. Social platform integrations

---

## Archived Specs

`docs/specs-archive/` contains 150+ specs including:
- Completed infrastructure (health, pagination, error handling, deploy readiness)
- Sprint artifacts and historical aliases
- Task files, verification records, audit findings
- Bug-fix specs (already resolved)
- Federation, marketplace, social bot, and speculative feature specs
- Garden metaphor, resonance navigation, and UX polish specs
