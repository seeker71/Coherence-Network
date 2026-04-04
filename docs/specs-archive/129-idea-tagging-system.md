# Spec 129: Idea Tagging System

## Purpose

The idea portfolio already supports prioritization, hierarchy, and execution state, but it does not have a first-class tagging contract for grouping related ideas across domains, execution surfaces, and portfolio themes. This spec adds a normalized idea tagging system so contributors, operators, and automation can filter, discover, and route ideas consistently without overloading free-text descriptions or inventing incompatible ad hoc labels.

## Requirements

- [ ] Ideas support a first-class `tags: list[str]` field that is returned by `GET /api/ideas`, `GET /api/ideas/{idea_id}`, and `POST /api/ideas`.
- [ ] Tag values are normalized at write time to lowercase slug format, deduplicated case-insensitively, trimmed, and stored in stable sorted order.
- [ ] The ideas list API supports filtering by one or more tags without breaking existing ranking, pagination, or `include_internal` behavior.
- [ ] The system exposes a tag catalog endpoint with counts so web and automation clients can populate faceted filters without scanning the full portfolio.
- [ ] Tag mutations use a dedicated endpoint and do not expand the existing Spec 053 `PATCH /api/ideas/{idea_id}` contract beyond validation fields.
- [ ] Tags persist through the existing unified idea registry store and remain backward compatible for ideas that have no tags.

## Research Inputs

- `2026-03-21` - [specs/053-ideas-prioritization.md](./053-ideas-prioritization.md) - establishes the current ideas API, persistence expectations, and patch-contract boundary that this spec must preserve.
- `2026-03-21` - [specs/117-idea-hierarchy-super-child.md](./117-idea-hierarchy-super-child.md) - shows that ideas already carry portfolio structure beyond simple scoring, which tagging should complement rather than replace.
- `2026-03-21` - [api/app/models/idea.py](../api/app/models/idea.py) - defines the current idea model and confirms there is no first-class tag field yet.
- `2026-03-21` - [api/app/routers/ideas.py](../api/app/routers/ideas.py) - shows the current route surface and confirms a dedicated tag mutation endpoint is the cleanest extension point.

## Task Card

```yaml
goal: Add a normalized, persistent tagging system for ideas with filtering and tag catalog APIs.
files_allowed:
  - api/app/models/idea.py
  - api/app/routers/ideas.py
  - api/app/services/idea_service.py
  - api/app/services/idea_registry_service.py
  - api/tests/test_idea_tags.py
  - specs/129-idea-tagging-system.md
done_when:
  - idea create/get/list responses include normalized tags
  - tag filters and tag catalog endpoint return stable, test-covered results
  - spec quality validation passes for this spec
commands:
  - python3 scripts/validate_spec_quality.py --file specs/129-idea-tagging-system.md
  - cd api && pytest -q tests/test_idea_tags.py
constraints:
  - do not change the existing Spec 053 PATCH contract for generic idea updates
  - no web UI changes in this task
  - no schema migrations outside the unified idea registry path listed above
```

## API Contract

### `GET /api/ideas`

**New query params**
- `tags`: comma-separated tag filter. When present, return ideas that match all normalized requested tags.

**Response 200**
```json
{
  "ideas": [
    {
      "id": "idea-tagging-system",
      "name": "Idea tagging system",
      "description": "Add normalized tags for filtering and discovery.",
      "tags": ["governance", "ideas", "search"],
      "free_energy_score": 4.2,
      "value_gap": 55.0
    }
  ],
  "summary": {
    "total_ideas": 1,
    "unvalidated_ideas": 1,
    "validated_ideas": 0,
    "total_potential_value": 80.0,
    "total_actual_value": 25.0,
    "total_value_gap": 55.0
  },
  "pagination": {
    "total": 1,
    "limit": 200,
    "offset": 0,
    "returned": 1,
    "has_more": false
  }
}
```

### `GET /api/ideas/tags`

**Purpose**
- Return the normalized idea tag catalog with counts for filter UIs and automation.

**Response 200**
```json
{
  "tags": [
    { "tag": "governance", "idea_count": 7 },
    { "tag": "ideas", "idea_count": 5 },
    { "tag": "search", "idea_count": 2 }
  ]
}
```

### `PUT /api/ideas/{idea_id}/tags`

