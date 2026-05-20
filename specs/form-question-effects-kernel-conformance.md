---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/services/substrate/form_runtime.py
    symbols: [_builtin_ask(), _builtin_await_answer(), form_execute_text()]
  - file: api/app/routers/substrate.py
    symbols: [evaluate_form(), FormRequest, FormResultOut]
  - file: api/app/services/mcp_tool_registry.py
    symbols: [_serialize_substrate_value(), substrate_run_handler()]
  - file: api/tests/test_substrate_form_question_effects.py
    symbols: [test_form_ask_opens_question_and_emits_sse_event(), test_form_await_answer_reads_answer_when_present(), test_substrate_form_run_mode_returns_question_value()]
  - file: api/tests/test_kernel_conformance_harness.py
    symbols: [test_python_kernel_passes_question_effect_vector(), test_rust_go_and_typescript_kernels_pass_question_effect_vector(), test_default_runs_all_implemented_kernels()]
  - file: scripts/verify_kernel_conformance.py
    symbols: [run_kernel(), run_python_kernel(), run_external_kernel(), main()]
  - file: experiments/form-question-kernels/rust/src/main.rs
    symbols: []
  - file: experiments/form-question-kernels/go/question_kernel.go
    symbols: []
  - file: experiments/form-kernel-ts/src/conformance.ts
    symbols: []
  - file: docs/coherence-substrate/kernel-conformance/agent-question-effects.json
    symbols: [form-question-effects]
requirements:
  - "Form runtime exposes ask(agent_id, question, choices=[], context={}) as the executable human-question effect."
  - "Form runtime exposes await_answer(question_id) so a sub-agent can poll the current human answer."
  - "POST /api/substrate/form accepts mode=run and returns computed Form runtime values as JSON-safe payloads."
  - "Rust, Go, and TypeScript question-effect kernels run the same opened/answered conformance vector through executable runner commands."
  - "The shared conformance vector is executable by a harness that passes for Python, Rust, Go, and TypeScript."
done_when:
  - "Runtime tests prove ask opens a question, emits question_opened, and await_answer reads the answer."
  - "Endpoint test proves /api/substrate/form mode=run returns the opened question value."
  - "Conformance harness proves Python, Rust, Go, and TypeScript pass the vector."
test: "cd api && .venv/bin/pytest tests/test_substrate_form_question_effects.py tests/test_kernel_conformance_harness.py tests/test_substrate_form_endpoint.py tests/test_agent_question_sse.py -q"
constraints:
  - "Do not invent a second Form question syntax; use existing FnCall runtime execution."
  - "Claim Rust, Go, and TypeScript only for the narrow question-effect kernel surface, not as full Form runtimes."
  - "Keep the question queue in-memory in this breath; persistence belongs to a later spec."
---

> **Parent idea**: [agent-pipeline](../ideas/agent-pipeline.md)

# Spec: Form Question Effects Kernel Conformance

*Format: [specs/TEMPLATE.md](TEMPLATE.md)*

## Purpose

The human question channel exists, streams to the web, and can be answered. This spec makes that channel writable from Form itself so a sub-agent can express the pause point in the same language it is executing. Rust, Go, and TypeScript now have narrow question-effect kernel runners: they do not implement the whole Form language, but they do produce the same `ask(...)` / `await_answer(...)` event transcript as Python.

## Requirements

- [x] **R1**: `ask(agent_id, question, choices=[], context={})` runs inside `form_execute_text()` and creates an open agent question with optional choices, `task_id`, `thread_id`, and context.
- [x] **R2**: `await_answer(question_id)` runs inside `form_execute_text()` and returns `null` until the question is answered, then returns the answer string.
- [x] **R3**: `POST /api/substrate/form` accepts `mode="run"` and returns `kind="value"` with a JSON-safe runtime payload.
- [x] **R4**: The MCP substrate run serializer recurses through dict values so question payloads can pass through tool output intact.
- [x] **R5**: A kernel conformance vector names the expected `question_opened` and `question_answered` effects for Python, Rust, Go, and TypeScript kernel implementations.
- [x] **R6**: `scripts/verify_kernel_conformance.py` consumes the conformance vector and passes Python, Rust, Go, and TypeScript implemented runners.
- [x] **R7**: Rust, Go, and TypeScript runner code implements the question-effect micro-surface only: `ask(...)`, `await_answer(...)`, question records, and opened/answered event transcripts.

