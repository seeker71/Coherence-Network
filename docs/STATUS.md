# Coherence Network — Status

> Snapshot of implementation status. See docs/SPEC-COVERAGE.md for spec→test mapping; docs/SPEC-TRACKING.md for quick reference.

## Sprint Status

| Sprint | Exit Criteria | Status |
|--------|---------------|--------|
| **0** | git push → CI green; /health 200; landing live | ✓ Complete |
| **1** | 5K+ npm packages; API returns real data; search works | ✓ Complete (`index_npm.py --target 5000`) |
| **2** | /project/npm/react shows score; search across npm+PyPI | ✓ Complete (020, 021) |
| **3** | Import Stack: package-lock.json + requirements.txt → risk analysis | ✓ Complete (022, 025) |

## Specs Implemented
- 001 Health
- 002 Agent Orchestration
- 003 Decision Loop
- 004 CI Pipeline
- 005 Project Manager
- 007 Sprint 0 Landing
- 008 Sprint 1 Graph
- 019 GraphStore Abstraction
- 009 API Error Handling
- 010 Request Validation
- 011 Pagination
- 012 Web Skeleton
- 013 Logging Audit
- 014 Deploy Readiness
- 016 Holdout Tests
- 017 Web CI
- 018 Coherence Algorithm Spec
- 020 Sprint 2 Coherence API
- 021 Web Project Search UI
- 022 Sprint 3 Import Stack
- 023 Web Import Stack UI
- 024 PyPI Indexing
- 025 requirements.txt Import
- PLAN Month 1 (Graph, indexer)
- 027 Fully Automated Pipeline
- 027 Auto Update Framework
- 028 Parallel By Phase Pipeline
- 030 Spec Coverage Update
- 032 Attention Heuristics Pipeline Status
- 034 Ops Runbook
- 035 Glossary
- 037 POST invalid task_type 422
- 038 POST empty direction 422
- 039 Pipeline Status Empty State 200
- 040 PM load_backlog Malformed Test
- 041 PM --state-file Flag Test
- 042 PM --reset Clears State Test
- 043 Agent spec→local Route Test
- 044 Agent test→local Route Test





























## Specs Pending Implementation
- 006 Overnight Backlog
- 015 Placeholder
- 026 Pipeline Observability And Auto Review
- 026 Phase 1 Task Metrics
- 029 GitHub API Integration
- 030 Pipeline Full Automation
- 031 Setup Troubleshooting Venv
- 033 README Quick Start Qualify
- 036 Check Pipeline Hierarchical View
- 045 Effectiveness Plan Progress Phase 6
- 046 Agent Debugging Pipeline Stuck Task Hang
- 047 Heal Completion Issue Resolutio





























## Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| GET / | Landing (name, version, docs, health) |
| GET /api/health | Liveness |
| GET /api/ready | Readiness (k8s) |
| GET /api/version | Version |
| GET /api/agent/tasks | List tasks (pagination: limit, offset) |
| GET /api/agent/tasks/count | Task counts |
| GET /api/agent/pipeline-status | Pipeline visibility |
| GET /api/projects/{eco}/{name} | Project by ecosystem/name |
| GET /api/projects/{eco}/{name}/coherence | Coherence score and components |
| GET /api/search?q={query} | Search projects |
| POST /api/import/stack | Upload package-lock.json or requirements.txt → risk analysis |

## Test Count

- 74 tests (CI runs full suite)

## Next Priority Tasks

1. **Implement spec 029 (GitHub API integration)** — P0; Contributor/Org nodes, index_github.py; critical for real coherence.
2. **Full automation (meta-pipeline):** specs/007-meta-pipeline-backlog items 1–5 — PLAN progress metric, heal→resolution, META-QUESTIONS check, backlog alignment, heal effectiveness. Interleaved at 20% via run_overnight_pipeline.
3. Pipfile / poetry.lock import (future)
