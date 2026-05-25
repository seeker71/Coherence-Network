---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-kernel-go/main.go
    symbols: [read_form_binary, write_form_binary, serializeArtifact, deserializeArtifact, node_pkg, node_level, node_type, node_inst, node_children, node_value, node_eq, intern_node, intern_trivial_int, intern_trivial_string]
  - file: form/form-kernel-rust/src/main.rs
    symbols: [read_form_binary, write_form_binary, serialize_artifact, deserialize_artifact]
  - file: form/form-kernel-ts/src/kernel.ts
    symbols: [read_form_binary, write_form_binary, serializeRecipeArtifact, deserializeRecipeArtifact]
  - file: form/form-stdlib/emit-engine.fk
    symbols: [emit-recipe, emit-children, lookup-template, encode]
  - file: form/form-stdlib/seedbank/emit.fk
    symbols: [emit-to, emit-all, list-targets, lookup-target]
  - file: form/form-stdlib/seedbank/universal-emit.fk
    symbols: [emit-function-decl, emit-call, emit-return, emit-math-op, emit-compare-op, emit-logic-op, emit-if, emit-if-else, emit-sequence, emit-do, emit-let, emit-local-access, emit-member, emit-subscript, emit-assign, emit-ident, emit-int, emit-string, emit-bool]
  - file: form/form-stdlib/seedbank/emits/python.fk
    symbols: [python-templates]
  - file: form/form-stdlib/seedbank/emits/typescript.fk
    symbols: [typescript-templates]
  - file: form/form-stdlib/seedbank/emits/go.fk
    symbols: [go-templates]
  - file: form/form-stdlib/seedbank/emits/rust.fk
    symbols: [rust-templates]
  - file: form/form-stdlib/seedbank/emits/form.fk
    symbols: [form-templates]
  - file: form/form-stdlib/tests/form-binary-multi-emit.fk
    symbols: []
  - file: form/validate.sh
    symbols: [prepare_sources, run_siblings, run_workload]
requirements:
  - "A Form binary (.fkb) is the substrate source of truth — load it as live Recipe nodes via read_form_binary; write back via write_form_binary in the same FORMBIN2 artifact format the --emit-binary CLI produces."
  - "Native source in any tongue emits from a loaded Recipe through ONE engine with each tongue as DATA — no per-tongue branching in the dispatcher itself."
  - "The semantic IR is target-neutral: universal-emit.fk vocabulary (function decl/call, math, compare, logic, cond, block, jump, access, write, identifier, literals) maps directly to kernel RBasic categories so compiled .fkb artifacts walk back through emit-engine without translation."
  - "Per-tongue rendering lives in emits/{target}.fk template tables that bind universal category NodeIDs to render functions. Adding a tongue is adding a row to the registry, never a branch in emit-engine.fk."
  - "Content-addressed identity holds across the binary round-trip: a Recipe written by write_form_binary and read back by read_form_binary satisfies node_eq with the original."
  - "Three sibling kernels (Go, Rust, TypeScript) agree on every step of the load/emit pipeline — verified by validate.sh's three-kernel parity contract."
done_when:
  - "write_form_binary native is exposed in Go, Rust, and TypeScript kernels and produces .fkb byte-identical to --emit-binary CLI output."
  - "form-binary-multi-emit.fk loads a .fkb from disk and fans it out across sixteen target template tables (Python, TypeScript, Go, Rust, JSON, YAML, Markdown, SQL, XML, HTML, CSS, Form, Image, Audio, Video, Model) via emit-all."
  - "Every target produces non-empty text from the same loaded Recipe."
  - "Python emission of a function-decl Recipe renders as readable native Python: 'def double(x):\\n    return x * 2'."
  - "Three-kernel parity sum on form-binary-multi-emit.fk = 65 (1 write + 1 round-trip + 16 registry + 16 non-empty + 31 Python length)."
  - 'file_exists("form/form-stdlib/tests/form-binary-multi-emit.fk")'
test: "cd form && ./validate.sh form-stdlib/tests/form-binary-multi-emit.fk"
constraints:
  - "No host-language handwritten emitter — emission lives in Form-native template tables, dispatched by the substrate engine."
  - "No source-text generator as the proof path — the binary IS the source; tongues are emitted from loaded Recipe trees."
  - "No Form graph interpreter in any target tongue — each target's templates render the loaded Recipe directly as native syntax for that tongue."
  - "No giant ROOT = R(...) graph literal as parity proof — the proof is multi-tongue emission of the same loaded Recipe."
  - "No per-tongue branching in emit-engine.fk or emit.fk — the dispatcher walks any Recipe through any templates table."
