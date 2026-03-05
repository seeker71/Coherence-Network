# 108 — Unified Agent CLI Flow: All Task Types, Patch on Verification Fail

## Purpose

Ensure every agent provider CLI (aider/claude, cursor, openclaw) can run the full delivery flow locally and remotely: generate spec from idea, implement a spec, run tests, review implementation against spec verification, and—when verification fails—produce enough structured information to create a patch so the next step can fix the implementation without discarding work. Optionally improve the spec’s Verification section when the verification step is ambiguous or wrong.

## Requirements

- [ ] Each provider CLI executor (`claude`/aider, `cursor`, `openclaw`) supports task types `spec`, `impl`, `test`, `review`, and `heal` with no task-type exclusions in routing templates.
- [ ] The delivery flow remains spec-driven: `spec` from idea, `impl` from spec, and `review` that verifies spec compliance and implementation behavior.
- [ ] Failed review output is structured and patchable, including `VERIFICATION_RESULT=FAIL`, `FILES_TO_CHANGE`, and `PATCH_GUIDANCE`.
- [ ] When review fails, project manager / pipeline passes sufficient review output into next `impl`/`heal` direction (no destructive truncation of patch guidance).
- [ ] Local and remote runner paths use the same task/output contract so patch-on-fail behavior works in both environments.
- [ ] Optional review output may include `SPEC_VERIFICATION_IMPROVEMENT` when the spec verification section is ambiguous or incorrect.

## API Contract

- No new API endpoints. Existing `POST /api/agent/tasks`, `GET /api/agent/tasks`, `PATCH /api/agent/tasks/{id}`, and execute/pickup endpoints remain unchanged.
- Task `context` may carry `spec_ref`, `idea_id`, `last_review_output`, or `patch_guidance` for downstream tasks; structure is convention for pipeline and agents, not a new API schema.

## Files to Create/Modify

- `specs/108-unified-agent-cli-flow-patch-on-fail.md` — this spec.
- `.cursor/skills/spec-guard/SKILL.md` — extend with “Review output (FAIL)” section: require VERIFICATION_RESULT, FILES_TO_CHANGE, PATCH_GUIDANCE; optional SPEC_VERIFICATION_IMPROVEMENT.
- `api/scripts/project_manager.py` — when building direction for impl after a failed review, pass full review output (or at least PATCH_GUIDANCE / FILES_TO_CHANGE) in context or direction, not only a 300-character truncation. Preserve existing behavior when output is small.
- `docs/AGENT-DEBUGGING.md` or `docs/PLAN.md` — add a short subsection describing the flow (spec → impl → test → review → patch on fail) and the review output contract.

## Acceptance Tests

- **Routing**: For each executor in `EXECUTOR_VALUES` (claude, cursor, openclaw) and each task_type in (spec, impl, test, review, heal), `GET /api/agent/route?task_type=X&executor=Y` returns a valid command_template and model. Validate with tests under `api/tests/test_agent_executor_policy.py` and `api/tests/test_agent_execution_model_resolution.py`.
- **Review output contract**: Spec and spec-guard require FAIL output blocks (`VERIFICATION_RESULT=FAIL`, `FILES_TO_CHANGE`, `PATCH_GUIDANCE`). Manual validation is acceptable if parser automation is deferred.
- **Project manager carry-over**: After a failed review, next impl task includes review output / patch guidance in direction or context; validate with tests in `api/tests/test_agent_execute_endpoint.py` and `api/tests/test_agent_executor_policy.py`.

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

- Follow-up task: add a small parser-focused test that asserts `PATCH_GUIDANCE` is present when `VERIFICATION_RESULT=FAIL`.
- Follow-up task: automate spec Verification section updates from `SPEC_VERIFICATION_IMPROVEMENT` with human approval gate.

## See also

- specs/002-agent-orchestration-api.md
- specs/005-project-manager-pipeline.md
- specs/026-pipeline-observability-and-auto-review.md
- .cursor/skills/spec-driven/SKILL.md
- .cursor/skills/spec-guard/SKILL.md
- docs/MODEL-ROUTING.md
