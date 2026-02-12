# Spec: PyPI Indexing

## Purpose

Per docs/STATUS.md and docs/PLAN.md Sprint 2: search across npm+PyPI. Add PyPI package indexing so the graph includes Python packages. Uses deps.dev PyPI API (same pattern as npm).

## Requirements

- [x] index_pypi_packages() in indexer service: fetch from deps.dev (pypi system) + PyPI JSON API
- [x] index_pypi.py script: --limit, --target, --packages, --persist (same as index_npm)
- [x] GraphStore stores pypi projects with ecosystem="pypi"
- [x] Search and projects API return pypi projects (already supported via ecosystem param)
- [x] Real API calls (no mocks)
- [x] Default seed list: popular PyPI packages (requests, django, flask, etc.)

## API Contract

Consumes existing APIs:
- deps.dev: GET /v3/systems/pypi/packages/{name}
- deps.dev: GET /v3/systems/pypi/packages/{name}/versions/{version}:dependencies
- PyPI JSON: https://pypi.org/pypi/{name}/json for description

## Files to Create/Modify

- `api/app/services/indexer_service.py` — add index_pypi_packages()
- `api/scripts/index_pypi.py` — CLI to index PyPI packages
- `docs/RUNBOOK.md` — add index_pypi.py usage

## Acceptance Tests

- index_pypi.py --limit 3 runs without error
- index_pypi.py --target 15 populates pypi projects
- GET /api/projects/pypi/requests returns 200 when indexed
- GET /api/search?q=requests returns pypi results when indexed

## Out of Scope

- requirements.txt import (separate; spec 022 is package-lock only)
- PyPI coherence weights (use same algorithm as npm)

## See also

- [019-graph-store-abstraction.md](019-graph-store-abstraction.md) — GraphStore
- [index_npm.py](../../api/scripts/index_npm.py) — npm indexer pattern
