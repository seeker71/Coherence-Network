# Spec 181: Idea Dual Identity — UUID Primary Key + Structured Human Slug

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

---

## Why This Matters

### Before (single slug ID)

```
POST /api/ideas  { "id": "cc-minting", "name": "CC Minting" }
PATCH /api/ideas/cc-minting  { "parent_idea_id": "treasury-phase-1" }
```

- Renaming `cc-minting` → `treasury/cc-minting` breaks every foreign key pointing to it.
- The runner embeds the slug in `direction` text and spec file globs — wrong idea gets
  picked up when slugs partially match (`cc-minting` matches `cc-minting-testnet`).
- Ideas cannot be addressed by a stable key across federation/import/export.

### After (UUID + slug)

```
POST /api/ideas  { "name": "CC Minting" }
# Returns: { "id": "3fa06e6c-...", "slug": "cc-minting", "name": "CC Minting" }

PATCH /api/ideas/3fa06e6c-.../slug  { "slug": "treasury/cc-minting" }
# All FKs still resolve via id — nothing breaks.
# GET /api/ideas/treasury/cc-minting still works via slug index.
```

---

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

---

## API Changes

### Route resolution

All idea endpoints that currently take `{idea_id}` accept **either UUID4 or slug**:

```
GET  /api/ideas/{id_or_slug}
PATCH /api/ideas/{id_or_slug}
DELETE /api/ideas/{id_or_slug}
```

Resolution order:
1. If `id_or_slug` matches UUID4 pattern → look up by `id`.
2. Otherwise → look up by current slug; if not found, check `slug_history`.
3. If still not found → 404.

### New slug management endpoint

```
PATCH /api/ideas/{id_or_slug}/slug
Body: { "slug": "finance/cc-minting" }
Returns: { "id": "...", "slug": "finance/cc-minting", "slug_history": ["cc-minting"] }
```

Constraints:
- New slug must not already be the current slug of another idea.
- Old slug is appended to `slug_history` (never deleted — permanent redirect).
- `last_activity_at` updated.

### `GET /api/ideas` response

Each idea now includes `slug` alongside `id`.

---

## Storage

### Neo4j

- `slug` stored as node property, indexed: `CREATE INDEX idea_slug IF NOT EXISTS FOR (i:Idea) ON (i.slug)`
- `slug_history` stored as JSON array string property.
- `id` remains the node's primary identifier in `graph_service.get_node(id)`.

### PostgreSQL (idea_registry)

- `slug VARCHAR(100) UNIQUE NOT NULL` column added.
- `slug_history TEXT` column (JSON array).
- Migration: backfill `slug` from existing `id` for all rows.

---

## Migration Strategy

### Phase 1 — Backfill (non-breaking)

A one-shot migration script:

```python
for idea in all_ideas:
    slug = idea.id                    # existing slug ID becomes the slug
    uuid = str(uuid4())               # new stable machine ID
    # Write: id=uuid, slug=slug, update all FKs that pointed to old id
```

Foreign key fields to rewrite:
- `Idea.parent_idea_id`
- `Idea.child_idea_ids[]`
- `Idea.duplicate_of`
- `SpecRegistryEntry.idea_id`
- Task `extra_context["idea_id"]`
- Runner `_EVENTS_DIR` filenames

### Phase 2 — Slug enrichment

After migration, slugs can be renamed to add namespace prefixes without
touching any machine identifiers. This is safe because all FKs use UUID4.

### Backward compat during migration

- The resolver checks `slug_history` — any old URL or FK pointing to the
  slug-as-ID continues to resolve correctly for the lifetime of the data.
- The runner always writes `idea_id` (UUID) into task context at task creation;
  any task already in flight resolves via the slug history path.

---

## Verification

1. `POST /api/ideas` with no `id` and no `slug` → response has UUID4 `id` and
   a slug derived from `name`.
2. `GET /api/ideas/{slug}` resolves the same idea as `GET /api/ideas/{uuid}`.
3. `PATCH /api/ideas/{id}/slug { "slug": "new-slug" }` → old slug resolves
   via history (301-style lookup), new slug resolves directly.
4. Rename does not break any FK: parent/child relationships still resolve.
5. All existing `test_ideas.py` tests pass without modification.
6. `cc idea triage` lists ideas with both UUID and slug visible.

---

## Risks and Assumptions

- **Slug collision on backfill**: existing IDs that are identical except for
  prefix (e.g. two ideas both mapping to `backlog`) must be disambiguated with
  `-2` suffix. The migration script must detect and resolve these.
- **Runner task context**: tasks in flight at migration time carry old slug IDs.
  The resolver's history lookup handles this transparently.
- **Neo4j node identity**: `graph_service` currently uses the `id` field as the
  graph node key. After migration, node keys become UUID4s. Any hardcoded
  `"idea-{slug}"` node ID patterns in `idea_graph_adapter.py` must be updated.
- **Federation**: remote nodes receiving ideas over the federation protocol must
  preserve the UUID `id`, not re-generate it. The slug may be re-namespaced
  locally.

---

## Known Gaps and Follow-up Tasks

- **Slug search**: `GET /api/ideas?slug_prefix=finance/` — filtered listing by namespace.
- **Slug autocomplete** in CLI: `cc idea <TAB>` resolves slugs.
- **Structured slug enforcement**: optional future constraint that all slugs
  under a pillar super-idea share its namespace prefix.
- **Slug registry**: a dedicated `GET /api/ideas/slugs` catalog endpoint for
  tooling (runner spec-file lookup, CLI autocomplete).
