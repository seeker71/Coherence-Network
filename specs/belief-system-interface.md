# Belief system — per-contributor worldview and preferences

## Summary

Each contributor stores a **belief profile** on their graph node (`properties.belief_profile`): worldview, axis weights (radar), and concept weights (tag cloud). Resonance with an idea is computed from text overlap and axis alignment.

## API

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/contributors/{id}/beliefs` | Public |
| PATCH | `/api/contributors/{id}/beliefs` | `X-API-Key` |
| GET | `/api/contributors/{id}/beliefs/resonance?idea_id=` | Public |

## Files to modify

- `api/app/models/belief.py`
- `api/app/services/belief_service.py`
- `api/app/routers/contributors.py`
- `web/app/contributors/[id]/beliefs/page.tsx`
- `cli/lib/commands/beliefs.mjs`
- `cli/bin/cc.mjs`
- `api/tests/test_belief_contributor_beliefs.py`

## Verification

- `cd api && pytest api/tests/test_belief_contributor_beliefs.py -v`
- Manual: `GET /api/contributors/<id>/beliefs` after creating a contributor

## Risks and Assumptions

- Beliefs live in merged `properties` on the contributor node; no separate table.
- Resonance is heuristic (not ML).

## Known Gaps and Follow-up Tasks

- Optional OAuth-scoped PATCH without raw API key in the browser.
