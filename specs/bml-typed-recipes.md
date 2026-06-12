---
idea_id: idea-realization-engine
status: draft
source:
  - file: form/form-stdlib/bml.fk
    symbols: []
  - file: form/form-stdlib/bml-source.fk
    symbols: []
  - file: form/form-stdlib/grammars/bml.fk
    symbols: []
  - file: form/form-stdlib/name-check.fk
    symbols: []
  - file: form/form-stdlib/tests/bml-generics-band.fk
    symbols: []
  - file: specs/form-intrinsic-casting.md
    symbols: []
  - file: docs/field/urs/artifacts/master-thesis-2000/backtracking-model-languages.txt
    symbols: []
  - file: docs/system_audit/bml_thesis_feature_audit_20260601.md
    symbols: []
  - file: docs/coherence-substrate/name-resolution-as-recipe.form
    symbols: []
requirements:
  - "FNDEF grows a typed form as one universal shape (not BML-prefixed): (name, return-typeref, typed-params, body) where each typed-param composes (name, typeref) and typerefs reuse the existing type-application shapes the generics band already proves expressed-not-erased. The untyped (name, params, body) form stays valid for the dynamic .fk dialect."
  - "bml.fk lowering stops erasing: the method, gmethod, opmethod, ctor, ifacesig, and param rules splice their parsed typerefs into the typed FNDEF slots instead of dropping them (today param emits only the name; method drops the return typeref it matched)."
  - "A type-resolution walk — the peer of name resolution per name-resolution-as-recipe.form — infers expression types per the thesis rules (constant kinds; identifier from resolved declaration; member access from selected member; call from return type) and resolves every BML operator to a concrete method on the base's type via the thesis naming conventions."
  - "Ill-typed BML source reports compile-time diagnostics (unknown method for operator on type, arity mismatch, argument-type mismatch, return-type mismatch) through the check door, three-way identical — never a runtime crash."
  - "No silent coercion: BML coercion-attribute methods register as dialect coercion rows per form-intrinsic-casting R5; the checker validates or inserts explicit CAST recipes where a declared coercion applies, and reports a diagnostic where none does."
  - "BML.lang.Boolean stays a distinct type at the type lane (instanceof, logical and relational operators type as Boolean per the thesis) while the value lane carries the 0/1 states — the eq-shape settlement: value unified, type visible."
  - "Both lanes prove three-way via form/validate.sh: a typed-fndef band (typed signatures survive lowering and read back via .children) and a type-check band (a well-typed program passes clean; a deliberately mistyped program names its diagnostic identically in Go, Rust, TypeScript)."
done_when:
  - 'file_exists("form/form-stdlib/tests/bml-typed-fndef-band.fk")'
  - 'file_exists("form/form-stdlib/tests/bml-type-check-band.fk")'
  - "Both bands pass three-way (Go, Rust, TypeScript agree) under form/validate.sh."
  - "A mistyped .bml source (operator with no matching method on the base type) reports a compile diagnostic, not a runtime crash, identically in all three kernels."
  - "bml.fk method/param emits carry typerefs; the typed slots are readable from Form via .children."
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/line-grammar.fk form-stdlib/bmf-core.fk form-stdlib/bmf-grammar.fk form-stdlib/lang-common.fk form-stdlib/bml.fk form-stdlib/tests/bml-typed-fndef-band.fk"
constraints:
  - "One universal typed-function shape shared by every dialect lifter (BML, Python annotations, TS types) — never a bml_typed_fndef parallel shape."
  - "Type checking is a Form recipe walk (the resolution walk carrying type coordinates), not a Python or host-language checker."
  - "The dynamic .fk dialect stays untyped and keeps its intrinsic door coercion; typed checking activates where the source language declares types."
  - "Diagnostics are data (cells with positions and reasons) the same way name-check emits them — readable by lifters, the JIT, and the visualizer."
---

# BML Typed Recipes — signatures survive lowering, the checker resolves methods by type

## Purpose

BML is a fully typed language: the thesis defines every operator as a method
call resolved from the static type of its base — "the return type of the
method called defines the type of a call expression" — and expects
compile-time type checking with error reporting. Today the BML grammar
parses every type and erases it at the lowering boundary: `bml.fk`'s
`method` rule matches a return `typeref` and emits `fndef(name, params,
body)` without it; the `param` rule matches `typeref name` and emits only
the name. The compiler therefore cannot know which methods a value
supports, cannot resolve operators, and mistyped programs crash at runtime
instead of failing at compile. This spec gives the executable recipe layer
typed signatures and a type-resolution walk, so full BML language support
rests on the same content-addressed ground as everything else.

## The two lanes (settled in the eq-shape work)

- **Value lane** — truth answers are the 0/1 integer states; the dynamic
  `.fk` dialect coerces int⇄bool intrinsically at every door.
- **Type lane** — `BML.lang.Boolean` is a distinct type; the visualizer,
  the match lane, and the checker see truth-intent. Types live in NodeID
  coordinates and, with this spec, in recipe signatures.

## Requirements

- [ ] **R1 — typed FNDEF as one universal shape.** The typed form carries
  `(name, return-typeref, typed-params, body)`; a typed-param composes
  `(name, typeref)`; typerefs reuse the type-application shapes
  `bml-generics-band.fk` already proves expressed-not-erased. Untyped
  FNDEF stays valid for the dynamic dialect.