**Request**
```json
{
  "tags": ["Ideas", "search", "  governance  ", "ideas"]
}
```

**Behavior**
- Replace the full tag set for the idea after normalization.
- Unknown idea id returns `404`.
- Empty tag arrays are valid and clear all tags.
- Invalid tag values return `422`.

**Response 200**
```json
{
  "id": "idea-tagging-system",
  "tags": ["governance", "ideas", "search"]
}
```

### `POST /api/ideas`

**Extension**
- Accept optional `tags` in the create payload.
- Omitted `tags` defaults to `[]`.

## Data Model

```yaml
Idea:
  properties:
    id: { type: string }
    name: { type: string }
    description: { type: string }
    tags:
      type: list[str]
      default: []
      normalization:
        - trim whitespace
        - lowercase
        - replace internal whitespace with "-"
        - allow only "a-z", "0-9", and "-"
        - deduplicate
        - sort ascending

IdeaTagCatalogEntry:
  properties:
    tag: { type: string }
    idea_count: { type: integer, minimum: 1 }
```

Implementation note: persist tags in the unified idea registry record so reads, discovery, and restart behavior remain consistent with the existing idea source of truth.

## Files to Create/Modify

- `api/app/models/idea.py` - add tag fields and tag-update request/response models.
- `api/app/routers/ideas.py` - add tag filter parsing, tag catalog route, and dedicated tag mutation route.
- `api/app/services/idea_service.py` - normalize, persist, filter, and aggregate tag catalog data.
- `api/app/services/idea_registry_service.py` - store/retrieve tags in the unified idea registry backend.
- `api/tests/test_idea_tags.py` - cover normalization, filtering, persistence, and catalog behavior.
- `specs/129-idea-tagging-system.md` - feature spec and acceptance contract.

## Acceptance Tests

- `api/tests/test_idea_tags.py::test_create_idea_normalizes_and_returns_tags`
- `api/tests/test_idea_tags.py::test_list_ideas_filters_by_all_requested_tags`
- `api/tests/test_idea_tags.py::test_put_idea_tags_replaces_existing_tags`
- `api/tests/test_idea_tags.py::test_get_idea_tags_catalog_returns_counts`
- Manual validation: `GET /api/ideas?tags=ideas,search` returns only ideas carrying both normalized tags.

## Concurrency Behavior

- **Read operations**: Tag filtering and tag catalog reads are safe for concurrent access.
- **Write operations**: `PUT /api/ideas/{idea_id}/tags` is full-replacement, last-write-wins, matching current registry update semantics.
- **Recommendation**: Clients should send the complete intended tag set and not assume optimistic merge behavior.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/129-idea-tagging-system.md
cd api && pytest -q tests/test_idea_tags.py
```

Manual verification after implementation:

```bash
curl -s http://localhost:8000/api/ideas?tags=ideas,search
curl -s http://localhost:8000/api/ideas/tags
```

Expected result: responses include normalized tags, filtered idea lists, and stable catalog counts.

## Out of Scope

- Tag synonyms, aliases, or hierarchical tag trees.
- Full-text search redesign or semantic tagging.
- Web faceted-filter UI implementation.
- Automated tag suggestion from runtime evidence or LLM classification.

## Risks and Assumptions

- Risk: uncontrolled free-form tags could create noisy duplicates and weak filtering value.
- Risk: list filtering could become inconsistent if normalization happens in some write paths but not others.
- Assumption: the unified idea registry can store tags without a separate migration framework beyond its existing persistence path.
- Assumption: exact-match filtering is sufficient for the first release; clients do not need alias expansion yet.

## Known Gaps and Follow-up Tasks

- Follow-up task: add tag facets to the web ideas inventory once the API contract is stable.
- Follow-up task: evaluate whether internal/system-generated tags should be hidden when `include_internal=false`.
- Follow-up task: define governance rules for approved portfolio tags if the free-form catalog becomes noisy.

## Failure/Retry Reflection

- Failure mode: tags are accepted but not normalized consistently across create and update flows.
- Blind spot: implementing normalization only in the router instead of the service/storage boundary.
- Next action: centralize normalization in `idea_service` and re-run `api/tests/test_idea_tags.py`.

## Decision Gates

- No human decision gate required for MVP if the implementation stays API-only and preserves Spec 053 patch behavior.
