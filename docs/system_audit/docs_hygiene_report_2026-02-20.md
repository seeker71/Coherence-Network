# Docs Hygiene Sweep Report - 2026-02-20

## Scope

- Scanned `docs/` and `specs/` for stale references, broken links, and fragmentation signals.
- Validated spec-quality gate and local PR preflight gate.
- Applied safe doc-only updates for broken internal links.

## Validation Commands

- `make start-gate` -> pass
- `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main` -> initially fail (HEAD behind origin/main), then pass after rebase
- `python3 scripts/validate_spec_quality.py --base origin/main --head HEAD` -> pass
- Custom markdown link validation over `docs/**/*.md` and `specs/**/*.md` -> `TOTAL_MISSING=0` after fixes

## Findings

1. Broken spec links (fixed)
- 6 broken internal links pointed to missing files:
  - `specs/008-sprint-1-graph-foundation.md`
  - `specs/024-pypi-indexing.md`

2. Fragmentation / duplication (not changed in this run)
- Duplicate spec number prefixes remain and create discoverability overhead:
  - `005, 007, 026, 027, 030, 048, 049, 050, 051, 052, 053, 054`

3. Potentially stale model alias references (not changed in this run)
- `claude-3-5-haiku-20241022` appears in docs/specs and may require periodic validation against current provider/model policy.

## Actions Taken

- Added canonical alias specs for missing legacy references:
  - `specs/008-sprint-1-graph-foundation.md`
  - `specs/024-pypi-indexing.md`
- Preserved existing historical docs/spec references without broad rewrites.
- Verified link integrity after alias additions (`TOTAL_MISSING=0`).

## Remaining Tasks

1. Canonicalize duplicate spec numbering
- Define canonical file per duplicate prefix.
- Add alias policy (redirect file or cross-reference convention) to prevent future dead links.

2. Validate model alias freshness
- Confirm `claude-3-5-haiku-20241022` remains approved in routing policy; update docs/specs if superseded.

## Run Outcome

- GH auth is healthy for current operations (`gh auth status`, `gh api user`, and remote git access succeeded).
- Deployment verification passed:
  - `./scripts/verify_worktree_local_web.sh --start`
  - `./scripts/verify_web_api_deploy.sh`
- Docs/spec link integrity improved; zero missing internal markdown link targets in scanned scope.
