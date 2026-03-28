# Belief system interface — per-contributor worldview and preferences

## Purpose

Expose each contributor’s belief profile: worldview lens, weighted concept interests, and value axes (radar), aligned with Living Codex UserConceptModule / BeliefSystemModule concepts.

## Requirements

- Persist profile on the contributor graph node under `properties.belief_profile` (merged JSON).
- API: `GET/PATCH /api/contributors/{id}/beliefs`; `GET /api/contributors/{id}/beliefs/resonance?idea_id=...`.
- Web: contributor beliefs page with radar (axes), concept tag cloud, worldview selector.
- CLI: `cc beliefs <contributor_id>` and `cc beliefs <contributor_id> resonance <idea_id>`.

## API Contract

- **GET** `/api/contributors/{contributor_id}/beliefs` → `BeliefProfile` (defaults if empty).
- **PATCH** `/api/contributors/{contributor_id}/beliefs` → body partial: `worldview`, `concept_weights`, `axis_values` → updated `BeliefProfile`.
- **GET** `/api/contributors/{contributor_id}/beliefs/resonance?idea_id=` → resonance score 0–1 plus breakdown.

## Files to Create/Modify

- `api/app/models/belief.py`
- `api/app/services/belief_service.py`
- `api/app/routers/contributor_beliefs.py`
- `api/app/main.py` (register router)
- `web/app/contributors/[id]/beliefs/page.tsx`
- `cli/lib/commands/beliefs.mjs`
- `cli/bin/cc.mjs` (register `beliefs` command)
- `specs/belief-system-interface.md` (this file)

## Verification

- OpenAPI lists new routes; `GET` beliefs returns JSON; `PATCH` round-trips; resonance requires valid `idea_id`.

## Risks and Assumptions

- Resonance is heuristic (text overlap + axis keywords), not ML embedding.

## Known Gaps and Follow-up Tasks

- Optional auth for PATCH; federated sync of profiles.
