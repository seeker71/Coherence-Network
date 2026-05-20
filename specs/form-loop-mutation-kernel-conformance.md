---
idea_id: agent-pipeline
status: active
source:
  - file: docs/coherence-substrate/kernel-conformance/form-loop-mutation.json
    symbols: [form-loop-mutation]
  - file: scripts/verify_kernel_conformance.py
    symbols: [run_kernel(), run_python_kernel(), run_external_kernel(), main()]
  - file: experiments/form-question-kernels/rust/src/main.rs
    symbols: []
  - file: experiments/form-question-kernels/go/question_kernel.go
    symbols: []
  - file: experiments/form-kernel-ts/src/conformance.ts
    symbols: []
  - file: api/tests/test_kernel_conformance_harness.py
    symbols: [test_python_kernel_passes_loop_mutation_vector(), test_rust_go_and_typescript_kernels_pass_loop_mutation_vector()]
requirements:
  - "The kernel conformance harness accepts a Form loop/mutation vector separate from host effects, core built-ins, infix operators, and control flow."
  - "Python, Rust, Go, and TypeScript return the same JSON-safe values for deterministic for, while, and set forms over local values."
  - "The Rust, Go, and TypeScript implementation claim stays bounded to the vector forms and does not claim complete Form grammar/runtime parity."
done_when:
  - "The loop/mutation vector passes for Python, Rust, Go, and TypeScript."
  - "The existing control-flow, infix, core built-ins, and question-effect vectors still pass for Python, Rust, Go, and TypeScript."
  - "Docs state the exact conformance boundary."
test: "python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-loop-mutation.json --kernel python --kernel rust --kernel go --kernel typescript --json && python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel python --kernel rust --kernel go --kernel typescript --json && python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --kernel typescript --json && python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --kernel typescript --json && python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --kernel typescript --json && cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q"
constraints:
  - "Do not claim Rust, Go, or TypeScript implement the full Form language."
  - "Do not add defn/closure support, recursion, match, with, method dispatch, cell lookup, recipe introspection, or persistence."
  - "Keep the vector deterministic and host-effect free."
---

# Form Loop/Mutation Kernel Conformance — local iteration breath across Python, Rust, Go, and TypeScript

## Purpose

The control-flow vector proved branch choice and lexical local binding. This spec adds local iteration and mutation: `for`, `while`, and `set` over JSON-safe values. It proves accumulator patterns and loop body value flow without widening into functions, recursion, cell lookup, methods, or persistent state.

## Requirements

- [x] **R1**: `docs/coherence-substrate/kernel-conformance/form-loop-mutation.json` names deterministic cases for `for`, `while`, and `set`.
- [x] **R2**: The vector proves list iteration, string iteration, accumulator mutation, list appending through `concat`, unentered while returning `null`, and mutation through an inner block to an outer binding.
- [x] **R3**: Rust, Go, and TypeScript runners evaluate only the vector's bounded loop/mutation forms over literals, existing built-ins, existing infix expressions, and local names.
- [x] **R4**: The question-effect, core built-ins, infix, and control-flow vectors continue to pass after widening the runners.

## Research Inputs

- `2026-05-20` - `api/app/services/substrate/form_runtime.py` - Python runtime behavior for `ForExpr`, `WhileExpr`, and `SetExpr`.
- `2026-05-20` - `api/tests/test_substrate_form_loops.py` - existing Python behavior tests for loops and mutation.
- `2026-05-20` - `docs/coherence-substrate/kernel-conformance/form-control-flow.json` - previous control-flow vector shape.

## Vector Contract

The vector is host-effect free: every case has `expected_events: []`, and the result is a JSON-safe literal value. The vector covers:

- `for x in [items] { body }` returning the list of body values;
- `for c in "abc" { c }` iterating characters;
- `set name = expr` mutating the nearest existing binding;
- `for` bodies that mutate an outer accumulator;
- `while cond { body }` returning the last body value;
- `while false { body }` returning `null`.

