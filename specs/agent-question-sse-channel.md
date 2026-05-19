---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/routers/agent_question_routes.py
    symbols: [create_question(), list_questions_route(), question_events_sse(), answer_question_route()]
  - file: api/app/services/agent_question_service.py
    symbols: [create_question(), list_questions(), answer_question(), get_question_events()]
  - file: api/tests/test_agent_question_sse.py
    symbols: [test_agent_question_lifecycle(), test_agent_question_sse_replays_opened_event()]
  - file: web/app/agent/questions/page.tsx
    symbols: [AgentQuestionsPage]
requirements:
  - "POST /api/agent/questions lets a sub-agent open a bounded human question with optional task, thread, choices, and context."
  - "GET /api/agent/questions lists open or answered questions for the web console."
  - "GET /api/agent/questions/stream emits server-sent events for opened and answered questions with monotonic sequence numbers."
  - "POST /api/agent/questions/{id}/answer records a human answer and emits a question_answered event."
  - "The web console at /agent/questions receives SSE question events and can answer open questions without a page reload."
done_when:
  - "API lifecycle test proves create, list, answer, and answered status."
  - "SSE test proves the stream emits a question_opened event for a sub-agent question."
  - "Web build succeeds with the question console route."
test: "cd api && .venv/bin/pytest tests/test_agent_question_sse.py -q && cd ../web && npm run build"
constraints:
  - "MVP storage is in-memory only; no database migration in this breath."
  - "Form/Rust/Go kernel work is named as a conformance boundary; this change implements the human question channel first."
---

> **Parent idea**: [agent-pipeline](../ideas/agent-pipeline.md)

# Spec: Agent Question SSE Channel

*Format: [specs/TEMPLATE.md](TEMPLATE.md)*

## Purpose

Let a sub-agent pause and ask a human a question through a live web surface. The first working breath is intentionally small: a Python API channel, server-sent events, and a web console. This gives Form, Rust, and Go kernels a concrete boundary to target instead of a speculative abstraction.

## Requirements

- [x] `POST /api/agent/questions` accepts `agent_id`, `question`, optional `task_id`, `thread_id`, `choices`, and `context`.
- [x] `GET /api/agent/questions` returns recent questions, filterable by `status=open|answered`.
- [x] `GET /api/agent/questions/stream` emits SSE data frames for `question_opened` and `question_answered`.
- [x] `POST /api/agent/questions/{id}/answer` records the human answer and emits an event.
- [x] `/agent/questions` shows a live queue and answer controls.

## Research Inputs

- `2026-05-19` - Existing task activity SSE routes — `api/app/routers/task_activity_routes.py` and `api/app/services/task_activity_service.py` already establish the local stream pattern.
- `2026-05-19` - Agent task model — existing task updates already carry decision prompts; this channel keeps questions separate so sub-agent questions can stream independently.

## API Contract

### `POST /api/agent/questions`

**Request**
```json
{
  "agent_id": "sub-agent-1",
  "question": "Which path should this sub-agent take?",
  "task_id": "task_123",
  "thread_id": "thread_abc",
  "choices": ["continue", "pause"],
  "context": { "form": "(ask human ...)" }
}
```

**Response 201**
```json
{
  "id": "question_abc123",
  "agent_id": "sub-agent-1",
  "question": "Which path should this sub-agent take?",
  "status": "open",
  "answer": null
}
```

### `GET /api/agent/questions/stream`

Streams `data: {...}\n\n` frames with `sequence`, `event_type`, `question_id`, and `question`.

## Data Model

```yaml
AgentQuestion:
  id: string
  agent_id: string
  question: string
  task_id: string | null
  thread_id: string | null
  choices: list[string]
  context: object
  status: open | answered
  answer: string | null
  answered_by: string | null
  created_at: iso8601
  updated_at: iso8601
  answered_at: iso8601 | null
```

## Kernel Boundary

Form can write the channel as two verbs:

```form
(ask human
  :question "Which deployment path should this sub-agent use?"
  :task task.id
  :choices ["continue" "pause" "handoff"])

(await_answer question.id)
```

The Python surface is the executable host contract. Rust and Go kernels should prove conformance by producing the same opened/answered event sequence for those two Form verbs.

## Files to Create/Modify

- `api/app/services/agent_question_service.py` — bounded in-memory question queue and event log.
- `api/app/routers/agent_question_routes.py` — question lifecycle and SSE endpoints.
- `api/app/routers/agent.py` — compose the question router under `/api/agent`.
- `api/tests/test_agent_question_sse.py` — lifecycle and SSE replay contract.
- `web/app/agent/questions/page.tsx` — live web console for questions.
- `web/app/agent/page.tsx` — navigation link to the question console.
- `specs/agent-question-sse-channel.md` — this executable spec.

## Acceptance Tests

- `api/tests/test_agent_question_sse.py::test_agent_question_lifecycle`
- `api/tests/test_agent_question_sse.py::test_agent_question_sse_replays_opened_event`
- `cd web && npm run build`

## Verification

```bash
cd api && python3 -m pytest tests/test_agent_question_sse.py -q
cd web && npm run build
python3 scripts/validate_spec_quality.py --file specs/agent-question-sse-channel.md
```

## Out of Scope

- Database persistence for questions.
- Authentication and role-specific answer authorization.
- Full Rust or Go kernel execution.
- Complete Form evaluator support for `ask` and `await_answer`.

## Risks and Assumptions

- In-memory storage is process-local; the first production hardening pass should move the queue to the existing durable task or runtime store.
- SSE connections are bounded and reconnecting; a future high-volume channel may need backpressure and per-thread fanout.
- The Form verbs in this spec are a conformance target, not a parser/evaluator implementation in this breath.

## Known Gaps and Follow-up Tasks

- Follow-up task: Rust and Go conformance harnesses should prove the same opened/answered sequence for Form `ask` and `await_answer`.
- Follow-up task: The sub-agent runner should call `POST /api/agent/questions` automatically when Form emits an `ask` effect.

## Task Card

```yaml
goal: Let sub-agents ask human questions through a live SSE web channel.
files_allowed:
  - specs/agent-question-sse-channel.md
  - api/app/routers/agent.py
  - api/app/routers/agent_question_routes.py
  - api/app/services/agent_question_service.py
  - api/tests/test_agent_question_sse.py
  - web/app/agent/questions/page.tsx
done_when:
  - API lifecycle test proves create, list, answer, and answered status.
  - SSE test proves the stream emits a question_opened event for a sub-agent question.
  - Web build succeeds with the question console route.
commands:
  - cd api && .venv/bin/pytest tests/test_agent_question_sse.py -q
  - cd web && npm run build
constraints:
  - MVP storage is in-memory only; no database migration in this breath.
  - Form/Rust/Go kernel work is named as a conformance boundary; this change implements the human question channel first.
```
