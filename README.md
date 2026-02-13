# Coherence Network

[![Test](https://github.com/seeker71/Coherence-Network/actions/workflows/test.yml/badge.svg)](https://github.com/seeker71/Coherence-Network/actions/workflows/test.yml)

Coherence Network is an execution-focused platform for open-source ecosystem intelligence.

## Current Scope

The repository is currently focused on:

- building and operating the OSS graph + coherence API,
- maintaining spec-driven delivery (spec → test → implement → CI → review),
- improving autonomous pipeline reliability, monitoring, and recovery.

## Tech Stack

- **API**: FastAPI (Python)
- **Web**: Next.js 15 (`web/`)
- **Graph**: Neo4j
- **Relational**: PostgreSQL
- **Data Sources**: deps.dev, Libraries.io, GitHub API

## Quick Start

```bash
# API
cd api && uvicorn app.main:app --reload --port 8000

# Pipeline run (watchdog + restart support)
cd api && ./scripts/run_overnight_pipeline.sh
```

## Development Workflow

Spec → Test → Implement → CI → Review → Merge

- Specs in `specs/`
- Tests are written before implementation
- Agents implement against specs/tests
- Human review required before merge

## Active Documentation

- [Setup](docs/SETUP.md)
- [Status](docs/STATUS.md)
- [Plan](docs/PLAN.md)
- [Execution Plan](docs/EXECUTION-PLAN.md)
- [Spec Coverage](docs/SPEC-COVERAGE.md)
- [Spec Tracking](docs/SPEC-TRACKING.md)
- [Pipeline Attention](docs/PIPELINE-ATTENTION.md)
- [Pipeline Monitoring Automated](docs/PIPELINE-MONITORING-AUTOMATED.md)
- [Agent Debugging](docs/AGENT-DEBUGGING.md)
- [Runbook](docs/RUNBOOK.md)
- [Deploy](docs/DEPLOY.md)
- [Model Routing](docs/MODEL-ROUTING.md)
- [Glossary](docs/GLOSSARY.md)

## License

MIT