The executable command is:

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-loop-mutation.json --kernel python --kernel rust --kernel go --kernel typescript --json
```

## Files to Create/Modify

- `docs/coherence-substrate/kernel-conformance/form-loop-mutation.json` - shared loop/mutation vector.
- `experiments/form-question-kernels/rust/src/main.rs` - add the narrow local loop/mutation evaluator.
- `experiments/form-question-kernels/go/question_kernel.go` - add the narrow local loop/mutation evaluator.
- `experiments/form-kernel-ts/src/conformance.ts` - add the narrow local loop/mutation evaluator.
- `api/tests/test_kernel_conformance_harness.py` - assert Python/Rust/Go/TypeScript pass the loop/mutation vector.
- `docs/coherence-substrate/kernel-conformance/README.md` - document the vector.
- `docs/coherence-substrate/form-language.md` - state the widened but bounded conformance surface.
- `specs/form-control-flow-kernel-conformance.md` - close the previous follow-up pointer.

## Acceptance Tests

- `api/tests/test_kernel_conformance_harness.py::test_python_kernel_passes_loop_mutation_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_go_and_typescript_kernels_pass_loop_mutation_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_go_and_typescript_kernels_pass_control_flow_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_go_and_typescript_kernels_pass_infix_operator_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_go_and_typescript_kernels_pass_core_builtin_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_go_and_typescript_kernels_pass_question_effect_vector`

## Verification

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-loop-mutation.json --kernel python --kernel rust --kernel go --kernel typescript --json
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel python --kernel rust --kernel go --kernel typescript --json
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --kernel typescript --json
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --kernel typescript --json
python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --kernel typescript --json
cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q
python3 scripts/validate_spec_quality.py --file specs/form-loop-mutation-kernel-conformance.md
```

## Out of Scope

- `defn`, closures, recursion, `match`, `with`, methods, substrate cell lookup, recipe introspection, or persistence in Rust, Go, or TypeScript.
- Error-case parity for runaway loops or missing `set` bindings.
- Durable state or host effects beyond the existing question vector.

## Risks and Assumptions

- The Rust, Go, and TypeScript evaluators are deliberately tiny loop/mutation evaluators for this vector.
- `set` mutates only local in-memory bindings created inside the current evaluation.
- The while-loop guard exists in Rust, Go, and TypeScript, but this vector proves only terminating and unentered loops.

## Known Gaps and Follow-up Tasks

- Follow-up task: add `defn` call and recursion conformance once the runner boundary is renamed away from question-only experiments.
- Follow-up task: add `match` and `with` conformance over local JSON-safe values.
- Follow-up task: rename or split the experiment runner directory once it carries enough surface to justify a non-question-specific module boundary.

## Task Card

```yaml
goal: Add a pure Form loop/mutation conformance vector that passes in Python, Rust, Go, and TypeScript.
files_allowed:
  - docs/coherence-substrate/kernel-conformance/form-loop-mutation.json
  - docs/coherence-substrate/kernel-conformance/README.md
  - docs/coherence-substrate/form-language.md
  - experiments/form-question-kernels/rust/src/main.rs
  - experiments/form-question-kernels/go/question_kernel.go
  - experiments/form-kernel-ts/src/conformance.ts
  - api/tests/test_kernel_conformance_harness.py
  - specs/form-control-flow-kernel-conformance.md
  - specs/form-loop-mutation-kernel-conformance.md
done_when:
  - Loop/mutation vector passes for Python, Rust, Go, and TypeScript.
  - Control-flow, infix, core built-ins, and question-effect vectors still pass for Python, Rust, Go, and TypeScript.
  - Docs/spec state the bounded Rust/Go/TypeScript conformance claim.
commands:
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-loop-mutation.json --kernel python --kernel rust --kernel go --kernel typescript --json
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel python --kernel rust --kernel go --kernel typescript --json
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --kernel typescript --json
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --kernel typescript --json
  - python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --kernel typescript --json
  - cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q
constraints:
  - No full Form runtime claim for Rust, Go, or TypeScript.
  - No defn, closures, recursion, match, with, methods, cell lookup, recipe introspection, or persistence.
  - No parser work outside the vector's loop/mutation subset.
```
