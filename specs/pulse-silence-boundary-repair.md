---
idea_id: pipeline-reliability
status: done
source:
  - file: form/form-stdlib/sovereign-boundary-protocol.fk
    symbols: [sbp-evidence, sbp-choice, sbp-can-re-enter?, sbp-boundary-receipt]
  - file: form/form-stdlib/pulse-boundary-repair.fk
    symbols: [pbr-evidence, pbr-generic-choice, pbr-boundary-receipt, pbr-decision-valid?]
  - file: form/form-stdlib/tests/sovereign-boundary-protocol-band.fk
    symbols: [sovereign-boundary-protocol-band-score]
  - file: form/form-stdlib/tests/pulse-boundary-repair-band.fk
    symbols: [pulse-boundary-repair-band-score]
  - file: form/form-stdlib/source-compiler.fk
    symbols: [fsc-compiler-error, fsc-compile-form-bml-def-recipe, fsc-compile-form-bml-let-recipe]
  - file: form/form-kernel-go/main.go
  - file: form/form-kernel-rust/src/main.rs
  - file: form/form-kernel-ts/src/kernel.ts
  - file: form/form-kernel-ts/src/main.ts
  - file: form/form-kernel-go/server.go
  - file: form/form-kernel-go/server_test.go
  - file: pulse/pulse_app/analysis.py
    symbols: [BoundaryRepairReceipt, reconcile_all_silences, reconcile_silences, overall_status_with_open_silences]
  - file: pulse/pulse_app/storage.py
    symbols: [Store.close_silence]
  - file: pulse/pulse_app/main.py
    symbols: [pulse_now]
  - file: pulse/tests/test_analysis.py
    symbols: [test_reconcile_closes_with_boundary_repair_receipt, test_reconcile_all_repairs_stale_open_silence_from_samples, test_overall_status_with_open_silences_refuses_breathing_contradiction]
  - file: pulse/tests/test_main.py
    symbols: [test_pulse_now_repairs_stale_open_silence_before_response, test_pulse_now_keeps_open_silence_strained_without_reentry_evidence]
requirements:
  - "R1: An open pulse silence closes only when stored sample evidence shows at least three consecutive breathing samples for that organ."
  - "R2: Closure writes a boundary_repair_protocol receipt note into the silence ledger so repair is visible in history."
  - "R3: GET /pulse/now repairs stale open silences from durable samples before returning ongoing_silences."
  - "R4: GET /pulse/now never reports overall=breathing while unresolved open silences remain."
  - "R6: The boundary rule is expressed as a generic Form protocol with allow, stop, witness, and re_enter choices; pulse repair specializes it rather than owning a private law."
  - "R7: Malformed BML definition shapes report source-aware compiler errors before host-language slice crashes; uncaught kernel panics in Go, Rust, and TypeScript leave source-bearing crash traces for inspection."
done_when:
  - "cd pulse && python3 -m pytest -q"
  - "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/choice-receipt.fk form-stdlib/sovereign-boundary-protocol.fk form-stdlib/tests/sovereign-boundary-protocol-band.fk && ./validate.sh --binary form-stdlib/core.fk form-stdlib/choice-receipt.fk form-stdlib/sovereign-boundary-protocol.fk form-stdlib/pulse-boundary-repair.fk form-stdlib/tests/pulse-boundary-repair-band.fk"
  - "A stale open silence with three breathing samples is absent from /pulse/now ongoing_silences and has a closure note; incomplete evidence leaves the silence visible."
test: "cd pulse && python3 -m pytest -q"
constraints:
  - "No new pulse database table; repair evidence travels through the existing silences.note field."
  - "No weakening of the three-success re-entry threshold."
  - "Pulse remains a public read-only witness API."
---

# Pulse Silence Boundary Repair - executable stop receipt and re-entry proof

## Purpose

The pulse witness records silences as stop receipts: an organ crossed from breathing into failure, and the body keeps that evidence visible until repair is witnessed. A previous readout showed the contradictory shape `overall=breathing` with unresolved `ongoing_silences`. That means current breath and the silence ledger disagreed.

This spec makes the repair protocol executable. When durable samples show enough re-entry evidence, the witness closes the silence with a repair receipt before returning the current snapshot. When evidence is not yet sufficient, the silence stays open and the overall status reflects that unresolved receipt.

## Requirements

- [x] **R1**: An open pulse silence closes only when stored sample evidence shows at least three consecutive breathing samples for that organ.
- [x] **R2**: Closure writes a `boundary_repair_protocol` receipt note into the existing silence ledger.
- [x] **R3**: `GET /pulse/now` reconciles all organs from durable samples before returning `ongoing_silences`.
- [x] **R4**: `GET /pulse/now` does not return `overall=breathing` while unresolved open silences remain.
- [x] **R5**: The historical `/pulse/silences` surface can show the closure note through the existing `note` field.
- [x] **R6**: The rule is lifted into `sovereign-boundary-protocol.fk` as a generic Form protocol; pulse maps its evidence into that shape.
- [x] **R7**: Malformed BML definition cuts now return source-aware compiler errors instead of host-language slice crashes, and uncaught sibling-kernel panics write crash traces with argv, mode, source excerpts, line counts, and host stacks.

## Concept Link

