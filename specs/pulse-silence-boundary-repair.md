---
idea_id: pipeline-reliability
status: done
source:
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
done_when:
  - "cd pulse && python3 -m pytest -q"
  - "A stale open silence with three breathing samples is absent from /pulse/now ongoing_silences and has a closure note."
  - "An open silence with fewer than three breathing samples remains open and forces overall=strained or silent."
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

## Concept Link

- [`lc-boundary-repair-protocol`](../docs/vision-kb/concepts/lc-boundary-repair-protocol.md) names the general shape: stop receipt, repair witness, changed evidence, and re-entry through a new protocol. Pulse silence repair is the first operational proof of that concept in the runtime witness.
- [`lc-pulse`](../docs/vision-kb/concepts/lc-pulse.md) names the witness surface this proof tends.

## Protocol Shape

```text
failure run -> silence row -> breathing evidence -> boundary_repair_protocol note -> closed silence
```

The receipt note records:

- the protocol name: `boundary_repair_protocol`
- the choice: `re_enter`
- the number of consecutive breathing samples
- the evidence window from first closing sample to latest witnessed sample

## Files Modified

- `pulse/pulse_app/analysis.py` — adds the repair receipt, all-organ reconciliation, and contradiction guard.
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
```

Expected result:

```text
73 passed
```

## Out of Scope

- Manual operator closure of silences.
- External witness signatures for pulse repair.
- A new incidents table. The existing `silences` table is the receipt carrier for this proof.

## Risks

- Read-time reconciliation mutates the pulse SQLite ledger during a public GET. This is intentional for this witness: the mutation is derived only from already-durable samples, preserves a closure note, and keeps the public read consistent with evidence when the scheduler missed the exact repair moment.
- The route still depends on the same SQLite writer path as the scheduler. If the database is unavailable, `/pulse/now` keeps the existing failure behavior rather than inventing an in-memory repair.

## Gaps

- The repair receipt is a compact text note, not a structured receipt object. A later external-witness or incident-ledger lift can promote it to typed fields without changing the close threshold.
- Pulse repair is internal witness only. Tessera or another external witness is still a follow-up proof.
