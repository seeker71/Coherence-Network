---
idea_id: idea-realization-engine
status: active
source:
  - file: form/form-stdlib/core.fk
    symbols: [core Form prelude]
  - file: form/form-stdlib/compiler.fk
    symbols: [BMF grammar section, compiler recipes]
  - file: form/form-stdlib/source-compiler.fk
    symbols: [form-source-compile-file, section compiler, form.action compiler]
  - file: form/form-stdlib/engine.fk
    symbols: [BMF runtime support]
  - file: form/form-stdlib/emit-engine.fk
    symbols: [encode, emit-recipe]
  - file: form/form-stdlib/seedbank/emits/python.fk
    symbols: [python-templates]
  - file: form/validate.sh
    symbols: [prepare_sources, run_siblings, run_siblings_binary]
requirements:
  - "Emit native Python implementation source from actual compiled Form binary artifacts, not from source text or host-language side generators."
  - "Generated Python expresses compiler behavior as Python functions/classes/rules with Python-native control flow and data structures."
  - "Parity proof runs the emitted Python compiler on its own emitted compiler surface and compares the resulting .fkb to the source .fkb with explained differences."
done_when:
  - "A compiler .fkb emits readable native Python source without giant Form graph literals or a Form graph interpreter."
  - "The emitted Python compiler produces a roundtrip .fkb from its own emitted source."
  - "A structural diff report names every difference class between source .fkb and roundtrip .fkb."
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/source-compiler.fk && cd .. && python3 scripts/validate_spec_quality.py --file specs/form-binary-to-native-python-emitter.md"
constraints:
  - "No handwritten Python emitter outside Form-native recipes."
  - "No tokenizer fallback; grammar/parser support is BMF or another declared runtime grammar, loaded dynamically."
  - "No generated ROOT = R(...) graph dump as the implementation proof."
  - "No kernel Python interpreter; host-language runtimes run their own native emitted code."
---

# Form Binary to Native Python Emitter -- compiler parity through readable Python

## Purpose

The Form binary is the substrate source of truth. The Python output is not a Form graph runner. It is a native Python implementation of the same compiler: BMF objects, BMF rule execution, section parsing, `form.action` parsing, compiler lowering, and artifact emission expressed in Python functions, classes, and idioms that a human or machine can read as Python.

This spec gives the next agent a precise path after the false starts: do not emit a giant object literal, do not interpret Form in Python, and do not generate Python from source text. Load the compiled `.fkb`, recover semantic compiler intent through recipes plus symbol/source lenses, emit Python-native implementation code, then prove by compiling the emitted compiler back to a comparable `.fkb`.

## Requirements

- [ ] **R1**: The emitter input is an actual `.fkb` loaded as Form nodes. It does not read `.fk`, `.form`, or Python source text to decide what to emit.
- [ ] **R2**: The emitter is implemented in Form-native recipes. Host-language code may expose minimal substrate access primitives, but it does not contain language-specific emission logic.
- [ ] **R3**: The output Python is implementation-shaped: modules, dataclasses or plain classes, functions, parser rules, BMF object constructors, section handlers, compiler passes, and artifact writers.
- [ ] **R4**: The output Python avoids Form graph dominance. It may use a tiny SDK only for concepts Python lacks directly: content-addressed node identity, binary artifact writing, reversible cell metadata, and symbol/source lens lookup.
- [ ] **R5**: Names are emitted through symbol lenses. Node identity does not depend on Python names, Form names, or source identifiers; names are surface symbols attached for a target language and context.
- [ ] **R6**: BMF rule sections emit as readable Python rule definitions, not strings passed into another parser. Each rule carries match shape, captures, native action recipe, reverse action where available, and source span references.
- [ ] **R7**: Section parsing is represented as native Python compiler code: detect section headers, select a dialect/grammar dynamically, parse section content, and merge emitted Form objects into the compiler output.
- [ ] **R8**: `form.action` compilation emits native Python functions for action recipes where Python has a direct semantic equivalent: `def`, call, assignment, branch, list construction, string/int/bool/null values, comparisons, math, logic, and file reads/writes where explicitly part of compiler IO.
- [ ] **R9**: Dynamic grammar/dialect registration is data-driven. Adding a new language or section dialect is done by adding runtime-loaded grammar/config artifacts, not by adding special cases to a fixed engine file.
- [ ] **R10**: The proof command builds a source compiler `.fkb`, emits native Python, runs the emitted Python compiler against its own emitted source surface, writes a roundtrip `.fkb`, and compares source and roundtrip artifacts.
- [ ] **R11**: The diff tool maps node ids between artifact contexts before comparison. Unregistered temporary blueprint/recipe ids are local to an artifact context and must be matched by structure, not raw id equality.
- [ ] **R12**: Every accepted difference class is named in the diff report: node-id remapping, symbol lens differences, source span differences, formatting/comments, helper-name allocation, stable ordering, or runtime-registration metadata.

