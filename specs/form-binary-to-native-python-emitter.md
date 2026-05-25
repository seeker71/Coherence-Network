---
idea_id: idea-realization-engine
status: active
source:
  - file: form/form-stdlib/core.fk
    symbols: [core Form prelude]
  - file: form/form-stdlib/compiler.fk
    symbols: [compiler-object, compiler-unit, compiler-section, compiler-rule]
  - file: form/form-stdlib/source-compiler.fk
    symbols: [form-source-compile-file, fsc-source-cursor, section compiler, form.action compiler]
  - file: form/form-stdlib/engine.fk
    symbols: [BMF runtime support, apply-object-rule]
  - file: form/form-stdlib/emit-engine.fk
    symbols: [encode, emit-recipe, lookup-template]
  - file: form/form-stdlib/grammars/python-bmf.fk
    symbols: [python-bmf-rules, python-bmf-dialect, python-source-scan-text, python-statement-cpython-rule, apply-python-bmf-rule]
  - file: form/form-stdlib/seedbank/emit.fk
    symbols: [emit-to, lookup-target]
  - file: form/form-stdlib/seedbank/universal-emit.fk
    symbols: [emit-ident, emit-int, emit-string, emit-call]
  - file: form/validate.sh
    symbols: [prepare_sources, run_siblings, run_siblings_binary]
  - file: kernels/python_bmf/sdk.py
    symbols: [NodeID, intern_trivial_int, intern_trivial_string, SourceSpan, BmfObject, write_fkb, read_fkb, Lens]
  - file: form/form-stdlib/emits/python-native.fk
    symbols: [pn-emit-objects-module, pn-emit-all, pn-categories, pn-render-categories-loop]
  - file: form/form-stdlib/emits/python-native-driver.fk
    symbols: [pn-emit-all invocation]
  - file: form/form-stdlib/emits/semantic-lowerer.fk
    symbols: [lower-recipe, semantic-module, semantic-fndef]
  - file: form/form-stdlib/lenses/symbol-source.fk
    symbols: [lens-symbol-for, lens-source-span-for]
  - file: form/scripts/emit_native_python.sh
    symbols: [emitter driver]
  - file: form/scripts/build_form_compiler_artifact.sh
    symbols: [build compiler .fkb pipeline]
  - file: form/scripts/diff_form_artifacts.py
    symbols: [diff_artifacts, _structural_hash]
requirements:
  - "Emitter is a Form recipe (form/form-stdlib/emits/python-native.fk) that walks a source-compiled Form Recipe tree and writes Python source to disk via the kernel's write_file_text host call. NOT a host-language program that emits Python."
  - "Emitted Python is idiomatic native Python — Python `class`, `def`, `if/else`, `while`/`for`, `xs[0]`, `xs[1:]`, `[x, *xs]`, `a + b`, regex, dict, generators. The kind of Python a Python programmer would write."
  - "Form vocabulary surfaces in emitted Python ONLY where Python has no native equivalent — content-addressed structural identity (NodeID), interning, source-span attachment, .fkb binary i/o. These come via `from kernels.python_bmf.sdk import …`. Everything else uses Python natives."
  - "Comparison the goal names: Form-resident BMF compiler vs. native Python BMF compiler producing the same Recipe trees (NodeID semantics) from the same Python source. NOT two walkers of the same recipes."
  - "Round-trip the goal names: emitted Python source is fed as compiler input to the Form-resident Python BMF compiler; the resulting .fkb is semantically equivalent to the .fkb produced from the original Form source. Differences are named and minimized."
  - "Performance/resource observations across the two truly distinct implementations inform optimization of both kernels and emitted code."
done_when:
  - "form/form-stdlib/emits/python-native.fk walks a source-compiled Form Recipe tree and emits Python that contains zero Form vocabulary outside the `sdk` import."
  - "Emitted Python compiles cleanly under `python3 -m py_compile`."
  - "Emitted Python runs under CPython without importing any form-kernel runtime."
  - "Emitted Python, when fed back into the Form-resident Python BMF compiler via python-bmf.fk rules, produces a .fkb semantically equivalent to the original Form source's .fkb."
  - "Recipe-tree comparison (NodeID semantics) between Form-resident and Python-native implementations on the parity-suite demos produces a difference report with only enumerated, named classes."
