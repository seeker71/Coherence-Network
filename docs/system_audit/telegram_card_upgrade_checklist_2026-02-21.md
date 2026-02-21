# Telegram Card Upgrade Checklist (2026-02-21)

## Scope
Upgrade Telegram task cards to be user friendly and actionable with:
- task description summary
- executor + model visibility
- practical why/next/proof lines

## Step Proof
1. Contract defined
- Proof file: `docs/TELEGRAM-CARD-CONTRACT.md`
- Includes: format spec, field map, failure-class action map, before-vs-after notes.

2. Flow + payload mapping completed
- Implementation file: `api/app/routers/agent_telegram.py`
- Added helpers:
  - `summarize_direction`
  - `task_runtime_label`
  - `next_action_for_status`
  - `proof_hints_for_task`

3. Formatter upgraded
- Function updated: `format_task_alert`
- Enforced card lines:
  - Task, Status, Runtime, Why, Next, Proof
  - optional Updated/Progress/Step/Idea/Decision
  - max 10 lines

4. Executor/model fallback behavior implemented
- Runtime fallback now renders unknown values when metadata is absent.
- Codex alias normalization (`openclaw`/`clawwork` -> `codex`) included in runtime display.

5. Actionability mapping implemented
- Failed task categories handled: quota, paid-provider, env/secrets, test/lint, rebase, flaky/network, generic.
- Each class maps to one explicit next command.

6. Tests and verification
- Command: `cd api && pytest -q tests/test_agent_telegram_webhook.py`
- Result: `15 passed, 2 warnings`
- Focused contract test command:
  - `cd api && pytest -q tests/test_agent_telegram_webhook.py -k "format_task_alert or telegram_card_helpers or runner_update"`
  - Result: `4 passed`

7. Rendered card evidence
- Sample output artifact:
  - `docs/system_audit/telegram_card_samples_2026-02-21.json`
  - Contains sample cards for: pending, running, needs_decision, failed, completed.

## Done Criteria
- [x] Cards show task description, status, executor/model, one next action, and proof links
- [x] Cards stay concise and practical
- [x] Tests pass for formatter behavior and webhook flows
- [x] Evidence artifacts captured

## Remaining blocker for hosted deploy proof
- Not executed in this local run: push/hosted workflow deployment validation.
- Required next commands:
  - `git push origin <branch>`
  - Trigger/observe workflow and capture run URL + Telegram output in production diagnostics.
