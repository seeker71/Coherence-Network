# Docs Hygiene Sweep Report - 2026-02-27

## Scope

- Scan `docs/**/*.md` and `specs/**/*.md` for stale, duplicated, fragmented, or broken references.
- Re-run spec-quality and duplicate-prefix canonicalization checks.
- Apply only safe docs/spec metadata updates.

## Validation Commands

- `make start-gate` -> pass
- `git fetch origin main && git rebase origin/main` -> initial fail due unstaged edits; self-healed via stash/rebase/pop
- `python3 scripts/validate_spec_quality.py --base origin/main --head HEAD` -> pass
- `python3 scripts/validate_spec_prefix_canonicalization.py` -> pass after mapping update
- Custom markdown internal link scan over docs/specs -> `FILES_SCANNED=152`, `TOTAL_MISSING=0`
- `python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict` -> fail (stale open Codex PR #344)
- `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main --skip-api-tests --skip-web-build` -> fail (`local_preflight=fail`, tied to follow-through gate)

## Findings

1. Duplicate-prefix validator drift
- Duplicate spec prefix `111` existed but was missing from canonical map, causing `validate_spec_prefix_canonicalization` failure.

2. Link integrity
- No missing internal markdown links across docs/specs (`TOTAL_MISSING=0`).

3. Remaining stale pinned model alias
- `specs/002-agent-orchestration-api.md` still contains `claude-3-5-haiku-20241022`.
- Direct normalization in this legacy spec is not safely automatable in this sweep because per-file spec-quality gate fails on untouched historical section-shape requirements.

4. Process blocker outside docs content
- Strict follow-through gate blocked by unrelated stale Codex PR #344.

## Actions Taken

- Added canonical duplicate mapping for prefix `111` in:
  - `config/spec_prefix_canonical_map.json`
- Updated canonicalization documentation table in:
  - `docs/SPEC-TRACKING.md`
- Re-ran docs/spec hygiene checks and captured blocker outputs for traceability.

## Remaining Tasks

1. Resolve stale PR blocker (`#344`) so `check_pr_followthrough --strict` and `worktree_pr_guard --mode local` can pass.
2. Perform a dedicated legacy-spec uplift for `specs/002-agent-orchestration-api.md` (section normalization first), then replace remaining pinned alias safely.

## Run Outcome

- Safe docs hygiene updates applied and validated.
- Internal doc/spec link integrity remains clean.
- Run cannot be advanced to commit/push readiness until follow-through blocker is resolved.