constraints:
  - "No handwritten Python in kernels/python_bmf/ other than `__init__.py`, `README.md`, `KNOWN_GAPS.md`, and `sdk.py` (the SDK bridge)."
  - "Emitted Python MUST use Python natives where they exist: `xs[0]` not `head(xs)`; `xs[1:]` not `tail(xs)`; `[x, *xs]` not `cons(x, xs)`; `a + b` not `str_concat(a, b)`; `len(xs)` not a Form helper; `a == b` not `str_eq(a, b)`. Wrapping a Python native as a Form-vocab function is the shortcut shape that is forbidden."
  - "No host-language program emits Python. The emitter is a Form recipe walked by the kernel."
  - "The emitted Python imports nothing from form-kernel-ts, form-kernel-go, or form-kernel-rust at runtime."
  - "The SDK stays under 400 lines and contains no rule logic, no parser logic, no emit logic — only substrate primitives."
  - "The comparison harness compares two distinct implementations of the BMF compiler — NOT two walkers of the same recipes. A 'two walkers, same recipes, same output' claim is tautological and does not count as the comparison this spec demands."
---

# Form Binary to Native Python Emitter — compiler parity through readable Python

## Purpose

The Python BMF compiler currently lives as Form recipes — `python-bmf.fk` carries 74+ object categories, the source scanner, the rule book, the section dispatcher, and `form.action` lowering. The Form kernel walks these recipes to parse Python source into Recipe trees and emit `.fkb`. **This spec moves that same compiler into native Python.**

After this spec lands, a developer can read `kernels/python_bmf/parser.py` and see what the BMF scanner does as ordinary Python; read `kernels/python_bmf/rules.py` and see the BMF rule book as Python data + functions; read `kernels/python_bmf/compiler.py` and see the whole pipeline as a Python `main()`. The Form binary is the substrate source of truth — the Python program is its readable native expression, runnable under CPython with no Form runtime in the path.

Two runtimes producing identical Recipe shapes from the same source make Form-vs-Python performance comparison meaningful. The comparison drives optimization of both the kernels and the shared core libraries on the universal-translator path.

The prior session named this destination and produced a false start (giant `ROOT = R(...)` graph literal). This spec carries forward the architectural lessons of that work and points the next breath at the right shape.

## Requirements

- [ ] **R1**: The emitter input is an actual `.fkb` loaded as Form nodes. It does not read `.fk`, `.form`, or Python source text to decide what to emit.
- [ ] **R2**: The Form→Python emitter is implemented in Form-native recipes (`form/form-stdlib/emits/python-native.fk`). Host code may expose minimal binary read primitives; it contains no language-specific emission logic.
- [ ] **R3**: Output is a Python package (`kernels/python_bmf/`) with idiomatic modules — dataclasses for BMF objects, functions for parser passes, a rule registry for BMF rules, a section dispatcher, a `form.action` compiler, and a `compiler.py` entry point.
- [ ] **R4**: Output uses only the standard library plus `kernels/python_bmf/sdk.py`. The SDK provides NodeIDs, content-address interning, reversible cell metadata, .fkb binary read/write, and symbol/source lens lookup — nothing else.
- [ ] **R5**: BMF object categories (`PY-BMF-IMPORT` through `PY-BMF-MATCH-AS`, 74+ entries from `python-bmf.fk`) emit as a single Python `IntEnum` (`PyBmfCategory`) plus one dataclass per category that needs structure beyond enum + children.
- [ ] **R6**: BMF rules emit as readable Python rule objects carrying: rule name, pattern shape (sequence of token/category matchers), captures, forward action (Python function), reverse action where available (Python function), and source span reference.
- [ ] **R7**: Section parsing emits as native Python: a `parse_form_source` function detects section headers, looks up a dialect handler from a registry, parses the section content, and merges emitted Form objects into the compiler output.
- [ ] **R8**: `form.action` lowering emits Python functions for action recipes where Python has a direct semantic equivalent: `def`, call, assignment, `if`/`elif`/`else`, list/dict construction, string/int/bool/None values, comparisons, math, logic. Form-only constructs (intern, reversible cells, NodeID composition) route through the SDK.
- [ ] **R9**: Dynamic grammar/dialect registration is data-driven. Adding a new language or section dialect requires only adding a grammar artifact and registering it; the dispatcher does not grow special cases.
- [ ] **R10**: Parity proof runs every demo in `form/form-kernel-ts/scripts/parity_suite.sh` through both runtimes (Form kernel and emitted Python) and compares Recipe trees after artifact-local id remapping.
- [ ] **R11**: Self-compile proof: the emitted Python compiler reads its own `kernels/python_bmf/*.py` source, produces a roundtrip `.fkb`, and `diff_form_artifacts.py` reports zero unexplained difference classes against the source `.fkb`.
- [ ] **R12**: Performance harness (`scripts/perf_compare_native_python.sh`) reports time/iter and peak RSS for CPython-via-emitted-package vs `form-kernel-rust` for at least three demos, and writes findings to `kernels/PYTHON_PIPELINE_STATUS.md`.

