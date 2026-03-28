# Spec 159: Split Review Into code-review → deploy → verify-production

**Spec ID**: 159-split-review-deploy-verify-phases
**Idea ID**: task_c8e7c8c3f0411f69
**Status**: Draft
**Depends on**: Spec 139 (Agent Pipeline), Spec 138 (Idea Lifecycle Management)
**Depended on by**: Spec 157 (Investment UX — validated status now requires verify-production)

---

## Purpose

The Coherence Network pipeline conflates code quality review, production deployment, and production verification into a single "review" phase, causing 60–80% false-failure rates and leaving production regressions undetected. Splitting into three discrete, sequentially gated phases (`code-review → deploy → verify-production`) eliminates the ambiguity, gives each phase its own retry budget and failure handler, and ensures that `manifestation_status = validated` only reflects ideas that are genuinely live and working in production.

## Summary

The current pipeline conflates three distinct concerns in a single "review" phase: code quality assessment, production deployment, and production verification. This causes 60–80% false-failure rates because a code review can pass but the idea is declared failed when deployment hasn't happened yet — or vice versa, deployment succeeds but broken features are never caught in production.

This spec splits the post-test pipeline into three independent, sequentially gated phases:

1. **`code-review`** — Does the code meet spec? Is it mergeable? Do tests pass?
2. **`deploy`** — Merge to main, build Docker image, deploy to VPS, health check.
3. **`verify-production`** — Run spec verification scenarios against live production endpoints.

Each phase has its own retry budget, failure classification, and escalation path. An idea's `manifestation_status` becomes `validated` **only after `verify-production` passes**. A production verification failure creates a **hotfix task** at highest priority — because the feature is publicly broken.

The proof that this change is working is measurable: the review-phase failure rate drops below 20% and the number of ideas stuck at `reviewing` with no active task drops to zero within 7 days of deployment.

---

## Problem Statement

### Current behavior

The `pipeline_advance_service.py` defines `_NEXT_PHASE` as:

```python
"code-review": None   # dead end — no auto-advance to deploy or verify
```

And `local_runner.py` (seeder, line ~3264) treats a passing code-review as a signal to advance to `merge`, but the advance service still doesn't chain `deploy → verify`. Additionally the `review` task type is overloaded: it handles both "code quality review" and (in some cases) "did it ship?". This means:

- A passing code review never automatically triggers deployment.
- A deployed idea never automatically gets production-verified.
- `manifestation_status = validated` is set when code-review passes, not when production works.
- No hotfix task is ever created when production verification fails.

### Impact

- 60–80% of ideas in `reviewing` stage are not actually blocked — the code is fine, it just hasn't been deployed.
- Production regressions go undetected because there is no verify-production phase wired into the pipeline.
- The operator must manually trigger deploy and verify steps, creating toil and missed validations.

---

## Requirements

### R1 — Phase Sequence

The auto-advance chain MUST be:

```
spec → impl → test → code-review → deploy → verify-production
```

`pipeline_advance_service._NEXT_PHASE` must be updated:

```python
"code-review": "deploy",
"deploy":       "verify-production",
"verify-production": None,  # terminal — triggers manifestation_status update
```

Backward compatibility: the old `review` task type still maps to `None` (it is the legacy dead-end and should not trigger new phase chaining).

### R2 — code-review Phase

The code-review phase prompt must produce exactly one of:

- `CODE_REVIEW_PASSED` — code matches spec, tests pass, PR is mergeable.
- `CODE_REVIEW_FAILED: <specific issues>` — one or more spec requirements are missing, tests fail, or there is a blocking code quality issue.

**Pass gate**: Output contains `CODE_REVIEW_PASSED`.

**Failure handling**:
- Up to 2 retries (existing `_MAX_RETRIES = 2` logic applies).
- After exhausting retries: create a `needs_decision` task with the collected review failures for human triage.
- Do NOT advance to `deploy` if code-review fails or is ambiguous.

**Retry budget**: 2 (existing).

### R3 — deploy Phase

The deploy phase MUST execute the following steps in order:

