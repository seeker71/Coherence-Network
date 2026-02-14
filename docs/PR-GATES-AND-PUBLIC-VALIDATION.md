# PR Gates And Public Validation

Automated process to check merge gates for a PR branch and then validate public deployments.

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

### Public validation gates

Defaults:

- `https://coherence-network-production.up.railway.app/api/health`
- `https://coherence-network-production.up.railway.app/api/ideas`
- `https://coherence-network.vercel.app/api-health`

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
