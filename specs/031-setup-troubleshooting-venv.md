# Spec: Expand docs/SETUP.md — Troubleshooting and venv Path Note

## Purpose

Reduce setup friction for contributors and agents: document common failures and how to fix them, and make venv usage for scripts explicit so scripts run reliably from any working directory.

## Requirements

- [ ] `docs/SETUP.md` has a **Troubleshooting** section that includes at least: ModuleNotFoundError/import errors when running scripts, pytest not found, port in use, venv activation vs path.
- [ ] `docs/SETUP.md` has a clear **venv path note for scripts**: recommend `api/.venv/bin/python` (or `.venv/bin/python` when already in `api/`) for all `api/scripts/*` invocations; note Windows equivalent if applicable.
- [ ] Troubleshooting entries are specific and actionable (problem → fix).
- [ ] No new files; only modify `docs/SETUP.md`.

## API Contract (if applicable)

N/A — documentation only.

## Data Model (if applicable)

N/A.

## Files to Create/Modify

- `docs/SETUP.md` — add or expand Troubleshooting section; add or consolidate venv path note for scripts (e.g. in Run Tests / Scripts or a dedicated "Scripts and venv" subsection).

## Acceptance Tests

- Human review: SETUP.md reads clearly; a new user can resolve "script fails with ModuleNotFoundError" and "pytest not found" using the doc.
- No automated test required for doc-only change (per project conventions).

## Out of Scope

- Changing any script implementation or adding new scripts.
- Modifying AGENTS.md, CLAUDE.md, or other docs unless they explicitly reference SETUP.md content that is moved/renamed.

## Decision Gates (if any)

None.

## See also

- `specs/006-overnight-backlog.md` — backlog item "Expand docs/SETUP.md: add Troubleshooting section, venv path note for scripts"
- `specs/TEMPLATE.md` — spec format
