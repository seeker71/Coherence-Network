# Belief system — per-contributor worldview, interests, and concept preferences

## Purpose

Expose each contributor’s **belief profile**: worldview lens, value axes (for visualization), and concept/tag preferences. Support **resonance** between a contributor’s beliefs and an idea. Adapted from Living Codex UserConceptModule patterns.

## Requirements

1. **GET** `/api/contributors/{contributor_id}/beliefs` — return full belief profile (defaults when unset).
2. **PATCH** `/api/contributors/{contributor_id}/beliefs` — merge-update worldview, axes, and concept weights.
3. **GET** `/api/contributors/{contributor_id}/beliefs/resonance?idea_id=` — numeric alignment with an idea (0–1 scores + breakdown).
4. **Web**: `/contributors/[id]/profile` — radar (SVG), tag cloud, worldview selector.
5. **CLI**: `cc beliefs [contributor_id]` and `cc beliefs [contributor_id] resonance <idea_id>`.

## Data model

- Persist under contributor graph node `properties["belief_profile"]` (merged JSON).
- `worldview`: one of `scientific`, `spiritual`, `pragmatic`, `holistic`, `artistic`, `systems`.
- `axes`: map string → float in `[0,1]` (default keys: `rigor`, `empathy`, `speed`, `creativity`, `collaboration`, `systems`).
- `concepts`: map tag string → weight in `[0,1]`.

## API contract

- Responses are Pydantic models; dates ISO 8601 UTC if added later.
- Resonance uses idea text (name, description, interfaces) from `idea_service.get_idea`.

## Files to Create/Modify

- `specs/belief-system-interface.md` (this file)
- `api/app/models/belief.py`
- `api/app/services/belief_service.py`
- `api/app/routers/contributor_beliefs.py`
- `api/app/main.py` (register router)
- `api/tests/test_belief_system.py`
- `web/app/contributors/[id]/profile/page.tsx`
- `cli/lib/commands/beliefs.mjs`
- `cli/bin/cc.mjs`

## Verification

- `cd api && pytest api/tests/test_belief_system.py -v`
- Manual: GET/PATCH beliefs, GET resonance with valid `idea_id`.

## Risks and Assumptions

- Resonance is **heuristic** (token/concept overlap + worldview keywords + axis inference); not ML.
- Beliefs stored on same DB as graph nodes; no separate table.

## Known Gaps and Follow-up Tasks

- Optional auth on PATCH in production.
- Richer concept ontology linked to `concepts` router.
