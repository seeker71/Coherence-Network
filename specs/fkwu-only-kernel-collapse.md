---
idea_id: coherence-substrate
status: active
source:
  - file: form/runtime/fkwu-uni.c
    symbols: []
  - file: form/form-stdlib/primitive-registry.fk
    symbols: [prim, prim-name]
  - file: scripts/fkwu_run.sh
    symbols: []
  - file: api/app/services/form_kernel_bridge.py
    symbols: [run_recipe, run_kernel, serve_via_kernel]
requirements:
  - "Single production execution kernel: c-bootstrap fkwu; Go/Rust/TS cross-check basic primitives and native assumptions only"
  - "One native catalog (primitive-registry + fkwu dispatch pool); no hand-maintained per-op tags in four places"
  - "One JIT path: recipe → form-asm bytes → native; compost jit.go / clang production / parallel plugin JIT"
  - "New host-io and kernel surface lands in Form stdlib + registry first; sibling kernels frozen"
  - "Production proof executes fkwu; sibling runs are explicitly labeled primitive conformance checks"
done_when:
  - "Phase 0 gate: validate_fkwu_native_surface.py passes in CI on every form/validate.sh run"
  - "Phase 1: native-op-manifest is source for flt-ops rows (generated or single .fk manifest); zero manual flt-ops edits for new natives"
  - "Phase 2: fkwu BUILD uses form-asm (macho/pe/elf), not clang; table flatten runs on fkwu, not Go bin-go"
  - "Phase 3: form-cli built from c-bootstrap fkwu; scripts/form_fs_fkwu_receipt.sh class of receipts pass on mac/windows/android"
  - "Phase 4: deployment and API expose only fkwu; Go/Rust/TS remain bounded primitive witnesses"
test: "cd form && python3 scripts/validate_fkwu_native_surface.py && python3 scripts/gen_flt_ops_from_manifest.py && python3 scripts/sync_native_op_manifest.py && GO_BIN=./form-kernel-go/bin-go ./validate.sh form-stdlib/core.fk form-stdlib/form-fs.fk form-stdlib/tests/form-fs-band.fk"
constraints:
  - "Do not add new registerNative entries to Go/Rust/TS except oracle bugfixes on frozen allowlist"
  - "Do not add new per-op fkwu tags without manifest + gate entry"
  - "Do not expand jit.go, plugin.Open, or clang-as-production paths"
  - "Honest-floor: name pending receipt rows; never claim c-bootstrap until observed"
---

# Spec: fkwu-only kernel collapse — one runtime, Form-native body

## Purpose

The body’s execution runtime is the c-bootstrapped **fkwu** kernel. Go, Rust,
and TypeScript are retained only to challenge basic primitive semantics and
native assumptions. They are not alternate runtimes, HTTP front doors,
fallbacks, preload paths, or deployment candidates.

This spec is the **collapse plan**: phased moves from today’s honest floor to the standard receipt in `docs/coherence-substrate/standard-receipt.form`, with explicit **stop rules** so effort stops feeding parallel kernels.

## Requirements

- [ ] **R1 — Gate on every validate:** `validate_fkwu_native_surface.py` runs at start of `form/validate.sh` and fails on tag drift or missing `fkc-flat` coverage.
- [ ] **R2 — Manifest is source of truth:** `native-op-manifest.fk` drives `flt-ops` via generator; no hand-edited per-op tags without manifest row.
- [x] **R3 — Sibling boundary:** Go/Rust/TS participate only in primitive/native-assumption conformance; production execution and observation require `fkwu`.
- [ ] **R4 — Receipt honesty:** Standard receipt rows stay `pending` until c-bootstrap fkwu + form-cli traces exist on mac/windows/android.

## Stop rules (effective immediately)

| Action | Verdict |
|--------|---------|
| New feature native only in `form-kernel-go/main.go` | **Blocked** — registry + fkwu manifest only |
| New hand-assigned fkwu tag in `flt-ops` without gate | **Blocked** — Phase 1 manifest |
| New `jit.go` / Go plugin / Rust libloading JIT feature | **Blocked** — fkwu + form-asm only |
| clang/zig-cc as production fkwu build | **Blocked** after Phase 2 — oracle only until then |
| Sibling kernel as API/deploy/runtime fallback | **Blocked** — siblings cross-check primitives only |

## Phases

### Phase 0 — Freeze surface + gate (now)

**Goal:** Stop the bleeding; catch tag/flatten/walker drift before it ships.

- [x] `form/scripts/validate_fkwu_native_surface.py` — tag uniqueness, `fkc-arm-slots` bound, unary/tri natives have `fkc-flat` coverage
- [x] Run gate at start of `form/validate.sh`
- [x] Document frozen sibling policy in agent guides (`docs/shared/agent-start-packet.md` pointer)

**Exit:** Gate green on main; form-fs and existing fourth-arm bands still four-way.

### Phase 1 — One native catalog

**Goal:** Replace hand-edited `flt-ops` with a **single manifest** derived from `primitive-registry.fk`.

- [x] `form/form-stdlib/native-op-manifest.fk` — `(name arity dispatch-class pool-index|tag)` 
- [x] Generator: manifest → `flt-ops` slice + fkwu pool metadata (script or Form recipe)
- [ ] Extend gate: every lane-1 host-io primitive in registry has manifest row + fkwu coverage
- [ ] **Arity-class dispatch** design: tags for UNARY/BINARY/TRI/QUAD host pool, not per-primitive opcodes (target end of Phase 1)

