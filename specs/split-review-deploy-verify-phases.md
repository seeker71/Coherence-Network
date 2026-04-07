---
idea_id: agent-pipeline
status: done
source:
  - file: api/app/models/agent.py
    symbols: [TaskType.CODE_REVIEW, TaskType.DEPLOY, TaskType.VERIFY]
  - file: api/app/services/pipeline_advance_service.py
    symbols: [phase sequencing]
  - file: api/scripts/run_cli_task_flow_matrix.py
    symbols: [PASS_FAIL contract, review flow]
requirements:
  - code-review pass auto-triggers deploy task creation
  - deploy pass auto-triggers verify-production task creation
  - verify-production pass sets manifestation_status to validated
  - verify-production failure creates hotfix task with context.hotfix=true
  - Deploy failure creates fix task, not verify-production task
  - Add regression to ManifestationStatus enum
  - phase_stats in GET /api/pipeline/status shows per-phase pass rates
done_when:
  - Full chain code-review to deploy to verify to validated works end-to-end
  - No orphaned reviewing ideas with no active task
  - pytest api/tests/test_pipeline_phase_split.py passes
---

> **Parent idea**: [agent-pipeline](../ideas/agent-pipeline.md)
> **Source**: [`api/app/models/agent.py`](../api/app/models/agent.py) | [`api/app/services/pipeline_advance_service.py`](../api/app/services/pipeline_advance_service.py) | [`api/scripts/run_cli_task_flow_matrix.py`](../api/scripts/run_cli_task_flow_matrix.py)

# Split Review Into code-review → deploy → verify-production

**Spec ID**: 159-split-review-deploy-verify-phases
**Idea ID**: task_c8e7c8c3f0411f69
**Status**: Draft
**Depends on**: Spec 139 (Agent Pipeline), Spec 138 (Idea Lifecycle Management)
**Depended on by**: Spec 157 (Investment UX — validated status now requires verify-production)

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

## Research Inputs

- `2026-03-27` - [local_runner.py `_PHASE_SEQUENCE`](api/scripts/local_runner.py#L886) — defines the intended sequence but it is not wired into auto-advance
- `2026-03-27` - [pipeline_advance_service.py `_NEXT_PHASE`](api/app/services/pipeline_advance_service.py#L118) — current dead-end at `code-review: None`
- `2026-03-27` - [local_runner.py seeder ~L3264](api/scripts/local_runner.py#L3261) — advances to `merge` on review pass, does not chain deploy/verify
- `2026-03-27` - [Spec 139](specs/coherence-network-agent-pipeline.md) — pipeline auto-advance and retry logic this spec modifies
- `2026-03-27` - [Spec 138](specs/idea-lifecycle-management.md) — idea lifecycle and `manifestation_status` values this spec extends

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

## Files to Create/Modify

- `api/app/services/pipeline_advance_service.py` — extend `_NEXT_PHASE`, `_DOWNSTREAM`, add deploy/verify handlers
- `api/scripts/local_runner.py` — update seeder phase-advancement logic (remove `merge` short-circuit, wire deploy/verify direction prompts)
- `api/app/models/agent.py` — add `regression` to `ManifestationStatus` enum (or wherever this is defined)
- `api/app/routers/pipeline.py` — add `phase_stats` to `/api/pipeline/status` response
- `api/tests/test_pipeline_phase_split.py` — new test file (created by impl)

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

## How We Know It's Working

The implementation is working when ALL of the following are true week-over-week:

1. **Review failure rate drops below 20%**: `phase_stats.code-review.pass_rate >= 0.80`
2. **No orphaned reviewing ideas**: `GET /api/ideas?stage=reviewing` returns 0 ideas with no active task.
3. **Deploy success rate stays above 85%**: `phase_stats.deploy.pass_rate >= 0.85`
4. **Hotfix tasks catch regressions**: Any `verify-production` failure produces a task with `context.hotfix=true` visible in the task list within 30 seconds.
5. **Validated means truly live**: Every idea with `manifestation_status=validated` has a passing `verify-production` task in its task history.

The pulse service (`pipeline_pulse_service.py`) already tracks per-phase success rates. Extend it to emit a weekly summary that includes these five metrics.

## Risks and Assumptions

- **Risk**: Existing ideas at `reviewing` stage (old `review` task type) may be inadvertently re-triggered. Mitigation: the old `review` task type maps to `None` in `_NEXT_PHASE` and is not touched by the new logic.
- **Risk**: `verify-production` tasks that run curl against production may hit rate limits or CDN caching. Mitigation: use cache-busting headers (`Cache-Control: no-cache`) in verify prompts.
- **Assumption**: The deploy step assumes the VPS SSH key is available at `~/.ssh/hostinger-openclaw` on the runner node. If the runner runs in a container without this key, deploy tasks will always fail. This is a pre-existing constraint, not new.
- **Assumption**: All spec files include a `Verification Scenarios` section with runnable curl commands. Ideas without this section will produce verify-production tasks that output `VERIFY_FAILED` (no scenarios to run) — this is acceptable and forces a spec quality improvement.
- **Risk**: `regression` status is a new enum value. Adding it to the Pydantic model without a database migration will cause validation errors on read if the DB stores the string. Migration required in `alembic/` before deploy.

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
