---
idea_id: idea-realization-engine
status: done
source:
  - file: docs/coherence-substrate/native-mutation-side-effect-ledger.form
    symbols: [native_mutation_side_effect_ledger, native_mutation_side_effect_recipe_shift]
  - file: api/tests/test_native_mutation_side_effect_ledger.py
    symbols: [test_ledger_declares_anti_circular_decision_rule, test_python_parity_entries_cite_python_sources_and_form_carriers, test_gate_receipts_are_not_claimed_as_python_parity, test_missing_python_parity_blocks_ordinary_flip, test_route_forms_and_specs_link_the_ledger_boundary]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
  - file: specs/native-mutation-side-effects.md
    symbols: []
  - file: specs/native-mutation-route-side-effect-binding.md
    symbols: []
  - file: specs/native-mutation-public-gate.md
    symbols: []
requirements:
  - "A Form-native ledger classifies mutable effects as primary mutation, Python parity effect, gate receipt, missing Python parity, or not carried."
  - "The ledger states that side-effect proof does not justify side effects."
  - "Rollback receipts and public-gate rollback receipts are classified as gate-local safety rather than Python parity."
  - "The ledger names idea valuation audit-ledger writes as missing Python parity that blocks ordinary no-header mutation flips until carried or intentionally retired."
  - "Ideas/spec route forms and mutation specs link the ledger boundary."
done_when:
  - 'file_exists("docs/coherence-substrate/native-mutation-side-effect-ledger.form")'
  - 'file_contains("docs/coherence-substrate/native-mutation-side-effect-ledger.form", "unjustified_additions: 0")'
  - 'pytest_passes("api/tests/test_native_mutation_side_effect_ledger.py")'
test: "cd api && python3 -m pytest -q tests/test_native_mutation_side_effect_ledger.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py"
constraints:
  - "Do not add new domain side effects in this slice."
  - "Do not flip ordinary no-header mutation traffic."
  - "Do not treat rollback receipts as Python parity."
---

# Spec: Native Mutation Side-Effect Ledger

## Purpose

The previous native mutation work proved side-effect execution and reversible
public gating, but proof alone can become circular if it is used as the reason
to add side effects. This spec adds a Form-native ledger that classifies each
mutable companion before movement: existing Python parity, reversible gate
safety, missing parity, or not carried.

## Requirements

- [ ] **R1**: `native-mutation-side-effect-ledger.form` declares
  `native_mutation_side_effect_ledger()` and
  `native_mutation_side_effect_recipe_shift()`.
- [ ] **R2**: The ledger states that side-effect proof does not justify side
  effects and that Python parity effects must cite Python source behavior.
- [ ] **R3**: Parent-edge repair, spec delete edge cleanup, cache invalidation,
  and contributor-key audit are classified as Python parity effects with both
  Python sources and Form-native carriers.
- [ ] **R4**: Rollback receipts and public-gate rollback receipts are classified
  as gate receipts, with no Python parity claim.
- [ ] **R5**: Idea valuation audit-ledger writes are classified as missing
  Python parity and block ordinary no-header mutation flips until carried
  Form-native or intentionally retired by spec.
- [ ] **R6**: Ideas/spec route forms and native mutation specs link the ledger.

## Research Inputs

- `2026-06-09` - User asked whether proof was being used circularly as an
  excuse to add side effects.
- `api/app/routers/ideas.py` - live idea create/update parent invariant.
- `api/app/services/idea_write_ops.py` - idea create/update persistence and
  audit-ledger writes.
- `api/app/services/idea_service.py` - idea cache invalidation behavior.
- `api/app/services/spec_registry_service.py` - spec graph mutation and cache
  invalidation behavior.
- `api/app/services/graph_service.py` - graph node delete edge cleanup.
- `api/app/services/contributor_key_store.py` - contributor key `last_used_at`
  refresh.
- `specs/native-mutation-public-gate.md` - reversible public-gate receipt
  boundary.

## Files to Create/Modify

- `docs/coherence-substrate/native-mutation-side-effect-ledger.form` -
  Form-native keep/delete ledger.
- `api/tests/test_native_mutation_side_effect_ledger.py` - focused ledger proof.
- `docs/coherence-substrate/ideas-router.form` - ideas route structure link.
- `docs/coherence-substrate/spec-registry-router.form` - spec route structure
  link.
- `specs/native-mutation-side-effects.md` - side-effect carrier contract link.
- `specs/native-mutation-route-side-effect-binding.md` - route-runner contract
  link.
- `specs/native-mutation-public-gate.md` - public-gate contract link.
- `specs/native-mutation-side-effect-ledger.md` - this contract.

## Acceptance Tests

- `api/tests/test_native_mutation_side_effect_ledger.py::test_ledger_declares_anti_circular_decision_rule`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_python_parity_entries_cite_python_sources_and_form_carriers`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_gate_receipts_are_not_claimed_as_python_parity`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_missing_python_parity_blocks_ordinary_flip`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_route_forms_and_specs_link_the_ledger_boundary`

## Verification

```bash
cd api && python3 -m pytest -q tests/test_native_mutation_side_effect_ledger.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-side-effect-ledger.md
```

## Out of Scope

- Adding new domain side effects.
- Carrying the idea valuation audit ledger in this slice.
- Flipping ordinary no-header mutable ideas/spec traffic.

## Gaps

- GAP-NMSEL1 follow-up task: `native-idea-valuation-audit-ledger`. Carry
  `idea_write_ops.update_idea` and `update_ideas_batch` valuation audit-ledger
  writes Form-native or explicitly retire them by spec before ordinary no-header
  mutation traffic moves.
- GAP-NMSEL2 follow-up task: `native-mutation-deployed-public-canary`. Observe a
  deployed `X-Form-Native-Public-Gate` canary before any no-header flip.

## Risks and Assumptions

- The ledger is source classification, not execution proof.
- Rollback receipts remain useful only while the public-gate movement is
  reversible and transitional.
- Missing parity is a constraint, not failure. It names the next native carrier
  before a public traffic flip.