**Exit:** Adding `fs_*` native = one manifest row + generated artifacts; no manual `fkc-flat` branch per op.

### Phase 2 — Self-hosted build

**Goal:** Bootstrap builds and compiles without Go/clang on the receipt path.

- [ ] fkwu runs flatten recipe (`fks-table-file` / `flt-band-sources-*`) — retire Go `bin-go` for table build
- [ ] fkwu BUILD via `form-asm` → `{form-macho, form-pe-coff, form-elf}` (bootstrap-host 4095)
- [ ] `ensure_form_cli_kernel.sh` → load c-bootstrap fkwu artifact, not Go compile

**Exit:** `c_bootstrap_build: observed` in receipt JSON; clang only in oracle lane.

### Phase 3 — form-cli + platform receipt

**Goal:** Standard receipt on real metal.

- [ ] form-cli on c-bootstrap fkwu
- [ ] Receipt scripts per band (form-fs pattern generalised)
- [ ] mac / windows / android traces in commit evidence

**Exit:** `standard-receipt.form` rows observed for core bands.

### Phase 4 — Bound sibling proof surface

**Goal:** Go/Rust/TS remain useful and permanently bounded to basic primitive
and native-implementation cross-checks.

- [x] API runtime returns only `fkwu`; inline/preload/subprocess sibling selection is retired
- [x] API image builds and ships `/app/form/fkwu`; no sibling binary enters the image
- [x] deploy removes legacy sibling-router containers before observation
- [x] thread gate executes fkwu and invokes siblings only on the `round_ndigits` primitive band
- [ ] Classify every remaining sibling test as primitive/native conformance or retire it

**Exit:** CI and deployment have one execution kernel; every sibling invocation
names the primitive assumption it cross-checks.

## Architecture target

```
bootstrap bytes (form-asm, once)
        ↓
      fkwu  ←── form-cli
        ↓
 Form recipes: flatten · emit · JIT · ports · grammar · self-replace
        ↓
   next fkwu / dylibs / tables (content-addressed)

 Go / Rust / TypeScript ── primitive + native-assumption comparison only
```

## Files to Create/Modify

- `form/scripts/validate_fkwu_native_surface.py` — Phase 0 gate
- `form/scripts/gen_flt_ops_from_manifest.py` — manifest → flt-ops generator
- `form/scripts/sync_native_op_manifest.py` — drift check between manifest and flt-ops
- `form/form-stdlib/native-op-manifest.fk` — canonical native catalog
- `form/form-stdlib/form-fs.fk` — first host-io band proving tags 200/202
- `form/scripts/fourth-arm.sh` — emit chain + Go flatten fallback
- `form/validate.sh` — invoke gates before band runs
- `specs/fkwu-only-kernel-collapse.md` — this plan

## Acceptance Tests

- `form/form-stdlib/tests/form-fs-band.fk` — four-way 16383 on fkwu with fs_is_dir + source_inventory
- `form/scripts/validate_fkwu_native_surface.py` — exits 0 with 107 manifest rows
- `form/scripts/gen_flt_ops_from_manifest.py` — exits 0 aligned with manifest

## Verification

```bash
cd form && python3 scripts/validate_fkwu_native_surface.py \
  && python3 scripts/gen_flt_ops_from_manifest.py \
  && python3 scripts/sync_native_op_manifest.py \
  && GO_BIN=./form-kernel-go/bin-go ./validate.sh \
    form-stdlib/core.fk form-stdlib/form-fs.fk form-stdlib/tests/form-fs-band.fk
```

## Out of Scope

- Removing Go/Rust/TS primitive witnesses
- form-asm production fkwu build without clang (Phase 2)
- Platform receipt scripts on mac/windows/android (Phase 3)
- Arity-class dispatch replacing per-op tags (end of Phase 1 — design only)

## Risks and Assumptions

- **Assumption:** bin-go remains available for maintainer regen (`form/scripts/regen_fkwu_bootstrap.sh`) until Phase 2.
- **Risk:** Stale `fourth-flatten-table.txt` diverges fkwu flatten from Go path — mitigated by `form/scripts/regen_t_flat.sh` (fks bootstrap + executable Adler verdict smoke) and Go fallback when T_flat is absent.

## Known Gaps

- **Follow-up:** T_flat maintainer regen still uses bin-go once (`form/scripts/regen_t_flat.sh`); fkwu-only regen bus-errors on full driver flatten (arena lift — Phase 2).
- **Follow-up:** Arity-class dispatch replacing per-op tags (end of Phase 1).
- **Follow-up:** Bootstrap `fkwu-uni.c` must be regen'd when `FOURTH_EMIT_CHAIN` changes via `form/scripts/regen_fkwu_bootstrap.sh`.

## Research inputs

- `docs/coherence-substrate/standard-receipt.form` — receipt bar
- `docs/coherence-substrate/primitive-registry.form` — native discipline
- `docs/coherence-substrate/kernel-self-composition.form` — self-replace theorem (retire jit.go citations)
- `form/fourth-arm-bands.txt` — current fkwu proof floor
- `scripts/form_fs_fkwu_receipt.sh` — toolchain-free RUN pattern

## See also

- `specs/fkwu-native-host-platform.md` (if present) — host port layer
- `docs/coherence-substrate/form-native-models.form` — ML/native floor
- `kernels/README.md` — sibling tracking (to be rewritten in Phase 4)
