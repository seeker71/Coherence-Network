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
  - "A parity band proves cursor output node_eq line-compiler output, three-way (Go/Rust/TS), verdict 255"
  - "A cursor-only parse band proves the form.bml grammar parses on the fourth arm (fkwu) too, verdict 123"
  - "The existing hand line compiler stays authoritative; the only floor-file change is one additive char class in bmf-core.fk"
done_when:
  - "g-parse over form-bml-grammar parses every `def name(params) = expr;` line in the breath-1 fixture to a non-empty tree"
  - "For each fixture def, node_eq(fbl-lower(cursor parse), fsc-compile-form-bml-def-recipe) is true"
  - "form-bml-cursor-parity-band.fk returns 255 identically on Go, Rust, and TS via validate.sh (1 ok, 0 divergent)"
  - "form-bml-cursor-parse-band.fk crosses the fourth arm: scripts/fourth-arm-gate.sh form-bml-cursor-parse reports PASS-4WAY (verdict 123)"
  - "fsc-compile-section-recipe routing default is unchanged — form.bml still compiles through the line path"
  - "bmf-core and bmf-grammar still PASS-4WAY (no regression from the bmlname char class)"
test: "cd form && export PATH=\"$PATH:/c/Program Files/LLVM/bin\" && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/line-grammar.fk form-stdlib/bmf-core.fk form-stdlib/bmf-grammar.fk form-stdlib/grammars/form-bml.fk form-stdlib/form-bml-lower.fk form-stdlib/tests/form-bml-cursor-parity-band.fk && bash scripts/fourth-arm-gate.sh form-bml-cursor-parse"
constraints:
  - "Do not delete or alter the hand line compiler fsc-compile-form-bml-section-recipe in this breath"
  - "Do not flip form.bml routing onto the cursor by default — promotion is a later, ratchet-gated breath"
  - "Keep the cursor compiler data-driven (grammars-as-data + string-tag dispatch); no parser-combinator rule-closures (they hit the fkwu closure-of-closure wall)"
  - "The bmf-core.fk change is limited to one additive char class (bmlname); digit/alpha/alnum/ws are byte-unchanged"
  - "Do not retire any core.fk defn — core.fk's 146 floor defns are the irreducible bootstrap floor"
---

# Spec: Lift `form.bml` onto the BMF cursor — breath 1, the `def … = expr;` construct

## Purpose

The north star (`kernels/BMF_BML_COMPILER_PICTURE.md` "Bootstrap Boundary"; `docs/coherence-substrate/north-star-compiler.md`) is to move compiler logic off hand-written s-expression scanners and onto the BMF cursor grammar, retiring s-expr to a minimum bootstrap. The BMF cursor engine (`bmf-core`, verdict 600; `bmf-grammar`, verdict 300) already crosses all four kernels including the emitted-C fkwu arm. But `core.fk` (`section [form.bml]`) is still compiled by a hand-written line/string scanner — `fsc-compile-form-bml-section-recipe` — and `form.bml` is hard-routed away from `g-parse`. This spec begins the lift, per the project's per-construct, parity-gated discipline: it establishes the cursor compile path for the simplest and most common `form.bml` construct, `def name(params) = expr;`, proves the cursor produces recipes node_eq-identical to the line compiler across the reference kernels, and proves the cursor parse itself crosses the fourth arm. The hand compiler stays authoritative; nothing is deleted. This is the foundation later breaths extend construct by construct until `core.fk` (then `source-compiler.fk`) compiles wholly through the cursor.

## Requirements

