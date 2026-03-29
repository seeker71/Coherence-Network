# Progress — concept-layer-foundation

## Completed phases

- **task_ddb1053638a5aa53 (spec):** Referenced spec work; `specs/concept-layer-foundation.md` now present in repo with API/web/CLI/MCP summary and verification notes.
- **task_acdaecdb09e33831 / prior:** API `concepts` router + `concept_service`, web `/concepts` grid.
- **task_c0c31096f6449ad8 (impl):** Concept detail route `/concepts/[id]`, CLI `cc concepts` / `cc concept` / `cc concept link`, MCP coherence_* concept tools.

## Current task

- Idle after implementation commit (pending local `git commit` if shell available).

## Key decisions

- **Web:** Neighbor titles resolved with parallel GETs to `/api/concepts/{id}` for edge endpoints only (small N for typical concepts).
- **CLI/MCP:** Edge create sends `from_id` in JSON body matching path segment (required by `EdgeCreate` model).
- **Verification base URL:** `$API` = `https://api.coherencycoin.com/api` for production checks; local `http://localhost:8000/api` for dev.

## Blockers

- None.
