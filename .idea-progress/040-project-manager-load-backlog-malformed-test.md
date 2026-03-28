# Progress — 040-project-manager-load-backlog-malformed-test

## Completed phases

- **2026-03-28 — Spec (task_9910a1448165f3fe):** Added `specs/040-project-manager-load-backlog-malformed-test.md` defining hardened `load_backlog` / `_parse_backlog_file` behavior (UTF-8, empty numbered lines, missing file/dir, meta interleave) with pytest file targets and five executable verification scenarios. Repaired corrupted `.gitignore` tail (task hygiene).

## Current task

Done (pending local `git commit` if not run).

## Key decisions

- **Scope:** Script + tests only (`api/scripts/project_manager.py`, `api/tests/test_project_manager.py`); no REST API in this idea.
- **Malformed UTF-8:** Spec requires defined behavior—empty list or replacement strategy—must be asserted in tests during impl phase.

## Blockers

- None for spec content; CI validation should be run after commit.
