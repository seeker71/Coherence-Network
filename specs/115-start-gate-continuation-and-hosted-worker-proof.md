# Spec: Start-Gate Continuation UX and Hosted Worker Low-Level Execution Proof

## Purpose

Reduce execution friction when start-gate is blocked, preserve in-flight thread work, and prove that low-level tasks (spec/test/review) can run primarily on hosted workers with measurable outcomes.

## Requirements

- [ ] Improve `scripts/start_gate.py` failure output with explicit unblock guidance and waiver examples.
- [ ] Ensure dirty-worktree and dirty-primary failures point to `scripts/auto_heal_start_gate.sh` so work can continue without abandonment.
- [ ] Fix `scripts/auto_heal_start_gate.sh --start-command` so multi-token commands work.
- [ ] Add a repeatable hosted-worker proof script for low-level task execution.
- [ ] Produce before/after start-gate output artifacts showing new remediation guidance.
- [ ] Run hosted-worker low-level tasks against production API and capture proof of execution + outcomes.
- [ ] Persist a measurable before/after hosted-worker execution summary under `docs/system_audit/`.

## API Contract (if applicable)

No API shape changes are required in this spec.

## Files to Create/Modify

- `specs/115-start-gate-continuation-and-hosted-worker-proof.md`
- `scripts/start_gate.py`
- `scripts/auto_heal_start_gate.sh`
- `api/scripts/prove_hosted_low_level_tasks.py`
- `docs/system_audit/start_gate_output_before_2026-02-28.txt`
- `docs/system_audit/start_gate_output_after_2026-02-28.txt`
- `docs/system_audit/hosted_worker_low_level_before_2026-02-28.json`
- `docs/system_audit/hosted_worker_low_level_after_2026-02-28.json`
- `docs/system_audit/hosted_worker_low_level_delta_2026-02-28.md`

## Acceptance Tests

- `./scripts/auto_heal_start_gate.sh --with-rebase --with-pr-gate`
- `./scripts/auto_heal_start_gate.sh --start-command "START_GATE_ENFORCE_REMOTE_FAILURES=0 make start-gate"`
- `cd api && python3 scripts/prove_hosted_low_level_tasks.py --api-url https://coherence-network-production.up.railway.app --before-output ../docs/system_audit/hosted_worker_low_level_before_2026-02-28.json --after-output ../docs/system_audit/hosted_worker_low_level_after_2026-02-28.json`
- `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main`
- `python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict`
- Manual validation: confirm before/after artifact deltas in `docs/system_audit/hosted_worker_low_level_delta_2026-02-28.md` and `docs/system_audit/start_gate_output_delta_2026-02-28.md`.

## Verification

```bash
python3 scripts/start_gate.py
./scripts/auto_heal_start_gate.sh --start-command "START_GATE_ENFORCE_REMOTE_FAILURES=0 make start-gate"

API_URL=https://coherence-network-production.up.railway.app
# capture baseline usage/events
curl -sS "$API_URL/api/runtime/endpoints/summary?limit=40"
curl -sS "$API_URL/api/agent/tasks?limit=40"

# run hosted-worker tasks (spec/test/review) and collect resulting task/event evidence
```

## Out of Scope

- Changing the business logic of task execution beyond hosted-worker routing inputs.
- Replacing existing CI workflows.

## Risks and Assumptions

- Production hosted worker capacity may vary; some tasks can remain pending.
- Main-workflow failures on `main` still require root-cause remediation; waivers are temporary.

## Known Gaps and Follow-up Tasks

- Add automated test coverage for `scripts/start_gate.py` remediation text generation.
- Add dashboard trendline for hosted-worker ratio by task type.

## Decision Gates (if any)

- None.
