# Spec Tracking — Coherence Network

Quick reference: spec status, test coverage, last verified.

## Summary

| Spec | Implemented | Tested | CI |
|------|-------------|--------|-----|
| 001–011 | ✓ | ✓ | ✓ |
| 012–014 | ✓ | ✓ | ✓ |
| 016–019 | ✓ | ✓ | ✓ |
| 020–025 | ✓ | ✓ | ✓ |

**Total:** 25 specs (001–025, excluding 006, 015); all implemented and covered.

## Test Verification

```bash
cd api && pytest -v          # 74 tests
cd web && npm run build      # 7 routes
```

**CI:** `.github/workflows/test.yml` runs full suite on push/PR.

## Spec → Test File Mapping

| Spec | Test File(s) |
|------|--------------|
| 001 | test_health.py |
| 002, 003 | test_agent.py |
| 007 | test_health.py |
| 008, 019 | test_projects.py, test_graph_store.py |
| 009, 010 | test_agent.py, test_health.py |
| 011 | test_agent.py |
| 014 | test_health.py |
| 016 | holdout/test_placeholder.py |
| 020 | test_projects.py |
| 022, 025 | test_import_stack.py |
| 024 | test_projects.py |

## Last Updated

Run `pytest -v` and `npm run build` to verify before updating this doc.
