---
id: lift-form-bml-onto-bmf-cursor
idea_id: bmf-bml-compiler-self-host
status: draft
decision: needs-decision
source:
  - file: form/form-stdlib/source-compiler.fk
    symbols: [fsc-compile-section-recipe, fsc-compile-form-bml-section-recipe, fsc-compile-form-bml-def-recipe, fsc-rec-fndef, fsc-rec-form-call]
  - file: form/form-stdlib/bmf-grammar.fk
    symbols: [g-parse]
  - file: form/form-stdlib/bmf-core.fk
    symbols: [cp-in-class?]
  - file: form/form-stdlib/core.fk
  - file: kernels/BMF_BML_COMPILER_PICTURE.md
  - file: docs/coherence-substrate/north-star-compiler.md
requirements:
  - "A form.bml-surface cursor grammar parses `def name(params) = expr;` from core.fk's actual surface (incl. `?`/`-`/`!` in names)"
  - "A lowerer turns the parsed cursor nodes into the SAME recipe the line compiler emits, by reusing fsc-rec-* constructors"
  - "A parity band proves cursor output node_eq line-compiler output, three-way (Go/Rust/TS)"
  - "The existing hand line compiler stays authoritative; the cursor path is proven in parallel; bmf-core.fk (a floor file) is not modified"
  - "The emitted fkwu walker reserves enough stack to run the cursor-grammar lane on Windows (the cursor engine already crosses four-way on CI)"
done_when:
  - "g-parse over form-bml-grammar parses every `def name(params) = expr;` line in the breath-1 fixture to a non-empty tree"
  - "For each fixture def, node_eq(fbl-lower(cursor parse), fsc-compile-form-bml-def-recipe) is true"
  - "form-bml-cursor-parity-band.fk returns 255 identically on Go, Rust, and TS via validate.sh (1 ok, 0 divergent)"
  - "fsc-compile-section-recipe routing default is unchanged — form.bml still compiles through the line path"
  - "The cursor engine (bmf-core/bmf-grammar) and the form.bml cursor band run on the emitted fkwu binary without a stack-overflow on Windows"
test: "cd form && export PATH=\"$PATH:/c/Program Files/LLVM/bin\" && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/line-grammar.fk form-stdlib/bmf-core.fk form-stdlib/bmf-grammar.fk form-stdlib/grammars/form-bml.fk form-stdlib/form-bml-lower.fk form-stdlib/tests/form-bml-cursor-parity-band.fk"
constraints:
  - "Do not delete or alter the hand line compiler fsc-compile-form-bml-section-recipe in this breath"
  - "Do not flip form.bml routing onto the cursor by default — promotion is a later, ratchet-gated breath"
  - "Keep the cursor compiler data-driven (grammars-as-data + string-tag dispatch); no parser-combinator rule-closures (they hit the fkwu closure-of-closure wall)"
  - "Do not modify the floor file bmf-core.fk — extend its char-class via a late-bound superset override in form-bml.fk"
  - "Do not retire any core.fk defn — core.fk's 146 floor defns are the irreducible bootstrap floor"
---

# Spec: Lift `form.bml` onto the BMF cursor — breath 1, the `def … = expr;` construct

## Purpose

The north star (`kernels/BMF_BML_COMPILER_PICTURE.md` "Bootstrap Boundary"; `docs/coherence-substrate/north-star-compiler.md`) is to move compiler logic off hand-written s-expression scanners and onto the BMF cursor grammar, retiring s-expr to a minimum bootstrap. The BMF cursor engine (`bmf-core`, verdict 600; `bmf-grammar`, verdict 300) already crosses all four kernels including the emitted-C fkwu arm. But `core.fk` (`section [form.bml]`) is still compiled by a hand-written line/string scanner — `fsc-compile-form-bml-section-recipe` — and `form.bml` is hard-routed away from `g-parse`. This spec begins the lift, per the project's per-construct, parity-gated discipline: it establishes the cursor compile path for the simplest and most common `form.bml` construct, `def name(params) = expr;`, and proves it produces recipes node_eq-identical to the line compiler across the reference kernels. The hand compiler stays authoritative; nothing is deleted; the floor file `bmf-core.fk` is untouched. This is the foundation later breaths extend construct by construct until `core.fk` (then `source-compiler.fk`) compiles wholly through the cursor.

## Requirements

- [ ] **R1**: A `form.bml`-surface grammar (`form/form-stdlib/grammars/form-bml.fk`) expressed as grammar-as-data parses `def name(params) = expr;` — including `//` comments and `?`/`-`/`!` in identifiers — driven by the existing `g-parse` cursor. It admits the extra name chars via a late-bound superset redefinition of `cp-in-class?` in form-bml.fk (digit/alpha/alnum/ws unchanged), so `bmf-core.fk` stays pristine.
- [ ] **R2**: A lowerer (`form/form-stdlib/form-bml-lower.fk`) maps the parsed cursor nodes for a `def` to the SAME recipe `fsc-compile-form-bml-def-recipe` emits, by reusing `fsc-rec-fndef`/`fsc-rec-if3`/`fsc-rec-form-call`/`fsc-rec-ident`/`fsc-rec-call` — so `node_eq` holds by content-addressing. Covers the operators core.fk's `def … = expr;` bodies use (call-form primitives + user calls, idents, int literals, `if…then…else`, `empty`). `let`, `match`, top-level `==`, and multi-line `{ … }` bodies are later breaths.
- [ ] **R3**: A parity band `form/form-stdlib/tests/form-bml-cursor-parity-band.fk` compiles each `def` in an 8-construct fixture through both paths and scores `node_eq(cursor, line)` per cell, summing to 255 (bit per construct).
- [ ] **R4**: The band returns 255 identically on Go, Rust, and TypeScript via `form/validate.sh` (`1 ok, 0 divergent`).
- [ ] **R5**: `fsc-compile-section-recipe` routing is unchanged by default: `form.bml` still lowers through `fsc-compile-form-bml-section-recipe`. No flag flip in this breath.
- [ ] **R6**: The emitted fkwu walker is built with enough stack reserve (`form/scripts/fourth-arm.sh`, 64 MiB) that the cursor-grammar lane — `bmf-grammar` and the form.bml cursor band — runs on the fourth arm on Windows without a `0xC00000FD` stack overflow, matching CI (Linux/macOS 8 MiB default).

