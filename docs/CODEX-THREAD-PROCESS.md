# Codex Thread Process (Parallel-Safe)

Date: 2026-02-14

Purpose: ensure each Codex thread can work independently, commit only its own scope, and advance phases only when validation gates pass.

## Core Rules

1. Scope isolation
   - Only edit files required for the current thread task.
   - Do not stage or commit unrelated files from other parallel threads.
2. Commit isolation
   - One logical change per commit.
   - Include evidence that process gates were executed.
3. Phase gating
   - Do not move to next phase until current phase gates pass.

## Required Phase Gates

### Phase A: Local Validation (required before commit)

Run and record:

```bash
./scripts/worktree_bootstrap.sh
python3 scripts/local_cicd_preflight.py --base-ref origin/main --head-ref HEAD
python3 scripts/check_worktree_isolation.py
python3 scripts/check_worktree_bootstrap.py
python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-open --fail-on-stale --strict
cd api && .venv/bin/pytest -q
./scripts/verify_worktree_local_web.sh
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
```

Gate status:
- PASS only if tests/build succeed for the thread’s touched surface.
- PASS only if changed specs pass the spec quality contract (when any feature spec changed).
- PASS only if no stale open `codex/*` PR is left unattended.
- PASS only if there are no open `codex/*` PRs from previous work (previous work must be finished first).
- PASS only if local CI/CD preflight catches no blocking issues.
- PASS only if `check_worktree_isolation.py` confirms execution is in a linked worktree (`.git` file pointing to `.git/worktrees/...`).
- PASS only if `check_worktree_bootstrap.py` confirms setup doc acknowledgment, API venv deps, and web dependencies are ready.

Worktree notes:
- This command is the default local web validation for Codex threads.
- It runs API + web inside the current worktree, validates key API/web routes, and fails on runtime errors in page content.
- Override ports when needed:
  - `API_PORT=18100 WEB_PORT=3110 ./scripts/verify_worktree_local_web.sh`

### Phase B: CI Validation (required before merge)

Gate:
- GitHub Actions pipeline for the branch/PR is green.

If CI fails:
- Fix in the same thread scope.
- Re-run local validation.
- Push fix and wait for green CI.

Collective review signal:
- `thread-gates.yml` records collective review status on PRs (non-blocking).
- Contributor acknowledgment remains blocked by post-merge Change Contract until collective review passes.

### Phase C: Public Deploy Validation (required before next product phase)

After deployment:

```bash
./scripts/verify_web_api_deploy.sh
```

Gate:
- API health/ready pass
- web root + api-health pass
- CORS check pass

If deploy checks fail:
- Treat as blocker.
- Fix and re-validate before moving to next phase.

### Phase D: Collective Review + Contributor Acknowledgment Contract (post-merge)

On merge to `main`, the Change Contract workflow enforces:
- merged commit checks are green,
- collective review approvals are present,
- public endpoints are validated.

Contributor acknowledgment is emitted **only** when all gates pass.

## Evidence Artifact (required per commit)

For each commit, add/update one evidence file under:
- `docs/system_audit/commit_evidence_<date>_<short-topic>.json`

It must include:
- `thread_branch`
- `commit_scope`
- `files_owned`
- `idea_ids` (non-empty list)
- `spec_ids` (non-empty list)
- `task_ids` (non-empty list)
- `contributors` (non-empty list; each with `contributor_id`, `contributor_type` = `human|machine`, `roles`)
- `agent` (`name`, `version`)
- `evidence_refs` (non-empty list of verifiable references)
- `change_files` (non-empty list of file paths changed by the commit)
- `change_intent` (`runtime_feature` | `runtime_fix` | `process_only` | `docs_only` | `test_only`)
- `local_validation` (commands + pass/fail)
- `ci_validation` (pass/fail/pending + run URL when available)
- `deploy_validation` (pass/fail/pending + environment checked)
- `phase_gate` (can_move_next_phase: true/false)

Runtime intent contract:
- If `change_intent` is `runtime_feature` or `runtime_fix`, evidence must include `e2e_validation` with:
  - `status` (`pass` | `pending` | `fail`)
  - `expected_behavior_delta`
  - `public_endpoints` (non-empty list)
  - `test_flows` (non-empty list)
- Runtime intents must include changed files under `api/app/`, `web/app/`, or `web/components/`.
- Non-runtime intents cannot include runtime file changes.

CI enforcement:
- `python3 scripts/validate_commit_evidence.py --base <sha> --head <sha> --require-changed-evidence`
- Fails if no changed `docs/system_audit/commit_evidence_*.json` exists for the diff range.
- Fails if changed files are not declared in `change_files`.

Local CI/CD preflight:
- `python3 scripts/local_cicd_preflight.py --base-ref origin/main --head-ref HEAD`
- Mirrors common branch CI failure checks in local order before PR creation.
- Includes `vercel_rate_limit_guard` and blocks new PR iteration when Vercel cooldown is active.
- Persists machine-readable optimization data:
  - `docs/system_audit/local_cicd_preflight_latest.json`
  - `docs/system_audit/local_cicd_preflight_history.jsonl`
  - `docs/system_audit/vercel_rate_limit_guard_latest.json`
  - `docs/system_audit/vercel_rate_limit_guard_history.jsonl`
- Ranks recurring loss under `highest_energy_loss_steps` so teams can reduce repeated PR iteration cost.

## Merge Policy

A commit can exist with local-pass and CI/deploy pending.

A thread can move to the **next execution phase** only when:
- local validation = pass
- CI validation = pass
- deploy validation = pass
- collective review/contract = pass (for merged changes)

If CI/deploy are pending, thread status must explicitly stay `blocked_for_next_phase`.