1. Merge the feature branch to `main` via `gh pr merge --squash --admin`.
2. SSH deploy: `ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 'cd /docker/coherence-network/repo && git pull origin main && cd /docker/coherence-network && docker compose build --no-cache api web && docker compose up -d api web'`
3. Health check: `curl -s https://api.coherencycoin.com/api/health` — must return HTTP 200.

**Pass gate**: Health check returns HTTP 200 and response body contains `"status": "ok"` (or equivalent non-error JSON).

**Failure handling**:
- If merge fails: create a `fix` task for the merge conflict. Mark deploy as failed. Do NOT attempt SSH deploy.
- If SSH deploy fails or health check returns non-200: mark deploy as failed, create a `fix` task tagged `deploy_failure` with the error output. Do NOT advance to `verify-production`.
- Retry budget: **1 retry** (deploy is expensive; a second retry should be human-supervised).
- After retry exhaustion: escalate to `needs_decision` with `failure_type: deploy_failure`.

### R4 — verify-production Phase

The verify-production phase MUST run the spec's `Verification Scenarios` section against live production (`https://api.coherencycoin.com`, `https://coherencycoin.com`). Each scenario is checked with `curl` or `cc` commands from the spec.

**Pass gate**: Output contains `VERIFY_PASSED` and at least one scenario is demonstrated to work (URL + HTTP status + response snippet).

**Failure handling** (CRITICAL — feature is publicly broken):
- If output contains `VERIFY_FAILED` OR any scenario returns 404/500 for a spec endpoint:
  1. Create a new `AgentTask` of type `impl` with `priority = "urgent"`, tagged `hotfix`, containing the failing scenario output.
  2. Set `idea.manifestation_status = "regression"` (new status value).
  3. Do NOT mark the idea as `validated`.
  4. Broadcast: `cc msg broadcast "HOTFIX NEEDED: <idea_name> verify-production failed — feature publicly broken"`.
- Retry budget: **0** — if production verification fails, it is a live incident, not a retry candidate. Human or hotfix task must fix first.

### R5 — Idea Validation Gate

`idea.manifestation_status = "validated"` MUST be set **only** when `verify-production` phase completes with `VERIFY_PASSED`. The current code that sets `validated` on code-review pass must be removed or gated on the full chain.

`_DOWNSTREAM` must be extended to include `deploy` and `verify-production`:

```python
"code-review": ["deploy", "verify-production"],
"deploy":       ["verify-production"],
```

So that if a `code-review` task is reclassified as failed, any downstream `deploy` and `verify-production` tasks for that idea are also invalidated.

### R6 — Observability

The pipeline status endpoint (`GET /api/pipeline/status`) must include per-phase counters:

```json
{
  "phase_stats": {
    "code-review": {"completed": 12, "failed": 3, "pass_rate": 0.80},
    "deploy":       {"completed": 9,  "failed": 1, "pass_rate": 0.89},
    "verify-production": {"completed": 8, "failed": 2, "pass_rate": 0.75}
  }
}
```

These counters are the primary signal that the split is working. If `code-review` pass rate stays below 60%, something structural is wrong with the review prompt or the code quality bar. If `deploy` fails repeatedly, there is an infrastructure issue.

### R7 — `regression` Manifestation Status

Add `"regression"` as a valid value for `idea.manifestation_status` in the Pydantic model and database schema. This status means: the feature was once deployed but production verification is currently failing.

Valid transitions:
- `none → specced → implementing → testing → reviewing → deployed → validated` (happy path)
- `validated → regression` (verify-production fails after previous validation)
- `regression → deployed` (hotfix deployed, re-entering verify-production)

---

## Research Inputs