## Files to Create/Modify

- `form/form-stdlib/grammars/form-bml.fk` — new: the `form.bml` cursor grammar + the late-bound `cp-in-class?` superset.
- `form/form-stdlib/form-bml-lower.fk` — new: lowerer from cursor nodes to the line compiler's recipe shape.
- `form/form-stdlib/tests/form-bml-cursor-parity-band.fk` — new: per-construct `node_eq(cursor, line)` parity band → 255.
- `form/scripts/fourth-arm.sh` — modify: reserve 64 MiB stack when emitting the fkwu binary so the cursor lane crosses the fourth arm on Windows.
- `form/fourth-arm-bands.txt` — modify: register the `form-bml-cursor-parity` row once it crosses four-way.
- `specs/lift-form-bml-onto-bmf-cursor.md` — this contract.

## Acceptance Tests

- `form/form-stdlib/tests/form-bml-cursor-parity-band.fk` passing three-way (Go/Rust/TS) via `form/validate.sh` with `1 ok, 0 divergent` → 255.
- Manual validation: run the `test` command in the frontmatter from a worktree rebased to `origin/main` with `form/` present.

## Verification

```bash
# Three-way parity (Go/Rust/TS) — expect "1 ok, 0 divergent" and verdict 255
cd form && export PATH="$PATH:/c/Program Files/LLVM/bin" && \
  ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk \
    form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk \
    form-stdlib/source-compiler.fk form-stdlib/line-grammar.fk form-stdlib/bmf-core.fk \
    form-stdlib/bmf-grammar.fk form-stdlib/grammars/form-bml.fk form-stdlib/form-bml-lower.fk \
    form-stdlib/tests/form-bml-cursor-parity-band.fk

# Fourth arm (fkwu) — after registering the row; expect "0 divergent" and "fourth arm: 1"
cd form && bash scripts/fourth-arm-gate.sh form-bml-cursor-parity

# Spec quality gate
python3 scripts/validate_spec_quality.py --file specs/lift-form-bml-onto-bmf-cursor.md
```

## Out of Scope

- Flipping `form.bml` routing onto the cursor by default — a later breath, gated by the `.fkb` ratchet and full construct coverage.
- The kernel-ABI lift (carrying a Recipe/`.fkb` binary into the kernel to retire the s-expr text wire) — a separable, heavier arc.
- Constructs beyond `def name(params) = expr;`: `let`, `match`, top-level `==`, multi-line `{ … }` bodies, `class`/`template`, and the `form.route`/`form.action` dialects.
- Lifting `source-compiler.fk` itself (raw s-expr bootstrap; follows core.fk).
- Deleting or shrinking any existing scanner tissue (the floor-audit "release" step happens only after the cursor subsumes a construct).

## Risks and Assumptions

- **Recipe-shape parity is exact-match-sensitive**: `node_eq` requires the lowerer to reproduce the line compiler's interned tree precisely. Mitigated by reusing the line compiler's own `fsc-rec-*` constructors, so content-addressing guarantees equality (proven: 255 three-way).
- **Late-bound override**: form-bml.fk redefines `cp-in-class?` as a superset; this relies on the kernels resolving the predicate at call time (verified — three-way 255). It governs only runs that load form-bml.fk.
- **fkwu stack on Windows**: the emitted walker's recursive descent overflows Windows' default 1 MiB stack on grammar-engine recipes (confirmed `0xC00000FD` on `bmf-grammar` itself). The 64 MiB reserve in fourth-arm.sh is the fix; reserve is address space, committed lazily, so there is no runtime cost. CI (Linux/macOS, 8 MiB) was never affected.
- **The parity band exercises the line compiler on fkwu** (it compares against it). If a line-compiler op lacks an fkwu arm, a cursor-only signature band is the fallback fourth-arm proof (see Known Gaps).
- This is a bootstrap-architecture change and carries `decision: needs-decision`.

## Known Gaps and Follow-up Tasks

- Follow-up task: register this idea via `POST /api/ideas` per the project idea-tracking guardrail (the north star exists in `BMF_BML_COMPILER_PICTURE.md`; the new unit is the per-breath cursor-lift sequencing).
- Follow-up task: if the parity band does not cross the fourth arm because the line compiler uses an fkwu-unsupported op, add a cursor-only signature band (a deterministic fold over the lowered recipe) as the fourth-arm proof.
- Follow-up task: breath 2 — `let` and top-level `==` body constructs in the form.bml cursor grammar + lowerer, same parity gate.
- Follow-up task: breath 3 — multi-line `{ … }` method-body bodies (the `cell-undo` / `task-step` shapes in core.fk).
- Follow-up task: breath N — flip `form.bml` routing onto the cursor behind a flag once all of core.fk's constructs round-trip, then promote via the `.fkb` ratchet and run the floor audit before composting the released scanner tissue.
- Follow-up task: repeat the arc for `source-compiler.fk` after core.fk fully lifts.
- Follow-up task: the separable kernel-ABI lift (Recipe/`.fkb` binary load path on all four arms) to retire the s-expr text wire.