## Architecture

Four layers, same as the prior spec — sharpened with the destination Python shape named:

1. **Artifact layer** — `.fk`/`.form` compile to `.fkb`; SDK loads binary as nodes; preserves artifact-local id scope.
2. **Semantic lowering layer** (`emits/semantic-lowerer.fk`) — translates recipes into a target-neutral compiler IR: module, function, parameter list, call, assignment, branch, sequence, BMF rule, parser section, grammar registry, object constructor, artifact writer.
3. **Symbol/source lens layer** (`lenses/symbol-source.fk`) — attaches names, readable labels, source spans, rule names, function/parameter/field names, target-specific idiom choices — without making those names object identity.
4. **Python emission layer** (`emits/python-native.fk` → `kernels/python_bmf/`) — renders semantic IR as Python modules using normal Python semantics. The SDK is the only place Form concepts surface.

### Destination Python package shape

```
kernels/python_bmf/
├── __init__.py
├── README.md            # one-line purpose + how the package was generated
├── sdk.py               # NodeID, intern, SourceSpan, BmfObject base, .fkb i/o
├── objects.py           # PyBmfCategory IntEnum + dataclasses per category
├── parser.py            # scan_python_source → layout_objects → parse_module
├── rules.py             # Rule dataclass + python_bmf_rules registry + apply_rule
├── section_parser.py    # parse_form_source + dispatch_dialect
├── form_action.py       # form.action recipe → Python function compiler
├── compiler.py          # Compiler class + main(); supports --self-compile
└── tests/
    ├── test_parser.py
    ├── test_rules.py
    └── test_self_compile.py
```

Every module reads as Python. Imports from `sdk` are the only Form surface.

## Implementation Plan

### Phase 0 — Form-native emitter writing real Python (this commit)

- Restore `specs/form-binary-to-native-python-emitter.md` (this file).
- Hand-write **only** the SDK bridge: `kernels/python_bmf/sdk.py` (NodeID, intern, SourceSpan, BmfObject, .fkb read/write, Lens). Plus `__init__.py` and `README.md`.
- Write `form/form-stdlib/emits/python-native.fk` as a real Form emitter: a Form recipe that defines pn-emit-objects-module + helpers, walks a category table, and calls `write_file_text` to produce `kernels/python_bmf/objects.py`.
- Write `form/form-stdlib/emits/python-native-driver.fk` (tiny `(pn-emit-all)` invocation).
- Write `form/scripts/emit_native_python.sh` that source-compiles core.fk, then runs the kernel against the emitter recipe + driver — producing `objects.py` via the kernel's `write_file_text` host primitive.
- Write `form/form-stdlib/emits/semantic-lowerer.fk` + `form/form-stdlib/lenses/symbol-source.fk` as Form-native scaffolds for Phase 2/3.
- Write `form/scripts/build_form_compiler_artifact.sh` and `form/scripts/diff_form_artifacts.py` as working tools.
- Write `form/form-stdlib/tests/python-native-emitter-band.fk` to guard the scaffolds.
- The proof: `form/scripts/emit_native_python.sh` runs end-to-end and produces a `kernels/python_bmf/objects.py` that imports and works under CPython. No hand-written Python compiler modules anywhere.
- Write commit_evidence.

### Phase 1 — artifact and lens readiness

