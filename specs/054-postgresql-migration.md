# Spec: PostgreSQL Migration for In-Memory Stores

## Purpose

Migrate in-memory data stores (GraphStore and AgentTask storage) to PostgreSQL for production scalability, data persistence, and multi-instance support. Enable zero-downtime migration via dual-write and gradual read switchover.

## Requirements

### Database Schema

- [ ] PostgreSQL schemas defined for all in-memory stores
  - [ ] Projects table with (ecosystem, name) unique constraint
  - [ ] Project dependencies table (graph edges) with foreign keys
  - [ ] Contributors table with UUID primary keys
  - [ ] Assets table with UUID primary keys
  - [ ] Contributions table with foreign keys to contributors and assets
  - [ ] Agent tasks table with ENUM types for task_type and status
- [ ] Indexes for performance
  - [ ] Composite index on (ecosystem, name) for projects
  - [ ] Full-text search indexes (trigram) for project search
  - [ ] Index on (status, created_at) for agent task queries
  - [ ] Index on (contributor_id) and (asset_id) for contributions
- [ ] Database triggers
  - [ ] Auto-update asset.total_cost when contribution inserted
  - [ ] Auto-update updated_at timestamps
- [ ] Constraints
  - [ ] CHECK constraints for coherence_score (0.0–1.0)
  - [ ] CHECK constraints for progress_pct (0–100)
  - [ ] UNIQUE constraints on composite keys
  - [ ] Foreign key constraints with CASCADE deletes where appropriate

### Adapter Implementations

- [ ] PostgresGraphStore adapter implementing GraphStore protocol
  - [ ] get_project, upsert_project, search, count_projects
  - [ ] add_dependency, count_dependents
  - [ ] create_contributor, get_contributor, list_contributors
  - [ ] create_asset, get_asset, list_assets
  - [ ] create_contribution, get_contribution
  - [ ] get_asset_contributions, get_contributor_contributions
- [ ] PostgresAgentTaskStore adapter implementing AgentTaskStore protocol
  - [ ] create_task, get_task, list_tasks
  - [ ] update_task (with status transitions)
  - [ ] get_attention_tasks, get_task_count
  - [ ] get_review_summary, get_usage_summary
  - [ ] get_pipeline_status
- [ ] Connection pooling with asyncpg
  - [ ] Pool configuration via environment variables
  - [ ] Min/max pool size, max queries, connection lifetime
  - [ ] Health check queries
- [ ] Transaction support
  - [ ] All write operations in transactions
  - [ ] Rollback on error
  - [ ] Atomic multi-table operations

### Migration Path

- [ ] **Phase 1: Dual-Write Mode**
  - [ ] Environment variable: `DUAL_WRITE_MODE=true`
  - [ ] All writes go to both in-memory and PostgreSQL
  - [ ] All reads from in-memory (trusted source)
  - [ ] Log PostgreSQL write failures but don't fail request
  - [ ] Background job to verify data consistency
- [ ] **Phase 2: Read Migration**
  - [ ] Environment variable: `READ_FROM_POSTGRES_PERCENT=0-100`
  - [ ] Gradually shift read traffic to PostgreSQL
  - [ ] Start at 10%, increase by 10% every 24 hours if no errors
  - [ ] Monitor query performance (p50, p95, p99 latency)
  - [ ] Rollback to 0% if error rate > 1%
- [ ] **Phase 3: PostgreSQL as Primary**
  - [ ] Set `READ_FROM_POSTGRES_PERCENT=100`
  - [ ] Disable in-memory writes (keep for emergency rollback)
  - [ ] Monitor for 48 hours before cleanup
  - [ ] Final JSON snapshot of in-memory data
- [ ] **Phase 4: Cleanup**
  - [ ] Remove in-memory store implementations
  - [ ] Remove dual-write logic
  - [ ] Remove feature flags
  - [ ] Archive final in-memory snapshot to S3/backup

### Rollback Strategy

- [ ] Phase 1 rollback: Set `DUAL_WRITE_MODE=false`, continue in-memory only
- [ ] Phase 2 rollback: Set `READ_FROM_POSTGRES_PERCENT=0`, reads from in-memory
- [ ] Phase 3 rollback: Re-enable in-memory writes, restore from JSON snapshot
- [ ] Automated rollback script: `scripts/rollback_postgres_migration.py`
- [ ] Manual rollback runbook in docs/POSTGRESQL-MIGRATION.md

### Observability

- [ ] Metrics
  - [ ] PostgreSQL query latency (p50, p95, p99)
  - [ ] Connection pool utilization (active, idle, waiting)
  - [ ] Failed query rate
  - [ ] Dual-write consistency check results
  - [ ] Read switchover percentage actual vs. configured
