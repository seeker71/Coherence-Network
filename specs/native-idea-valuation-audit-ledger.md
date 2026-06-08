---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/native-idea-valuation-audit-ledger.fk
    symbols: [nival-audit-ledger-ddl-sql, nival-valuation-change-insert-sql, nival-record-valuation-change, nival-record-batch-valuation-change, nival-run-idea-update-with-valuation-audit, nival-audit-ledger-test]
  - file: form/form-stdlib/tests/native-idea-valuation-audit-ledger-band.fk
    symbols: []
  - file: form/form-stdlib/integration/native-idea-valuation-audit-ledger-live.fk
    symbols: []
  - file: form/scripts/native-idea-valuation-audit-ledger-test.sh
    symbols: []
  - file: form/form-stdlib/native-mutation-public-gate.fk
    symbols: [nmpg-run-idea-update-public-gate]
  - file: api/tests/test_native_idea_valuation_audit_ledger.py
    symbols: [test_audit_ledger_form_names_python_parity_and_hash_chain, test_audit_ledger_band_executes_across_sibling_kernels, test_audit_ledger_live_script_runs_or_skips_when_pg_missing, test_audit_ledger_live_integration_verifies_hash_chain_and_route_binding, test_ledger_and_route_forms_mark_audit_parity_carried]
  - file: docs/coherence-substrate/native-mutation-side-effect-ledger.form
    symbols: [native_mutation_side_effect_ledger, native_mutation_side_effect_recipe_shift]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
requirements:
  - "Form-native idea update appends VALUATION_CHANGE rows to audit_ledger with SYSTEM sender/receiver, reason, reference_id, metadata_json, previous_hash, and hash."
  - "The audit hash uses the same field order as Python compute_entry_hash and a SHA-256 chain over previous_hash plus payload."
  - "The live proof recomputes stored hashes and verifies the previous_hash chain in throwaway Postgres."
  - "The public-gate Form layer exposes an idea update runner over the audit-ledger carrier."
  - "The side-effect ledger moves idea-valuation-audit-ledger from missing parity to Python parity effect."
done_when:
  - 'file_exists("form/form-stdlib/native-idea-valuation-audit-ledger.fk")'
  - 'file_exists("form/scripts/native-idea-valuation-audit-ledger-test.sh")'
  - 'pytest_passes("api/tests/test_native_idea_valuation_audit_ledger.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/native-idea-valuation-audit-ledger.fk form-stdlib/tests/native-idea-valuation-audit-ledger-band.fk && cd .. && form/scripts/native-idea-valuation-audit-ledger-test.sh && cd api && python3 -m pytest -q tests/test_native_idea_valuation_audit_ledger.py tests/test_native_mutation_side_effect_ledger.py tests/test_native_mutation_public_gate.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py"
constraints:
  - "Use a throwaway local PostgreSQL database or caller-supplied test DSN only."
  - "Do not execute against the production application database."
  - "Do not flip ordinary no-header public mutation traffic."
---

# Spec: Native Idea Valuation Audit Ledger

## Purpose

The side-effect ledger surfaced `idea_write_ops.update_idea` audit-ledger writes
as the missing Python parity before ordinary mutable traffic can move. This spec
ships that carrier in Form: idea update route runners can now append
hash-chained `VALUATION_CHANGE` rows to `audit_ledger` without calling Python
service code.

## Requirements

- [ ] **R1**: `native-idea-valuation-audit-ledger.fk` defines audit-ledger DDL
  and `pgcrypto` extension setup for the Postgres SHA-256 hash chain.
- [ ] **R2**: The same module defines `nival-record-valuation-change` and
  `nival-record-batch-valuation-change` with Python-parity entry type,
  `SYSTEM` sender/receiver, reason text, idea reference, metadata field order,
  `previous_hash`, and `hash`.
- [ ] **R3**: The same module defines
  `nival-run-idea-update-with-valuation-audit`, composing `agn-update-node`,
  cache receipt, contributor-key audit, rollback receipt, and audit-ledger row
  append.
- [ ] **R4**: The sibling-kernel band returns `111111`.
- [ ] **R5**: The live integration returns `11111111` after appending direct
  and route-runner audit rows, reading back graph revisions, recomputing stored
  hashes, verifying previous_hash chaining, cleaning up, and closing.
