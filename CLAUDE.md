# Coherence Network — Project Configuration

## Overview

Coherence maps the open source ecosystem as an intelligence graph. This repo uses spec-driven development: specs are the source of truth; AI implements against specs and tests.

## Architecture

- **API**: FastAPI (Python) in `api/`
- **Web**: Next.js 16 + shadcn/ui in `web/`
- **Graph DB**: Neo4j
- **Relational DB**: PostgreSQL
- **Specs**: `specs/` — human-written, machine-readable

## Workflow: Spec → Test → Implement → CI → Review → Merge

1. **Spec** — Human writes (or approves) spec in `specs/`
2. **Test** — Human writes test skeleton (or approves)
3. **Implement** — AI implements to make tests pass
4. **CI** — Automated validation
5. **Review** — Human approves merge

## Key Conventions

- API: REST `/api/{resource}/{id}`
- All responses: Pydantic models
- Frontend API client: from OpenAPI
- Neo4j labels: `Project`, `Contributor`, `Organization`
- Coherence scores: 0.0–1.0
- Dates: ISO 8601 UTC

## File Size Limits

| Type | Max Lines |
|------|-----------|
| Pydantic models | ~50 |
| Route handlers | ~80 |
| Service files | ~150 |
| React components | ~100 |

## Agent Guardrails

- **Do NOT modify test files** when implementing. Fix implementation, not tests.
- **Implement exactly what the spec says.** No simplification, no scope creep.
- **Only modify files listed in the issue.** Stay in scope.
- **Flag security-sensitive code** with `security-review` on PR.
- **Start fresh sessions per task.** Context rot after ~45 min.

## Decision Gates

Escalate to human (`needs-decision`) for:
- New dependencies
- Schema changes
- Coherence algorithm changes
- Auth/infra changes
- Security-sensitive changes

## Interface

- **Cursor** — Primary manual interface for development
- **Future**: OpenClaw, Agent Zero, or similar for autonomous agent work when multi-agent framework is set up