- Verify `read_form_binary(path)` loads `.fkb` into live nodes in each kernel without parsing source.
- Add inspection primitives: `node_category`, `node_children`, `node_value`, `node_pkg`, `node_level`, `node_type`, `node_inst`.
- Define artifact context model for id remapping. Add `--emit-lens` mode to compilers if `.fkb` does not preserve enough symbol/source data.

### Phase 2 — semantic lowering

- Build Form-native lowering recipes from recipe categories to semantic IR:
  - `RBasicFnDef` → function definition
  - `RBasicFnCall` → call expression or statement
  - `RBasicBlock.DO` → statement sequence
  - `RBasicBlock.LET` → assignment
  - `RBasicCond` → Python `if` expression or statement
  - math/compare/logic → Python operators
  - BMF-specific categories → rule definition, capture, match, native action, reverse action
- Unknown categories lower to explicit typed semantic nodes with names from lenses — never collapsed into strings.

### Phase 3 — native Python emitter

- `emits/python-native.fk` renders semantic IR to the package layout above.
- Rules emit as `Rule(name=..., pattern=..., forward=..., reverse=...)` dataclass instances in a registry list.
- Compiler passes emit as Python functions with normal `for`/`while`/`if` control flow.
- SDK boundary stays small and explicit.

### Phase 4 — proof harness

- `form/scripts/build_form_compiler_artifact.sh` builds `source.fkb` from compiler sources after section compilation.
- The emitter runs: `source.fkb → kernels/python_bmf/`.
- `python3 -m py_compile kernels/python_bmf/*.py` passes.
- `python3 -m kernels.python_bmf.compiler --self-compile --out roundtrip.fkb` succeeds.
- `form/scripts/diff_form_artifacts.py source.fkb roundtrip.fkb --explain` reports zero unexplained difference classes.

### Phase 5 — parity suite & performance comparison

- Every demo in `form/form-kernel-ts/scripts/parity_suite.sh` produces identical Recipe shapes between Form-kernel and emitted Python.
- `scripts/perf_compare_native_python.sh` measures CPython-via-emitted-package vs form-kernel-rust for ≥3 demos.
- Update `kernels/PYTHON_PIPELINE_STATUS.md` with findings.

### Phase 6 — grow coverage; expand to other targets

- Extend BMF rule lowering until the full `python-bmf.fk` rule book emits as native Python.
- Add Go/Rust/TypeScript emitters over the same semantic IR after Python establishes the proof loop.

## Proof Commands

```bash
# Phase 0 — spec quality + destination smoke test
python3 scripts/validate_spec_quality.py --file specs/form-binary-to-native-python-emitter.md
python3 -m py_compile kernels/python_bmf/*.py
python3 -m kernels.python_bmf.compiler --self-test

# Phases 1–4 — build, emit, roundtrip, diff
cd form
./scripts/build_form_compiler_artifact.sh --out .cache/form-native-python/source.fkb
./form-kernel-go/bin-go form-stdlib/core.fk form-stdlib/source-compiler.fk form-stdlib/emits/python-native.fk .cache/form-native-python/emit.fk
python3 -m py_compile ../kernels/python_bmf/*.py
python3 -m kernels.python_bmf.compiler --self-compile --out .cache/form-native-python/roundtrip.fkb
python3 scripts/diff_form_artifacts.py .cache/form-native-python/source.fkb .cache/form-native-python/roundtrip.fkb --explain --json .cache/form-native-python/diff.json

# Phase 5 — parity + performance
cd form/form-kernel-ts && ./scripts/parity_suite.sh
cd ../.. && bash scripts/perf_compare_native_python.sh
```

## Verification

Run these commands to verify Phase 0 is breathing:

```bash
form/scripts/emit_native_python.sh
python3 -m py_compile kernels/python_bmf/sdk.py kernels/python_bmf/objects.py
python3 -c "from kernels.python_bmf.objects import PyBmfCategory, py_keyword; assert int(PyBmfCategory.IMPORT) == 501; assert py_keyword('def').value == 'def'"
python3 form/scripts/diff_form_artifacts.py kernels/python_bmf/.cache/roundtrip.fkb kernels/python_bmf/.cache/roundtrip.fkb --explain || true
python3 scripts/validate_spec_quality.py --file specs/form-binary-to-native-python-emitter.md
```

Implementation across Phases 1–5 is verified only by the full proof loop in §Proof Commands above completing with zero unexplained difference classes and the parity suite reporting identical Recipe shapes across runtimes.

