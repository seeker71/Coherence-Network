# Field Story Public Runtime Docs

## Purpose

Ensure the public API runtime can read published field-story docs after deployment, including trace artifacts that live outside the API source tree.

## Requirements

- [x] Resolve field-story manifests from repo-root and API-container field-doc locations.
- [x] Sync `docs/field` into the Hostinger API container during deploy.
- [x] Preserve local repository behavior and avoid environment-variable configuration fallbacks.

## Files To Modify

- `api/app/services/field_story_service.py`
- `api/tests/test_field_story_runtime_docs.py`
- `deploy/hostinger/auto-deploy.sh`
- `specs/field-story-public-runtime-docs.md`
- `docs/system_audit/commit_evidence_2026-05-07_field_story_public_runtime_docs.json`

## Acceptance Criteria

- `api/tests/test_field_story_runtime_docs.py` verifies fallback field-doc roots.
- Public deploy copies `docs/field` into API container locations used by the service.
- `/api/field-stories` can return published stories after Hostinger deploy.

## Verification

```bash
cd api && .venv/bin/pytest -q tests/test_field_story_runtime_docs.py tests/test_field_story_trace_index.py
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-07_field_story_public_runtime_docs.json
```

## Out Of Scope

- This does not change field-story content or trace classification.
- This does not introduce runtime environment-variable configuration for field docs.

## Risks

- Copying all field docs increases deploy artifact transfer size, but keeps the API runtime aligned with repo-published story artifacts.

## Known Gaps

- None for this runtime unblock; future task can bake `docs/field` directly into an API image if the compose build context is moved to repo root.