- [`lc-boundary-repair-protocol`](../docs/vision-kb/concepts/lc-boundary-repair-protocol.md) names the general shape: stop receipt, repair witness, changed evidence, and re-entry through a new protocol. Pulse silence repair is the first operational proof of that concept in the runtime witness.
- [`lc-pulse`](../docs/vision-kb/concepts/lc-pulse.md) names the witness surface this proof tends.

## Protocol Shape

```text
boundary evidence -> allow/stop/witness/re_enter -> receipt -> optional specialized carrier
failure run -> silence row -> generic boundary evidence -> breathing evidence -> boundary_repair_protocol note -> closed silence
```

The receipt note records:

- the protocol name: `boundary_repair_protocol`
- the choice: `re_enter`
- the number of consecutive breathing samples
- the evidence window from first closing sample to latest witnessed sample

The generic Form receipt records:

- the offered interface and protocol
- the observed reach and consent state
- whether a violation was witnessed
- trusted repair evidence and threshold
- vitality, certainty, and source time
- a `CHOICE-RECEIPT` preserving the selected path and trace

## Files Modified

- `form/form-stdlib/sovereign-boundary-protocol.fk` — names the reusable allow / stop / witness / re-enter protocol.
- `form/form-stdlib/pulse-boundary-repair.fk` — maps pulse silence evidence into the generic boundary protocol.
- `form/form-stdlib/tests/sovereign-boundary-protocol-band.fk` — proves the generic protocol across source and binary kernels.
- `form/form-stdlib/tests/pulse-boundary-repair-band.fk` — proves pulse is a specialization of the generic protocol.
- `form/form-stdlib/source-compiler.fk` — reports malformed BML definition and let cuts with source lines.
- `form/form-kernel-go/main.go` — bounds-checks string access and writes source-bearing crash traces for recovered CLI panics.
- `form/form-kernel-rust/src/main.rs` — bounds-checks string access and writes source-bearing crash traces from the panic hook.
- `form/form-kernel-ts/src/kernel.ts` — bounds-checks string access and exposes `form_error` for compiler diagnostics.
- `form/form-kernel-ts/src/main.ts` — writes source-bearing crash traces from the CLI catch path.
- `form/form-kernel-go/server.go` — aligns source-compile preludes and converts source-compiler panics to returned errors.
- `form/form-kernel-go/server_test.go` — proves malformed BML is inspectable through `source_compile_last_error`.
- `pulse/pulse_app/analysis.py` — adds the deployed repair receipt, all-organ reconciliation, and contradiction guard.
- `pulse/pulse_app/storage.py` — lets `Store.close_silence()` preserve a closure note.
- `pulse/pulse_app/main.py` — reconciles all open silences before `/pulse/now` reads them.
- `pulse/tests/test_analysis.py` — proves receipt closure and unresolved-silence status behavior.
- `pulse/tests/test_main.py` — proves `/pulse/now` repairs stale open silences before response.

## Acceptance Tests

- `pulse/tests/test_analysis.py::test_reconcile_closes_with_boundary_repair_receipt`
- `pulse/tests/test_analysis.py::test_reconcile_all_repairs_stale_open_silence_from_samples`
- `pulse/tests/test_analysis.py::test_reconcile_all_keeps_silence_open_without_enough_reentry_evidence`
- `pulse/tests/test_analysis.py::test_overall_status_with_open_silences_refuses_breathing_contradiction`
- `pulse/tests/test_main.py::test_pulse_now_repairs_stale_open_silence_before_response`
- `pulse/tests/test_main.py::test_pulse_now_keeps_open_silence_strained_without_reentry_evidence`

## Verification

```bash
cd pulse && python3 -m pytest -q
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/choice-receipt.fk form-stdlib/sovereign-boundary-protocol.fk form-stdlib/tests/sovereign-boundary-protocol-band.fk
cd form && ./validate.sh --binary form-stdlib/core.fk form-stdlib/choice-receipt.fk form-stdlib/sovereign-boundary-protocol.fk form-stdlib/pulse-boundary-repair.fk form-stdlib/tests/pulse-boundary-repair-band.fk
cd form/form-kernel-go && go test ./...
cd form/form-kernel-rust && cargo test --quiet
cd form/form-kernel-ts && npm run check
```

Expected result:

```text
pulse tests pass; sovereign boundary band returns 16383; pulse boundary band returns 32767; Go/Rust/TypeScript kernel checks pass.
```

## Out of Scope

- Manual operator closure of silences.
- External witness signatures for pulse repair beyond the generic trusted-witness evidence field.
- A new incidents table. The existing `silences` table is the receipt carrier for this proof.

## Risks

- Read-time reconciliation mutates the pulse SQLite ledger during a public GET. This is intentional for this witness: the mutation is derived only from already-durable samples, preserves a closure note, and keeps the public read consistent with evidence when the scheduler missed the exact repair moment.
- The route still depends on the same SQLite writer path as the scheduler. If the database is unavailable, `/pulse/now` keeps the existing failure behavior rather than inventing an in-memory repair.

## Gaps

- The deployed Python pulse service still stores a compact text note. The typed Form receipt exists in `sovereign-boundary-protocol.fk`; wiring that exact structured receipt into the deployed pulse storage format is a later carrier lift.
- Pulse repair is internal witness only in production. Tessera or another external witness is still a follow-up proof.
