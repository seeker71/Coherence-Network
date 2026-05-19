---
idea_id: agent-pipeline
status: active
source:
  - file: docs/coherence-substrate/kernel-conformance/form-control-flow.json
    symbols: [form-control-flow]
  - file: scripts/verify_kernel_conformance.py
    symbols: [run_kernel(), run_python_kernel(), run_external_kernel(), main()]
  - file: experiments/form-question-kernels/rust/src/main.rs
    symbols: []
  - file: experiments/form-question-kernels/go/question_kernel.go
    symbols: []
  - file: api/tests/test_kernel_conformance_harness.py
    symbols: [test_python_kernel_passes_control_flow_vector(), test_rust_and_go_kernels_pass_control_flow_vector()]
requirements:
  - "The kernel conformance harness accepts a Form control-flow vector separate from host effects, core built-ins, and infix operators."
  - "Python, Rust, and Go return the same JSON-safe values for deterministic if, do, and let forms over literals, local names, existing infix expressions, and existing built-in calls."
  - "The Rust and Go implementation claim stays bounded to the vector forms and does not claim complete Form grammar/runtime parity."
done_when:
  - "The control-flow vector passes for Python, Rust, and Go."
  - "The existing infix, core built-ins, and question-effect vectors still pass for Python, Rust, and Go."
  - "Docs state the exact conformance boundary."
test: "python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel python --kernel rust --kernel go --json && python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --json && python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --json && python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --json && cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q"
constraints:
  - "Do not claim Rust or Go implement the full Form language."
  - "Do not add loops, set mutation, defn/closure support, match, with, method dispatch, cell lookup, or persistence."
  - "Keep the vector deterministic and host-effect free."
---

# Form Control-Flow Kernel Conformance — lexical breath across Python, Rust, and Go

## Purpose

The infix vector proved that Rust and Go can evaluate a pure expression surface. This spec adds the next Form rung: deterministic control flow and lexical local binding. It proves branch choice, do-block result flow, local names, and inner block scope without widening into loops, mutation, functions, or substrate cell behavior.

## Requirements

- [x] **R1**: `docs/coherence-substrate/kernel-conformance/form-control-flow.json` names deterministic cases for `if`, `do`, and `let`.
- [x] **R2**: The vector proves lazy branch selection by leaving an unbound name in an unselected branch.
- [x] **R3**: Rust and Go runners evaluate only the vector's bounded control-flow forms over literals, existing built-ins, existing infix expressions, and local names.
- [x] **R4**: The question-effect, core built-ins, and infix vectors continue to pass after widening the runners.

## Research Inputs

- `2026-05-20` - `api/app/services/substrate/form_runtime.py` - Python runtime behavior for `IfExpr`, `DoBlock`, and `Let`.
- `2026-05-20` - `api/tests/test_substrate_form_runtime.py` - existing Python behavior tests for conditionals and lexical binding.
- `2026-05-20` - `docs/coherence-substrate/kernel-conformance/form-infix-operators.json` - previous pure value vector shape.

## Vector Contract

The vector is host-effect free: every case has `expected_events: []`, and the result is a JSON-safe literal value. The vector covers:

- `if cond then a else b`;
- `if cond then a` returning `null` when the condition is false;
- branch laziness over the unselected branch;
- `do { stmt; ... }` returning the last statement value;
- `let name = expr` bindings inside a do-block;
- local names feeding later expressions and built-in calls;
- inner `do` block lexical bindings that do not leak outward.

The executable command is:

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel python --kernel rust --kernel go --json
```

## Files to Create/Modify

- `docs/coherence-substrate/kernel-conformance/form-control-flow.json` - shared control-flow vector.
- `experiments/form-question-kernels/rust/src/main.rs` - add the narrow lexical control-flow evaluator.
- `experiments/form-question-kernels/go/question_kernel.go` - add the narrow lexical control-flow evaluator.
- `api/tests/test_kernel_conformance_harness.py` - assert Python/Rust/Go pass the control-flow vector.
- `docs/coherence-substrate/kernel-conformance/README.md` - document the vector.
- `docs/coherence-substrate/form-language.md` - state the widened but bounded conformance surface.
- `specs/form-infix-kernel-conformance.md` - close the previous follow-up pointer.

## Acceptance Tests

- `api/tests/test_kernel_conformance_harness.py::test_python_kernel_passes_control_flow_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_and_go_kernels_pass_control_flow_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_and_go_kernels_pass_infix_operator_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_and_go_kernels_pass_core_builtin_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_and_go_kernels_pass_question_effect_vector`

## Verification

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel python --kernel rust --kernel go --json
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --json
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --json
python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --json
cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q
python3 scripts/validate_spec_quality.py --file specs/form-control-flow-kernel-conformance.md
```

## Out of Scope

- `for`, `while`, `set`, `defn`, closures, recursion, `match`, `with`, methods, substrate cell lookup, or recipe introspection in Rust or Go.
- Function calls nested inside infix expressions.
- Durable state or host effects beyond the existing question vector.

## Risks and Assumptions

- The Rust and Go evaluators are deliberately tiny control-flow evaluators for this vector.
- `let` introduces only local JSON-safe values; it does not persist names across top-level cases.
- The do-block splitter only promises the vector syntax, with string/list/object/paren nesting preserved.

## Known Gaps and Follow-up Tasks

- Follow-up task: add `for`, `while`, and `set` conformance over local JSON-safe values.
- Follow-up task: add `defn` call/recursion conformance once the runner boundary is renamed away from question-only experiments.
- Follow-up task: rename or split the experiment runner directory once it carries enough surface to justify a non-question-specific module boundary.

## Task Card

```yaml
goal: Add a pure Form control-flow conformance vector that passes in Python, Rust, and Go.
files_allowed:
  - docs/coherence-substrate/kernel-conformance/form-control-flow.json
  - docs/coherence-substrate/kernel-conformance/README.md
  - docs/coherence-substrate/form-language.md
  - experiments/form-question-kernels/rust/src/main.rs
  - experiments/form-question-kernels/go/question_kernel.go
  - api/tests/test_kernel_conformance_harness.py
  - specs/form-infix-kernel-conformance.md
  - specs/form-control-flow-kernel-conformance.md
done_when:
  - Control-flow vector passes for Python, Rust, and Go.
  - Infix, core built-ins, and question-effect vectors still pass for Python, Rust, and Go.
  - Docs/spec state the bounded Rust/Go conformance claim.
commands:
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-control-flow.json --kernel python --kernel rust --kernel go --json
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --json
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --json
  - python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --json
  - cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q
constraints:
  - No full Form runtime claim for Rust or Go.
  - No loops, set mutation, defn, closures, match, with, cell lookup, or persistence.
  - No parser work outside the vector's control-flow subset.
```
