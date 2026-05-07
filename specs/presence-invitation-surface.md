---
idea_id: presence-invitation-surface
status: active
source:
  - file: api/app/services/presence_invitation_service.py
    symbols: [invite_presence(), list_invited_presences(), get_invited_presence()]
  - file: api/app/routers/presence.py
    symbols: [invite_presence(), list_invited_presences(), get_invited_presence()]
  - file: api/scripts/coherence.py
    symbols: [cmd_presence()]
  - file: web/app/people/invite/page.tsx
    symbols: [InvitePresencePage()]
  - file: web/app/people/invite/InvitePresenceForm.tsx
    symbols: [InvitePresenceForm()]
requirements:
  - "A steward can invite a person, place, event, service, plant, animal, thing, project, need, offering, story, community, or practice into the graph as a Presence."
  - "Invited presences expose internal and external paths, visibility, steward, story, offerings, needs, and connection fields through API, web, and CLI."
  - "The people directory has a direct invitation path without replacing the existing directory or presence-walk surfaces."
done_when:
  - "Focused API tests pass for inviting, listing, reading, and validating presences."
  - "The web build succeeds with the new /people/invite page."
  - "The CLI exposes presence invite/list/read commands."
test: "cd api && python3 -m pytest tests/test_presence_invitation.py -q"
constraints:
  - "Only change files listed in this spec."
  - "Use the existing graph node service as the persistence layer."
  - "Do not add external provider calls or new runtime dependencies."
---

# Spec: Presence Invitation Surface

## Purpose

Coherence Network needs a first embodied path for non-technical people to welcome living parts into the network: people, places, events, services, plants, animals, things, needs, offerings, stories, communities, and practices. This slice turns Presence from language into a repo-level primitive across API, web, and CLI while keeping persistence on the existing graph.

## Requirements

- [ ] **R1**: `POST /api/presences/invite` accepts a stewarded Presence payload and writes a graph node with a stable `presence:<kind>:<slug>` id.
- [ ] **R2**: The API normalizes presence kinds to existing graph node types while preserving the original kind in node properties.
- [ ] **R3**: `GET /api/presences` lists invited presences, optionally filtered by kind.
- [ ] **R4**: `GET /api/presences/{presence_id}` returns the normalized invited presence shape or a 404.
- [ ] **R5**: `/people` links to `/people/invite`, and `/people/invite` provides a usable form that posts to the API and shows the created internal and external paths.
- [ ] **R6**: The CLI supports `coherence presence invite`, `coherence presence list`, and `coherence presence read`.

## API Contract

### `POST /api/presences/invite`

**Request**
```json
{
  "name": "Mira's Healing Garden",
  "kind": "place",
  "story": "A garden for herbal integration and quiet circles.",
  "steward": "Mira",
  "location": "Ubud",
  "offerings": ["herbal integration"],
  "needs": ["shade cloth"],
  "ways_to_connect": ["hello@example.org"],
  "visibility": "public"
}
```

**Response 201**
```json
{
  "created": true,
  "presence": {
    "id": "presence:place:miras-healing-garden",
    "kind": "place",
    "type": "scene",
    "name": "Mira's Healing Garden",
    "internal_path": "/people/presence%3Aplace%3Amiras-healing-garden",
    "external_path": "/people/presence%3Aplace%3Amiras-healing-garden"
  }
}
```

## Data Model

```yaml
Presence:
  id: string
  type: graph node type
  kind: original presence kind
  name: string
  story: string
  steward: string
  location: string | null
  offerings: list[string]
  needs: list[string]
  ways_to_connect: list[string]
  visibility: private | network | public
  internal_path: string
  external_path: string | null
  external_url: string | null
```

## Files to Create/Modify

- `specs/presence-invitation-surface.md`
- `api/tests/test_presence_invitation.py`
- `api/tests/core_suite.txt`
- `api/app/services/presence_invitation_service.py`
- `api/app/routers/presence.py`
- `api/scripts/coherence.py`
- `web/app/people/page.tsx`
- `web/app/people/invite/page.tsx`
- `web/app/people/invite/InvitePresenceForm.tsx`
- `web/components/SecondaryLayerNav.tsx`
- `docs/system_audit/commit_evidence_2026-05-01_presence-invitation.json`
- `docs/system_audit/model_executor_runs.jsonl`

## Acceptance Tests

- `api/tests/test_presence_invitation.py::test_invite_presence_creates_graph_backed_presence`
- `api/tests/test_presence_invitation.py::test_invited_presence_kind_mapping_keeps_living_kind`
- `api/tests/test_presence_invitation.py::test_invite_presence_rejects_unknown_kind`

## Verification

```bash
cd api && python3 -m pytest tests/test_presence_invitation.py -q
cd api && python3 -m ruff check app/services/presence_invitation_service.py app/routers/presence.py tests/test_presence_invitation.py scripts/coherence.py
cd web && npm run build
python3 scripts/validate_spec_quality.py --file specs/presence-invitation-surface.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-01_presence-invitation.json
```

## Out of Scope

- Payment, booking, calendar, email, or custom-domain integrations.
- A full relationship editor between presences.
- Moderation, approval queues, or public search ranking.
- Database migrations beyond using the existing graph node shape.

## Risks and Assumptions

- Risk: The existing graph vocabulary does not have first-class plant or animal node types. Mitigation: store those as `asset` nodes while preserving `presence_kind`.
- Risk: A public invitation form can receive low-quality entries. Mitigation: this slice only makes the path; governance and moderation are follow-up work.
- Assumption: Existing graph nodes and `/people/{id}` pages remain the source of truth for visible presence pages.

## Known Gaps

- Follow-up task: add relationships between presences, such as stewarded-by, hosted-at, offers, needs, and part-of.
- Follow-up task: add booking, payments, newsletter, and calendar integrations for healer/service presences.