## Architecture

The flow has four layers.

1. **Artifact layer**: compile `.fk` and `.form` into `.fkb`; load the binary as nodes; read child/category/value/id fields; preserve artifact-local id scope.
2. **Semantic lowering layer**: translate recipes into a target-neutral compiler IR: module, function, parameter list, call, assignment, branch, sequence, BMF rule, parser section, grammar registry, object constructor, artifact writer.
3. **Symbol/source lens layer**: attach names, readable labels, source spans, rule names, function names, parameter names, field names, and target-specific idiom choices without making those names object identity.
4. **Python emission layer**: render the semantic IR as Python modules with normal Python semantics and a small SDK only for substrate-native features.

## Implementation Plan

### Phase 0 -- release wrong paths from active tissue

- Remove or quarantine any emitter whose proof is a giant `ROOT = R(...)` graph expression.
- Remove Python source roundtrip work from the parity claim; that belongs to grammar coverage, not binary-to-native emission.
- Keep only learnings that serve this spec: binary load primitives, string escaping requirements, artifact-local node-id remapping, and the need for declaration/DAG output as a diagnostic tool.

### Phase 1 -- artifact and lens readiness

- Add or verify `read_form_binary(path)` can load `.fkb` into live nodes in each supported kernel without parsing source.
- Add or verify node inspection primitives: `node_category`, `node_children`, `node_value`, `node_pkg`, `node_level`, `node_type`, `node_inst`.
- Add an artifact context model for id remapping. Raw node ids from one `.fkb` are not globally comparable to raw node ids from another `.fkb` unless registered with the substrate.
- Add symbol/source lens extraction from compiled artifacts. If current `.fkb` does not preserve enough naming/source data, extend compilation to emit a sibling lens artifact or embedded lens section.

### Phase 2 -- semantic lowering

- Build Form-native lowering recipes from known recipe categories to semantic IR:
  - `RBasicFnDef` -> function definition
  - `RBasicFnCall` -> call expression or statement
  - `RBasicBlock.DO` -> statement sequence
  - `RBasicBlock.SEQUENCE` -> ordered list
  - `RBasicBlock.LET` -> assignment/binding
  - `RBasicCond` -> Python `if` expression or statement
  - math/compare/logic -> Python operators
  - BMF-specific categories -> rule definition, capture, match, native action, reverse action
- Unknown categories lower to explicit typed semantic nodes with names from lenses. They must not collapse into strings or Form graph literals.
- Keep lowering target-neutral so Go, Rust, TypeScript, BML, natural language, and media emitters can reuse it.

### Phase 3 -- native Python emitter

- Emit a Python package layout, not one file if the compiler naturally separates:
  - `bmf_objects.py`
  - `bmf_rules.py`
  - `section_parser.py`
  - `form_action.py`
  - `compiler.py`
  - `artifact.py`
  - `sdk.py` for substrate-only primitives
