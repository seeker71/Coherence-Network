# Spec 085: Tracked Count Parity and Source Discovery

## Goal
Ensure public API and web UI show idea/spec/usage counts that match tracked system artifacts, even when deployment packages do not include full repository files.

## Requirements
- [x] Idea portfolio auto-discovers missing tracked idea IDs from commit-evidence artifacts and adds them as derived ideas.
- [x] Inventory spec discovery falls back to GitHub repository `specs/` listing when local specs are sparse or missing.
- [x] Inventory response exposes discovery source and tracked-count telemetry for machine inspection.
- [x] Portfolio and Specs web pages display source-aware counts so human users can verify parity.
- [x] Add deterministic tests for derived idea discovery and spec-source fallback behavior.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Idea portfolio auto-discovers missing tracked idea IDs from commit-evidence artifacts and adds them as derived ideas.
  - Inventory spec discovery falls back to GitHub repository `specs/` listing when local specs are sparse or missing.
  - Inventory response exposes discovery source and tracked-count telemetry for machine inspection.
  - Portfolio and Specs web pages display source-aware counts so human users can verify parity.
  - Add deterministic tests for derived idea discovery and spec-source fallback behavior.
commands:
  - python3 -m pytest api/tests/test_inventory_discovery_sources.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

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

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add end-to-end browser tests for critical paths.

## Acceptance Tests

See `api/tests/test_tracked_count_parity_and_source_discovery.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_inventory_discovery_sources.py -x -v
```
