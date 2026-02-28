# Hosted Worker Low-Level Task Proof Delta (2026-02-28)

## Run

- API: `https://coherence-network-production.up.railway.app`
- Script: `api/scripts/prove_hosted_low_level_tasks.py`
- Run ID: `20260228T095700Z`
- Executor requested: `claude`
- Task types: `spec,test,review,spec,test`

## Before vs After

| Metric | Before | After |
|---|---:|---:|
| matching tasks for run tag | 0 | 5 |
| hosted-claimed count | 0 | 3 |
| hosted-claim ratio | 0.0 | 0.6 |
| completed | 0 | 3 |
| pending | 0 | 2 |
| failed | 0 | 0 |

Source artifacts:
- `docs/system_audit/hosted_worker_low_level_before_2026-02-28.json`
- `docs/system_audit/hosted_worker_low_level_after_2026-02-28.json`

## Concrete task outcomes

- `task_8a7c4e7cbc2b633c` (`test`) -> `completed`, claimed by `openai-codex:railway-runner-1`
- `task_5190320b94ff9830` (`spec`) -> `completed`, claimed by `openai-codex:railway-runner-1`
- `task_5ce7c162e166d8bd` (`review`) -> `completed`, claimed by `openai-codex:railway-runner-1`
- `task_1bfbaf8bb05c747d` (`spec`) -> `pending`
- `task_0836c3b93c45450f` (`test`) -> `pending`

## Learning from failures/retries in this run

1. Blind spot: assumed `/api/agent/tasks` accepted `limit=300` and `limit=200`.
- Correction: script now clamps list limit to `<=100` (API contract reality).

2. Blind spot: assumed explicit execute endpoint could be called without execute token.
- Correction: rely on hosted auto-runner pickup and poll task status for terminal proof.

3. Blind spot: assumed openclaw+oauth path would be stable for quick proofs.
- Evidence: `refresh_token_reused` and invalid API key in `api_key` mode on separate smoke tasks.
- Correction: for low-level hosted proof, force executor `claude` and measure claim/completion outcomes directly.
