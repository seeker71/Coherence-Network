---
idea_id: form-native-view-history-store
status: draft
source:
  - file: api/app/services/translation_cache_service.py
    symbols: [list_history]
  - file: api/app/routers/concepts.py
    symbols: [list_view_history]
  - file: api/app/services/form_kernel_bridge.py
    symbols: [serve_via_kernel]
  - file: form/form-kernel-ts/seedbank/python-adapter/examples/view_history_order.fk
    symbols: [view-history ordering recipe]
done_when:
  - "view-history ordering runs as a four-way Form recipe (Go/Rust/TS/fkwu) and the Python sort comparator is removed from list_history"
  - "list_history delegates ordering to the recipe via serve_via_kernel and returns the same list[EntityViewRecord] shape"
  - "the ordering recipe has a four-way band covering the tie case where a superseded row's updated_at >= the canonical row's"
  - "test_flow_multilingual passes deterministically across PYTHONHASHSEED 0-8"
  - 'file_exists("form/form-kernel-ts/seedbank/python-adapter/examples/view_history_order.fk")'
  - 'file_exists("form/form-stdlib/tests/view-history-order-band.fk")'
test: "cd api && python -m pytest tests/test_flow_multilingual.py -q"
constraints:
  - "changes scoped to list_history plus the new ordering recipe and its band"
  - "no SQLAlchemy mechanism is ported to Form; the ORM query/read stays as the carrier for Phase 1"
  - "API response shapes and status codes are unchanged"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [form-native-view-history-store](../ideas/form-native-view-history-store.md)
> **Doctrine**: [`services-on-form-plan.md`](../docs/coherence-substrate/services-on-form-plan.md) — Step 1 (re-express a contract in Form and route it through a port; do not port the ORM).
> **Source**: [`translation_cache_service.py`](../api/app/services/translation_cache_service.py) | [`concepts.py`](../api/app/routers/concepts.py) | [`form_kernel_bridge.py`](../api/app/services/form_kernel_bridge.py)

# Form-Native View-History Store (Storage-Port Slice)

