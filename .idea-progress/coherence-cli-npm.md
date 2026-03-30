# Idea Progress — coherence-cli-npm

## Current task
- **Task:** impl (task_140faad0b5667499)
- **Status:** Complete

## Completed phases
- **spec** — Wrote `specs/148-coherence-cli-comprehensive.md` defining npm-publishable CLI with 15 core commands, zero deps, TOFU identity onboarding, 5 verification scenarios, 13 files to modify/create.
- **impl** — Formalized CLI for npm publishing: bumped version to 0.11.0, restructured help output to clearly separate 15 core commands from extended commands (per spec R3), verified zero dependencies and npm pack. All 15 commands were already implemented; this task aligned them with the spec.

## Key decisions
- Primary binary name: `coh` (not `cc`) to avoid C compiler conflict
- 15 commands are a curated subset of the 54 already implemented — others remain as unlisted power-user commands
- No new API endpoints needed — CLI consumes existing public API
- TOFU onboarding via `POST /api/onboard` (setup.mjs) and `ensureIdentity()` (identity.mjs)
- Package size target: < 150 KB tarball (verified ~140KB)
- Help output restructured with "15 Core Commands" section header and "Extended Commands" section

## Blockers
None
