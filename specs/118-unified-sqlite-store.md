# Spec 118: Unified SQLite Store — Single Source of Truth

**Idea**: `unified-persistence` (sub-idea of `coherence-signal-depth`)
**Depends on**: All existing persistence services

## Status: In Progress

## Problem

The system has 4 separate SQLite databases and 5 JSON file stores, each with
their own engine, session management, env vars, and caching. This creates:

- **Double-sourcing**: Some data exists in both JSON and DB with sync logic
- **Configuration sprawl**: 10+ env vars for different DB paths
- **No joins**: Can't query across ideas + specs + lineage in one query
- **Inconsistent patterns**: Some services use DB, others JSON, others both
- **Complex test setup**: Each test needs to mock/configure multiple stores

## Design

### Single database: `coherence.db`

One SQLite file, one engine, one session pool. All services import from
`app.services.unified_db` instead of managing their own connections.

```
api/logs/coherence.db
  ├── idea_registry_ideas
  ├── idea_registry_questions
  ├── idea_registry_meta
  ├── spec_registry_entries
  ├── governance_change_requests
  ├── governance_change_request_votes
  ├── commit_evidence_records
  ├── automation_usage_snapshots
  ├── friction_events
  ├── external_tool_usage_events
  ├── task_metrics
  ├── telemetry_meta
  ├── value_lineage_links       (NEW — migrated from JSON)
  ├── value_lineage_events      (NEW — migrated from JSON)
  ├── prompt_ab_measurements    (NEW — migrated from JSON)
  ├── runtime_events            (existing schema)
  ├── agent_tasks               (existing schema)
  └── agent_runners             (existing schema)
```

### unified_db module

```python
# app/services/unified_db.py
def database_url() -> str:
    """Single source: COHERENCE_DATABASE_URL > DATABASE_URL > sqlite:///logs/coherence.db"""

def engine() -> Engine:
    """Shared engine, created once."""

def Session() -> sessionmaker:
    """Shared session factory."""

@contextmanager
def session() -> Generator[Session, None, None]:
    """Shared session context manager."""

def ensure_schema() -> None:
    """Create all tables if they don't exist."""
```

### Migration approach

Phase 1: Create unified_db module + wire existing SQLAlchemy services to it
Phase 2: Migrate JSON stores (value_lineage, prompt_ab_roi) to SQLAlchemy tables
Phase 3: Remove old DB modules and env vars

Each phase is independently deployable and backward compatible.

## Acceptance Criteria

1. All services use `unified_db.session()` for database access
2. Single `COHERENCE_DATABASE_URL` env var (or `DATABASE_URL`) controls all persistence
3. JSON file stores migrated to SQLAlchemy tables
4. Old per-service DB env vars still work as fallbacks during migration
5. Tests can configure one env var to use an isolated test DB
6. No data loss — existing data migrates cleanly

## Risks and Assumptions

- **Risk**: Migration could lose data if not careful. Mitigation: migration
  reads old stores and inserts into new tables, keeping old files as backup.
- **Risk**: SQLite concurrent write contention. Mitigation: WAL mode +
  short transactions (already the pattern in existing services).
- **Assumption**: Local SQLite is the primary development/CI store. Postgres
  is production-only and syncs from SQLite exports.

## Known Gaps and Follow-up Tasks

- [ ] Postgres sync mechanism (export SQLite → import Postgres)
- [ ] Schema migration tooling (alembic or manual versioning)
- [ ] Drop legacy env vars after transition period

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.

## Acceptance Tests

See `api/tests/test_unified_sqlite_store.py` for test cases covering this spec's requirements.




## Verification

```bash
python3 -m pytest api/tests/test_schema_init_fastpath.py -x -v
```
