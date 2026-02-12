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

- 001 Health, 002 Agent API, 003 Decision Loop, 004 CI
- 005 Project Manager, 007 Sprint 0 Landing
- 009 Error Handling, 010 Request Validation, 011 Pagination
- 012 Web Skeleton (Next.js 15 + shadcn in web/)
- 013 Logging Audit (RUNBOOK, no-secrets, format consistency)
- 014 Deploy Readiness (DEPLOY.md, CORS from env, health probes)
- 016 Holdout Tests (pattern)
- 017 Web CI (web build in test.yml)
- 018 Coherence Algorithm Spec (COHERENCE-ALGORITHM-SKETCH expanded)
- 019 GraphStore Abstraction (in-memory, indexer, projects API)
- 020 Sprint 2 Coherence API (GET /coherence; downstream_impact + dependency_health from real data)
- 021 Web Project Search UI (/search, /project/[eco]/[name])
- 022 Sprint 3 Import Stack (POST /api/import/stack; package-lock.json → risk analysis)
- 023 Web Import Stack UI (/import with file upload and results)
- 024 PyPI Indexing (index_pypi.py; deps.dev + PyPI JSON API)
- 025 requirements.txt Import (POST /api/import/stack accepts .txt; pypi ecosystem)

## Specs Pending Implementation

- None

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

- 74 tests (73 non-holdout; PM validation excludes holdout)
- CI runs full suite

## Next Priority Tasks

1. Pipfile / poetry.lock import (future)
