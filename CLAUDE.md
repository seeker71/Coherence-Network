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
- All responses: Pydantic models
- Coherence scores: 0.0–1.0
- Dates: ISO 8601 UTC

## Agent Guardrails

- Do not modify tests to force passing behavior.
- Implement exactly what the spec requires.
- For spec authoring/updates, run `python3 scripts/validate_spec_quality.py` before implementation.
- Every changed feature spec must include explicit `Verification`, `Risks and Assumptions`, and `Known Gaps and Follow-up Tasks` sections.
- Keep changes scoped to requested files/tasks.
- Escalate via `needs-decision` for security-sensitive or high-impact architecture changes.

## Context-Conscious Exploration

Before scanning many files for a task, run the budget helper first:

- `python3 scripts/context_budget.py <files-or-dirs-or-patterns>`

The helper reports file sizes, estimated token cost, and compact summaries using a cache in
`.cache/context_budget/summary_cache.json`, so future passes avoid re-reading large files.

Suggested workflow:
1. Run a manifest pass to see sizes and estimated token impact.
2. Open only the highest-signal file subset.
3. If a file is large, use a cached summary first (`--force-summaries` only when needed),
   then read targeted line ranges.