- `2026-03-27` - [local_runner.py `_PHASE_SEQUENCE`](api/scripts/local_runner.py#L886) — defines the intended sequence but it is not wired into auto-advance
- `2026-03-27` - [pipeline_advance_service.py `_NEXT_PHASE`](api/app/services/pipeline_advance_service.py#L118) — current dead-end at `code-review: None`
- `2026-03-27` - [local_runner.py seeder ~L3264](api/scripts/local_runner.py#L3261) — advances to `merge` on review pass, does not chain deploy/verify
- `2026-03-27` - [Spec 139](specs/139-coherence-network-agent-pipeline.md) — pipeline auto-advance and retry logic this spec modifies
- `2026-03-27` - [Spec 138](specs/138-idea-lifecycle-management.md) — idea lifecycle and `manifestation_status` values this spec extends

---

## Task Card

```yaml
goal: Wire code-review → deploy → verify-production as three distinct auto-advancing pipeline phases with per-phase retry, failure handling, and hotfix creation.
files_allowed:
  - api/app/services/pipeline_advance_service.py
  - api/scripts/local_runner.py
  - api/app/models/agent.py
  - api/app/routers/pipeline.py
  - api/tests/test_pipeline_phase_split.py
done_when:
  - _NEXT_PHASE chains code-review → deploy → verify-production
  - code-review failure triggers retry then needs_decision (not silent skip)
  - deploy failure creates fix task tagged deploy_failure and does NOT advance to verify
  - verify-production failure creates hotfix task with priority=urgent and sets manifestation_status=regression
  - manifestation_status=validated is only set when verify-production passes
  - _DOWNSTREAM includes deploy and verify-production in cascade invalidation
  - GET /api/pipeline/status includes phase_stats with per-phase counters
  - regression is a valid manifestation_status value
  - All tests in test_pipeline_phase_split.py pass
commands:
  - cd api && python -m pytest tests/test_pipeline_phase_split.py -v -q
  - cd api && python -m pytest tests/ -x -q --timeout=60
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
  - backward compat: old review task type must not break existing ideas
  - do not change code-review prompt text — only wire auto-advance chain
```

---

## API Contract

### `GET /api/pipeline/status` — extended response

**Response 200 (addition)**
```json
{
  "phase_stats": {
    "code-review": {
      "completed": 12,
      "failed": 3,
      "pass_rate": 0.80,
      "avg_retries": 0.4
    },
    "deploy": {
      "completed": 9,
      "failed": 1,
      "pass_rate": 0.89,
      "avg_retries": 0.1
    },
    "verify-production": {
      "completed": 8,
      "failed": 2,
      "pass_rate": 0.75,
      "avg_retries": 0.0
    }
  }
}
```

### `GET /api/ideas/{idea_id}` — extended manifestation_status

`manifestation_status` now accepts `"regression"` in addition to existing values.

---

## Data Model

```yaml
IdeaManifestationStatus:
  type: string
  enum:
    - none
    - partial
    - specced
    - implementing
    - testing
    - reviewing
    - deployed       # code-review passed, deploy succeeded
    - validated      # verify-production passed (previously set on code-review pass)
    - regression     # NEW: verify-production failed after previous deployment
```

---

## Files to Create/Modify

- `api/app/services/pipeline_advance_service.py` — extend `_NEXT_PHASE`, `_DOWNSTREAM`, add deploy/verify handlers
- `api/scripts/local_runner.py` — update seeder phase-advancement logic (remove `merge` short-circuit, wire deploy/verify direction prompts)
- `api/app/models/agent.py` — add `regression` to `ManifestationStatus` enum (or wherever this is defined)
- `api/app/routers/pipeline.py` — add `phase_stats` to `/api/pipeline/status` response
- `api/tests/test_pipeline_phase_split.py` — new test file (created by impl)

---

## Acceptance Tests

- `api/tests/test_pipeline_phase_split.py::test_code_review_pass_advances_to_deploy`
- `api/tests/test_pipeline_phase_split.py::test_code_review_fail_does_not_advance`
- `api/tests/test_pipeline_phase_split.py::test_deploy_fail_creates_fix_task`
- `api/tests/test_pipeline_phase_split.py::test_verify_production_fail_creates_hotfix_and_regression_status`
- `api/tests/test_pipeline_phase_split.py::test_full_chain_ends_in_validated`
- `api/tests/test_pipeline_phase_split.py::test_phase_stats_in_pipeline_status`
- `api/tests/test_pipeline_phase_split.py::test_downstream_invalidation_includes_deploy_verify`

## Verification Scenarios

### Scenario 1 — code-review passes and auto-advances to deploy

**Setup**: An idea with completed `test` phase tasks. No `deploy` or `verify-production` task exists.

**Action**:
```bash
# Simulate code-review task completing with PASSED output
curl -s -X PATCH https://api.coherencycoin.com/api/agent/tasks/<code_review_task_id> \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "output": "CODE_REVIEW_PASSED: All spec requirements met, tests pass, PR is mergeable."}'
```

**Expected result**: Within 30 seconds, a new `deploy` task is created for the same idea. `GET /api/agent/tasks?limit=5` returns a task with `task_type=deploy` and `context.idea_id=<idea_id>`. The idea's `manifestation_status` is NOT yet `validated`.

**Edge case**: If code-review output contains `CODE_REVIEW_FAILED`, no `deploy` task is created. The pipeline creates a retry or `needs_decision` task instead.

---

### Scenario 2 — deploy failure creates fix task (not hotfix)

**Setup**: An idea at `deploy` phase. The VPS is unreachable or the build fails.

**Action**:
```bash
# Simulate deploy task completing with FAILED output
curl -s -X PATCH https://api.coherencycoin.com/api/agent/tasks/<deploy_task_id> \
  -H "Content-Type: application/json" \
  -d '{"status": "failed", "output": "DEPLOY_FAILED: SSH connection timeout to 187.77.152.42"}'
```

**Expected result**:
1. No `verify-production` task is created.
2. A new `impl` (fix) task is created with `context.failure_type=deploy_failure` and the error in its description.
3. `GET /api/pipeline/status` shows `phase_stats.deploy.failed` incremented by 1.

**Edge case**: If deploy fails a second time (retry exhausted), the pipeline creates a `needs_decision` task instead of another fix task.

---

### Scenario 3 — verify-production failure creates urgent hotfix task

**Setup**: An idea at `verify-production` phase. A production endpoint returns 404.

**Action**:
```bash
# Simulate verify-production task completing with FAILED output
curl -s -X PATCH https://api.coherencycoin.com/api/agent/tasks/<verify_task_id> \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "output": "VERIFY_FAILED: GET https://api.coherencycoin.com/api/ideas returned 404 — feature not found in production"}'
```

**Expected result**:
1. `GET /api/ideas/<idea_id>` returns `"manifestation_status": "regression"` (not `validated`).
2. A new `impl` task is created with `priority=urgent` and `context.hotfix=true`.
3. The task description contains the failing scenario output.
4. `GET /api/pipeline/status` shows `phase_stats.verify-production.failed` incremented by 1.

**Edge case**: If `verify-production` output contains `VERIFY_PASSED`, the idea advances to `manifestation_status=validated` and NO hotfix task is created.

---

### Scenario 4 — full chain: code-review → deploy → verify → validated

**Setup**: An idea at `testing` stage with a completed test task.

**Action** (end-to-end chain):
```bash
API=https://api.coherencycoin.com

# 1. Check that code-review task exists after test completes
curl -s "$API/api/agent/tasks?limit=10" | jq '.tasks[] | select(.task_type == "code-review")'

# 2. Simulate code-review pass
curl -s -X PATCH "$API/api/agent/tasks/<cr_task_id>" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "output": "CODE_REVIEW_PASSED: LGTM"}'

# 3. Confirm deploy task created
sleep 5 && curl -s "$API/api/agent/tasks?limit=5" | jq '.tasks[] | select(.task_type == "deploy")'

# 4. Simulate deploy pass
curl -s -X PATCH "$API/api/agent/tasks/<deploy_task_id>" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "output": "DEPLOY_PASSED: SHA abc1234 live at coherencycoin.com"}'

# 5. Confirm verify-production task created
sleep 5 && curl -s "$API/api/agent/tasks?limit=5" | jq '.tasks[] | select(.task_type == "verify-production")'

# 6. Simulate verify pass
curl -s -X PATCH "$API/api/agent/tasks/<verify_task_id>" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "output": "VERIFY_PASSED: All 3 scenarios green. GET /api/health 200 OK."}'

# 7. Confirm idea is now validated
curl -s "$API/api/ideas/<idea_id>" | jq '.manifestation_status'
# Expected: "validated"
```

**Expected result**: `manifestation_status = "validated"` only after step 6 succeeds. Each intermediate phase produces exactly one downstream task.

---

### Scenario 5 — phase_stats endpoint reflects real counts

**Setup**: 3 code-reviews completed (2 passed, 1 failed), 2 deploys completed (both passed), 1 verify-production completed (passed).

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/pipeline/status | jq '.phase_stats'
```

**Expected result**:
```json
{
  "code-review": {"completed": 3, "failed": 1, "pass_rate": 0.67},
  "deploy":       {"completed": 2, "failed": 0, "pass_rate": 1.0},
  "verify-production": {"completed": 1, "failed": 0, "pass_rate": 1.0}
}
```

**Edge case**: If no tasks of a given phase have completed, that phase entry shows `{"completed": 0, "failed": 0, "pass_rate": null}` rather than erroring.

---

## How We Know It's Working

The implementation is working when ALL of the following are true week-over-week:

1. **Review failure rate drops below 20%**: `phase_stats.code-review.pass_rate >= 0.80`
2. **No orphaned reviewing ideas**: `GET /api/ideas?stage=reviewing` returns 0 ideas with no active task.
3. **Deploy success rate stays above 85%**: `phase_stats.deploy.pass_rate >= 0.85`
4. **Hotfix tasks catch regressions**: Any `verify-production` failure produces a task with `context.hotfix=true` visible in the task list within 30 seconds.
5. **Validated means truly live**: Every idea with `manifestation_status=validated` has a passing `verify-production` task in its task history.

The pulse service (`pipeline_pulse_service.py`) already tracks per-phase success rates. Extend it to emit a weekly summary that includes these five metrics.

---

## Out of Scope

- Changing the code-review prompt text (separate concern).
- Parallel phase execution (deploy and verify always sequential by design).
- Automatic rollback (deploy failure creates a fix task; human or fix agent initiates rollback explicitly).
- Notification via Telegram or email on hotfix creation (follow-up: Spec 003-style notification hook).

---

## Risks and Assumptions

- **Risk**: Existing ideas at `reviewing` stage (old `review` task type) may be inadvertently re-triggered. Mitigation: the old `review` task type maps to `None` in `_NEXT_PHASE` and is not touched by the new logic.
- **Risk**: `verify-production` tasks that run curl against production may hit rate limits or CDN caching. Mitigation: use cache-busting headers (`Cache-Control: no-cache`) in verify prompts.
- **Assumption**: The deploy step assumes the VPS SSH key is available at `~/.ssh/hostinger-openclaw` on the runner node. If the runner runs in a container without this key, deploy tasks will always fail. This is a pre-existing constraint, not new.
- **Assumption**: All spec files include a `Verification Scenarios` section with runnable curl commands. Ideas without this section will produce verify-production tasks that output `VERIFY_FAILED` (no scenarios to run) — this is acceptable and forces a spec quality improvement.
- **Risk**: `regression` status is a new enum value. Adding it to the Pydantic model without a database migration will cause validation errors on read if the DB stores the string. Migration required in `alembic/` before deploy.

---

## Known Gaps and Follow-up Tasks

- `pulse_service.py` needs extension to emit per-phase weekly stats (Spec 139 follow-up).
- The `merge` task type (currently between code-review and deploy in `local_runner.py`) is not in the new auto-advance chain. Spec 159 treats merge as a sub-step of `deploy`, not a standalone phase. A clean-up spec to remove the orphaned `merge` task type is a follow-up.
- Hotfix task priority field (`priority=urgent`) requires the `AgentTask` model to support a `priority` field; if not present, the task is created without priority and a follow-up spec should add it.
- Consider adding `verify-production` to the `_CODE_REQUIRED_PHASES` exclusion list (it produces curl output, not code diffs) to avoid false-positive hollow-output failures.

---

## Failure/Retry Reflection

| Phase | Failure mode | Blind spot | Next action |
|-------|-------------|------------|-------------|
| code-review | Agent outputs hollow text, not `CODE_REVIEW_PASSED/FAILED` | Prompt doesn't force structured output | Add output format enforcement to code-review prompt |
| deploy | SSH key missing on runner node | Runner provisioning gap | Check runner node key setup; add deploy pre-flight check |
| verify-production | Spec has no `Verification Scenarios` section | Spec quality gate missing | Add spec quality validator check for `Verification Scenarios` before allowing verify-production phase |

---

## Decision Gates

- Alembic migration for `regression` status: requires DBA/ops approval before deploy.
- Removing `merge` as standalone phase: requires architectural review (Spec 139 dependency).
