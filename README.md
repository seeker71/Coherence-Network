# Coherence Network

[![Test](https://github.com/seeker71/Coherence-Network/actions/workflows/test.yml/badge.svg)](https://github.com/seeker71/Coherence-Network/actions/workflows/test.yml)

A platform that maps the open source ecosystem as an intelligence graph, computes project health (coherence) scores, and enables fair funding flows from enterprises to maintainers.

## Vision

**Coherence** maps the open source ecosystem as a concept graph — tracking contributions, computing project health, discovering cross-project connections, and enabling fair compensation flows. The concept model and architecture are designed to evolve into a broader knowledge graph + coherence platform over time.

## Tech Stack (MVP)

- **API**: FastAPI (Python) — speed to value
- **Web**: Next.js 15 + shadcn/ui
- **Graph**: Neo4j (dependency graph)
- **Relational**: PostgreSQL (users, events, billing)
- **Data**: deps.dev API, Libraries.io, GitHub API

## Quick Start

```bash
# API
cd api && uvicorn app.main:app --reload --port 8000

# Web (optional)
cd web && npm run dev
```

Visit http://localhost:3000 for the web app. See [SETUP.md](docs/SETUP.md).

## Development Workflow

Spec → Test → Implement → CI → Review → Merge

- Specs in `specs/` (source of truth)
- Tests written BEFORE implementation
- AI agents implement against spec + tests
- Human reviews every PR before merge

## Documentation

- [Status](docs/STATUS.md) — implementation status, sprint progress
- [Consolidated Plan](docs/PLAN.md) — vision, architecture, roadmap
- [Model Routing](docs/MODEL-ROUTING.md) — AI cost optimization
- [API Keys Setup](docs/API-KEYS-SETUP.md) — subscription configuration
- [Agent Debugging](docs/AGENT-DEBUGGING.md) — add tasks, run agent, debug failures
- [Agent Frameworks](docs/AGENT-FRAMEWORKS.md) — OpenClaw, Agent Zero, future autonomy
- [Reference Repos](docs/REFERENCE-REPOS.md) — links to Crypo-Coin & Living-Codex (source material)

## Reference Material

`references/` contains symlinks to the two source repos used to create this project:

- **crypo-coin** → [references/crypo-coin](references/crypo-coin) — plans, specs, agent architecture
- **living-codex** → [references/living-codex](references/living-codex) — implementation patterns, node architecture

Use them for context; implement in Coherence-Network.

## License

MIT