- [x] **R1**: A `form.bml`-surface grammar (`form/form-stdlib/grammars/form-bml.fk`) expressed as grammar-as-data parses `def name(params) = expr;` — including `//` comments and `?`/`-`/`!` in identifiers — driven by the existing `g-parse` cursor. The extra name chars come from one additive char class `bmlname` (alnum + `-`/`?`/`!`) in `bmf-core.fk` (digit/alpha/alnum/ws unchanged) — placed there, not as a late-bound override, so the fourth-arm flattener binds `gm-run`'s `cp-in-class?` to the class-aware definition.
- [x] **R2**: A lowerer (`form/form-stdlib/form-bml-lower.fk`) maps the parsed cursor nodes for a `def` to the SAME recipe `fsc-compile-form-bml-def-recipe` emits, by reusing `fsc-rec-fndef`/`fsc-rec-if3`/`fsc-rec-form-call`/`fsc-rec-ident`/`fsc-rec-call` — so `node_eq` holds by content-addressing. Covers call-form primitives + user calls, idents, int literals, `if…then…else`, and `empty`. `let`, `match`, top-level `==`, multi-line `{ … }` bodies are later breaths.
- [x] **R3**: A parity band `form/form-stdlib/tests/form-bml-cursor-parity-band.fk` compiles each `def` in an 8-construct fixture through both paths and scores `node_eq(cursor, line)` per cell, summing to **255** (bit per construct), three-way (Go/Rust/TS).
- [x] **R4**: A cursor-only band `form/form-stdlib/tests/form-bml-cursor-parse-band.fk` proves the form.bml grammar parses the fixture identically on all four kernels including fkwu — verdict **123** (summed AST node counts), registered in `fourth-arm-bands.txt`, `PASS-4WAY`.
- [x] **R5**: `fsc-compile-section-recipe` routing is unchanged by default: `form.bml` still lowers through `fsc-compile-form-bml-section-recipe`. No flag flip in this breath.
- [x] **R6**: The emitted fkwu walker is built with 64 MiB stack reserve (`form/scripts/fourth-arm.sh`) so the recursive cursor-grammar lane runs on the fourth arm on Windows without a `0xC00000FD` stack overflow (1 MiB default overflowed even `bmf-grammar`; CI's 8 MiB was never affected). `bmf-core`/`bmf-grammar` still `PASS-4WAY`.

## Files to Create/Modify

- `form/form-stdlib/grammars/form-bml.fk` — new: the `form.bml` cursor grammar.
- `form/form-stdlib/form-bml-lower.fk` — new: lowerer from cursor nodes to the line compiler's recipe shape.
- `form/form-stdlib/bmf-core.fk` — modify: add the additive `bmlname` char class to `cp-in-class?`.
- `form/form-stdlib/tests/form-bml-cursor-parity-band.fk` — new: per-construct `node_eq(cursor, line)` parity band → 255 (three-way).
- `form/form-stdlib/tests/form-bml-cursor-parse-band.fk` — new: cursor-only parse-signature band → 123 (four-way).
- `form/scripts/fourth-arm.sh` — modify: reserve 64 MiB stack for the emitted fkwu binary (Windows cursor lane).
- `form/fourth-arm-bands.txt` — modify: register the `form-bml-cursor-parse` row.
- `specs/lift-form-bml-onto-bmf-cursor.md` — this contract.

## Acceptance Tests

- `form/form-stdlib/tests/form-bml-cursor-parity-band.fk` passing three-way (Go/Rust/TS) via `form/validate.sh` with `1 ok, 0 divergent` → 255.
- `scripts/fourth-arm-gate.sh form-bml-cursor-parse` → `PASS-4WAY`.
- Manual validation: run the `test` command in the frontmatter from a worktree rebased to `origin/main` with `form/` present.

## Verification

```bash
# Three-way recipe parity (Go/Rust/TS) — expect "1 ok, 0 divergent" and verdict 255
cd form && export PATH="$PATH:/c/Program Files/LLVM/bin" && \
  ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk \
    form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk \
    form-stdlib/source-compiler.fk form-stdlib/line-grammar.fk form-stdlib/bmf-core.fk \
    form-stdlib/bmf-grammar.fk form-stdlib/grammars/form-bml.fk form-stdlib/form-bml-lower.fk \
    form-stdlib/tests/form-bml-cursor-parity-band.fk

# Fourth arm (fkwu) — cursor parse crosses; expect PASS-4WAY (verdict 123)
cd form && bash scripts/fourth-arm-gate.sh form-bml-cursor-parse

# Regression: the cursor engine still crosses after the bmlname char class
cd form && bash scripts/fourth-arm-gate.sh bmf-core bmf-grammar

# Spec quality gate
python3 scripts/validate_spec_quality.py --file specs/lift-form-bml-onto-bmf-cursor.md
```

## Out of Scope

- Flipping `form.bml` routing onto the cursor by default — a later breath, gated by the `.fkb` ratchet and full construct coverage.
- The kernel-ABI lift (carrying a Recipe/`.fkb` binary into the kernel to retire the s-expr text wire) — a separable, heavier arc.
- Constructs beyond `def name(params) = expr;`: `let`, `match`, top-level `==`, multi-line `{ … }` bodies, `class`/`template`, and the `form.route`/`form.action` dialects.
- Crossing the *recipe lowering* (form-bml-lower → fsc-rec-*) on the fourth arm — it reuses the s-expr line compiler's constructors, which are not yet fkwu-crossing; the cursor parse is what this breath proves on fkwu.
- Lifting `source-compiler.fk` itself (raw s-expr bootstrap; follows core.fk).
- Deleting or shrinking any existing scanner tissue (the floor-audit "release" step happens only after the cursor subsumes a construct).

## Risks and Assumptions

- **Recipe-shape parity is exact-match-sensitive**: `node_eq` requires the lowerer to reproduce the line compiler's interned tree precisely. Mitigated by reusing the line compiler's own `fsc-rec-*` constructors, so content-addressing guarantees equality (proven: 255 three-way).
- **Flattener binds names at flatten time, not late**: a redefinition of `cp-in-class?` in a later prelude is honored by the tree-walkers but NOT by the fkwu flattener (it binds `gm-run`'s reference to the first definition). That is why `bmlname` lives in `bmf-core.fk`, not as an override. Confirmed empirically (override → fkwu 8 vs 123; in bmf-core → PASS-4WAY).
- **fkwu stack on Windows**: confirmed `0xC00000FD` stack overflow on `bmf-grammar` at 1 MiB; the 64 MiB reserve fixes it. Reserve is address space, committed lazily — no runtime cost. CI (8 MiB) was never affected.
- This is a bootstrap-architecture change and carries `decision: needs-decision`.

## Known Gaps and Follow-up Tasks

- Follow-up task: register this idea via `POST /api/ideas` per the project idea-tracking guardrail (the north star exists in `BMF_BML_COMPILER_PICTURE.md`; the new unit is the per-breath cursor-lift sequencing).
- Follow-up task: cross the recipe *lowering* on the fourth arm — either by getting the line compiler's `fsc-rec-*`/`FORM-PRIMITIVE-TABLE` path to cross fkwu, or by a cursor-native lowerer that does not depend on it, so the full source→recipe path (not just the parse) is four-way.
- Follow-up task: breath 2 — `let` and top-level `==` body constructs in the form.bml cursor grammar + lowerer, same parity gate.
- Follow-up task: breath 3 — multi-line `{ … }` method-body bodies (the `cell-undo` / `task-step` shapes in core.fk).
- Follow-up task: breath N — flip `form.bml` routing onto the cursor behind a flag once all of core.fk's constructs round-trip, then promote via the `.fkb` ratchet and run the floor audit before composting the released scanner tissue.
- Follow-up task: repeat the arc for `source-compiler.fk` after core.fk fully lifts.
- Follow-up task: the separable kernel-ABI lift (Recipe/`.fkb` binary load path on all four arms) to retire the s-expr text wire.
