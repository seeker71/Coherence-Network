---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/form-ontology.json
    symbols: []
  - file: form/form-stdlib/form-ontology-loader.fk
    symbols: [FOL-DIALECT-BINDING-NAMES]
  - file: form/form-stdlib/intrinsic-cast.fk
    symbols: [ic-apply, ic-cast-node, ic-eval-tree, ic-cast-check, ic-nothing]
  - file: form/form-stdlib/tests/intrinsic-cast-band.fk
    symbols: []
  - file: form/form-stdlib/tests/intrinsic-cast-check-band.fk
    symbols: []
  - file: form/form-stdlib/typescript-bmf-lift.fk
    symbols: [ts-bmf-run-expr-text, lift-plus-node, lift-cast-to-string]
  - file: form/form-stdlib/typescript-bmf-eval.fk
    symbols: [ts-run, ts-eval-cast]
  - file: form/form-kernel-go/main.go
    symbols: [str_to_int, str_to_float, float_to_int]
  - file: docs/coherence-substrate/core-axioms.form
    symbols: []
  - file: docs/coherence-substrate/fourth-kernel.form
    symbols: []
  - file: scripts/gen_bp_table.py
    symbols: []
  - file: form/validate.sh
    symbols: []
requirements:
  - "A CAST recipe category in form-ontology.json names every primitive cast pair (bool/int/float/string) as a composed recipe: (CAST from-token to-token value-recipe), registered through gen_bp_table.py in all three kernel bp tables."
  - "Cast bodies are Form recipes wherever the math allows (bool<->int, truthiness, int->bool); only the irreducible leaves (string parse/format, int<->float bit movement) stay native, and each native leaf carries a Form verification recipe."
  - "A failed cast returns nothing — the third state from core-axioms.form — never 0, never an exception; str_to_int(\"abc\") returning 0 is named drift and composts behind the cast surface."
  - "Each cast pair declares reversibility as data: lossless pairs register a reverse recipe and a round-trip law; lossy pairs register none and the checker can say why."
  - "Dialect implicit-coercion rules (TS string-concat coercion, Python truthiness) live as data rows in form-ontology.json; lifters consult them and emit explicit CAST recipes, so the kernels never coerce silently."
  - "A Form-native static lane: a cast-chain check recipe walks a recipe tree by Blueprint coordinates and reports incoherent chains, lossy steps, and unhandled nothing as diagnostics, without executing the tree."
  - "Both lanes prove three-way: a cast-band (value-walk: casts, round-trips, nothing-failure) and a cast-check-band (resolution-walk diagnostics) pass identically in Go, Rust, and TypeScript via form/validate.sh."
done_when:
  - 'file_contains("form/form-stdlib/form-ontology.json", "CAST")'
  - 'file_exists("form/form-stdlib/intrinsic-cast.fk")'
  - 'file_exists("form/form-stdlib/tests/intrinsic-cast-band.fk")'
  - 'file_exists("form/form-stdlib/tests/intrinsic-cast-check-band.fk")'
  - "Both bands pass three-way (Go, Rust, TypeScript agree) under form/validate.sh."
  - "ts-bmf-run-expr-text on a mixed string+int expression lifts to an explicit CAST recipe and evaluates to the coerced string."
  - "A failing cast (string->int on a non-numeric string) realizes to nothing in all three kernels."
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/typescript-bmf.fk form-stdlib/intrinsic-cast.fk form-stdlib/typescript-bmf-eval.fk form-stdlib/typescript-bmf-lift.fk form-stdlib/tests/intrinsic-cast-band.fk && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/intrinsic-cast.fk form-stdlib/tests/intrinsic-cast-check-band.fk"
constraints:
  - "No silent kernel-level coercion: every type movement visible in a recipe tree as an explicit CAST node."
  - "Cast failure is nothing, never a thrown error and never a default value."
  - "Dialect coercion rules are ontology data consulted by lifters, not branches inside kernel evaluators."
  - "The static check lane is a Form recipe, not an extension of Python form_check.py."
  - "Existing str_to_int/str_to_float/int_to_str natives keep working until the cast surface replaces their call sites; no breaking rename in this slice."
---

# Form Intrinsic Casting — explicit cast recipes for bool, int, float, string

## Purpose

Lifting real source dies at the first mixed-type expression: TS `'n=' + 5`, Python `if count:`, JSON `"42"` arriving where an int is needed. Today the kernels carry three scattered natives (`str_to_int`, `str_to_float`, `int_to_str`) that silently return `0`/`0.0` on failure, and every dialect's implicit coercion would otherwise become hardcoded kernel branches. This spec makes casting an intrinsic, inspectable part of Form: every type movement is an explicit, content-addressed CAST recipe; failure is `nothing`; dialect coercion is data; and the same cast tree serves both the value-walk (runtime) and the resolution-walk (static checking).

## Requirements