- [ ] Alerts
  - [ ] Query latency > 500ms (p95)
  - [ ] Failed queries > 1% of total
  - [ ] Connection pool exhausted
  - [ ] Dual-write consistency failures
  - [ ] Replication lag > 10 seconds (if using replicas)
- [ ] Health checks
  - [ ] GET /api/ready includes PostgreSQL connection check
  - [ ] Timeout: 5 seconds
  - [ ] Returns 503 if PostgreSQL unavailable

### Configuration

- [ ] Environment variables
  - [ ] `DATABASE_URL` — PostgreSQL connection string
  - [ ] `DUAL_WRITE_MODE` — Enable dual-write (default: false)
  - [ ] `READ_FROM_POSTGRES_PERCENT` — Read traffic percentage (0-100, default: 0)
  - [ ] `POSTGRES_POOL_SIZE` — Connection pool size (default: 20)
  - [ ] `POSTGRES_MAX_OVERFLOW` — Max additional connections (default: 10)
  - [ ] `POSTGRES_POOL_TIMEOUT` — Connection acquisition timeout (default: 30s)
  - [ ] `POSTGRES_POOL_RECYCLE` — Connection recycle time (default: 3600s)
- [ ] Startup validation
  - [ ] Verify DATABASE_URL is set when DUAL_WRITE_MODE=true
  - [ ] Verify PostgreSQL connection on startup
  - [ ] Fail fast if schema version mismatch

### Data Consistency

- [ ] Consistency verification script: `scripts/verify_data_consistency.py`
  - [ ] Sample 10% of records from in-memory store
  - [ ] Compare with PostgreSQL records
  - [ ] Report mismatches (missing, different values)
  - [ ] Run daily during dual-write phase
- [ ] Consistency alerts
  - [ ] Alert if > 1% of sampled records are inconsistent
  - [ ] Alert if verification job fails to run
- [ ] Backfill script: `scripts/backfill_postgres.py`
  - [ ] Copy all in-memory data to PostgreSQL
  - [ ] Run before enabling dual-write mode
  - [ ] Idempotent (safe to run multiple times)

## API Contract

No new API endpoints. Existing endpoints continue to work unchanged.

### Configuration Endpoints

#### `GET /api/agent/store-status`

**Purpose**: Show which store backend is active for reads/writes

**Response 200**
```json
{
  "graph_store": {
    "write_target": "dual",
    "read_target": "postgres",
    "read_from_postgres_percent": 100,
    "dual_write_enabled": true
  },
  "agent_task_store": {
    "write_target": "dual",
    "read_target": "in-memory",
    "read_from_postgres_percent": 50,
    "dual_write_enabled": true
  },
  "postgres": {
    "connected": true,
    "pool_size": 20,
    "pool_active": 5,
    "pool_idle": 15
  }
}
```

## Data Model

### Projects Table

```python
class Project(BaseModel):
    id: int
    ecosystem: str  # lowercase, max 100 chars
    name: str  # lowercase, max 255 chars
    description: Optional[str] = None
    homepage_url: Optional[str] = None
    repository_url: Optional[str] = None
    dependency_count: int = 0
    created_at: datetime
    updated_at: datetime
```

### Contributors Table

```python
class Contributor(BaseModel):
    id: UUID
    name: str  # max 255 chars
    email: Optional[str] = None
    github_username: Optional[str] = None
    wallet_address: Optional[str] = None
    metadata: dict = {}
    created_at: datetime
    updated_at: datetime
```

### Assets Table

```python
class Asset(BaseModel):
    id: UUID
    name: str  # max 255 chars
    description: Optional[str] = None
    asset_type: str  # max 50 chars
    total_cost: Decimal = Decimal("0.00")
    metadata: dict = {}
    created_at: datetime
    updated_at: datetime
```

### Contributions Table

```python
class Contribution(BaseModel):
    id: UUID
    contributor_id: UUID
    asset_id: UUID
    cost_amount: Decimal  # >= 0
    coherence_score: float  # 0.0 to 1.0
    metadata: dict = {}
    timestamp: datetime
```

### Agent Tasks Table

```python
class AgentTask(BaseModel):
    id: str  # task_abc123 format
    direction: str  # 1-5000 chars
    task_type: TaskType  # ENUM
    status: TaskStatus  # ENUM
    model: str  # max 100 chars
    command: str
    output: Optional[str] = None
    context: dict = {}
    progress_pct: Optional[int] = None  # 0-100
    current_step: Optional[str] = None
    decision_prompt: Optional[str] = None
    decision: Optional[str] = None
    tier: Optional[str] = None
    started_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
```

## Files to Create/Modify

### New Files

