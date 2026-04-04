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
| 053 | Ideas Prioritization (free energy scoring) | done |
| 138 | Idea Lifecycle Management (stages: none→specced→implementing→testing→reviewing→complete) | active |
| 176 | Idea Lifecycle Closure (exit task-generation pool on complete) | active |
| 117 | Idea Hierarchy — Super/Child Ideas | in progress |
| 120 | Super-Idea Rollup Criteria | active |
| 158 | Idea Right-Sizing (split bloated / merge nano ideas) | active |
| 181 | Idea Dual Identity (UUID + human slug) | active |

### Contributions and Value

| Spec | Title | Status |
|------|-------|--------|
| 048 | Contributions API (time, effort, code tracking) | done |
| 048 | Value Lineage and Payout Attribution (idea→spec→impl→usage→payout chain) | active |
| 049 | Distribution Engine (fair value distribution by coherence scores) | done |
| 052 | Assets API (code, models, content, data) | done |
| 083 | Task Claim Tracking and ROI De-duplication | done |
| 086 | Normalize GitHub Commit Cost Estimation | done |
| 094 | Contributor Onboarding and Governed Change Flow | active |

### Economics and Measurement

| Spec | Title | Status |
|------|-------|--------|
| 119 | Coherence Credit (CC) — Internal Currency | done |
| 124 | CC Economics and Value Coherence | in progress |
| 114 | MVP Cost Tracking and Acceptance Proof | active |
| 115 | Grounded Cost and Value Measurement (real signals → A/B ROI) | done |
| 116 | Grounded Idea Portfolio Metrics | done |
| 126 | Portfolio Governance Effectiveness | active |

---

## 2. Agent Pipeline (Execution Engine)

The engine that turns ideas into working software.

### Core Pipeline

| Spec | Title | Status |
|------|-------|--------|
| 002 | Agent Orchestration API (task submission, routing, status) | done |
| 005 | Project Manager Pipeline (spec→impl→test→review cycle) | done |
| 139 | Agent Pipeline — umbrella spec | active |
| 026 | Pipeline Observability and Auto-Review | partial |
| 032 | Attention Heuristics in Pipeline Status | done |
| 159 | Split Review/Deploy/Verify Phases | active |

### Reliability and Self-Healing

| Spec | Title | Status |
|------|-------|--------|
| 113 | Failed Task Diagnostics Contract (error_summary + error_category) | done |
| 114 | Auto-Heal from Diagnostics | done |
| 125 | Incident Response and Self-Healing | active |
| 169 | Smart Reap (diagnose/resume stuck tasks) | active |
| 186 | Data-Driven Timeout and Resume | active |
| 047 | Heal Completion and Issue Resolution | partial |
| stale-task-reaper | Stale Task Reaper | active |
| task-deduplication | Task Deduplication | active |

### Optimization

| Spec | Title | Status |
|------|-------|--------|
| 074 | Tool Failure Awareness (cost without gain) | active |
| 112 | Prompt A/B ROI Measurement | done |
| 113 | Provider Usage Coalescing + Timeout Resilience | active |
| 127 | Cross-Task Outcome Correlation | active |
| 135 | Provider Health Alerting | active |
| runner-auto-contribution | Runner Auto-Contribution | active |

### Agent CLI

| Spec | Title | Status |
|------|-------|--------|
| 108 | Unified Agent CLI Flow (patch on fail) | active |
| 111 | Agent Execution Lifecycle Hooks | active |

---

## 3. Infrastructure (Foundations)

### Data and Storage

| Spec | Title | Status |
|------|-------|--------|
| 018 | Coherence Algorithm Formal Spec (0.0–1.0 scores) | done |
| 054 | PostgreSQL Migration | active |
| 118 | Unified SQLite Store | in progress |
| 166 | Universal Node + Edge Layer | active |
| 050 | Canonical Route Registry and Runtime Mapping | active |
| 107 | Runtime Telemetry DB Precedence | active |
| 130 | API Request Logging Middleware | active |
| 051 | Release Gates API | done |

### Surfaces

| Spec | Title | Status |
|------|-------|--------|
| 148 | Coherence CLI (comprehensive, 35+ commands) | partial |
| 075 | Web Ideas/Specs/Usage Pages | active |
| 161 | Node and Task Visibility | active |
| 162 | Metadata and Self-Discovery | active |
| 165 | UX Homepage Readability (WCAG AA) | active |
| 180 | MCP Skill Registry Submission | active |

---

## 4. Phase 2 (Multi-User)

Not active until core idea lifecycle is proven reliable.

| Spec | Title | Status |
|------|-------|--------|
| 168 | Identity-Driven Onboarding (TOFU) | active |
| 157 | Investment UX — Stake CC on Ideas | active |

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
