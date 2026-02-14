# Codex Thread Process (Parallel-Safe)

Date: 2026-02-14

Purpose: ensure each Codex thread can work independently, commit only its own scope, and advance phases only when validation gates pass.

## Core Rules

1. Scope isolation
   - Only edit files required for the current thread task.
   - Do not stage or commit unrelated files from other parallel threads.
2. Commit isolation
   - One logical change per commit.
   - Include evidence that process gates were executed.
3. Phase gating
   - Do not move to next phase until current phase gates pass.

## Required Phase Gates

### Phase A: Local Validation (required before commit)

Run and record:

```bash
cd api && .venv/bin/pytest -q
cd web && npm run build
```

Gate status:
- PASS only if tests/build succeed for the thread’s touched surface.

### Phase B: CI Validation (required before merge)

Gate:
- GitHub Actions pipeline for the branch/PR is green.

If CI fails:
- Fix in the same thread scope.
- Re-run local validation.
- Push fix and wait for green CI.

Collective review enforcement:
- `thread-gates.yml` fails PR checks unless at least 1 unique `APPROVED` review exists.

### Phase C: Public Deploy Validation (required before next product phase)

After deployment:

```bash
./scripts/verify_web_api_deploy.sh
```

Gate:
- API health/ready pass
- web root + api-health pass
- CORS check pass

If deploy checks fail:
- Treat as blocker.
- Fix and re-validate before moving to next phase.

### Phase D: Collective Review + Contributor Acknowledgment Contract (post-merge)

On merge to `main`, the Change Contract workflow enforces:
- merged commit checks are green,
- collective review approvals are present,
- public endpoints are validated.

Contributor acknowledgment is emitted **only** when all gates pass.

## Evidence Artifact (required per commit)

For each commit, add/update one evidence file under:
- `docs/system_audit/commit_evidence_<date>_<short-topic>.json`

It must include:
- `thread_branch`
- `commit_scope`
- `files_owned`
- `local_validation` (commands + pass/fail)
- `ci_validation` (pass/fail/pending + run URL when available)
- `deploy_validation` (pass/fail/pending + environment checked)
- `phase_gate` (can_move_next_phase: true/false)

## Merge Policy

A commit can exist with local-pass and CI/deploy pending.

A thread can move to the **next execution phase** only when:
- local validation = pass
- CI validation = pass
- deploy validation = pass
- collective review/contract = pass (for merged changes)

If CI/deploy are pending, thread status must explicitly stay `blocked_for_next_phase`.
