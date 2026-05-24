---
idea_id: agent-pipeline
status: done
source:
  - file: docs/coherence-substrate/kernel-conformance/form-core-builtins.json
    symbols: [form-core-builtins]
  - file: scripts/verify_kernel_conformance.py
    symbols: [run_kernel(), run_python_kernel(), run_external_kernel(), main()]
  - file: experiments/form-question-kernels/rust/src/main.rs
    symbols: []
  - file: experiments/form-question-kernels/go/question_kernel.go
    symbols: []
  - file: experiments/form-kernel-ts/src/conformance.ts
    symbols: []
  - file: api/tests/test_kernel_conformance_harness.py
    symbols: [test_python_kernel_passes_core_builtin_vector(), test_rust_go_and_typescript_kernels_pass_core_builtin_vector()]
requirements:
  - "The kernel conformance harness accepts a Form core built-ins vector separate from the host-bound question vector."
  - "Python, Rust, Go, and TypeScript return the same JSON-safe values for len, head, tail, sum, concat, and reverse over literal strings and lists."
  - "The Rust, Go, and TypeScript implementation claim stays bounded to the vector forms and does not claim complete Form grammar/runtime parity."
done_when:
  - "The core built-ins vector passes for Python, Rust, Go, and TypeScript."
  - "The existing question-effect vector still passes for Python, Rust, Go, and TypeScript."
  - "Docs state the exact conformance boundary."
  - 'file_exists("docs/coherence-substrate/kernel-conformance/form-core-builtins.json")'
  - 'symbol_in_file("docs/coherence-substrate/kernel-conformance/form-core-builtins.json", "form-core-builtins")'
  - 'file_exists("scripts/verify_kernel_conformance.py")'
  - 'symbol_in_file("scripts/verify_kernel_conformance.py", "run_kernel")'
  - 'symbol_in_file("scripts/verify_kernel_conformance.py", "run_python_kernel")'
  - 'symbol_in_file("scripts/verify_kernel_conformance.py", "run_external_kernel")'
  - 'symbol_in_file("scripts/verify_kernel_conformance.py", "main")'
  - 'file_exists("experiments/form-question-kernels/rust/src/main.rs")'
  - 'file_exists("experiments/form-question-kernels/go/question_kernel.go")'
  - 'file_exists("experiments/form-kernel-ts/src/conformance.ts")'
  - 'file_exists("api/tests/test_kernel_conformance_harness.py")'
  - 'symbol_in_file("api/tests/test_kernel_conformance_harness.py", "test_python_kernel_passes_core_builtin_vector")'
  - 'symbol_in_file("api/tests/test_kernel_conformance_harness.py", "test_rust_go_and_typescript_kernels_pass_core_builtin_vector")'
  - 'pytest_passes("api/tests/test_kernel_conformance_harness.py")'
  - 'pytest_passes("tests/test_kernel_conformance_harness.py")'
test: "python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --kernel typescript --json && python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --kernel typescript --json && cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q"
constraints:
  - "Do not claim Rust, Go, or TypeScript implement the full Form language."
  - "Do not add persistent runtime state."
  - "Keep the vector deterministic and host-effect free."
---

# Form Core Kernel Conformance — pure built-ins breathe across Python, Rust, Go, and TypeScript

## Purpose

The question-effect vector proved that Rust, Go, and TypeScript can match the host transcript for sub-agent questions. This spec adds a pure Form core vector so the same kernels also prove value-level execution for deterministic built-ins over literals and lists. The surface is intentionally small: it is a stable rung toward broader runtime parity, not a declaration that the full Form grammar has landed in Rust, Go, or TypeScript.

## Requirements

- [x] **R1**: `docs/coherence-substrate/kernel-conformance/form-core-builtins.json` names deterministic cases for `len`, `head`, `tail`, `sum`, `concat`, and `reverse`.
- [x] **R2**: `scripts/verify_kernel_conformance.py` runs the vector through the same Python, Rust, Go, and TypeScript kernel contract used by question effects.
- [x] **R3**: Rust, Go, and TypeScript runners parse the literal/function-call subset required by the vector and emit JSON values that the harness validates against the shared expectations.
- [x] **R4**: The question-effect vector continues to pass after widening the runners.

## Research Inputs