- [ ] `api/app/adapters/postgres_graph_store.py` — PostgresGraphStore implementation
- [ ] `api/app/adapters/postgres_agent_task_store.py` — PostgresAgentTaskStore implementation
- [ ] `api/migrations/001_initial_schema.sql` — SQL schema for all tables
- [ ] `api/migrations/002_indexes.sql` — Performance indexes
- [ ] `api/migrations/003_triggers.sql` — Database triggers
- [ ] `api/scripts/verify_data_consistency.py` — Consistency checker
- [ ] `api/scripts/backfill_postgres.py` — One-time migration script
- [ ] `api/scripts/rollback_postgres_migration.py` — Automated rollback
- [ ] `docs/POSTGRESQL-MIGRATION.md` — Migration runbook
- [ ] `specs/054-postgresql-migration.md` — This spec

### Modified Files

- [ ] `api/app/adapters/graph_store.py` — Add dual-write wrapper
- [ ] `api/app/services/agent_service.py` — Add dual-write wrapper
- [ ] `api/app/main.py` — Initialize PostgreSQL pool on startup
- [ ] `api/app/routers/agent.py` — Add GET /api/agent/store-status endpoint
- [ ] `api/app/routers/health.py` — Add PostgreSQL check to /api/ready
- [ ] `api/pyproject.toml` — Add asyncpg, psycopg2-binary dependencies
- [ ] `api/requirements.txt` — Update lockfile
- [ ] `docs/SETUP.md` — Document PostgreSQL setup steps
- [ ] `docs/RUNBOOK.md` — Add PostgreSQL troubleshooting section
- [ ] `.env.example` — Add DATABASE_URL and migration config examples

## Testing Requirements

- [ ] Unit tests
  - [ ] `tests/test_postgres_graph_store.py` — All GraphStore operations
  - [ ] `tests/test_postgres_agent_task_store.py` — All AgentTaskStore operations
  - [ ] Test constraint violations (unique, foreign key, check)
  - [ ] Test transaction rollback scenarios
  - [ ] Test connection pool exhaustion handling
- [ ] Integration tests
  - [ ] `tests/test_dual_write_mode.py` — Dual-write consistency
  - [ ] `tests/test_read_switchover.py` — Gradual read migration
  - [ ] `tests/test_rollback.py` — Rollback procedures
- [ ] Performance tests
  - [ ] Benchmark GraphStore operations (in-memory vs PostgreSQL)
  - [ ] Benchmark AgentTaskStore operations
  - [ ] Load test: 1000 req/sec sustained for 10 minutes
  - [ ] Bulk insert: 10k projects in < 10 seconds
- [ ] End-to-end tests
  - [ ] Full migration path: dual-write → read-switch → primary
  - [ ] Rollback from each phase
  - [ ] Data consistency after full migration

## Dependencies

- **asyncpg** >= 0.29.0 — PostgreSQL async driver
- **psycopg2-binary** >= 2.9.0 — PostgreSQL sync driver (for scripts)
- **alembic** >= 1.13.0 — Database migrations (optional, for versioning)

## Migration Timeline

| Phase | Duration | Activities |
|-------|----------|----------|
| Phase 0: Preparation | 1 week | Schema design, adapter implementation, tests |
| Phase 1: Dual-Write | 2 weeks | Enable dual-write, verify consistency daily |
| Phase 2: Read Migration | 2 weeks | Gradual switchover 0% → 100%, monitor performance |
| Phase 3: PostgreSQL Primary | 1 week | Final cutover, monitor, disable in-memory writes |
| Phase 4: Cleanup | 1 week | Remove in-memory code, archive snapshot, update docs |

**Total**: 7 weeks

## Rollback Windows

- **Phase 1**: Instant rollback (disable dual-write)
- **Phase 2**: < 5 minutes (set READ_FROM_POSTGRES_PERCENT=0)
- **Phase 3**: < 30 minutes (re-enable in-memory writes, restore snapshot)
- **Phase 4**: No rollback (in-memory code removed; requires code revert + data restore)

## Success Criteria

- [ ] All API endpoints continue to work unchanged
- [ ] Query latency (p95) < 100ms for all operations
- [ ] Zero data loss during migration
- [ ] < 1% error rate during dual-write phase
- [ ] Successful rollback drill from each phase
- [ ] Documentation complete and validated
- [ ] Load tests pass at 2x expected production load

## Security Requirements

- [ ] Database credentials never logged or exposed in errors
- [ ] Use environment variables for all secrets
- [ ] Require SSL/TLS for production PostgreSQL connections
- [ ] Use least-privilege database user (no DROP, TRUNCATE in production)
- [ ] Parameterized queries only (no string concatenation)
- [ ] Audit log for all schema changes
- [ ] Daily automated backups with 30-day retention

## References

- [asyncpg documentation](https://magicstack.github.io/asyncpg/)
- [PostgreSQL best practices](https://wiki.postgresql.org/wiki/Don%27t_Do_This)
- [FastAPI with databases](https://fastapi.tiangolo.com/advanced/async-sql-databases/)
- See detailed implementation plan: `docs/POSTGRESQL-MIGRATION.md`