- Emit readable functions/classes from semantic IR.
- Emit BMF rules as first-class Python rule objects or decorated functions:
  - pattern shape
  - captures
  - forward action
  - reverse action when available
  - source span reference
- Emit compiler passes with Python-native loops/recursion/conditionals.
- Keep the SDK small and explicit. It may provide Form binary encode/decode, local id remapping, content-address interning, and cell metadata; it must not become a Form interpreter.

### Phase 4 -- proof harness

- Build `source.fkb` from the compiler sources after section compilation.
- Run the Form-native emitter:
  - `source.fkb -> emitted_python_package/`
- Run Python checks:
  - `python3 -m py_compile emitted_python_package/**/*.py`
  - `python3 emitted_python_package/compiler.py --self-compile --out roundtrip.fkb`
- Compare:
  - `source.fkb` vs `roundtrip.fkb`
  - apply artifact-local id remapping
  - compare semantic structure, category, child order, values, registered ids, symbol lenses, and spans
- Write a diff report with counts and named classes.

### Phase 5 -- grow coverage without changing the target

- Expand BMF rule lowering until the BMF compiler itself is emitted as native Python.
- Expand `form.action` lowering until `core.fk`, `compiler.fk`, `source-compiler.fk`, and the relevant grammar files roundtrip.
- Add Go/Rust/TypeScript emitters over the same semantic IR after Python establishes the proof loop.
- Add natural language and media output as new emitters over declared semantic domains, not as byte-level dumpers.

## Proof Commands

The final implementation must provide a single command equivalent to:

```bash
cd form
./scripts/build_form_compiler_artifact.sh --out .cache/form-native-python/source.fkb
./form-kernel-go/bin-go form-stdlib/core.fk form-stdlib/source-compiler.fk form-stdlib/emits/python-native.fk .cache/form-native-python/emit.fk
python3 -m py_compile .cache/form-native-python/emitted/**/*.py
python3 .cache/form-native-python/emitted/compiler.py --self-compile --out .cache/form-native-python/roundtrip.fkb
python3 scripts/diff_form_artifacts.py .cache/form-native-python/source.fkb .cache/form-native-python/roundtrip.fkb --explain --json .cache/form-native-python/diff.json
```

The exact file names can change. The proof shape cannot.

## Verification

This planning commit is verified by the spec quality gate and by the repository wellness/start gates. The implementation that follows this plan is verified only when the full proof loop runs:

```bash
cd form
./scripts/build_form_compiler_artifact.sh --out .cache/form-native-python/source.fkb
./form-kernel-go/bin-go form-stdlib/core.fk form-stdlib/source-compiler.fk form-stdlib/emits/python-native.fk .cache/form-native-python/emit.fk
python3 -m py_compile .cache/form-native-python/emitted/**/*.py
python3 .cache/form-native-python/emitted/compiler.py --self-compile --out .cache/form-native-python/roundtrip.fkb
python3 scripts/diff_form_artifacts.py .cache/form-native-python/source.fkb .cache/form-native-python/roundtrip.fkb --explain --json .cache/form-native-python/diff.json
```

The proof fails if generated Python is only a Form graph reconstruction, if the roundtrip `.fkb` cannot be produced, or if the diff report contains an unnamed difference class.

## Gaps

- The current repository does not yet have `python-native.fk`, `semantic-lowerer.fk`, `symbol-source.fk`, `build_form_compiler_artifact.sh`, or `diff_form_artifacts.py`.
- The current `.fkb` shape may not preserve all symbol/source lens data needed for readable native Python. The next implementation task must verify this before writing broad emit rules.
- Existing exploratory emitter work that emits graph-shaped Python is not accepted by this spec as parity proof.

## Difference Policy

Accepted differences are narrow and named:

- **artifact-local-id-remap**: temporary node ids differ because each binary has its own local allocation context.
- **symbol-lens-choice**: emitted Python uses a generated or target-specific name while preserving semantic binding.
- **source-span-normalization**: emitted source spans point to generated Python rather than original `.fk` text, while preserving origin links.
- **formatting-comment-loss**: comments/whitespace differ when they are not part of structural identity.
- **helper-allocation**: generated helper functions/classes exist in Python because Python needs an SDK boundary for a substrate feature.
- **stable-order-normalization**: unordered collections are emitted in deterministic order.

Any other difference fails the proof until explained or repaired.

## Files to Create/Modify

- `form/form-stdlib/emits/python-native.fk` - Form-native semantic Python emitter.
- `form/form-stdlib/emits/semantic-lowerer.fk` - target-neutral recipe-to-semantic lowering.
- `form/form-stdlib/lenses/symbol-source.fk` - symbol/source lens extraction and lookup.
- `form/scripts/build_form_compiler_artifact.sh` - compiler artifact builder used by proof.
- `form/scripts/diff_form_artifacts.py` - artifact-context-aware structural diff.
- `form/form-stdlib/tests/python-native-emitter-band.fk` - focused Form validation.
- `specs/form-binary-to-native-python-emitter.md` - this contract.

## Acceptance Tests

- Small proof: `fib.fk -> source.fkb -> emitted native Python -> roundtrip.fkb`, with zero unexplained differences.
- Compiler proof: `core.fk + compiler.fk + source-compiler.fk -> source.fkb -> emitted native Python compiler -> roundtrip.fkb`, with only accepted difference classes.
- Readability proof: generated Python contains named functions/classes for BMF objects, BMF rules, section parser, `form.action` parser, and compiler passes; no `ROOT = R(...)` giant graph literal is present.
- Boundary proof: generated Python does not import a Form graph interpreter.

## Out of Scope

- Full CPython grammar parsing from arbitrary Python source. That is a language grammar task over BMF rules, not this binary-to-native emitter task.
- Byte-level media ingestion. Media support belongs behind declared decoders and semantic domains.
- Kernel-level Python interpretation. The kernel loads binaries and executes Form; Python executes emitted Python.

## Risks and Mitigations

- **Risk**: current `.fkb` artifacts lack enough symbol/source lens data for readable Python. **Mitigation**: add lens preservation to the compiler before emitter expansion.
- **Risk**: artifact-local node ids make binary equality look worse than semantic equality. **Mitigation**: require id remapping and structural diff before declaring mismatch.
- **Risk**: emitter grows Python-specific branches in shared lowering. **Mitigation**: keep lowering target-neutral and put idioms in target emitters.
- **Risk**: SDK becomes a hidden Form interpreter. **Mitigation**: constrain SDK to substrate-native features Python cannot express directly.

## Task Card For Next Agent

goal: Implement the Form-native binary-to-native-Python emitter proof loop for the Form compiler.

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
- `specs/form-binary-to-native-python-emitter.md`
- `docs/system_audit/commit_evidence_*.json`

done_when:
- `source.fkb -> emitted Python -> roundtrip.fkb` works for the compiler artifact.
- The diff report has zero unexplained difference classes.
- Generated Python is readable native Python and contains no giant `ROOT = R(...)` graph literal.

commands:
- `make prompt-guide`
- `make wellness`
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/source-compiler.fk form-stdlib/tests/python-native-emitter-band.fk`
- `cd form && ./scripts/build_form_compiler_artifact.sh --out .cache/form-native-python/source.fkb`
- `cd form && python3 scripts/diff_form_artifacts.py .cache/form-native-python/source.fkb .cache/form-native-python/roundtrip.fkb --explain`
- `python3 scripts/validate_spec_quality.py --file specs/form-binary-to-native-python-emitter.md`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_<date>_form_binary_to_native_python_emitter.json`

constraints:
- No host-language handwritten emitter.
- No source-text generator as the proof path.
- No Form graph interpreter in Python.
- No giant graph literal output as parity proof.
