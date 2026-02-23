# Docs Hygiene Sweep Report - 2026-02-23

## Scope

- Scanned `docs/` and `specs/` for stale references, broken internal links, and fragmentation signals.
- Validated spec-quality gate before and after doc/spec updates.
- Applied safe, low-risk content updates for stale pinned model alias references.

## Validation Commands

- `make start-gate` -> pass
- `python3 scripts/validate_spec_quality.py --base origin/main --head HEAD` -> pass
- Custom markdown link validation over `docs/**/*.md` and `specs/**/*.md` -> `TOTAL_MISSING=0`

## Findings

1. Internal markdown links
- No missing internal markdown targets detected (`TOTAL_MISSING=0`).

2. Duplicate spec prefixes (fragmentation)
- Duplicate numeric prefixes still exist and increase lookup overhead:
  - `005, 007, 026, 027, 030, 048, 049, 050, 051, 052, 053, 054`

3. Stale pinned model alias references
- A pinned alias (`claude-3-5-haiku-20241022`) remained in routing/debug docs and spec table while most docs use unpinned `claude-3-5-haiku`.

## Actions Taken

- Normalized stale pinned Claude fallback references to unpinned alias:
  - `docs/MODEL-ROUTING.md`
  - `docs/AGENT-DEBUGGING.md`
  - `specs/002-agent-orchestration-api.md`
- Re-ran spec-quality and markdown-link checks after edits.

## Proposed Consolidations

1. Duplicate spec number policy
- Create/maintain one canonical spec per numeric prefix.
- Keep non-canonical files as explicit alias wrappers with a short banner (`Canonical spec: ...`) to prevent future dead links.

2. Model alias policy centralization
- Keep all recommended runtime model aliases in one canonical doc (`docs/MODEL-ROUTING.md`) and avoid pinned dated aliases in other docs/specs unless required by a hard compatibility constraint.

## Remaining Tasks

1. Implement duplicate-prefix canonicalization for the listed prefixes.
2. Add a lightweight docs lint check to fail if stale pinned model aliases reappear outside approved exceptions.

## Run Outcome

- Start gate and spec-quality checks passed.
- Internal markdown links remain healthy (`TOTAL_MISSING=0`).
- Safe stale-content normalization applied without changing runtime code paths.
