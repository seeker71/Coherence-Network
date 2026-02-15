# Spec 057: Spec Lineage Auto-Create From PR Metadata

**Idea**: `traceability-maturity-governance`

## Goal
Reduce PR friction by auto-deriving lineage metadata for changed specs and guiding contributors when required fields are missing.

## Requirements
1. Add script to extract `spec_id`, `idea_id`, and `estimated_cost` from spec content.
2. Add script to prepare or create lineage links from:
   - changed spec paths
   - PR number
   - PR author
3. Auto-create flow must support `--dry-run` for CI-safe validation.
4. Add workflow to run lineage validation and attempt auto-derivation for missing lineage.
5. Emit actionable guidance when auto-derivation cannot determine `idea_id`.

## Implementation
- `.github/workflows/spec-lineage-enforcement.yml`
- `scripts/extract_spec_metadata.py`
- `scripts/auto_create_lineage.py`
- `api/tests/test_lineage_autocreate_scripts.py`

## Validation
- `cd api && /opt/homebrew/bin/python3.11 -m pytest -q tests/test_lineage_autocreate_scripts.py`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_spec-lineage-autocreate.json`
