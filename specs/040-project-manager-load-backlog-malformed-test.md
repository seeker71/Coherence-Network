# Spec: Project Manager load_backlog — Malformed File (Missing Numbers) Test

## Purpose

Ensure the project manager's `load_backlog` behavior is tested when the backlog file contains lines that lack the required number prefix (`N. `). Parsing must skip such lines and return only valid numbered items, with no crash or inclusion of malformed content.

## Requirements

- [ ] A test exists that uses a backlog file containing **both** numbered lines and lines missing the `\d+\.\s+` prefix.
- [ ] The test asserts that `load_backlog()` returns only the parsed items from numbered lines (order preserved); lines without a leading number are skipped.
- [ ] The test does not rely on mocks; it uses real file I/O and the real `load_backlog` (or `_parse_backlog_file` via `load_backlog` with a single-file setup).

## API Contract (if applicable)

N/A — script behavior only.

## Data Model (if applicable)

N/A. Backlog format: lines matching `^\d+\.\s+(.+)$` are included; other lines are ignored. Comments (`#`) are excluded.

## Files to Create/Modify

- `api/tests/test_project_manager.py` — add or expand test for `load_backlog` with a malformed file (mixed numbered and unnumbered lines).

## Acceptance Tests

- [ ] New or expanded test in `api/tests/test_project_manager.py`: e.g. backlog file content like:
  - `1. First item`
  - `Unnumbered line`
  - `2. Second item`
  - `Another line without number`
  - Expected: `load_backlog()` returns `["First item", "Second item"]`.
- [ ] `pytest api/tests/test_project_manager.py -v` passes.

## Out of Scope

- Changing `_parse_backlog_file` or `load_backlog` behavior (implementation is already correct; this spec adds test coverage).
- Testing empty file or comment-only file (already covered by `test_load_backlog_empty_and_malformed`).
- Meta-backlog or `--backlog` flag (covered by other tests).

## See also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — project manager orchestrator
- [006-overnight-backlog.md](006-overnight-backlog.md) — backlog item 21

## Decision Gates (if any)

None.