---

# Form Binary to Native Python Emitter -- universal translator from a .fkb

## Purpose

A Form binary (`.fkb`) loaded from disk renders as readable native source
in any tongue the registry knows, through ONE engine, with each tongue as
DATA. Python is the load-bearing instance; fifteen other tongues ride
the same engine from the same loaded Recipe.

The architecture is content-addressed and target-blind. The substrate
holds Recipe trees by structural identity. `read_form_binary` deserializes
a `.fkb` into live nodes whose NodeIDs match what produced the file.
`emit-engine.fk` walks any Recipe through any template table. `emit.fk`
holds the registry of (target-name, templates) rows. Adding a tongue is
adding a row; the engine does not learn anything new.

This is the universal-translator shape made tangible: substrate-resident
identity in, native syntax out, sixteen times over.

## Requirements

- [x] **R1**: Form binary (`.fkb`) is the substrate source of truth — `read_form_binary` loads it as live Recipe nodes; `write_form_binary` writes the same FORMBIN2 artifact format `--emit-binary` produces.
- [x] **R2**: Native source in any tongue emits from a loaded Recipe through ONE engine, each tongue as DATA — no per-tongue branching in the dispatcher.
- [x] **R3**: Semantic IR is target-neutral: `universal-emit.fk` vocabulary maps directly to kernel RBasic categories so compiled `.fkb` artifacts walk back through `emit-engine` without translation.
- [x] **R4**: Per-tongue rendering lives in `emits/{target}.fk` template tables binding universal category NodeIDs to render functions. Adding a tongue is adding a row.
- [x] **R5**: Content-addressed identity holds across the binary round-trip: `node_eq` is true between original Recipe and the one read back.
- [x] **R6**: Three sibling kernels (Go, Rust, TypeScript) agree on every step — verified by `validate.sh`'s three-kernel parity contract.

## How it lives

**Three layers, target-blind:**

1. **Binary artifact layer** — `read_form_binary(path)` returns a NodeID
   rooted at the deserialized Recipe tree. `write_form_binary(path, root)`
   writes the same FORMBIN2 format `--emit-binary` produces. Content
   addressing means the loaded NodeID is the original NodeID; `node_eq`
   holds across the disk round-trip.

2. **Semantic IR layer** — `universal-emit.fk` exposes target-neutral
   Recipe constructors (`emit-function-decl`, `emit-call`, `emit-if`,
   `emit-return`, `emit-math-op`, etc.) that intern into the kernel's
   own RBasic categories. Compiled `.fk` source produces the same
   categories — so a `.fkb` from any source walks through the engine
   without translation.

3. **Emit dispatch layer** — `emit-engine.fk` walks one Recipe, looking up
   each node's category in the templates table, recursing into children,
   then invoking the template function with the emitted-children list.
   `emit.fk` adds a target-name registry so `emit-to "python" recipe
   registry` and `emit-all recipe registry` are one-liners. No per-tongue
   knowledge lives in the dispatcher.

## The proof

`form-stdlib/tests/form-binary-multi-emit.fk` carries the architectural
claim as a stable arithmetic probe sum across all three sibling kernels:

```
def body = emit-return(emit-math-op("*", emit-local-access("x"), 2))
def recipe = emit-function-decl("double", emit-ident("x"), body)

write_form_binary("/tmp/...", recipe)        ; → bytes written > 0  (probe-1 = 1)
let loaded = read_form_binary("/tmp/...")    ; → loaded == recipe   (probe-2 = 1)

let registry = [16-target table]             ; → list-targets = 16  (probe-3 = 16)
let fan-out = emit-all(loaded, registry)     ; → 16 non-empty texts (probe-4 = 16)
let py = emit-to("python", loaded, registry) ; → "def double(x):\n    return x * 2"
                                             ;   length 31          (probe-5 = 31)

sum: 1 + 1 + 16 + 16 + 31 = 65               (Go ≡ Rust ≡ TypeScript)
```

`validate.sh` runs all three sibling kernels and confirms the sum is
identical. Any divergence — a missing template, a node_eq failure, a
write failure — shifts the sum and surfaces the regression.

## The sixteen tongues

The registry in `form-binary-multi-emit.fk` binds the same loaded Recipe
to sixteen rows:

| Tongue | Templates file |
|---|---|
| Python | `form/form-stdlib/seedbank/emits/python.fk` |
| TypeScript | `form/form-stdlib/seedbank/emits/typescript.fk` |
| Go | `form/form-stdlib/seedbank/emits/go.fk` |
| Rust | `form/form-stdlib/seedbank/emits/rust.fk` |
| JSON | `form/form-stdlib/seedbank/emits/json.fk` |
| YAML | `form/form-stdlib/seedbank/emits/yaml.fk` |
| Markdown | `form/form-stdlib/seedbank/grammars/markdown.fk` |
| SQL | `form/form-stdlib/seedbank/emits/sql.fk` |
| XML | `form/form-stdlib/seedbank/emits/xml.fk` |
| HTML | `form/form-stdlib/seedbank/emits/html.fk` |
| CSS | `form/form-stdlib/seedbank/emits/css.fk` |
| Form | `form/form-stdlib/seedbank/emits/form.fk` |
| Image | `form/form-stdlib/seedbank/emits/image.fk` |
| Audio | `form/form-stdlib/seedbank/emits/audio.fk` |
| Video | `form/form-stdlib/seedbank/emits/video.fk` |
| Model | `form/form-stdlib/seedbank/emits/model.fk` |

A seventeenth tongue is a seventeenth row.

## Files

- `form/form-kernel-go/main.go` — Go kernel: `read_form_binary`, `write_form_binary`, `serializeArtifact`, `deserializeArtifact`.
- `form/form-kernel-rust/src/main.rs` — Rust kernel: sibling parity for the same natives.
- `form/form-kernel-ts/src/kernel.ts` — TypeScript kernel: sibling parity for the same natives.
- `form/form-stdlib/emit-engine.fk` — the target-blind walk-and-emit dispatcher.
- `form/form-stdlib/seedbank/emit.fk` — registry of (target-name, templates) rows; `emit-to`, `emit-all`.
- `form/form-stdlib/seedbank/universal-emit.fk` — target-neutral semantic IR vocabulary.
- `form/form-stdlib/seedbank/emits/python.fk` — Python template table.
- `form/form-stdlib/seedbank/emits/typescript.fk` — TypeScript template table.
- `form/form-stdlib/seedbank/emits/go.fk` — Go template table.
- `form/form-stdlib/seedbank/emits/rust.fk` — Rust template table.
- `form/form-stdlib/seedbank/emits/form.fk` — Form template table.
- `form/form-stdlib/seedbank/emits/json.fk` — JSON template table.
- `form/form-stdlib/seedbank/emits/yaml.fk` — YAML template table.
- `form/form-stdlib/seedbank/emits/sql.fk` — SQL template table.
- `form/form-stdlib/seedbank/emits/xml.fk` — XML template table.
- `form/form-stdlib/seedbank/emits/html.fk` — HTML template table.
- `form/form-stdlib/seedbank/emits/css.fk` — CSS template table.
- `form/form-stdlib/seedbank/emits/image.fk` — Image template table.
- `form/form-stdlib/seedbank/emits/audio.fk` — Audio template table.
- `form/form-stdlib/seedbank/emits/video.fk` — Video template table.
- `form/form-stdlib/seedbank/emits/model.fk` — Model template table.
- `form/form-stdlib/seedbank/grammars/markdown.fk` — Markdown templates (paired with grammar).
- `form/form-stdlib/tests/form-binary-multi-emit.fk` — the closing-loop proof harness.
- `form/validate.sh` — three-kernel parity runner.

## Acceptance Tests

- **Three-kernel parity** — `cd form && ./validate.sh form-stdlib/tests/form-binary-multi-emit.fk` returns `→ 65` from each of Go, Rust, TypeScript with zero divergence.
- **Auto-discovery** — running `./validate.sh` with no arguments picks up `form-binary-multi-emit.fk` via its `; preludes:` header and runs it alongside every other stdlib test.
- **Binary round-trip identity** — `write_form_binary` followed by `read_form_binary` produces a NodeID that satisfies `node_eq` against the original Recipe.
- **Sixteen non-empty tongues** — `emit-all` on a loaded Recipe returns sixteen `(target-name, text)` pairs, every `text` of length ≥ 1.
- **Readable native Python** — `emit-to "python"` on a function-decl Recipe loaded from disk renders as `def double(x):\n    return x * 2` (length 31), with no Form graph reconstruction.
- **CLI/Form artifact compatibility** — a `.fkb` produced by `bin-go --emit-binary ...` and one produced by `write_form_binary` from Form deserialize to equivalent Recipe trees.

## Verification

Local proof:

```bash
cd form && go build -o form-kernel-go/bin-go ./form-kernel-go
cd form && cargo build --release --manifest-path form-kernel-rust/Cargo.toml --quiet
cd form && ./validate.sh form-stdlib/tests/form-binary-multi-emit.fk
# expect: ✓ ... → 65 ; 1 ok, 0 divergent — kernels agree on every sample.
```

Spec quality:

```bash
python3 scripts/validate_spec_quality.py --file specs/form-binary-to-native-python-emitter.md
```

Commit evidence: `docs/system_audit/commit_evidence_20260525_form_binary_multi_emit.json`.

## Out of Scope

- Full CPython grammar coverage from arbitrary Python source. That is a
  language-grammar task over BMF rules in `form/form-stdlib/grammars/python-bmf.fk`,
  not part of this binary-to-native emission contract.
- Compiling the entire compiler `.fkb` into a working roundtrip-equivalent
  Python compiler. The architecture supports it; this contract proves the
  load-bearing primitive (write/read/emit) works end-to-end through binary.
  Compiler-scale roundtrip belongs to its own follow-up spec.
- Byte-level media ingestion. Image/audio/video templates render structural
  Recipe trees as text descriptors; binary media decoders live behind their
  own grammar files.
- Whitespace/comment preservation. Round-trip identity is at the structural
  (NodeID, content-addressed) level. Surface formatting rides as sibling
  annotation cells when needed.

## Risks and Assumptions

- **Risk**: per-tongue template tables drift out of sync with universal-emit
  categories as the semantic IR grows. **Mitigation**: every UE-* constant
  in universal-emit.fk maps to a category NodeID; missing template surfaces
  immediately as default-composite text in the affected target rather than
  failing silently. The probe-4 count would shift.
- **Risk**: artifact-local node ids could diverge between a CLI-emitted
  .fkb and a Form-emitted .fkb. **Mitigation**: both paths go through
  `serializeArtifact` (or its sibling-kernel equivalent) with the same
  FORMBIN2 format and string table; deserialization re-interns by content,
  preserving structural identity even when raw ids differ.
- **Risk**: a new tongue's templates table doesn't fully cover the universal
  vocabulary. **Mitigation**: emit-engine.fk's default-composite path keeps
  the engine productive with partial template tables, so a new tongue can
  grow incrementally without breaking the registry contract.
- **Assumption**: kernel parity (Go ≡ Rust ≡ TypeScript) is enforced by
  validate.sh on every default sweep. Any new native must land in all
  three kernels — write_form_binary itself was added in three sibling
  edits in the same commit.

## Known Gaps and Follow-up Tasks

- Follow-up task: compiler-scale roundtrip — apply the same architecture to the Form compiler's own `.fkb` (rather than a single function-decl). The primitives are in place; this belongs to a separate spec. Tracked via [#2048](https://github.com/seeker71/Coherence-Network/pull/2048) notes.
- Follow-up task: symbol/source lenses — for compiler-scale emit, generated names need stable lenses so the diff between source `.fkb` and roundtrip `.fkb` resolves cleanly. A lens layer over `node_value` / `node_category`.
- Follow-up task: per-tongue idiom expansion — emits/{target}.fk template tables currently cover the universal IR's load-bearing categories. Tongue-specific idioms (Python decorators, Rust traits, Go interfaces, TS generics) are additive and live as new template rows; one band per language.

## What this is not

- **Not a Form-graph interpreter in Python.** The emitted Python is
  native: function definitions, returns, operators, names — what a human
  or another tool can read as Python.
- **Not a giant graph literal.** No `ROOT = R(R(R(...)))` dump as parity
  proof. The proof is multi-tongue emission of a loaded Recipe.
- **Not a source-text generator.** The binary is the source; templates
  render loaded Recipes; nothing reads `.fk` or `.form` text to decide
  what to emit.
- **Not a per-tongue dispatcher.** Every tongue is a row. The engine is
  target-blind.

## Lineage

This spec replaces a prior plan-doc that was released on 2026-05-24
([#2046](https://github.com/seeker71/Coherence-Network/pull/2046)) under
the "plans calcify; let the work speak" discipline. The work then spoke:
binary sensing primitives shipped in
[#2047](https://github.com/seeker71/Coherence-Network/pull/2047), and the
closing-loop proof + write_form_binary native shipped in
[#2048](https://github.com/seeker71/Coherence-Network/pull/2048). This
spec returns as a contract describing the live architecture, not a plan
describing work to come.