- [ ] **R6**: `native-mutation-public-gate.fk` exposes
  `nmpg-run-idea-update-public-gate` over the audit-ledger carrier.
- [ ] **R7**: Route docs and the side-effect ledger name the audit ledger as
  carried Python parity, leaving the deployed public-gate canary as the remaining
  ordinary-traffic boundary.

## Research Inputs

- `2026-06-09` - User direction: ship `idea-valuation-audit-ledger`.
- `docs/coherence-substrate/native-mutation-side-effect-ledger.form` - previous
  source-classified ledger named audit-ledger parity as missing.
- `api/app/services/idea_write_ops.py` - Python writes
  `AuditEntryType.VALUATION_CHANGE` entries for changed idea fields.
- `api/app/services/audit_ledger_service.py` - Python `compute_entry_hash` and
  `append_entry` hash-chain shape.
- `specs/native-mutation-public-gate.md` - reversible header gate that remains
  no-header fanout until canary evidence.

## Files to Create/Modify

- `form/form-stdlib/native-idea-valuation-audit-ledger.fk` - audit-ledger SQL
  carrier and route-runner wrapper.
- `form/form-stdlib/tests/native-idea-valuation-audit-ledger-band.fk` -
  sibling-kernel proof.
- `form/form-stdlib/integration/native-idea-valuation-audit-ledger-live.fk` -
  live Postgres readback proof.
- `form/scripts/native-idea-valuation-audit-ledger-test.sh` - throwaway
  Postgres harness.
- `form/form-stdlib/native-mutation-public-gate.fk` - idea update public-gate
  runner over audit-ledger parity.
- `api/tests/test_native_idea_valuation_audit_ledger.py` - repository proof.
- `docs/coherence-substrate/native-mutation-side-effect-ledger.form` -
  classification moved from missing parity to Python parity effect.
- `docs/coherence-substrate/ideas-router.form` - ideas route state.
- `docs/coherence-substrate/spec-registry-router.form` - spec route state.
- `specs/native-idea-valuation-audit-ledger.md` - this contract.

## Acceptance Tests

- `api/tests/test_native_idea_valuation_audit_ledger.py::test_audit_ledger_form_names_python_parity_and_hash_chain`
- `api/tests/test_native_idea_valuation_audit_ledger.py::test_audit_ledger_band_executes_across_sibling_kernels`
- `api/tests/test_native_idea_valuation_audit_ledger.py::test_audit_ledger_live_script_runs_or_skips_when_pg_missing`
- `api/tests/test_native_idea_valuation_audit_ledger.py::test_audit_ledger_live_integration_verifies_hash_chain_and_route_binding`
- `api/tests/test_native_idea_valuation_audit_ledger.py::test_ledger_and_route_forms_mark_audit_parity_carried`
- Manual validation: `form/scripts/native-idea-valuation-audit-ledger-test.sh`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/native-idea-valuation-audit-ledger.fk form-stdlib/tests/native-idea-valuation-audit-ledger-band.fk
cd .. && form/scripts/native-idea-valuation-audit-ledger-test.sh
cd api && python3 -m pytest -q tests/test_native_idea_valuation_audit_ledger.py tests/test_native_mutation_side_effect_ledger.py tests/test_native_mutation_public_gate.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py
python3 scripts/validate_spec_quality.py --file specs/native-idea-valuation-audit-ledger.md
```

## Out of Scope

- Production application database writes.
- Ordinary no-header mutation routing changes.
- Full deployed canary observation.

## Gaps

- GAP-NIVAL1 follow-up task: `native-mutation-deployed-public-canary`. Observe a
  deployed `X-Form-Native-Public-Gate` canary before any ordinary no-header
  mutation traffic flip.

## Risks and Assumptions

- The live harness requires Postgres `pgcrypto`; self-provisioned test Postgres
  installs it with `CREATE EXTENSION IF NOT EXISTS pgcrypto`.
- Form callers must pass old and new values as JSON fragments so metadata keeps
  Python-compatible hash content.
- The carrier proves route-runner parity, not public no-header activation.
