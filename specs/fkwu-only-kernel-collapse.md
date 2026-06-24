---
idea_id: coherence-substrate
status: active
source:
  - file: form/form-stdlib/form-flatten.fk
    symbols: [flt-ops, flt-op2]
  - file: form/form-stdlib/hati-os-kernel-emit.fk
    symbols: [fkc-flat, fkc-arm-slots, fkc-emit-universal]
  - file: form/form-stdlib/primitive-registry.fk
    symbols: [prim, prim-name]
  - file: form/scripts/fourth-arm.sh
    symbols: [build_fourth, fourth_table]
  - file: docs/coherence-substrate/standard-receipt.form
    symbols: []
requirements:
  - "Single production kernel: c-bootstrap fkwu (+ form-cli on same binary); Go/Rust/TS shrink to oracle/bootstrap only, then compost"
  - "One native catalog (primitive-registry + fkwu dispatch pool); no hand-maintained per-op tags in four places"
  - "One JIT path: recipe → form-asm bytes → native; compost jit.go / clang production / parallel plugin JIT"
  - "New host-io and kernel surface lands in Form stdlib + registry first; sibling kernels frozen"
  - "Proof graduates from four interpreted walkers to standard receipt (platform traces on fkwu form-cli)"
done_when:
  - "Phase 0 gate: validate_fkwu_native_surface.py passes in CI on every form/validate.sh run"
  - "Phase 1: native-op-manifest is source for flt-ops rows (generated or single .fk manifest); zero manual flt-ops edits for new natives"
  - "Phase 2: fkwu BUILD uses form-asm (macho/pe/elf), not clang; table flatten runs on fkwu, not Go bin-go"
  - "Phase 3: form-cli built from c-bootstrap fkwu; scripts/form_fs_fkwu_receipt.sh class of receipts pass on mac/windows/android"
  - "Phase 4: validate.sh default leg is fkwu-only; Go/Rust/TS removed from required legs or composted"
test: "cd form && python3 scripts/validate_fkwu_native_surface.py && python3 scripts/gen_flt_ops_from_manifest.py && python3 scripts/sync_native_op_manifest.py && GO_BIN=./form-kernel-go/bin-go ./validate.sh form-stdlib/core.fk form-stdlib/form-fs.fk form-stdlib/tests/form-fs-band.fk"
constraints:
  - "Do not add new registerNative entries to Go/Rust/TS except oracle bugfixes on frozen allowlist"
  - "Do not add new per-op fkwu tags without manifest + gate entry"
  - "Do not expand jit.go, plugin.Open, or clang-as-production paths"
  - "Honest-floor: name pending receipt rows; never claim c-bootstrap until observed"
---

# Spec: fkwu-only kernel collapse — one runtime, Form-native body

## Purpose

The body’s north star is a **minimal non-Form bootstrap** that replaces itself, with **everything else Form-native** (compiler, primitives, host ports, grammar loader, JIT, kernel). Today we still maintain **four parallel native surfaces** (Go, Rust, TS, fkwu tag maps) and **multiple JIT paths** — that is the wrong destination.

This spec is the **collapse plan**: phased moves from today’s honest floor to the standard receipt in `docs/coherence-substrate/standard-receipt.form`, with explicit **stop rules** so effort stops feeding parallel kernels.

## Stop rules (effective immediately)

| Action | Verdict |
|--------|---------|
| New feature native only in `form-kernel-go/main.go` | **Blocked** — registry + fkwu manifest only |
| New hand-assigned fkwu tag in `flt-ops` without gate | **Blocked** — Phase 1 manifest |
| New `jit.go` / Go plugin / Rust libloading JIT feature | **Blocked** — fkwu + form-asm only |
| clang/zig-cc as production fkwu build | **Blocked** after Phase 2 — oracle only until then |
| Four-way as reason to grow Rust/TS surface | **Blocked** — fkwu-first; siblings oracle-only |

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

### Phase 4 — Sibling compost

**Goal:** Go/Rust/TS kernels equal **minimal oracle**, then removed.

- [ ] `validate.sh` — fkwu required; siblings optional divergence alarms on shrink list
- [ ] Delete or archive `form-kernel-go/rust/ts` eval paths not needed for bootstrap
- [ ] Compost `jit.go`, plugin JIT, duplicate lexers
- [ ] Update `CLAUDE.md` / `kernel-self-composition.form` to cite fkwu+form-asm only

**Exit:** CI and local proof run with **one** kernel binary; no four-way on three interpreters.

## Architecture target

```
bootstrap bytes (form-asm, once)
        ↓
      fkwu  ←── form-cli
        ↓
 Form recipes: flatten · emit · JIT · ports · grammar · self-replace
        ↓
   next fkwu / dylibs / tables (content-addressed)
```

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
