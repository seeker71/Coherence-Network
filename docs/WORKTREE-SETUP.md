# Worktree Setup and Validation

Purpose: avoid repeated `pytest` and `npm` environment failures by standardizing setup for every new git worktree.

## Required Before Any Work

Run this once per worktree (and again when this doc changes):

```bash
./scripts/worktree_bootstrap.sh
```

This does all required setup:
- Confirms you are in a linked git worktree (not the main checkout).
- Creates `api/.venv` (Python 3.11 preferred, fallback to `python3`) when missing.
- Installs API dependencies: `pip install -e ".[dev]"`.
- Installs web dependencies with local cache: `web/node_modules` via `npm ci`.
- Writes a worktree marker: `.worktree-state/setup_ack.json` with:
  - doc path
  - doc SHA256
  - timestamp
  - repo root and branch

## Required Before Validation

Run local preflight (this now enforces setup marker and environment readiness):

```bash
python3 scripts/local_cicd_preflight.py --base-ref origin/main --head-ref HEAD
```

If setup is stale/missing, the guard fails with instructions to run:

```bash
./scripts/worktree_bootstrap.sh
```

## Normal Daily Flow

1. Create/switch to a linked worktree branch.
2. Run `./scripts/worktree_bootstrap.sh`.
3. Implement changes.
4. Run preflight + focused tests.
5. Commit and push.

## Notes

- This is intentionally per-worktree to keep parallel threads isolated.
- The marker is local-only and ignored by git.
