# Codex Thread Process (Parallel-Safe)

Date: 2026-02-14

Purpose: ensure each Codex thread can work independently, commit only its own scope, and advance phases only when validation gates pass.

Canonical setup reference:
- `docs/WORKTREE-QUICKSTART.md` (mandatory for every new thread)

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
make start-gate
```

### Phase 0: Start Gate (required before new task work)

Run from the target worktree:

```bash
make start-gate
```

Gate status:
- PASS only when running from a linked worktree (`.git` points to a worktree gitdir, not the primary `.git` directory).
- PASS only when current worktree has no local changes before starting the next task.
- PASS only when primary workspace is clean (prevents abandoned local changes in main workspace).
- PASS only when current start-command checks succeed, including remote `main` workflow health and open `codex/*` PR checks.

Start command:
- `make start-gate` enforces worktree-only execution, current+primary clean checks, and remote guard checks via GitHub (`gh`).

### Phase A: Local Validation (required before commit)

Run and record:

```bash
# Optional for n8n-backed flows: export N8N_VERSION=<deployed-version>
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
python3 scripts/pr_check_failure_triage.py --repo seeker71/Coherence-Network --base main --head-prefix codex/ --fail-on-detected
python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict
./scripts/thread-runtime.sh check
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
- This command is the default local PR failure-prevention guard for Codex threads.
- `./scripts/verify_worktree_local_web.sh` is readiness-first by default (it validates existing local API/web services).
- Start services intentionally with `THREAD_RUNTIME_START_SERVERS=1` only when needed.
- `./scripts/verify_worktree_local_web.sh --thread-ports` prints current thread-runtime port usage across active threads.
- Thread runtime defaults to per-thread deterministic base ports using `THREAD_RUNTIME_API_BASE_PORT` / `THREAD_RUNTIME_WEB_BASE_PORT`.
- It writes machine-readable artifacts under `docs/system_audit/pr_check_failures/`.
- `thread-runtime.sh run-e2e` does runtime API smoke against the active local API and is cache-aware.
- Remote/all mode also checks latest `Public Deploy Contract` health on `main` and blocks progression when deployment validation is failed or stale.
- If `N8N_VERSION` is set (or `--n8n-version` is passed), the local guard enforces n8n security floor (`v1>=1.123.17`, `v2>=2.5.2`) and blocks push when below floor.
- If running `./scripts/verify_worktree_local_web.sh` directly, npm cache defaults to per-worktree `<worktree>/.cache/npm` (override via `NPM_CACHE=...`).

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

## Merge Policy

A commit can exist with local-pass and CI/deploy pending.

A thread can move to the **next execution phase** only when:
- local validation = pass
- CI validation = pass
- deploy validation = pass
- collective review/contract = pass (for merged changes)

If CI/deploy are pending, thread status must explicitly stay `blocked_for_next_phase`.
