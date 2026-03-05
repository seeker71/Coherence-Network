# 108 — Unified Agent CLI Flow: All Task Types, Patch on Verification Fail

## Purpose

Ensure every agent provider CLI (aider/claude, cursor, openclaw) can run the full delivery flow locally and remotely: generate spec from idea, implement a spec, run tests, review implementation against spec verification, and—when verification fails—produce enough structured information to create a patch so the next step can fix the implementation without discarding work. Optionally improve the spec’s Verification section when the verification step is ambiguous or wrong.

## Requirements

1. **All provider CLIs support all task types**
   - Each executor (claude/aider, cursor, openclaw) must be able to execute: `spec`, `impl`, `test`, `review`, `heal`.
   - Routing and command templates already exist in `agent_service` / `agent_routing_service`; ensure no task type is excluded for any executor and that directions are appropriate per phase.

2. **Full flow**
   - **Spec from idea**: task_type `spec` with direction that references the idea; output is a spec path (or content) per existing `build_direction("spec", ...)`.
   - **Implement**: task_type `impl` with spec reference; only modify files listed in spec (spec-driven, spec-guard).
   - **Review / verification**: task_type `review` runs verification (spec compliance, tests, correctness). Review must consume the spec’s Verification section (e.g. `cd api && pytest ...`) and the current implementation state.

3. **Review output contract when verification fails**
   - When review concludes FAIL (or tests/spec compliance fail), the review task’s output must be structured so a follow-up `impl` or `heal` task can apply a patch without starting from scratch.
   - Required structure (machine- and human-readable):
     - **VERIFICATION_RESULT**: `PASS` or `FAIL`.
     - **FAIL** case must include:
       - **FILES_TO_CHANGE**: list of paths that need changes (from spec’s Files to Create/Modify or identified violations).
       - **PATCH_GUIDANCE**: concise, actionable instructions or a minimal diff/edits (file, location, suggested change) so an impl/heal agent can make targeted edits.
     - Optional: **SPEC_VERIFICATION_IMPROVEMENT**: if the spec’s Verification section is wrong or ambiguous, suggest a concrete improvement (e.g. exact command or steps) so the spec can be updated.

4. **Pipeline use of review output**
   - When a review task completes with FAIL, the pipeline (e.g. project_manager) must pass the full review output (or a sufficient subset) into the next impl/heal task’s direction/context—not only a truncated snippet (e.g. more than 300 chars when it contains PATCH_GUIDANCE). This allows “patch from review” instead of “start over.”

5. **Local and remote execution**
   - **Local**: agent_runner runs the CLI command (aider/cursor/openclaw) in a subprocess; task types and routing already apply. No change required for “all task types” per executor beyond ensuring command templates and directions are correct.
   - **Remote**: same flow must be possible when a runner on another host runs the same agent_runner (or equivalent) and reports status to the API. Server-side execute (OpenRouter chat) is a different path; this spec does not require server-side to run the CLI—only that the contract (task types, review output format) is consistent so that any runner (local or remote) can consume it.

6. **Spec verification improvement (optional)**
   - If review finds that the spec’s Verification section is missing, wrong, or ambiguous, the review output may include SPEC_VERIFICATION_IMPROVEMENT. A follow-up process (human or automated) may update the spec’s Verification section accordingly so future runs are deterministic.

## API Contract

- No new API endpoints. Existing `POST /api/agent/tasks`, `GET /api/agent/tasks`, `PATCH /api/agent/tasks/{id}`, and execute/pickup endpoints remain unchanged.
- Task `context` may carry `spec_ref`, `idea_id`, `last_review_output`, or `patch_guidance` for downstream tasks; structure is convention for pipeline and agents, not a new API schema.

## Files to Create/Modify

- `specs/108-unified-agent-cli-flow-patch-on-fail.md` — this spec.
- `.cursor/skills/spec-guard/SKILL.md` — extend with “Review output (FAIL)” section: require VERIFICATION_RESULT, FILES_TO_CHANGE, PATCH_GUIDANCE; optional SPEC_VERIFICATION_IMPROVEMENT.
- `api/scripts/project_manager.py` — when building direction for impl after a failed review, pass full review output (or at least PATCH_GUIDANCE / FILES_TO_CHANGE) in context or direction, not only a 300-character truncation. Preserve existing behavior when output is small.
- `docs/AGENT-DEBUGGING.md` or `docs/PLAN.md` — add a short subsection describing the flow (spec → impl → test → review → patch on fail) and the review output contract.

## Acceptance Tests

- **Routing**: For each executor in `EXECUTOR_VALUES` (claude, cursor, openclaw) and each task_type in (spec, impl, test, review, heal), `GET /api/agent/route?task_type=X&executor=Y` returns a valid command_template and model. (Covered by existing agent routing tests; add or extend one test that asserts all pairs if missing.)
- **Review output contract**: Document in spec and spec-guard that FAIL review output must include VERIFICATION_RESULT=FAIL, FILES_TO_CHANGE, PATCH_GUIDANCE. No new automated test for agent output format unless we add a small parser test for the convention.
- **Project manager**: After a review task completes with status failed or output indicating FAIL, the next impl task created by project_manager receives direction/context that includes the review output (or PATCH_GUIDANCE) sufficient for patch-oriented fix (e.g. test that state or direction length/carry-over is improved where applicable).

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

- Optional: Add a small test that parses a sample review output and asserts presence of PATCH_GUIDANCE when VERIFICATION_RESULT=FAIL.
- Optional: Automate spec Verification section updates from SPEC_VERIFICATION_IMPROVEMENT (human approval recommended first).

## See also

- specs/002-agent-orchestration-api.md
- specs/005-project-manager-pipeline.md
- specs/026-pipeline-observability-and-auto-review.md
- .cursor/skills/spec-driven/SKILL.md
- .cursor/skills/spec-guard/SKILL.md
- docs/MODEL-ROUTING.md
