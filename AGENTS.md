# Agent Instructions — Coherence Network

## Project Summary

Coherence Network maps the open source ecosystem as an intelligence graph. Tech stack: FastAPI (Python) API, Next.js web (to be added), Neo4j + PostgreSQL.

## Workflow

Spec → Test → Implement → CI → Review → Merge

- Specs in `specs/`
- Tests before implementation
- Do NOT modify tests to make implementation pass
- Only modify files listed in spec/issue

## Key Files

- `CLAUDE.md` — Project config, conventions, guardrails
- `docs/PLAN.md` — Consolidated vision and roadmap
- `docs/MODEL-ROUTING.md` — AI model cost optimization
- `specs/TEMPLATE.md` — Spec format

## Interface

- **Cursor** — Primary manual development interface
- **Chat (Grok, OpenAI)** — Copy/paste for hard framework/architecture issues (no API)
- **Future** — OpenClaw, Agent Zero, etc. when multi-agent framework is set up

## Commands

```bash
# API
cd api && uvicorn app.main:app --reload --port 8000

# Tests
cd api && pytest -v
```
