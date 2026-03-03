# Codex Thread Process (Parallel-Safe)

Date: 2026-02-14

Purpose: ensure each Codex thread can work independently, commit only its own scope, and advance phases only when validation gates pass.

Source of truth:
- `AGENTS.md` defines the mandatory process contract for all tasks.

## Core Rules

1. Scope isolation
   - Only edit files required for the current thread task.
   - Do not stage or commit unrelated files from other parallel threads.
2. Commit isolation
   - One logical change per commit.
   - Include evidence that process gates were executed.
3. Phase gating
   - Do not move to next phase until current phase gates pass.

## Task Start Protocol (Required)

Before any code changes in a new worktree/thread:

```bash
./scripts/setup_worktree_context.sh
./scripts/run_local_ci_context.sh
```

Then complete:
1. Read required context:
   - `CLAUDE.md`
   - `docs/SPEC-TRACKING.md`
   - `docs/SPEC-QUALITY-GATE.md`
2. Confirm scope:
   - Only modify files listed in the active spec/issue.
3. Follow process order:
   - Spec -> Test -> Implement -> CI -> Review -> Merge
4. Post-change gate:
   - Re-run local CI-equivalent checks before handoff.

Failure policy:
- If bootstrap or CI gates fail, stop implementation and report the exact failing command and output.
- Do not continue in a dirty worktree; create or switch to a clean worktree first.

## Required Phase Gates

### Phase -1: Worktree Setup Gate (required before Phase 0)

Non-negotiable:
- All implementation work happens in a linked worktree branch (`codex/*`).
- Never start implementation from the primary workspace.

Minimum startup sequence:

```bash
./scripts/fetch_origin_main.sh
git worktree add ~/.claude-worktrees/Coherence-Network/<thread-name> -b codex/<thread-name> origin/main
cd ~/.claude-worktrees/Coherence-Network/<thread-name>
git pull --ff-only origin main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
python3 scripts/ensure_worktree_start_clean.py --json
```

If the parity check fails (`HEAD != origin/main`), stop and repair base before any edits:

```bash
git fetch origin main
git rebase origin/main
```

### Phase 0: Start Gate (required before new task work)

Run from the target worktree:

```bash
make prompt-gate
```

Gate status:
- PASS only when not detached (`HEAD` is attached to a named branch).
- PASS only when not working directly on `main`/`master`.
- PASS only when thread context is valid: linked worktree OR `codex/*` branch.

Start command:
- `make prompt-gate` is the required prompt-entry command (clean tree runs start-gate + rebase + local guard; dirty tree enters continuation mode).
- `make start-gate` is intentionally minimal and only validates branch/worktree safety.

### Phase A: Local Validation (required before commit)

Run and record:

```bash
./scripts/run_local_ci_context.sh
./scripts/verify_worktree_local_web.sh
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
```

Gate status:
- PASS for local command set above.
- PASS for runtime branches only when `thread-runtime.sh run-e2e` is run and passes if runtime-surface files changed.
- PASS only if no stale open `codex/*` PR is left unattended.
- PASS only if open `codex/*` PR checks are green (or auto-rerun has healed flaky failures).
- PASS only if guard does not detect evidence/workflow/reference contract failures.

Optional runtime smoke (only when runtime-surface files under `api/` or `web/` changed):

```bash
./scripts/thread-runtime.sh run-e2e
```

Worktree notes:
- This command is the default local web validation for Codex threads.
- It runs API + web inside the current worktree, validates key API/web routes, and fails on runtime errors in page content.
- npm cache is isolated per worktree by default (`<worktree>/.cache/npm`) to avoid cross-thread cache permission collisions.
- Override ports when needed:
  - `API_PORT=18100 WEB_PORT=3110 ./scripts/verify_worktree_local_web.sh`
- Override npm cache when needed:
  - `NPM_CACHE=/tmp/coherence-npm-cache ./scripts/verify_worktree_local_web.sh`

### Phase B: CI Validation (required before merge)

Gate:
- GitHub Actions pipeline for the branch/PR is green.

If CI fails:
- Fix in the same thread scope.
- Re-run local validation.
- Push fix and wait for green CI.

Required pre-push base sync:

```bash
git fetch origin main
git rebase origin/main
python3 scripts/validate_commit_evidence.py --base origin/main --head HEAD --require-changed-evidence
```

Why this is mandatory:
- prevents stale-branch PR diffs against `main`,
- prevents commit-evidence failures caused by unrelated files appearing in the PR diff range.

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

## Merge Policy

A commit can exist with local-pass and CI/deploy pending.

A thread can move to the **next execution phase** only when:
- local validation = pass
- CI validation = pass
- deploy validation = pass
- collective review/contract = pass (for merged changes)

If CI/deploy are pending, thread status must explicitly stay `blocked_for_next_phase`.
