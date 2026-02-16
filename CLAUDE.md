# Coherence Network — Project Configuration

## Overview

Coherence Network is operated as a spec-driven OSS intelligence platform.

## Active Priorities

1. API and graph correctness
2. Pipeline stability and observability
3. Fast, test-backed implementation cycles
4. Clear status/spec documentation alignment

## Architecture

- **API**: FastAPI (Python) in `api/`
- **Web**: Next.js 15 + shadcn/ui in `web/`
- **Graph DB**: Neo4j
- **Relational DB**: PostgreSQL
- **Specs**: `specs/`

## Workflow: Spec → Test → Implement → CI → Review → Merge

1. **Spec** — approved spec in `specs/`
2. **Test** — expected behavior encoded in tests
3. **Implement** — implementation to satisfy tests
4. **CI** — automated validation
5. **Review** — human approval

## Key Conventions

- API paths: `/api/{resource}/{id}`
- Internal route versioning prefix `/v1` is disallowed; use `/api/*` only for project endpoints.
- All responses: Pydantic models
- Coherence scores: 0.0–1.0
- Dates: ISO 8601 UTC

## Agent Guardrails

- Do not modify tests to force passing behavior.
- Implement exactly what the spec requires.
- Before starting work or local validation in a worktree, run `./scripts/worktree_bootstrap.sh` (see `docs/WORKTREE-SETUP.md`).
- For spec authoring/updates, run `python3 scripts/validate_spec_quality.py` before implementation.
- Every changed feature spec must include explicit `Verification`, `Risks and Assumptions`, and `Known Gaps and Follow-up Tasks` sections.
- Keep changes scoped to requested files/tasks.
- Escalate via `needs-decision` for security-sensitive or high-impact architecture changes.
- Before starting new work, previous thread work must be finished (merged and publicly validated); enforce with `python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-open --fail-on-stale --strict`.
