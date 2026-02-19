# PR Gates And Public Validation

Automated process to check merge gates for a PR branch and then validate public deployments.

## Access Pattern

- **Machine access (API):**
  - `GET /api/gates/pr-to-public?branch=...`
  - `GET /api/gates/merged-contract?sha=...`
  - `GET /api/gates/main-head`
  - `GET /api/gates/main-contract`
- **Human access (Web UI):**
  - `/gates` page in the web app

## Why

After commits are pushed, we need a deterministic gate:

1. PR exists and is mergeable.
2. Required checks are green.
3. Public API/web endpoints are live and responding.

This prevents moving to the next phase before public reality matches the code.

## Command

From repo root:

```bash
cd api && .venv/bin/python scripts/validate_pr_to_public.py --branch codex/system-question-ledger --wait-public
```

## What It Checks

### PR / GitHub gates

- Open PR exists for `--branch`
- PR is not draft
- Commit combined status is `success`
- Required contexts (if branch protection is readable with auth) are all present and successful
- Collective review status is recorded on PR checks (non-blocking in `thread-gates.yml`)
- Collective approval is enforced by post-merge Change Contract for contributor acknowledgment

### Public validation gates

Defaults:

- `https://coherence-network-production.up.railway.app/api/health`
- `https://coherence-network-production.up.railway.app/api/ideas`
- `https://coherence-web-production.up.railway.app/api-health`

All must return HTTP 200.

## Auth

Set `GITHUB_TOKEN` to read branch protection required checks:

```bash
export GITHUB_TOKEN=...
```

Without token, the script still checks PR + commit/check statuses but may not know branch-protection-required contexts.

## Output and Exit Codes

- `0`: ready/validated
- `2`: blocked (no PR, failing/missing checks, or public timeout)

Use `--json` for machine-readable output:

```bash
cd api && .venv/bin/python scripts/validate_pr_to_public.py --branch codex/system-question-ledger --wait-public --json
```

## Optional Flags

- `--repo seeker71/Coherence-Network`
- `--base main`
- `--api-base ...`
- `--web-base ...`
- `--endpoint <url>` (repeatable; overrides defaults)
- `--timeout-seconds 1200`
- `--poll-seconds 30`

## Suggested Thread Workflow

1. Commit and push branch.
2. Open PR to `main`.
3. Run gate checker without waiting:
   `validate_pr_to_public.py --branch <branch>`
4. Merge when green.
5. Run with deployment wait:
   `validate_pr_to_public.py --branch <branch> --wait-public`
6. Only then start next high-value question/artifact cycle.

## Smart-Contract Style Change Contract (Post-Merge)

Workflow: `.github/workflows/change-contract.yml`

On each push to `main`, the workflow enforces:

1. **Checks green** for merged commit.
2. **Collective review passed**:
   - PR merged to `main`
   - minimum 1 approval event
   - minimum 1 unique approver
3. **Public validation passed**:
   - API health and ideas endpoint
   - web root and `/api-health`

Only when all three pass, the workflow acknowledges the contributor by posting a PR comment with:
- contributor handle,
- collective approvers,
- pass confirmation.

Manual run:

```bash
cd api && .venv/bin/python scripts/validate_merged_change_contract.py --sha <main_commit_sha> --json
```

## Public worker PR-thread runtime (agent_runner)

See also: `docs/AGENT-THREAD-RESUME-SPEC.md` for run-record and checkpoint/resume behavior.

When a task has `context.execution_mode` in `{"pr", "thread", "codex-thread"}` or `context.create_pr=true`, the
`api/scripts/agent_runner.py` worker executes it in PR mode:

1. Checkout/create `codex/<task_id>` (or `context.pr_branch` if provided).
2. Run the task command in that checkout.
3. If changes are present, commit and push to origin.
4. Create or update a PR targeting `main`.
5. Poll `scripts/validate_pr_to_public.py --json --branch <branch>` until merge-ready or timeout.
6. Optionally auto-merge and optionally wait for public validation.

Suggested environment for Railway/public workers:

```bash
export AGENT_WORKTREE_PATH=/workspace/Coherence-Network
export AGENT_REPO_GIT_URL=https://github.com/seeker71/Coherence-Network.git
export AGENT_GITHUB_REPO=seeker71/Coherence-Network
export AGENT_PR_BASE_BRANCH=main
export AGENT_TASKS_DATABASE_URL=$DATABASE_URL
export AGENT_TASKS_USE_DB=1
export GITHUB_TOKEN=...   # or GH_TOKEN
export AGENT_RUN_STATE_DATABASE_URL=$DATABASE_URL
export AGENT_PR_LOCAL_VALIDATION_CMD='bash ./scripts/verify_worktree_local_web.sh'
export AGENT_PR_GATE_ATTEMPTS=8
export AGENT_PR_GATE_POLL_SECONDS=30
export AGENT_PR_FLOW_TIMEOUT_SECONDS=3600
export AGENT_RUN_LEASE_SECONDS=120
export AGENT_PERIODIC_CHECKPOINT_SECONDS=300
export AGENT_PR_MERGE_METHOD=squash
```

Example task creation payload for UI-created threads:

```json
{
  "direction": "Run implementation task from Codex thread",
  "task_type": "impl",
  "context": {
    "execution_mode": "pr",
    "create_pr": true,
    "auto_merge_pr": true,
    "wait_public": true
  }
}
```
