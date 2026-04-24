---
idea_id: db-backed-vision-hub-content
status: done
source:
  - file: api/app/services/vision_content_service.py
    symbols: [get_hub_content()]
  - file: api/app/routers/vision.py
    symbols: [get_hub_content()]
  - file: web/app/vision/page.tsx
    symbols: [VisionPage]
requirements:
  - "GET /api/vision/{domain}/hub returns page hub data from graph nodes, not hardcoded application arrays."
  - "/vision renders concept sections, galleries, blueprint cards, emerging visions, and orientation chips from the API payload."
  - "The page may render empty-state text when the DB has no records, but must not fall back to embedded hub catalog data."
done_when:
  - "cd api && .venv/bin/pytest -q tests/test_vision_content.py"
  - "cd web && npm run build"
constraints:
  - "Do not move presentation-only Tailwind classes into the DB."
  - "Do not add hardcoded vision hub catalogs to application code."
  - "Use existing graph_nodes storage as the DB-backed source."
---

# Spec: DB-Backed Vision Hub Content

## Purpose

The `/vision` hub still carries a large amount of Living Collective page data in React arrays. Those arrays define which concepts, images, galleries, blueprint cards, emerging visions, and orientation words visitors see. This slice moves those hub collections to graph-backed records so the page can change through data instead of code.

## Requirements

- [x] **R1**: `GET /api/vision/{domain}/hub` returns graph-backed records grouped as `sections`, `galleries`, `blueprints`, `emerging`, and `orientation_words`.
- [x] **R2**: Records are selected from graph nodes with `properties.source_page == "/vision"` and `properties.vision_hub_group` identifying their group.
- [x] **R3**: `/vision` renders records from the API payload and uses empty states when a group has no records.

## API Contract

### `GET /api/vision/{domain}/hub`

**Response 200**
```json
{
  "source": "graph",
  "domain": "living-collective",
  "sections": [],
  "galleries": {
    "spaces": [],
    "practices": [],
    "people": [],
    "network": []
  },
  "blueprints": [],
  "emerging": [],
  "orientation_words": [],
  "counts": {
    "sections": 0,
    "gallery_items": 0,
    "blueprints": 0,
    "emerging": 0,
    "orientation_words": 0
  }
}
```

## Data Model

```yaml
Graph node:
  type: concept | asset | scene | practice | story | network-org
  properties:
    source_page: /vision
    domain: living-collective
    vision_hub_group: sections | gallery | blueprints | emerging | orientation_words
    gallery_group: spaces | practices | people | network
    sort_order: number
    image: string
    href: string
    body: string
    note: string
    tag: string
```

## Files to Create/Modify

- `specs/db-backed-vision-hub-content.md`
- `api/tests/test_vision_content.py`
- `api/app/services/vision_content_service.py`
- `api/app/routers/vision.py`
- `web/app/vision/page.tsx`
- `docs/system_audit/commit_evidence_2026-04-24_presence-perspectives.json`
- `docs/system_audit/model_executor_runs.jsonl`

## Acceptance Tests

- `api/tests/test_vision_content.py::test_vision_hub_reads_scoped_graph_nodes`
- `api/tests/test_vision_content.py::test_vision_hub_filters_domain_and_source_page`

## Verification

```bash
cd api && .venv/bin/pytest -q tests/test_vision_content.py
cd web && npm run build
```

## Out of Scope

- Adding a content editor.
- Seeding production hub records.
- Migrating `/vision/realize` and `/vision/economy` data.

## Risks and Assumptions

- Empty databases will render explicit empty states until graph records are published.
- Page-level layout and Tailwind presentation classes remain in code because they are view behavior, not content data.

## Known Gaps

- Follow-up task: add graph seed/editor support for hub records and migrate remaining `/vision/*` narrative copy in later slices.