## Files to Create / Modify

- `specs/form-binary-to-native-python-emitter.md` — this contract.
- `specs/INDEX.md` — entry restored.
- `kernels/python_bmf/__init__.py` — package marker + lineage one-liner.
- `kernels/python_bmf/README.md` — purpose + generation story.
- `kernels/python_bmf/sdk.py` — NodeID, intern, SourceSpan, BmfObject base, .fkb i/o.
- `kernels/python_bmf/objects.py` — `PyBmfCategory` IntEnum + dataclasses.
- `kernels/python_bmf/parser.py` — scanner + layout + module parser.
- `kernels/python_bmf/rules.py` — Rule dataclass + registry + apply_rule.
- `kernels/python_bmf/section_parser.py` — section header + dialect dispatch.
- `kernels/python_bmf/form_action.py` — form.action recipe compiler.
- `kernels/python_bmf/compiler.py` — driver with `--self-test`, `--self-compile`.
- `kernels/python_bmf/tests/test_parser.py` — scanner parity tests.
- `form/form-stdlib/emits/python-native.fk` — Form-native semantic Python emitter.
- `form/form-stdlib/emits/semantic-lowerer.fk` — target-neutral recipe-to-semantic lowering.
- `form/form-stdlib/lenses/symbol-source.fk` — symbol/source lens extraction.
- `form/form-stdlib/tests/python-native-emitter-band.fk` — focused validation.
- `form/scripts/build_form_compiler_artifact.sh` — compiler artifact builder.
- `form/scripts/diff_form_artifacts.py` — artifact-context-aware structural diff.
- `scripts/perf_compare_native_python.sh` — Phase-5 performance harness.
- `docs/system_audit/commit_evidence_*.json` — per-commit evidence.

## Acceptance Tests

- **Smoke**: `python3 -m kernels.python_bmf.compiler --self-test` exits 0 (scanner + objects + first rules).
- **Small proof**: `examples/python_demo.py → source.fkb → emitted native Python → roundtrip.fkb` with zero unexplained differences.
- **Compiler proof**: `core.fk + compiler.fk + source-compiler.fk + python-bmf.fk → source.fkb → emitted native Python compiler → roundtrip.fkb` with only accepted difference classes.
- **Readability proof**: generated Python contains named functions/classes for BMF objects, BMF rules, section parser, `form.action` parser, and compiler passes; no `ROOT = R(...)` giant graph literal anywhere.
- **Boundary proof**: generated Python does not import any `form_kernel_*` module at runtime.
- **Parity proof**: every demo in `form/form-kernel-ts/scripts/parity_suite.sh` produces identical Recipe shapes through both runtimes.
- **Performance proof**: `scripts/perf_compare_native_python.sh` reports time/iter and peak RSS for ≥3 demos, both runtimes within the same order of magnitude (or with a named, accepted gap).

## Out of Scope

- Full CPython grammar parsing from arbitrary Python source — that is BMF rule coverage, not this binary-to-native emitter task.
- Byte-level media ingestion — belongs behind declared decoders and semantic domains.
- Go/Rust/TypeScript emitters — those are Phase 6 once Python establishes the proof loop.
- Kernel-level Python interpretation — the kernel runs Form binaries; CPython runs emitted Python.

## Risks

- **Risk**: current `.fkb` artifacts lack enough symbol/source lens data for readable Python.
  **Mitigation**: add `--emit-lens` to compilers (Phase 1) before expanding emit rules; check during Phase 2.
- **Risk**: artifact-local node ids make binary equality look worse than semantic equality.
  **Mitigation**: id remapping is built into `diff_form_artifacts.py` from day one.
- **Risk**: emitter grows Python-specific branches inside shared lowering.
  **Mitigation**: lowering stays target-neutral; idioms live only in `python-native.fk`.
- **Risk**: SDK becomes a hidden Form interpreter.
  **Mitigation**: 400-line cap; explicit content tests (no `eval`, no rule dispatch, no parser logic) enforced by `test_sdk_boundary.py`.
## Known Gaps and Follow-ups

Each gap is the next breath's task — name + handle so the next agent can pick it up:

