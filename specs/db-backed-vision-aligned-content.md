---
idea_id: db-backed-vision-aligned-content
status: done
source:
  - file: api/app/services/vision_content_service.py
    symbols: [get_aligned_content()]
  - file: api/app/routers/vision.py
    symbols: [get_aligned_content()]
  - file: web/app/vision/aligned/page.tsx
    symbols: [AlignedPage]
requirements:
  - "GET /api/vision/aligned returns page catalog data from graph nodes, not hardcoded application arrays."
  - "/vision/aligned renders communities, host spaces, gatherings, practices, and networks from the API payload."
  - "The page may render an empty-state message when the DB has no records, but must not fall back to embedded external catalog data."
done_when:
  - "cd api && .venv/bin/pytest -q tests/test_vision_content.py"
  - "cd web && npm run build"
constraints:
  - "Do not move presentation-only CSS classes into the DB."
  - "Do not add hardcoded external entity catalogs to application code."
  - "Use existing graph_nodes storage as the first DB-backed surface."
---

# Spec: DB-Backed Vision Aligned Content

## Purpose

The aligned vision page currently carries external communities, practices, networks, and host-space story data in React constants. That makes presence data brittle: changing a community, image, URL, or invitation requires a code deploy. This slice moves that catalog surface to graph-backed records so the page reads living content from the database.

## Requirements

- [x] **R1**: `GET /api/vision/aligned` returns graph-backed records grouped as `communities`, `host_spaces`, `gatherings`, `practices`, and `networks`.
- [x] **R2**: Records are selected by graph node type and `properties.source_page == "/vision/aligned"`; host spaces and gatherings are `scene` nodes separated by `properties.aligned_kind`.
- [x] **R3**: `/vision/aligned` renders records from the API payload and uses an empty state when a group has no records.

## API Contract

### `GET /api/vision/aligned`

**Response 200**
```json
{
  "source": "graph",
  "communities": [],
  "host_spaces": [],
  "gatherings": [],
  "practices": [],
  "networks": [],
  "counts": {
    "communities": 0,
    "host_spaces": 0,
    "gatherings": 0,
    "practices": 0,
    "networks": 0
  }
}
```

## Data Model

```yaml
Graph node:
  type: community | scene | practice | network-org
  properties:
    source_page: /vision/aligned
    aligned_kind: host-space | gathering
    image: string
    url: string
    location: string
    size: string
    concepts: string[]
    concept_labels: string[]
```

## Files to Create/Modify

- `specs/db-backed-vision-aligned-content.md`
- `api/tests/test_vision_content.py`
- `api/app/services/vision_content_service.py`
- `api/app/routers/vision.py`
- `api/app/main.py`
- `web/app/vision/aligned/page.tsx`

## Acceptance Tests

- `api/tests/test_vision_content.py::test_aligned_content_reads_from_graph_nodes`
- `api/tests/test_vision_content.py::test_aligned_content_does_not_emit_unscoped_nodes`

## Verification

```bash
cd api && .venv/bin/pytest -q tests/test_vision_content.py
cd web && npm run build
```

## Out of Scope

- Migrating all `/vision/*` page copy in this slice.
- Adding an admin editor for graph content.
- Seeding production content.

## Risks and Assumptions

- Empty databases will show empty states until content is inserted through graph APIs or a seed operation.
- Relationship and node type registries remain a later migration because they need schema-versioning.

## Known Gaps

- Follow-up task: add graph seed/editor support so production-aligned records can be managed without direct node creation.