## Purpose
Move the language **view-history** contract of a concept off Python-that-computes
and onto Form-native code, in two phases. The contract: for an
`(entity_type, entity_id, lang)`, return its `EntityViewRecord` views ordered
**canonical-first, then newest-first**. Phase 1 (this spec's committed scope) makes
the *ordering* a four-way Form recipe and reduces `list_history` to a thin shell that
calls it — the same Python-as-shell / compute-in-Form shape `vitality_service._breath_balance`
already uses. Phase 2 (documented, deferred) projects the view rows themselves into
Form cells over the storage port so the *read* is Form-native too. Phase 1 is anchored
on a real bug we just fixed in Python: `list_history`'s ordering was hash-seed
nondeterministic. That bug class is **impossible** once ordering is a four-way recipe —
a hash-dependent order cannot be byte-identical across Go/Rust/TS/fkwu, so it cannot
pass the witness gate. We do not "fix the sort" again; we move it where the bug cannot
exist.

## Requirements
### View-history ordering as a four-way Form recipe (Phase 1, committed)
1. - [ ] Add `form/form-kernel-ts/seedbank/python-adapter/examples/view_history_order.fk`: given the views' ordering keys — a `status` rank (`canonical` = 0, every other status = 1) and a comparable `updated_at` key per row — it returns the row indices in canonical-first, then newest-first order, using only Form list/compare primitives. Pure function, no IO.
2. - [ ] Add `form/form-stdlib/tests/view-history-order-band.fk` proving the recipe four-way (Go/Rust/TS/fkwu), including the exact tie that broke Python: a superseded row whose `updated_at` equals or exceeds the canonical row's must still order *after* the canonical row.
3. - [ ] `list_history` delegates ordering to the recipe via `serve_via_kernel(...)` and the Python `rows.sort(...)` comparator is deleted; the function still returns `list[EntityViewRecord]` in the same order the current code intends (canonical first).
4. - [ ] The kernel carrier that served the ordering is observable (the `runtime` string), exactly as the vitality route exposes it; missing kernel remains a hard failure (no silent Python fallback).

## Files to Create/Modify
- `form/form-kernel-ts/seedbank/python-adapter/examples/view_history_order.fk` — new ordering recipe (the determinism core).
- `form/form-stdlib/tests/view-history-order-band.fk` — new four-way band for the ordering recipe.
- `api/app/services/translation_cache_service.py` — `list_history` becomes a thin shell over the Form runtime; the Python comparator is removed.

## Acceptance Criteria
- `cd api && python -m pytest tests/test_flow_multilingual.py -q` passes, including `test_history_preserves_superseded_views`, deterministically across `PYTHONHASHSEED` 0–8 (the prior failing seed was 0).
- `cd api && python -m pytest tests/ -q` shows no regression versus the current 400-passing baseline.
- The ordering recipe crosses four-way (Go/Rust/TS/fkwu) with zero divergence in `view-history-order-band.fk`.
- `GET /api/concepts/{id}/views/{lang}/history` returns the same JSON it returns today for a fixture with one canonical + one superseded view.

## Verification
```bash
# Four-way proof of the ordering recipe
cd form && ./validate.sh form-stdlib/core.fk \
  form-kernel-ts/seedbank/python-adapter/examples/view_history_order.fk \
  form-stdlib/tests/view-history-order-band.fk

# Determinism: the previously-flaky test across hash seeds
cd api && for s in 0 1 2 3 5 8; do PYTHONHASHSEED=$s python -m pytest \
  tests/test_flow_multilingual.py::test_history_preserves_superseded_views -q; done

# No regression on the full suite
cd api && python -m pytest tests/ -q

# Spec gate
python3 scripts/validate_spec_quality.py --file specs/form-native-view-history-store.md
```

## Out of Scope
- **Phase 2** (deferred to a follow-up spec): projecting `EntityViewRecord` rows into Form cells over the storage port (`view-store.fk` over `storage-port-file.fk`) so the *read*, not only the ordering, is Form-native. Phase 1 keeps the SQLAlchemy query as the carrier and moves only the ordering.
- The write path (`upsert_view`, supersession) is unchanged.
- Other view functions (`canonical_views` batch, `all_canonical_views`, glossary) and other entity families.
- The `intern_node` → storage-port bridge (the plan's crux) and any Python→Form **compiler** work — this slice is hand-written Form.
- Deleting the `EntityViewRecord` table or any schema migration.

## Risks and Assumptions
- **Marshalling shape**: `serve_via_kernel` must return a list/permutation, not only a scalar like `_breath_balance`. Assumption: the kernel's `list`/`head`/`tail` primitives support this; the band validates the returned shape before Python is wired, and `list_history` applies the returned index order to the SQLAlchemy rows it already holds (so only the comparison, not the row data, crosses the kernel boundary).
- **Round-trip cost**: one kernel call per history read. Assumption: the route-preload/inline carrier keeps this within the budget the vitality route already pays; if a hot path needs it, the ordered result is memoized per `(entity, lang, row-set hash)`.
- **Four-way tooling on this host**: the Windows dev host has the Rust kernel built and can serve the recipe via the subprocess carrier, so Python-level behavior is verifiable locally; full four-way `validate.sh` (incl. fkwu's clang-emitted carrier) may need CI/Linux. The four-way band is the gate of record, run in CI.
- **Tie semantics**: ordering must be total and deterministic even when `updated_at` ties across rows; the recipe breaks ties by `status` rank first, then a stable secondary key (e.g. `id`), so no hash-dependent comparison remains.

## Known Gaps and Follow-up Tasks
- **Phase 2 — view-store over the storage port**: `view-store.fk` (`vs-list-history`/`vs-canonical`) reading Form cells via `storage-get`/`storage-put`, with `upsert_view` projecting rows into the carrier and a read-parity band; retire the SQLAlchemy read for this family once parity holds.
- **Generalize** to `canonical_views`/`all_canonical_views` and then to other entity families.
- **The crux** — `intern_node` → storage-port bridge (`substrate-core.fk`) per `services-on-form-plan.md` Step 1 — remains the highest-leverage follow-up this slice de-risks but does not deliver.
- **Idea registration**: record `form-native-view-history-store` via `POST /api/ideas` (and create `ideas/form-native-view-history-store.md`); deferred here because the local API is not running on this host.