## Research Inputs

- `2026-05-19` - `specs/agent-question-sse-channel.md` - the existing API and web SSE channel are already the host surface.
- `2026-05-19` - `api/app/services/substrate/form_runtime.py` - Form runtime function calls already route through `_BUILTIN_FUNCTIONS`, so question effects fit as ordinary calls.
- `2026-05-19` - `docs/coherence-substrate/form-language.md` - Rust kernel work is named as a future hot-loop port; the question-effect runners land as a narrow executable surface, not as the full hot-loop port.

## API Contract

### Form Runtime

```form
ask("sub-agent", "Which path should I take?", ["continue", "pause"], {task_id: "task_1"})
await_answer("question_abc123")
```

`ask(...)` returns the created question object. `await_answer(...)` returns `null` while the question is open and the answer string after a human answers it.

### `POST /api/substrate/form`

**Request**
```json
{
  "mode": "run",
  "expression": "ask(\"sub-agent\", \"Continue?\", [\"yes\", \"no\"], {task_id: \"task_1\"})"
}
```

**Response 200**
```json
{
  "kind": "value",
  "value": {
    "id": "question_abc123",
    "agent_id": "sub-agent",
    "question": "Continue?",
    "task_id": "task_1",
    "status": "open",
    "answer": null
  }
}
```

## Data Model

This spec reuses the `AgentQuestion` model from [agent-question-sse-channel.md](agent-question-sse-channel.md). The Form runtime returns that object without adding persistence or a second queue.

## Kernel Conformance

The shared vector lives at `docs/coherence-substrate/kernel-conformance/agent-question-effects.json`. It defines:

- one `ask(...)` case that must create a question and emit `question_opened`;
- one `await_answer(...)` case that must read the answer once the host question is answered;
- kernel status markers and runner commands for Python, Rust, Go, and TypeScript.

The harness is executable:

```bash
python3 scripts/verify_kernel_conformance.py --kernel python
python3 scripts/verify_kernel_conformance.py --kernel rust
python3 scripts/verify_kernel_conformance.py --kernel go
```

Rust, Go, and TypeScript are implemented for this vector only. They parse the question-effect forms used here, emit actual question records/events, and the Python harness compares those values against the shared vector.

## Files to Create/Modify

- `api/app/services/substrate/form_runtime.py` - add host-bound question built-ins.
- `api/app/routers/substrate.py` - add `mode="run"` and runtime value serialization.
- `api/app/services/mcp_tool_registry.py` - recurse through dict-valued runtime output.
- `api/tests/test_substrate_form_question_effects.py` - prove Form question effects and endpoint runtime mode.
- `api/tests/test_kernel_conformance_harness.py` - prove the executable conformance harness.
- `scripts/verify_kernel_conformance.py` - consume vector cases and validate kernel transcripts.
- `experiments/form-question-kernels/rust/Cargo.toml` - Rust question-effect runner manifest.
- `experiments/form-question-kernels/rust/src/main.rs` - Rust question-effect runner.
- `experiments/form-question-kernels/go/question_kernel.go` - Go question-effect runner.
- `experiments/form-kernel-ts/src/conformance.ts` - TypeScript question-effect runner.
- `docs/coherence-substrate/form-language.md` - document the Form-visible question effect.
- `docs/coherence-substrate/kernel-conformance/agent-question-effects.json` - define the Rust/Go/TypeScript/Python runner contract.
- `docs/coherence-substrate/kernel-conformance/README.md` - document the runner contract.
- `specs/form-question-effects-kernel-conformance.md` - this executable spec.

## Acceptance Tests