- [x] **R1 — CAST category as ontology data.** `form-ontology.json` gains a `CAST` category whose rows name each primitive cast pair (`bool->int`, `int->bool`, `int->float`, `float->int`, `int->string`, `string->int`, `float->string`, `string->float`, `bool->string`, `string->bool`, plus dialect truthiness views). Each row composes per the structural discipline: from-token and to-token are typed-token cells, not free strings. `scripts/gen_bp_table.py` regenerates Go/Rust/TS bp tables.
- [x] **R2 — recipe-first bodies.** `form/form-stdlib/intrinsic-cast.fk` defines the cast surface. `bool<->int` and truthiness are pure Form (a bool *is* a Blueprint view over a 0/1 int cell — Python `True` and TS `true` resolve to the same cell). String parse/format and int<->float conversion bottom out in the existing natives, wrapped so the recipe tree shows the CAST node and the native is just the leaf carrier.
- [x] **R3 — nothing on failure.** The cast surface returns `nothing` when the movement cannot complete (`string->int` on `"abc"`). This is the core-axioms third state and the fourth kernel's tagged ABI null-ref, made behavioral. The current `str_to_int` silent-zero is drift this surface composts: call sites move to the cast recipe; the raw native stays untouched in this slice.
- [x] **R4 — reversibility as data.** Lossless pairs (`bool<->int`, `int->string`) register a reverse recipe plus a round-trip law the band proves (`cast back (cast there x) node_eq x`). Lossy pairs (`float->int`) register no reverse; the checker reports lossiness when a chain depends on one.
- [x] **R5 — dialect coercion tables.** Implicit-coercion rules per dialect live as ontology rows (e.g. TS: `string + int => CAST(int->string) then concat`; Python: `if <int> => CAST(int->bool) via truthiness`). `typescript-bmf-lift.fk` (and later siblings) consult the table at lift time and emit explicit CAST recipes. Kernels never coerce.
- [x] **R6 — static cast-check lane.** A Form recipe (`cast-check`) walks a recipe tree without executing it, comparing Blueprint coordinates across CAST boundaries. It reports: incoherent chains (cast target ≠ consumer expectation), lossy steps inside round-trip claims, and `nothing`-producing casts whose consumers have no `nothing` arm. Diagnostics are data the JIT and lifters can read.
- [x] **R7 — three-way proof bands.** `intrinsic-cast-band.fk` (value-walk: every pair, round-trip laws, nothing-failure cases, lifted TS mixed expression) and `intrinsic-cast-check-band.fk` (resolution-walk: clean chain passes, broken chain names its diagnostic) pass identically in Go, Rust, and TypeScript.

## Research Inputs

- `2026-06-11` - `form/form-stdlib/typescript-bmf-lift.fk` / `typescript-bmf-eval.fk` — the freshly shipped TS lift/eval pipeline is the first consumer; it currently has no way to lift `'n=' + 5`.
- `2026-06-11` - `form/form-kernel-go/main.go` `str_to_int` — `strconv.ParseInt` error is discarded, returning 0 on failure; the same shape repeats in Rust and TS kernels. Grounds R3.
- `2026-06-10` - `docs/coherence-substrate/core-axioms.form` — states axiom (0/1/nothing) gives the failure value for free.
- `docs/coherence-substrate/fourth-kernel.form` — tagged ABI already physically distinguishes `nothing` from 0; casting makes that distinction behavioral at the recipe level.
- `docs/coherence-substrate/name-resolution-as-recipe.form` — the resolution walk is the established static peer of the value-walk; cast-check is the same walk reading Blueprint coordinates.

## Data Model

```yaml
CastRow:                # one row per cast pair, in form-ontology.json
  name: CAST-INT-STRING # bp table entry
  from: typed-token ref # int
  to: typed-token ref   # string
  body: recipe ref      # pure Form, or native-leaf wrapper
  reverse: recipe ref | none
  lossy: bool

CoercionRow:            # one row per dialect implicit rule
  dialect: typescript.bmf
  trigger: "binop + with string operand"
  emit: CAST-INT-STRING # cast the lifter inserts explicitly
```

## Files to Create/Modify

- `form/form-stdlib/form-ontology.json` — `CAST` category rows + dialect coercion rows.
- `form/form-stdlib/form-ontology-loader.fk` — bind the new CAST names.
- `form/form-stdlib/intrinsic-cast.fk` — cast surface: recipe bodies, native-leaf wrappers, reverse registry, `cast-check` walk.
- `form/form-stdlib/typescript-bmf-lift.fk` — consult the TS coercion table; emit explicit CAST recipes for mixed-type binops.
- `form/form-stdlib/tests/intrinsic-cast-band.fk` — value-walk band.
- `form/form-stdlib/tests/intrinsic-cast-check-band.fk` — resolution-walk band.
- `form/form-kernel-go/bp_table.go`, `form/form-kernel-rust/src/bp_table.rs`, `form/form-kernel-ts/src/bp_table.ts` — regenerated.

