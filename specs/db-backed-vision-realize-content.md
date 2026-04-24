---
idea_id: db-backed-vision-realize-content
status: active
source:
  - file: api/app/services/vision_content_service.py
    symbols: [get_realize_content()]
  - file: api/app/routers/vision.py
    symbols: [get_realize_content()]
  - file: web/app/vision/realize/page.tsx
    symbols: [RealizePage]
requirements:
  - "GET /api/vision/{domain}/realize returns realize-page data from graph nodes, not hardcoded application arrays."
  - "/vision/realize renders vocabulary, host spaces, context pairs, and dual paths from the API payload."
  - "The page may render empty-state text when the DB has no records, but must not fall back to embedded realize catalog data."
done_when:
  - "cd api && .venv/bin/pytest -q tests/test_vision_content.py"
  - "cd web && npm run build"
constraints:
  - "Do not move presentation-only Tailwind classes into the DB."
  - "Do not add hardcoded realize-page catalogs to application code."
  - "Use existing graph_nodes storage as the DB-backed source."
---

# Spec: DB-Backed Vision Realize Content

## Purpose

The `/vision/realize` page still carries transformation vocabulary, host-space patterns, context comparisons, and dual-path invitations in React arrays. That makes the living-experience surface static and code-bound. This slice moves those core collections to graph-backed records so the page can evolve through data.

## Requirements

- [x] **R1**: `GET /api/vision/{domain}/realize` returns graph-backed records grouped as `vocabulary`, `host_spaces`, `context_pairs`, and `dual_paths`.
- [x] **R2**: Records are selected from graph nodes with `properties.source_page == "/vision/realize"` and `properties.realize_group` identifying their group.
- [x] **R3**: `/vision/realize` renders records from the API payload and uses empty states when a group has no records.

## API Contract

### `GET /api/vision/{domain}/realize`

**Response 200**
```json
{
  "source": "graph",
  "domain": "living-collective",
  "vocabulary": [],
  "host_spaces": [],
  "context_pairs": [],
  "dual_paths": [],
  "counts": {
    "vocabulary": 0,
    "host_spaces": 0,
    "context_pairs": 0,
    "dual_paths": 0
  }
}
```

## Data Model

```yaml
Graph node:
  type: concept | scene | practice | asset
  properties:
    source_page: /vision/realize
    domain: living-collective
    realize_group: vocabulary | host_spaces | context_pairs | dual_paths
    sort_order: number
    image: string
    body: string
    first_move: string
    old_word: string
    field_word: string
    meaning: string
```

## Files to Create/Modify

- `specs/db-backed-vision-realize-content.md`
- `api/tests/test_vision_content.py`
- `api/app/services/vision_content_service.py`
- `api/app/routers/vision.py`
- `web/app/vision/realize/page.tsx`
- `docs/system_audit/commit_evidence_2026-04-24_presence-perspectives.json`
- `docs/system_audit/model_executor_runs.jsonl`

## Acceptance Tests

- `api/tests/test_vision_content.py::test_vision_realize_reads_scoped_graph_nodes`
- `api/tests/test_vision_content.py::test_vision_realize_filters_domain_and_source_page`

## Verification

```bash
cd api && .venv/bin/pytest -q tests/test_vision_content.py
cd web && npm run build
```

## Out of Scope

- Migrating every long narrative paragraph on `/vision/realize`.
- Adding a content editor.
- Seeding production realize records.

## Risks and Assumptions

- Empty databases will render explicit empty states until graph records are published.
- Page-level layout and Tailwind presentation classes remain in code because they are view behavior, not content data.

## Known Gaps

- Follow-up task: migrate the remaining repeatable and narrative `/vision/realize` groups through dedicated graph-backed content shapes.