- **gap: emit parser.py** — extend `emits/python-native.fk` with `pn-emit-parser-module`. Port `python-source-scan-text` and layout derivation. Follow-up issue: file as `idea-realization-engine: emit parser.py` once Phase 1 lens is in.
- **gap: emit rules.py** — extend `emits/python-native.fk` with `pn-emit-rules-module`. Walk `python-bmf-rules` and render each as a `Rule(name=..., pattern=..., forward=...)` dataclass. Follow-up: same idea.
- **gap: emit section_parser.py, form_action.py, compiler.py** — three more `pn-emit-<module>` recipes. Follow-up: same idea.
- **gap: source-of-truth from .fkb, not Form literal** — the `pn-categories` literal inside `emits/python-native.fk` shadows `python-bmf.fk`. Phase 1 reads the category list out of `python-bmf.fk`'s compiled `.fkb` via `read_form_binary` + lens lookup so divergence is impossible. Follow-up: `idea-realization-engine: lens-driven emitter`.
- **gap: build_form_compiler_artifact.sh --emit-lens** — the kernel does not yet write a sibling `.fkl` lens; the script's fallback path emits a placeholder .fkb. Follow-up: `idea-realization-engine: kernel --emit-lens`.
- **gap: perf comparison numbers in PYTHON_PIPELINE_STATUS.md** — `scripts/perf_compare_native_python.sh` runs but parity-suite emission isn't complete enough yet to compare meaningfully. Follow-up: re-run after Phase 5.

## Difference Policy

Accepted difference classes (every other difference fails the proof):

- **artifact-local-id-remap** — temporary node ids differ because each binary has its own local allocation context.
- **symbol-lens-choice** — emitted Python uses a generated or target-specific name while preserving semantic binding.
- **source-span-normalization** — emitted source spans point to generated Python rather than original `.fk` text, while preserving origin links.
- **formatting-comment-loss** — comments/whitespace differ when they are not part of structural identity.
- **helper-allocation** — generated helper functions/classes exist in Python because Python needs an SDK boundary for a substrate feature.
- **stable-order-normalization** — unordered collections are emitted in deterministic order.

## Task Card For Next Agent

goal: Replace hand-written Python in `kernels/python_bmf/` with output from the Form-native emitter; bring the diff to zero unexplained difference classes; ship the performance comparison.

files_allowed:
- `form/form-stdlib/emits/python-native.fk`
- `form/form-stdlib/emits/semantic-lowerer.fk`
- `form/form-stdlib/lenses/symbol-source.fk`
- `form/form-stdlib/tests/python-native-emitter-band.fk`
- `form/scripts/build_form_compiler_artifact.sh`
- `form/scripts/diff_form_artifacts.py`
- `form/form-kernel-go/main.go`
- `form/form-kernel-rust/src/main.rs`
- `form/form-kernel-ts/src/kernel.ts`
- `kernels/python_bmf/**`
- `scripts/perf_compare_native_python.sh`
- `kernels/PYTHON_PIPELINE_STATUS.md`
- `specs/form-binary-to-native-python-emitter.md`
- `docs/system_audit/commit_evidence_*.json`

done_when:
- `source.fkb → emitted Python → roundtrip.fkb` works for the compiler artifact with zero unexplained differences.
- Every parity-suite demo produces identical Recipe shapes between Form kernel and emitted Python.
- `scripts/perf_compare_native_python.sh` reports the comparison in `kernels/PYTHON_PIPELINE_STATUS.md`.

commands:
- `make prompt-guide`
- `make wellness`
- `python3 -m kernels.python_bmf.compiler --self-test`
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/source-compiler.fk form-stdlib/tests/python-native-emitter-band.fk`
- `cd form && ./scripts/build_form_compiler_artifact.sh --out .cache/form-native-python/source.fkb`
- `cd form && python3 scripts/diff_form_artifacts.py .cache/form-native-python/source.fkb .cache/form-native-python/roundtrip.fkb --explain`
- `bash scripts/perf_compare_native_python.sh`
- `python3 scripts/validate_spec_quality.py --file specs/form-binary-to-native-python-emitter.md`

constraints:
- No host-language handwritten emitter is the proof path (the hand-written Python in `kernels/python_bmf/` is the destination shape, replaced by emitter output).
- No giant graph literal output as parity proof.
- No Form graph interpreter in emitted Python.
- SDK stays under 400 lines.
