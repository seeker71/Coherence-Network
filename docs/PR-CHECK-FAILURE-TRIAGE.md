# PR Check Failure Triage

Date: 2026-02-17

Purpose: detect PR check failures early, auto-retry flaky GitHub Actions failures, and provide deterministic local remediation commands.

## Commands

Detect and report failures for open `codex/*` PRs:

```bash
python3 scripts/pr_check_failure_triage.py --repo seeker71/Coherence-Network --base main --head-prefix codex/
```

CI now runs this triage check during `pull_request` thread-gates:

```bash
python3 scripts/pr_check_failure_triage.py \
  --repo seeker71/Coherence-Network \
  --base main \
  --head-prefix codex/ \
  --fail-on-detected
```

Detect and fail local/CI step if failures exist:

```bash
python3 scripts/pr_check_failure_triage.py --repo seeker71/Coherence-Network --base main --head-prefix codex/ --fail-on-detected
```

Detect, auto-rerun failed GitHub Actions jobs, wait for settlement, then fail only if still blocked:

```bash
python3 scripts/pr_check_failure_triage.py \
  --repo seeker71/Coherence-Network \
  --base main \
  --head-prefix codex/ \
  --rerun-failed-actions \
  --rerun-settle-seconds 180 \
  --poll-seconds 20 \
  --fail-on-detected
```

All runs write JSON artifacts under:
- `docs/system_audit/pr_check_failures/`

## Failure Resolution Contract

For each failed check/context, the triage report includes `suggested_local_preflight`.

Common mappings:
- `Thread Gates` -> `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main`
- `Test` / API checks -> `cd api && pytest -q`
- `Build web` -> `cd web && npm ci && npm run build`
- `Validate commit evidence` -> `python3 scripts/validate_commit_evidence.py --base origin/main --head HEAD --require-changed-evidence`
- `Validate spec quality` -> `python3 scripts/validate_spec_quality.py --base origin/main --head HEAD`
- `Public Deploy Contract` -> `./scripts/verify_web_api_deploy.sh`
- `n8n security floor/HITL readiness` -> `cd api && .venv/bin/python scripts/validate_pr_to_public.py --branch <branch> --wait-public --n8n-version \"${N8N_VERSION}\"`

## n8n Blocker Pattern

When deploy readiness reports `result=blocked_n8n_version`:

1. Confirm deployed n8n runtime version.
2. Upgrade to the minimum secure floor (`>=1.123.17` for v1 or `>=2.5.2` for v2).
3. Re-run:
   ```bash
   cd api && .venv/bin/python scripts/validate_pr_to_public.py --branch <branch> --wait-public --n8n-version "${N8N_VERSION}"
   ```
4. Verify HITL approvals still block destructive/external-impact actions until explicit approval.

## Catch-Next-Time Automation

GitHub Actions workflow:
- `.github/workflows/pr-check-failure-triage.yml`

Behavior:
1. Runs every 6 hours and on manual dispatch.
2. Executes `pr_check_failure_triage.py` with auto-rerun enabled.
3. Uploads machine-readable triage artifacts.
4. Fails when blocking PR check failures remain after retry window.

This catches regressions even when no new local development command is run.