- `2026-05-20` - `docs/coherence-substrate/kernel-conformance/agent-question-effects.json` - existing vector shape and runner declarations.
- `2026-05-20` - `experiments/form-question-kernels/rust/src/main.rs`, `experiments/form-question-kernels/go/question_kernel.go`, and `experiments/form-kernel-ts/src/conformance.ts` - narrow executable kernels already present for question effects.
- `2026-05-20` - `api/app/services/substrate/form_runtime.py` - Python runtime is the source of truth for the built-in behavior.

## Vector Contract

The vector is host-effect free: every case has `expected_events: []`, and the result is a JSON-safe value. This lets external kernels prove pure value conformance without relying on the Python question queue.

The executable command is:

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --kernel typescript --json
```

## Files to Create/Modify

- `docs/coherence-substrate/kernel-conformance/form-core-builtins.json` - shared core built-ins vector.
- `experiments/form-question-kernels/rust/src/main.rs` - widen the Rust runner to parse generic literal values and core built-ins.
- `experiments/form-question-kernels/go/question_kernel.go` - widen the Go runner to parse generic literal values and core built-ins.
- `experiments/form-kernel-ts/src/conformance.ts` - widen the TypeScript runner to parse generic literal values and core built-ins.
- `api/tests/test_kernel_conformance_harness.py` - assert Python/Rust/Go/TypeScript pass the core vector.
- `docs/coherence-substrate/kernel-conformance/README.md` - document both vectors.
- `docs/coherence-substrate/form-language.md` - state the widened but bounded conformance surface.

## Acceptance Tests

- `api/tests/test_kernel_conformance_harness.py::test_python_kernel_passes_core_builtin_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_go_and_typescript_kernels_pass_core_builtin_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_go_and_typescript_kernels_pass_question_effect_vector`

## Verification

```bash
python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --kernel typescript --json
python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --kernel typescript --json
cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q
python3 scripts/validate_spec_quality.py --file specs/form-core-kernel-conformance.md
```

## Out of Scope

- Infix operator parsing in Rust, Go, or TypeScript.
- `do`, `let`, `if`, closures, recursion, method dispatch, substrate cell lookup, or recipe introspection in Rust, Go, or TypeScript.
- Durable state or host effects beyond the existing question vector.

## Risks and Assumptions

- The Rust, Go, and TypeScript runners intentionally evaluate only literal function calls in this vector. Broader syntax needs its own vector and parser work.
- JSON numeric equality is the conformance boundary for this vector; it avoids language-specific integer representation details.

## Known Gaps and Follow-up Tasks

- Follow-up task: expand beyond built-ins with an infix arithmetic/logical vector and parser support for Rust/Go/TypeScript. See `specs/form-infix-kernel-conformance.md`.
- Follow-up task: add a lexical block vector for `do`, `let`, and `if`.
- Follow-up task: rename or split the experiment runner directory once it carries enough surface to justify a non-question-specific module boundary.

## Task Card

```yaml
goal: Add a pure Form core built-ins conformance vector that passes in Python, Rust, Go, and TypeScript.
files_allowed:
  - docs/coherence-substrate/kernel-conformance/form-core-builtins.json
  - docs/coherence-substrate/kernel-conformance/README.md
  - docs/coherence-substrate/form-language.md
  - experiments/form-question-kernels/rust/src/main.rs
  - experiments/form-question-kernels/go/question_kernel.go
  - experiments/form-kernel-ts/src/conformance.ts
  - api/tests/test_kernel_conformance_harness.py
  - specs/form-core-kernel-conformance.md
done_when:
  - Core built-ins vector passes for Python, Rust, Go, and TypeScript.
  - Existing question-effect vector still passes for Python, Rust, Go, and TypeScript.
  - Docs/spec state the bounded Rust/Go/TypeScript conformance claim.
commands:
  - python3 scripts/verify_kernel_conformance.py --vector docs/coherence-substrate/kernel-conformance/form-core-builtins.json --kernel python --kernel rust --kernel go --kernel typescript --json
  - python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --kernel typescript --json
  - cd api && .venv/bin/pytest tests/test_kernel_conformance_harness.py -q
constraints:
  - No full Form runtime claim for Rust, Go, or TypeScript.
  - No persistence or host-effect expansion.
  - No parser work outside the vector's literal function-call subset.
```
