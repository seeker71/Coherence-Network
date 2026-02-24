# Spec Tracking — Coherence Network

Quick reference: spec status, test coverage, last verified.

## Summary

| Spec | Implemented | Tested | CI |
|------|-------------|--------|-----|
| 001–011 | ✓ | ✓ | ✓ |
| 012–014 | ✓ | ✓ | ✓ |
| 016–019 | ✓ | ✓ | ✓ |
| 020–025 | ✓ | ✓ | ✓ |
| 048 | ✓ | ✓ | ✓ |
| 049 | ✓ | ✓ | ✓ |
| 050 | ✓ | ✓ | ✓ |
| 051 | ✓ | ✓ | ✓ |
| 052 | ✓ | ✓ | ✓ |
| 053 | ✓ | ✓ | ✓ |
| 054 | ✓ | ✓ | ✓ |
| 055 | ✓ | ✓ | ✓ |
| 056 | ✓ | ✓ | ✓ |
| 090 | ✓ | ✓ | ✓ |
| 091 | ✓ | ✓ | ✓ |
| 092 | ✓ | ✓ | ✓ |
| 093 | ✓ | ✓ | ✓ |
| 094 | ✓ | ✓ | ✓ |
| 100 | ✓ | ✓ | ✓ |

**Total:** 38 tracked specs implemented and covered (001–025 excluding 006, 015, plus 048–056, 090–094, 100).

## Test Verification

```bash
cd api && pytest -v          # 85 tests
cd web && npm run build      # 11 routes
```

**CI:** `.github/workflows/test.yml` runs full suite on push/PR.

## Spec → Test File Mapping

| Spec | Test File(s) |
|------|--------------|
| 001 | test_health.py |
| 004 | test_ci_pipeline.py |
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
| 027 (auto-update) | test_update_spec_coverage.py |
| 048 | test_value_lineage.py |
| 049 | test_runtime_api.py, test_inventory_api.py |
| 050 | test_runtime_api.py, test_inventory_api.py |
| 051 | test_ideas.py, test_value_lineage.py |
| 052 | web build + manual validation (`/portfolio`) |
| 053 | test_inventory_api.py |
| 054 | scripts/validate_commit_evidence.py (CLI validation), workflow gates |
| 055 | test_commit_evidence_validation.py, scripts/validate_commit_evidence.py |
| 056 | test_release_gate_service.py, test_gates.py |
| 090 | test_maintainability_audit_service.py, workflow gates |
| 091 | web build + manual live refresh/link verification |
| 092 | web build + manual refresh/version-check/nav verification |
| 093 | web build + manual OS light/dark theme verification |
| 094 | test_ideas.py, test_spec_registry_api.py, test_governance_api.py, web build + manual /contribute flow |
| 100 | test_automation_usage_api.py, test_inventory_api.py |

## Last Updated

Run `pytest -v` and `npm run build` to verify before updating this doc.

## Duplicate Prefix Canonicalization

The duplicate numeric prefixes are now managed by explicit canonical mapping:

- Mapping file: `config/spec_prefix_canonical_map.json`
- Validator: `python3 scripts/validate_spec_prefix_canonicalization.py`

| Prefix | Canonical Spec | Alias Spec |
|------|-----------------|------------|
| 005 | `005-project-manager-pipeline.md` | `005-backlog.md` |
| 007 | `007-meta-pipeline-backlog.md` | `007-sprint-0-landing.md` |
| 026 | `026-pipeline-observability-and-auto-review.md` | `026-phase-1-task-metrics.md` |
| 027 | `027-fully-automated-pipeline.md` | `027-auto-update-framework.md` |
| 030 | `030-pipeline-full-automation.md` | `030-spec-coverage-update.md` |
| 048 | `048-value-lineage-and-payout-attribution.md` | `048-contributions-api.md` |
| 049 | `049-distribution-engine.md` | `049-system-lineage-inventory-and-runtime-telemetry.md` |
| 050 | `050-friction-analysis.md` | `050-canonical-route-registry-and-runtime-mapping.md` |
| 051 | `051-release-gates.md` | `051-question-answering-and-minimum-e2e-flow.md` |
| 052 | `052-assets-api.md` | `052-portfolio-cockpit-ui.md` |
| 053 | `053-ideas-prioritization.md` | `053-standing-questions-roi-and-next-task-generation.md` |
| 054 | `054-commit-provenance-contract-gate.md` | `054-postgresql-migration.md` |

## Queued ROI Specs (Not Implemented Yet)

- `095` — `specs/095-openclaw-repo-context-index-foundation.md`
- `096` — `specs/096-openclaw-hybrid-retrieval-and-rerank.md`
- `097` — `specs/097-openclaw-citation-and-allowed-file-guard.md`
- `098` — `specs/098-openclaw-incremental-index-freshness.md`
- `099` — `specs/099-openclaw-roi-benchmark-and-telemetry-loop.md`
- `108` — `specs/108-n8n-security-and-hitl-hardening.md`
- `109` — `specs/109-open-responses-interoperability-layer.md`
- `110` — `specs/110-langgraph-stateschema-adoption.md`
