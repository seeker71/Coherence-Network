---
idea_id: agent-pipeline
status: active
source:
  - file: docs/coherence-substrate/kernel-conformance/form-infix-operators.json
    symbols: [form-infix-operators]
  - file: scripts/verify_kernel_conformance.py
    symbols: [run_kernel(), run_python_kernel(), run_external_kernel(), main()]
  - file: experiments/form-question-kernels/rust/src/main.rs
    symbols: []
  - file: experiments/form-question-kernels/go/question_kernel.go
    symbols: []
  - file: api/tests/test_kernel_conformance_harness.py
    symbols: [test_python_kernel_passes_infix_operator_vector(), test_rust_and_go_kernels_pass_infix_operator_vector()]
requirements:
  - "The kernel conformance harness accepts a Form infix-operator vector separate from host effects and core function-call built-ins."
  - "Python, Rust, and Go return the same JSON-safe values for arithmetic precedence, parentheses, integer division, modulo, unary minus, comparisons, boolean chains, unary not, and literal equality."
  - "The Rust and Go implementation claim stays bounded to the vector forms and does not claim complete Form grammar/runtime parity."
done_when:
  - "The infix-operator vector passes for Python, Rust, and Go."
  - "The existing core built-ins and question-effect vectors still pass for Python, Rust, and Go."
  - "Docs state the exact conformance boundary."
test: "python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --json && python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --json && python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --json && cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q"
constraints:
  - "Do not claim Rust or Go implement the full Form language."
  - "Do not add variables, do-block scope, closures, cell lookup, or persistence."
  - "Keep the vector deterministic and host-effect free."
---

# Form Infix Kernel Conformance — literal operators breathe across Python, Rust, and Go

## Purpose

The core built-ins vector proved that Rust and Go can return shared values for simple literal function calls. This spec adds the next pure Form rung: infix operators over literals. It covers precedence and parenthesized grouping, integer arithmetic, comparisons, and boolean flow without introducing variables, block scope, or substrate cell lookup.

## Requirements

- [x] **R1**: `docs/coherence-substrate/kernel-conformance/form-infix-operators.json` names deterministic cases for arithmetic, comparison, boolean, unary, and parenthesized expressions.
- [x] **R2**: `scripts/verify_kernel_conformance.py` runs the vector through the same Python, Rust, and Go kernel contract used by existing vectors.
- [x] **R3**: Rust and Go runners parse the literal infix subset required by the vector and emit JSON values that the harness validates against the shared expectations.
- [x] **R4**: The core built-ins vector and question-effect vector continue to pass after widening the runners.

## Research Inputs

- `2026-05-20` - `docs/coherence-substrate/kernel-conformance/form-core-builtins.json` - the existing pure value vector shape.
- `2026-05-20` - `api/app/services/substrate/form_runtime.py` - Python runtime behavior for operator precedence and truthy boolean flow.
- `2026-05-20` - `experiments/form-question-kernels/rust/src/main.rs` and `experiments/form-question-kernels/go/question_kernel.go` - existing narrow executable kernels.

## Vector Contract

The vector is host-effect free: every case has `expected_events: []`, and the result is a JSON-safe literal value. The vector covers:

- `*`, `/`, `%` binding tighter than `+` and `-`;
- parentheses overriding precedence;
- unary `-` and unary `!`;
- `==`, `!=`, `<`, `<=`, `>`, `>=`;
- `&&` and `||` over boolean-producing literal expressions.

The executable command is:

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --json
```

## Files to Create/Modify

- `docs/coherence-substrate/kernel-conformance/form-infix-operators.json` - shared infix-operator vector.
- `experiments/form-question-kernels/rust/src/main.rs` - add the narrow literal infix parser/evaluator.
- `experiments/form-question-kernels/go/question_kernel.go` - add the narrow literal infix parser/evaluator.
- `api/tests/test_kernel_conformance_harness.py` - assert Python/Rust/Go pass the infix vector.
- `docs/coherence-substrate/kernel-conformance/README.md` - document the vector.
- `docs/coherence-substrate/form-language.md` - state the widened but bounded conformance surface.
- `specs/form-core-kernel-conformance.md` - point its follow-up to this closed rung.

## Acceptance Tests

- `api/tests/test_kernel_conformance_harness.py::test_python_kernel_passes_infix_operator_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_and_go_kernels_pass_infix_operator_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_and_go_kernels_pass_core_builtin_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_and_go_kernels_pass_question_effect_vector`

## Verification

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --json
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --json
python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --json
cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q
python3 scripts/validate_spec_quality.py --file specs/form-infix-kernel-conformance.md
```

## Out of Scope

- Variables, `do`, `let`, `if`, closures, recursion, method dispatch, substrate cell lookup, or recipe introspection in Rust or Go.
- Function calls nested inside infix expressions.
- Durable state or host effects beyond the existing question vector.

## Risks and Assumptions

- The Rust and Go parsers are deliberately tiny expression parsers for this literal subset.
- Division is proven only for integer cases that match Python Form's integer division behavior.
- Boolean vectors stay on boolean-producing operands so the cross-language JSON result stays unambiguous.

## Known Gaps and Follow-up Tasks

- Follow-up task closed by `specs/form-control-flow-kernel-conformance.md`: add a lexical block vector for `do`, `let`, and `if`.
- Follow-up task: add variables and function-call operands inside infix expressions.
- Follow-up task: rename or split the experiment runner directory once it carries enough surface to justify a non-question-specific module boundary.

## Task Card

```yaml
goal: Add a pure Form infix-operator conformance vector that passes in Python, Rust, and Go.
files_allowed:
  - docs/coherence-substrate/kernel-conformance/form-infix-operators.json
  - docs/coherence-substrate/kernel-conformance/README.md
  - docs/coherence-substrate/form-language.md
  - experiments/form-question-kernels/rust/src/main.rs
  - experiments/form-question-kernels/go/question_kernel.go
  - api/tests/test_kernel_conformance_harness.py
  - specs/form-core-kernel-conformance.md
  - specs/form-infix-kernel-conformance.md
done_when:
  - Infix-operator vector passes for Python, Rust, and Go.
  - Core built-ins and question-effect vectors still pass for Python, Rust, and Go.
  - Docs/spec state the bounded Rust/Go conformance claim.
commands:
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-infix-operators.json --kernel python --kernel rust --kernel go --json
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --json
  - python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --json
  - cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q
constraints:
  - No full Form runtime claim for Rust or Go.
  - No variables, block scope, or persistence.
  - No parser work outside the vector's literal infix subset.
```