- `api/tests/test_substrate_form_question_effects.py::test_form_ask_opens_question_and_emits_sse_event`
- `api/tests/test_substrate_form_question_effects.py::test_form_await_answer_reads_answer_when_present`
- `api/tests/test_substrate_form_question_effects.py::test_substrate_form_run_mode_returns_question_value`
- `api/tests/test_kernel_conformance_harness.py::test_python_kernel_passes_question_effect_vector`
- `api/tests/test_kernel_conformance_harness.py::test_rust_go_and_typescript_kernels_pass_question_effect_vector`
- `api/tests/test_kernel_conformance_harness.py::test_default_runs_all_implemented_kernels`
- `api/tests/test_substrate_form_endpoint.py::test_form_endpoint_rejects_unknown_mode`
- `api/tests/test_agent_question_sse.py::test_agent_question_sse_replays_opened_event`

## Verification

```bash
python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --kernel typescript
cd api && .venv/bin/pytest tests/test_substrate_form_question_effects.py tests/test_kernel_conformance_harness.py tests/test_substrate_form_endpoint.py tests/test_agent_question_sse.py -q
python3 scripts/validate_spec_quality.py --file specs/form-question-effects-kernel-conformance.md
```

## Out of Scope

- Durable question persistence.
- Blocking awaits or long-poll runtime suspension.
- A new Form parser syntax for questions.
- Full Rust, Go, or TypeScript Form language runtimes beyond the question-effect forms in this vector.

## Risks and Assumptions

- `ask(...)` is a host-bound effect, so deterministic replay must compare emitted effects rather than only return values.
- `await_answer(...)` is deliberately non-blocking in this breath; callers poll or re-run after the web answer lands.
- The Rust, Go, and TypeScript runners are narrow conformance kernels; broader Form parsing remains a later kernel pass.
- In-memory question storage remains process-local until a persistence spec lands.

## Known Gaps and Follow-up Tasks

- Follow-up task: add durable question persistence with replay across API restarts.
- Follow-up task: expand Rust, Go, and TypeScript from question-effect runners to broader Form parser/runtime coverage.
- Follow-up task: teach sub-agent task execution to suspend and resume around unanswered Form questions.

## Task Card

```yaml
goal: Make the agent question SSE channel writable from Form and pass the shared question-effect vector in Python, Rust, Go, and TypeScript.
files_allowed:
  - api/app/services/substrate/form_runtime.py
  - api/app/routers/substrate.py
  - api/app/services/mcp_tool_registry.py
  - api/tests/test_substrate_form_question_effects.py
  - api/tests/test_kernel_conformance_harness.py
  - scripts/verify_kernel_conformance.py
  - experiments/form-question-kernels/rust/Cargo.toml
  - experiments/form-question-kernels/rust/src/main.rs
  - experiments/form-question-kernels/go/question_kernel.go
  - experiments/form-kernel-ts/src/conformance.ts
  - docs/coherence-substrate/form-language.md
  - docs/coherence-substrate/kernel-conformance/README.md
  - docs/coherence-substrate/kernel-conformance/agent-question-effects.json
  - specs/form-question-effects-kernel-conformance.md
done_when:
  - Runtime tests prove ask opens a question, emits question_opened, and await_answer reads the answer.
  - Endpoint test proves /api/substrate/form mode=run returns the opened question value.
  - Conformance harness proves Python, Rust, Go, and TypeScript pass the vector.
commands:
  - python3 scripts/verify_kernel_conformance.py --kernel python --kernel rust --kernel go --kernel typescript
  - cd api && .venv/bin/pytest tests/test_substrate_form_question_effects.py tests/test_kernel_conformance_harness.py tests/test_substrate_form_endpoint.py tests/test_agent_question_sse.py -q
  - python3 scripts/validate_spec_quality.py --file specs/form-question-effects-kernel-conformance.md
constraints:
  - No durable storage or database migration in this breath.
  - Rust, Go, and TypeScript implementation claims are limited to the question-effect conformance vector.
  - No new Form question parser syntax.
```
