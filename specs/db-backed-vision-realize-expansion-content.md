---
idea_id: db-backed-vision-realize-expansion-content
status: done
source:
  - file: api/app/services/vision_content_service.py
    symbols: [get_realize_content()]
  - file: web/app/vision/realize/page.tsx
    symbols: [RealizePage]
requirements:
  - "GET /api/vision/{domain}/realize includes remaining repeatable /vision/realize card/list groups from graph nodes."
  - "/vision/realize renders fastest opportunities, shell transformations, seasons, abundance flows, existing structures, and seeds from the API payload."
  - "The page must not fall back to embedded arrays for those groups when graph records are absent."
done_when:
  - "cd api && .venv/bin/pytest -q tests/test_vision_content.py"
  - "cd web && npm run build"
constraints:
  - "Do not move presentation-only Tailwind classes into the DB."
  - "Do not add hardcoded realize-page catalogs to application code."
  - "Use existing graph_nodes storage as the DB-backed source."
---

# Spec: DB-Backed Vision Realize Expansion Content

## Purpose

The first `/vision/realize` DB slice moved the core invitation groups out of React arrays. The page still embeds several repeatable card/list groups in JSX, which keeps the living-experience surface brittle and code-bound. This slice moves those remaining repeatable groups to graph-backed records.

## Requirements

- [x] **R1**: `GET /api/vision/{domain}/realize` returns graph-backed records grouped as `fastest_opportunities`, `shell_transformations`, `seasons`, `abundance_flows`, `existing_structures`, and `seeds`.
- [x] **R2**: Records are selected from graph nodes with `properties.source_page == "/vision/realize"` and `properties.realize_group` identifying their group.
- [x] **R3**: `/vision/realize` renders those groups from the API payload and uses empty states when a group has no records.

## API Contract

### `GET /api/vision/{domain}/realize`

**Response 200**
```json
{
  "fastest_opportunities": [],
  "shell_transformations": [],
  "seasons": [],
  "abundance_flows": [],
  "existing_structures": [],
  "seeds": [],
  "counts": {
    "fastest_opportunities": 0,
    "shell_transformations": 0,
    "seasons": 0,
    "abundance_flows": 0,
    "existing_structures": 0,
    "seeds": 0
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
    realize_group: fastest_opportunities | shell_transformations | seasons | abundance_flows | existing_structures | seeds
    sort_order: number
    title: string
    name: string
    body: string
```

## Files to Create/Modify

- `specs/db-backed-vision-realize-expansion-content.md`
- `api/tests/test_vision_content.py`
- `api/app/services/vision_content_service.py`
- `web/app/vision/realize/page.tsx`
- `docs/system_audit/commit_evidence_2026-04-24_presence-perspectives.json`
- `docs/system_audit/model_executor_runs.jsonl`

## Acceptance Tests

- `api/tests/test_vision_content.py::test_vision_realize_reads_expansion_graph_nodes`

## Verification

```bash
cd api && .venv/bin/pytest -q tests/test_vision_content.py
cd web && npm run build
```

## Out of Scope

- Moving the long narrative paragraphs for day, governance, arrival, children, and growth.
- Adding a content editor.
- Seeding production realize records.

## Risks and Assumptions

- Empty databases will render explicit empty states until graph records are published.
- Long-form narrative blocks need a separate shape from card/list groups to avoid forcing page prose into flat card records.

## Known Gaps

- Follow-up task: migrate the long-form `/vision/realize` narrative copy into ordered body-block graph records.
