# 108 — Unified Agent CLI Flow: All Task Types, Patch on Verification Fail

## Purpose

Ensure every agent provider CLI (aider/claude, cursor, openclaw) can run the full delivery flow locally and remotely: generate spec from idea, implement a spec, run tests, review implementation against spec verification, and—when verification fails—produce enough structured information to create a patch so the next step can fix the implementation without discarding work. Optionally improve the spec’s Verification section when the verification step is ambiguous or wrong.

## Requirements

- [ ] Every executor (`claude`, `cursor`, `codex`, `gemini`) supports `spec`, `impl`, `test`, `review`, and `heal` task types through routing and command templates.
- [ ] The flow executes end-to-end (`idea -> spec -> impl -> test -> review`) for local and remote runner modes with no task-type exclusion.
- [ ] `review` failure output includes structured `VERIFICATION_RESULT`, `FILES_TO_CHANGE`, and `PATCH_GUIDANCE` blocks that can drive a follow-up patch.
- [ ] On failed review, pipeline context carries patch guidance forward to the next `impl`/`heal` task without destructive truncation.
- [ ] Review may emit `SPEC_VERIFICATION_IMPROVEMENT` when verification steps are ambiguous, so spec verification can be tightened in follow-up.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 002, 005, 026, 300

## Task Card

```yaml
goal: Ensure every agent provider CLI (aider/claude, cursor, openclaw) can run the full delivery flow locally and remotely: generate spec from idea, implement a spec, run tests, review implementation against spec verification, and—when verification fails—produce enough structured information to create a patch so the next step can fix the implementation without discarding work.
files_allowed:
  - specs/108-unified-agent-cli-flow-patch-on-fail.md
  - .cursor/skills/spec-guard/SKILL.md
  - api/scripts/project_manager.py
  - docs/AGENT-DEBUGGING.md
done_when:
  - Every executor (`claude`, `cursor`, `codex`, `gemini`) supports `spec`, `impl`, `test`, `review`, and `heal` task typ...
  - The flow executes end-to-end (`idea -> spec -> impl -> test -> review`) for local and remote runner modes with no tas...
  - `review` failure output includes structured `VERIFICATION_RESULT`, `FILES_TO_CHANGE`, and `PATCH_GUIDANCE` blocks tha...
  - On failed review, pipeline context carries patch guidance forward to the next `impl`/`heal` task without destructive ...
  - Review may emit `SPEC_VERIFICATION_IMPROVEMENT` when verification steps are ambiguous, so spec verification can be ti...
commands:
  - cd api && pytest -q tests/test_agent.py tests/test_agent_executor_policy.py tests/test_openclaw_executor_integration.py -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

- No new API endpoints. Existing `POST /api/agent/tasks`, `GET /api/agent/tasks`, `PATCH /api/agent/tasks/{id}`, and execute/pickup endpoints remain unchanged.
- Task `context` may carry `spec_ref`, `idea_id`, `last_review_output`, or `patch_guidance` for downstream tasks; structure is convention for pipeline and agents, not a new API schema.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Files to Create/Modify

- `specs/108-unified-agent-cli-flow-patch-on-fail.md` — this spec.
- `.cursor/skills/spec-guard/SKILL.md` — extend with “Review output (FAIL)” section: require VERIFICATION_RESULT, FILES_TO_CHANGE, PATCH_GUIDANCE; optional SPEC_VERIFICATION_IMPROVEMENT.
- `api/scripts/project_manager.py` — when building direction for impl after a failed review, pass full review output (or at least PATCH_GUIDANCE / FILES_TO_CHANGE) in context or direction, not only a 300-character truncation. Preserve existing behavior when output is small.
- `docs/AGENT-DEBUGGING.md` or `docs/PLAN.md` — add a short subsection describing the flow (spec → impl → test → review → patch on fail) and the review output contract.

## Acceptance Tests

- **Routing**: For each executor in `EXECUTOR_VALUES` (claude, cursor, openclaw) and each task_type in (spec, impl, test, review, heal), `GET /api/agent/route?task_type=X&executor=Y` returns a valid command_template and model. (Covered by existing agent routing tests; add or extend one test that asserts all pairs if missing.)
- **Review output contract**: Document in spec and spec-guard that FAIL review output must include VERIFICATION_RESULT=FAIL, FILES_TO_CHANGE, PATCH_GUIDANCE. No new automated test for agent output format unless we add a small parser test for the convention.
- **Project manager**: After a review task completes with status failed or output indicating FAIL, the next impl task created by project_manager receives direction/context that includes the review output (or PATCH_GUIDANCE) sufficient for patch-oriented fix (e.g. test that state or direction length/carry-over is improved where applicable).
- **Automated verification references**: `api/tests/test_agent_executor_policy.py`, `api/tests/test_agent_integration_api.py`, `api/tests/test_agent_execute_endpoint.py`.
- **Manual verification**: Run one local matrix flow and one host-runner flow, then confirm usage page reflects non-zero successes and failure metadata with patch guidance context.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.


## Verification

```bash
cd api && pytest -q tests/test_agent.py tests/test_agent_executor_policy.py tests/test_openclaw_executor_integration.py -v
```

## Out of Scope

- Changing OpenRouter/server-side execute to run the CLI (remain as-is).
- Adding a fourth executor unless already present in code.
- Enforcing review output format via API schema (convention only).

## Risks and Assumptions

- Assumption: All three executors (claude/aider, cursor, openclaw) already have command templates for spec, impl, test, review, heal; this spec only requires verification and any missing wiring.
- Risk: Review agents might not consistently emit the structured blocks; the spec-guard skill and directions should be updated so that review tasks are instructed to output VERIFICATION_RESULT, FILES_TO_CHANGE, PATCH_GUIDANCE.

## Known Gaps and Follow-up Tasks

- Follow-up task: add parser coverage for review FAIL output contract in `api/tests/` so malformed `PATCH_GUIDANCE` is detected earlier.
- Optional: Add a small test that parses a sample review output and asserts presence of PATCH_GUIDANCE when VERIFICATION_RESULT=FAIL.
- Optional: Automate spec Verification section updates from SPEC_VERIFICATION_IMPROVEMENT (human approval recommended first).

## See also

- specs/002-agent-orchestration-api.md
- specs/005-project-manager-pipeline.md
- specs/026-pipeline-observability-and-auto-review.md
- .cursor/skills/spec-driven/SKILL.md
- .cursor/skills/spec-guard/SKILL.md
- docs/MODEL-ROUTING.md
