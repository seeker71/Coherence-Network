# Spec 085: Tracked Count Parity and Source Discovery

## Goal
Ensure public API and web UI show idea/spec/usage counts that match tracked system artifacts, even when deployment packages do not include full repository files.

## Requirements
- [x] Idea portfolio auto-discovers missing tracked idea IDs from commit-evidence artifacts and adds them as derived ideas.
- [x] Inventory spec discovery falls back to GitHub repository `specs/` listing when local specs are sparse or missing.
- [x] Inventory response exposes discovery source and tracked-count telemetry for machine inspection.
- [x] Portfolio and Specs web pages display source-aware counts so human users can verify parity.
- [x] Add deterministic tests for derived idea discovery and spec-source fallback behavior.

## Files To Modify (Allowed)
- `specs/085-tracked-count-parity-and-source-discovery.md`
- `api/app/services/idea_service.py`
- `api/app/services/inventory_service.py`
- `api/tests/test_inventory_discovery_sources.py`
- `web/app/portfolio/page.tsx`
- `web/app/specs/page.tsx`
- `docs/system_audit/commit_evidence_2026-02-16_tracked-count-parity-source-discovery.json`

## Validation
```bash
cd api && pytest -q tests/test_ideas.py tests/test_inventory_api.py tests/test_inventory_discovery_sources.py
cd web && npm run build
```

## Out of Scope
- Backfilling historical usage events that were never recorded.
- Replacing all runtime storage backends in this change.
