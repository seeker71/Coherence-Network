---
idea_id: idea-realization-engine
status: done
source:
  - file: api/app/services/idea_service.py
    symbols: [slugify(), update_idea_slug()]
  - file: api/app/models/idea.py
    symbols: [Idea.slug, Idea.slug_history]
requirements:
  - Idea has UUID4 id (immutable) and slug (mutable, unique, URL-safe)
  - Slug auto-derived from name at creation when omitted
  - Slug max 80 chars, lowercase, diacritics stripped, deduped with -2 suffix
  - GET /api/ideas/{slug} resolves same idea as GET /api/ideas/{uuid}
  - PATCH /api/ideas/{id}/slug renames slug and keeps old slug in history
  - Old slugs resolve via slug_history lookup
  - Rename does not break parent/child foreign key relationships
done_when:
  - POST /api/ideas with no slug returns derived slug from name
  - Old slug resolves after rename via history
  - All existing test_ideas.py tests pass without modification
---

> **Parent idea**: [idea-realization-engine](../ideas/idea-realization-engine.md)
> **Source**: [`api/app/services/idea_service.py`](../api/app/services/idea_service.py) | [`api/app/models/idea.py`](../api/app/models/idea.py)

# Idea Dual Identity — UUID Primary Key + Structured Human Slug

## Purpose

Ideas currently use a single `id` field that serves two incompatible roles: machine primary
key and human-readable label. Slugs like `006-overnight-backlog` are opaque to machines (no
collision guarantee, hard to generate, impossible to rename without breaking every foreign
key) and structured for humans only by convention. The system has grown to 306 ideas and the
slug namespace is already colliding — three ideas share the `169-` prefix in specs.

This spec introduces a clean separation:

- **`id`**: UUID4, immutable, generated at creation, all foreign keys reference this.
- **`slug`**: human-readable, URL-safe, mutable, unique across the portfolio, may be
  structured as `pillar/concept` or `pillar/domain/concept` as the taxonomy matures.
- **`name`**: free-form display string, no uniqueness constraint.

The UUID auto-generation shipped in the previous step (PR #786) was the necessary
prerequisite: it proved the API can generate stable machine identifiers without human
input, which is the foundation this full dual-identity system builds on.

## Data Model Changes

### `Idea` model additions

```python
slug: str = Field(
    description="URL-safe human identifier. Unique. May be namespaced: 'pillar/concept'.",
)
slug_history: list[str] = Field(
    default_factory=list,
    description="Previous slugs — kept so old URLs/links continue to resolve.",
)
```

### `IdeaCreate` changes

- `id` remains `Optional[str]` (UUID4 auto-generated — already shipped).
- `slug` is `Optional[str]`: if omitted, derived from `name` at creation time.

### Slug derivation rules (applied at write time)

1. Lowercase, strip diacritics.
2. Replace spaces and special chars with `-`.
3. Collapse consecutive `-` to one.
4. Strip leading/trailing `-`.
5. Max 80 characters total (including namespace prefix and `/` separators).
6. If derived slug already exists: append `-2`, `-3`, etc.

### Slug namespace convention (guidelines, not enforced by API)

| Maturity | Example |
|---|---|
| Flat (now) | `cc-minting` |
| Pillar-prefixed | `finance/cc-minting` |
| Fully hierarchical | `finance/treasury/cc-minting` |

The API accepts any namespace depth. Clients and the CLI display the full slug.

## Storage

### Neo4j

- `slug` stored as node property, indexed: `CREATE INDEX idea_slug IF NOT EXISTS FOR (i:Idea) ON (i.slug)`
- `slug_history` stored as JSON array string property.
- `id` remains the node's primary identifier in `graph_service.get_node(id)`.

### PostgreSQL (idea_registry)

- `slug VARCHAR(100) UNIQUE NOT NULL` column added.
- `slug_history TEXT` column (JSON array).
- Migration: backfill `slug` from existing `id` for all rows.

## Verification

1. `POST /api/ideas` with no `id` and no `slug` → response has UUID4 `id` and
   a slug derived from `name`.
2. `GET /api/ideas/{slug}` resolves the same idea as `GET /api/ideas/{uuid}`.
3. `PATCH /api/ideas/{id}/slug { "slug": "new-slug" }` → old slug resolves
   via history (301-style lookup), new slug resolves directly.
4. Rename does not break any FK: parent/child relationships still resolve.
5. All existing `test_ideas.py` tests pass without modification.
6. `cc idea triage` lists ideas with both UUID and slug visible.

## Known Gaps and Follow-up Tasks

- **Slug search**: `GET /api/ideas?slug_prefix=finance/` — filtered listing by namespace.
- **Slug autocomplete** in CLI: `cc idea <TAB>` resolves slugs.
- **Structured slug enforcement**: optional future constraint that all slugs
  under a pillar super-idea share its namespace prefix.
- **Slug registry**: a dedicated `GET /api/ideas/slugs` catalog endpoint for
  tooling (runner spec-file lookup, CLI autocomplete).
