# Telegram Card Contract

## Goal
Make Telegram task cards practical, useful, and actionable. Every task card must include:
- Task description
- Status
- Executor + model
- One next action
- Proof links
- Why this matters (short)

## Card Format
1. Header: icon + normalized status
2. Task: one-line description summary (max 160 chars)
3. Status: raw status value
4. Runtime: `Executor: <executor> | Model: <model>`
5. Why: one short practical sentence
6. Next: one exact action command
7. Proof: task link + task log + task id
8. Optional lines: updated/progress/current step/idea/decision prompt

Normal mode limit: max 10 lines.

## Field Map
| Source | Card field | Fallback |
|---|---|---|
| `task.direction` | Task | `(no task description)` |
| `task.status` | Header + Status + Why + Next | `unknown` |
| `context.executor` -> `context.route_decision.executor` | Runtime executor | `unknown` |
| `task.model` -> `context.model_override` -> `context.route_decision.model` | Runtime model | `unknown (metadata missing)` |
| `task.id` | Proof links + command target | omit links if missing |
| `task.updated_at`/`created_at` | Updated | omit |
| `task.progress_pct` | Progress | omit |
| `task.current_step` | Step | omit |
| `task.decision_prompt` | Decision | omit |

## Status Coverage
- `pending`
- `running`
- `needs_decision`
- `failed`
- `completed`

## Action Mapping (Failed)
| Failure class | Next action | Proof of unblock |
|---|---|---|
| quota/usage window | `/usage` | remaining ratio above threshold or no quota alert |
| paid-provider blocked | `/task <id>` | context shows approved override or reroute proof |
| missing env/secrets | `/railway verify` | readiness report no blocking secret/config issue |
| test/lint | `/direction Fix failing tests/lint for task <id> and rerun with proof` | passing test/lint evidence in task output |
| stale branch/rebase | `/direction Rebase and rerun gates for task <id>` | clean rebase + gate output |
| flaky/network | `/direction Retry task <id> once; capture provider error + retry proof` | retry output includes recovered provider call |
| generic | `/direction Retry task <id> with explicit proof of each fix` | step-by-step proof in result |

## Before vs After
Before:
- Long mixed context with low action clarity
- Runtime/model often hidden
- Multiple optional details but no single clear next step

After:
- Compact card (<=10 lines)
- Explicit executor/model on every card
- Exactly one next action
- Direct proof links for verification
