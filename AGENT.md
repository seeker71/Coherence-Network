# Agent Self-Unblock Playbook

Purpose: when a gate fails, the agent should self-unblock with concrete remediation steps and continue execution instead of stopping for clarification.

## Rule

- Do not stop at "gate blocked" as the final answer.
- Fix the blocker first, rerun the gate, then continue commit/deploy flow.
- Report exact failing command/output only after attempting remediation.

## Gate-Specific Unblock Steps

### 1) `make start-gate` fails with dirty worktree

This commonly happens mid-task after edits are already in progress.

- Treat it as a continuation task, not a new thread bootstrap.
- Continue with targeted validation for changed files.
- Before commit, run required pre-commit guards:

```bash
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict
```

### 2) Spec quality gate fails

- Read missing sections from output.
- Patch spec to include required sections from `docs/SPEC-QUALITY-GATE.md`:
  - `Acceptance Tests`
  - `Verification`
  - `Risks and Assumptions`
  - `Known Gaps and Follow-up Tasks`
- Re-run:

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
```

### 3) Pre-commit guard fails

- `worktree_pr_guard.py`:
  - Apply the remediation command it prints.
  - Re-run until exit code 0.
- `check_pr_followthrough.py`:
  - Resolve stale/strict follow-through signals and re-run.

### 4) Public deploy verify fails (`timeout`/`502`)

- Re-run with bounded retries (do not assume one-shot failure is final):

```bash
./scripts/verify_web_api_deploy.sh
```

- If still failing:
  - Capture failing endpoint(s), status code/timeouts, and UTC timestamps.
  - Record in `docs/system_audit/*` evidence artifacts.
  - Continue with merge/deploy blockers clearly documented.

## Required Before Commit

- Add or update commit evidence file:

```bash
docs/system_audit/commit_evidence_<date>_<topic>.json
python3 scripts/validate_commit_evidence.py --file <path>
```

- Execute local guards:

```bash
git fetch origin main && git rebase origin/main
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict
```