- [ ] **R2 — lowering carries types.** `bml.fk` `method`/`gmethod`/
  `opmethod`/`ctor`/`ifacesig`/`param` splice their typerefs into the
  typed slots.
- [ ] **R3 — type-resolution walk.** The peer of name resolution: infer
  expression types per the thesis rules, resolve operators to methods by
  base type and naming conventions, type member access from the selected
  member, calls from return types.
- [ ] **R4 — compile-time diagnostics.** Unknown method for operator on
  type, arity mismatch, argument-type mismatch, return-type mismatch —
  reported as diagnostic cells through the check door, three-way
  identical, never a runtime crash.
- [ ] **R5 — coercion as declared data.** BML's coercion-attribute methods
  become dialect coercion rows (form-intrinsic-casting R5); the checker
  validates or inserts explicit CAST recipes, and reports where no
  declared coercion bridges a mismatch.
- [ ] **R6 — proof bands.** `bml-typed-fndef-band.fk` (signatures survive
  and read back) and `bml-type-check-band.fk` (clean pass + named
  diagnostic) pass three-way under `form/validate.sh`.

## Research Inputs

- `2026-06-11` — `form/form-stdlib/bml.fk` rules 39–56: every signature
  rule parses typerefs and erases them at emit; `param` emits name only.
- `docs/field/urs/artifacts/master-thesis-2000/backtracking-model-languages.txt`
  — operator-as-method-call semantics; constant kinds; "the definition of
  the resolved name defines the type"; no default coercions, coercion as
  method attribute; `instanceof` types as `BML.lang.Boolean`.
- `form/form-stdlib/tests/bml-generics-band.fk` — type applications
  already parse into faithful structure ("generics expressed, not
  erased"); the same machinery carries signature typerefs.
- `docs/coherence-substrate/name-resolution-as-recipe.form` — the
  resolution walk as the static peer of the value walk; type resolution
  is that walk carrying type coordinates.
- `specs/form-intrinsic-casting.md` — CAST recipes, nothing-on-failure,
  dialect coercion tables; this spec supplies BML's rows and the
  signatures the cast-check lane reads at function boundaries.

## Files to Create/Modify

- `form/form-stdlib/bml.fk` — signature rules splice typerefs into typed FNDEF slots.
- `form/form-stdlib/form-ontology.json` — typed-FNDEF arm registration if a new inst is needed.
- `form/form-stdlib/bml-type-check.fk` — the type-resolution walk and diagnostic cells (new).
- `form/form-stdlib/tests/bml-typed-fndef-band.fk` — signatures survive lowering (new).
- `form/form-stdlib/tests/bml-type-check-band.fk` — clean pass + named diagnostics (new).
- `form/form-kernel-go/main.go`, `form/form-kernel-rust/src/main.rs`, `form/form-kernel-ts/src/kernel.ts` — walker FNDEF arm accepts the typed child shape (skip type children at value-walk).

## Acceptance Tests

- `form/form-stdlib/tests/bml-typed-fndef-band.fk` — a BML method `Integer Add(Integer a, Integer b) { ... }` lowers to a typed FNDEF whose `.children` expose return typeref and `(name, typeref)` params; the value walk still executes the body identically three-way.
- `form/form-stdlib/tests/bml-type-check-band.fk` — a well-typed program reports zero diagnostics; `"text" * 5` with no declared `*` method on String reports unknown-method-for-type; a return whose expression type mismatches the declared return reports return-type-mismatch; all diagnostics three-way identical.

## Risks and Assumptions

- **Walker compatibility**: the typed FNDEF child shape must not break the untyped arm — the walker dispatches on child count or a typed-marker inst; the typed-fndef band proves both forms walk.
- **Type identity**: typerefs resolve through the existing name-resolution walk; unresolved type names are name diagnostics first, type diagnostics second — no duplicate reporting lane.
- **Method tables**: operator resolution needs per-class method registries readable at check time; the BML model components already parse method signatures — the checker reads those, not a parallel table.
- **Assumption**: the thesis naming conventions for operator→method mapping are authoritative; where the thesis marks behavior unsupported (yfx associativity), the checker follows current parse shape.

## Gaps

- Generic constraint solving beyond carried typerefs is deferred — follow-up: a constraint-solving slice under `idea-realization-engine` after this spec's bands land (named in Out of Scope).
- The dynamic `.fk` dialect remains untyped by design; no gap closure intended there — explicit None.

## Out of Scope

- Implementing the CAST surface itself (form-intrinsic-casting's slice).
- Type inference for the dynamic `.fk` dialect — it stays untyped.
- Generic-type instantiation checking beyond what the typeref shapes
  already carry — full generic constraint solving is a later slice.
- Flow typing, nullability analysis, and the thesis's relaxed/strict
  field attributes (the thesis itself marks them not-yet-supported).

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk ... form-stdlib/bml.fk form-stdlib/tests/bml-typed-fndef-band.fk
cd form && ./validate.sh form-stdlib/core.fk ... form-stdlib/bml.fk form-stdlib/tests/bml-type-check-band.fk
python3 scripts/validate_spec_quality.py --file specs/bml-typed-recipes.md
```