## Acceptance Tests

- `form/form-stdlib/tests/intrinsic-cast-band.fk` — every pair realizes; round-trip laws hold via `node_eq`; `string->int` on `"abc"` realizes to `nothing`; lifted `'n=' + 5` evaluates to `"n=5"` with the CAST node visible in the recipe tree.
- `form/form-stdlib/tests/intrinsic-cast-check-band.fk` — a coherent chain reports no diagnostics; a chain casting `float->int->float` inside a round-trip claim reports lossiness; a `string->int` consumer without a `nothing` arm reports the gap.

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/engine.fk form-stdlib/compiler.fk form-stdlib/source-compiler.fk form-stdlib/grammars/typescript-bmf.fk form-stdlib/intrinsic-cast.fk form-stdlib/typescript-bmf-eval.fk form-stdlib/typescript-bmf-lift.fk form-stdlib/tests/intrinsic-cast-band.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/json.fk form-stdlib/cache.fk form-stdlib/form-ontology-loader.fk form-stdlib/intrinsic-cast.fk form-stdlib/tests/intrinsic-cast-check-band.fk
python3 scripts/validate_spec_quality.py --file specs/form-intrinsic-casting.md
```

Proven 2026-06-11: cast band → `7070915`, check band → `11111111`, three-way (Go, Rust, TypeScript); the ten grammar-coupled regression suites and both existing TS BMF bands unchanged.

## Out of Scope

- Numeric format families beyond int/float64 (f16/bf16/quantized live in the form-native-models milestones).
- User-defined casts between composite Blueprints (struct-to-struct projection) — same machinery later, primitives first.
- Replacing every existing `str_to_int`/`int_to_str` call site — migration happens per consumer after the surface lands.
- Removing the raw natives — they stay as leaf carriers under the cast surface.

## Risks and Assumptions

- Float formatting agrees across Go, Rust, and TypeScript because `float->string` IS a Form-side canonical formatter (6 fractional digits, trailing zeros stripped, at least one kept) — the same move the tensor work made for numerics. `string->float` is likewise pure Form over the `str_to_int` leaf (decimal form, no exponent yet), which also closed the TS kernel's missing `str_to_float` gap without adding a native.
- `nothing` propagation through existing eval arms (`ts-run` binop/compare) assumes consumers can hold `nothing`; the check lane (R6) exists to find consumers that cannot (`nothing-unhandled`).
- Fourth-kernel coupling: the tagged ABI ({nothing, 0, 1, node}) already carries the failure state physically, and CAST recipes flatten like any category through the observe-door flattener — but only the pure-int casts (`bool<->int`, truthiness) can walk on the fourth kernel today; string and float cast leaves land when m4e4's `str_*`/float op families land. The cast surface adds no new requirement; it rides the already-named ladder.

## Known Gaps and Follow-up Tasks

- Follow-up: Python BMF lifter consults the same coercion table (truthiness in `if`/`while`).
- Follow-up: JIT reads cast-check diagnostics to specialize hot paths where a chain is proven coherent.
- Follow-up: composite Blueprint casts (view-as generalization) once primitive pairs are proven.

## Task Card

```yaml
goal: Land the intrinsic cast surface — CAST ontology rows, recipe bodies, nothing-on-failure, dialect coercion tables, static cast-check — proven three-way.
files_allowed:
  - form/form-stdlib/form-ontology.json
  - form/form-stdlib/form-ontology-loader.fk
  - form/form-stdlib/intrinsic-cast.fk
  - form/form-stdlib/typescript-bmf-lift.fk
  - form/form-stdlib/tests/intrinsic-cast-band.fk
  - form/form-stdlib/tests/intrinsic-cast-check-band.fk
  - form/form-kernel-go/bp_table.go
  - form/form-kernel-rust/src/bp_table.rs
  - form/form-kernel-ts/src/bp_table.ts
  - specs/form-intrinsic-casting.md
done_when:
  - Both cast bands pass three-way under form/validate.sh.
  - Lifted TS mixed expression shows an explicit CAST node and evaluates correctly.
  - string->int on a non-numeric string realizes to nothing in all three kernels.
commands:
  - cd form && ./validate.sh form-stdlib/core.fk form-stdlib/form-ontology-loader.fk form-stdlib/intrinsic-cast.fk form-stdlib/tests/intrinsic-cast-band.fk
  - cd form && ./validate.sh form-stdlib/core.fk form-stdlib/form-ontology-loader.fk form-stdlib/intrinsic-cast.fk form-stdlib/tests/intrinsic-cast-check-band.fk
constraints:
  - No silent coercion in kernels; no thrown errors on cast failure; no default-value fallbacks.
  - Coercion rules are ontology data, not evaluator branches.
  - Keep existing natives working; no renames in this slice.
```
