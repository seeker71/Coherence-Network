# PostgreSQL Migration Plan

## Overview

This document outlines the migration path from in-memory stores to PostgreSQL for production scalability and data persistence. The current system uses two in-memory stores that need migration:

1. **GraphStore** — Projects, contributors, assets, contributions
2. **AgentTask Storage** — Task orchestration and tracking

## Current State

### InMemoryGraphStore
**Location**: `api/app/adapters/graph_store.py`

**Data Structures**:
- `_projects: dict[tuple[str, str], Project]` — keyed by (ecosystem, name)
- `_edges: list[tuple[tuple[str, str], tuple[str, str]]]` — dependency graph edges
- `_contributors: dict[UUID, Contributor]` — contributor records
- `_assets: dict[UUID, Asset]` — asset records
- `_contributions: dict[UUID, Contribution]` — contribution records

**Current Persistence**: Optional JSON file dump (not production-ready)

### Agent Task Store
**Location**: `api/app/services/agent_service.py`

**Data Structure**:
- `_store: dict[str, dict[str, Any]]` — keyed by task_id

**Current Persistence**: None (ephemeral, lost on restart)

## PostgreSQL Schema Design

### 1. Projects and Dependencies

```sql
-- Projects table
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    ecosystem VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    homepage_url VARCHAR(500),
    repository_url VARCHAR(500),
    dependency_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ecosystem, name),
    CHECK (ecosystem = LOWER(ecosystem)),
    CHECK (name = LOWER(name))
);

CREATE INDEX idx_projects_ecosystem ON projects(ecosystem);
CREATE INDEX idx_projects_name ON projects(name);
CREATE INDEX idx_projects_ecosystem_name ON projects(ecosystem, name);

-- Full-text search support
CREATE INDEX idx_projects_name_trgm ON projects USING gin(name gin_trgm_ops);
CREATE INDEX idx_projects_description_trgm ON projects USING gin(description gin_trgm_ops);

-- Dependencies table (graph edges)
CREATE TABLE project_dependencies (
    id SERIAL PRIMARY KEY,
    from_project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    to_project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(from_project_id, to_project_id),
    CHECK (from_project_id != to_project_id)
);

CREATE INDEX idx_dependencies_from ON project_dependencies(from_project_id);
CREATE INDEX idx_dependencies_to ON project_dependencies(to_project_id);
```

### 2. Contributors

```sql
CREATE TABLE contributors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    github_username VARCHAR(255),
    wallet_address VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_contributors_github ON contributors(github_username);
CREATE INDEX idx_contributors_email ON contributors(email);
CREATE INDEX idx_contributors_created ON contributors(created_at DESC);
```

### 3. Assets

```sql
CREATE TABLE assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    asset_type VARCHAR(50) NOT NULL,
    total_cost DECIMAL(15, 2) DEFAULT 0.00,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_assets_type ON assets(asset_type);
CREATE INDEX idx_assets_created ON assets(created_at DESC);
CREATE INDEX idx_assets_total_cost ON assets(total_cost DESC);
```

### 4. Contributions

```sql
CREATE TABLE contributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contributor_id UUID NOT NULL REFERENCES contributors(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    cost_amount DECIMAL(15, 2) NOT NULL CHECK (cost_amount >= 0),
    coherence_score DECIMAL(3, 2) NOT NULL CHECK (coherence_score >= 0 AND coherence_score <= 1),
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_contributions_contributor ON contributions(contributor_id);
CREATE INDEX idx_contributions_asset ON contributions(asset_id);
CREATE INDEX idx_contributions_timestamp ON contributions(timestamp DESC);
CREATE INDEX idx_contributions_coherence ON contributions(coherence_score DESC);

-- Trigger to update asset.total_cost when contribution is inserted
CREATE OR REPLACE FUNCTION update_asset_total_cost()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE assets
    SET total_cost = total_cost + NEW.cost_amount,
        updated_at = NOW()
    WHERE id = NEW.asset_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER contribution_update_asset_cost
AFTER INSERT ON contributions
FOR EACH ROW
EXECUTE FUNCTION update_asset_total_cost();
```

### 5. Agent Tasks

```sql
CREATE TYPE task_type AS ENUM ('spec', 'test', 'impl', 'review', 'heal');
CREATE TYPE task_status AS ENUM ('pending', 'running', 'completed', 'failed', 'needs_decision');

CREATE TABLE agent_tasks (
    id VARCHAR(50) PRIMARY KEY,
    direction TEXT NOT NULL,
    task_type task_type NOT NULL,
    status task_status NOT NULL DEFAULT 'pending',
    model VARCHAR(100) NOT NULL,
    command TEXT NOT NULL,
    output TEXT,
    context JSONB DEFAULT '{}',
    progress_pct INTEGER CHECK (progress_pct >= 0 AND progress_pct <= 100),
    current_step TEXT,
    decision_prompt TEXT,
    decision TEXT,
    tier VARCHAR(50),
    started_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT direction_not_empty CHECK (LENGTH(TRIM(direction)) > 0)
);

CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX idx_agent_tasks_type ON agent_tasks(task_type);
CREATE INDEX idx_agent_tasks_created ON agent_tasks(created_at DESC);
CREATE INDEX idx_agent_tasks_updated ON agent_tasks(updated_at DESC);
CREATE INDEX idx_agent_tasks_status_type ON agent_tasks(status, task_type);

-- Index for attention queries (needs_decision, failed)
CREATE INDEX idx_agent_tasks_attention ON agent_tasks(status, created_at DESC)
WHERE status IN ('needs_decision', 'failed');
```

## Migration Strategy

### Phase 1: Dual-Write Mode (Zero Downtime)

1. **Add PostgreSQL adapter implementations**
   - `PostgresGraphStore` in `app/adapters/postgres_graph_store.py`
   - `PostgresAgentTaskStore` in `app/adapters/postgres_agent_task_store.py`
   - Implement same Protocol interfaces as in-memory versions

2. **Enable dual-write mode**
   - Write to both in-memory and PostgreSQL
   - Read from in-memory (trusted source)
   - Use environment variable: `DUAL_WRITE_MODE=true`

3. **Verification period** (1-2 weeks)
   - Monitor PostgreSQL write success rates
   - Verify data consistency via background jobs
   - Alert on write failures

### Phase 2: Read Migration (Minimal Risk)

1. **Gradually shift reads to PostgreSQL**
   - Start with non-critical endpoints (health checks, stats)
   - Use feature flag: `READ_FROM_POSTGRES_PERCENT=10` (gradually increase)
   - Monitor query performance and error rates

2. **Performance tuning**
   - Add missing indexes based on slow query logs
   - Optimize connection pooling (asyncpg)
   - Tune PostgreSQL config for workload

### Phase 3: PostgreSQL as Primary (Switchover)

1. **Final verification**
   - Data consistency check
   - Performance benchmarks
   - Rollback plan tested

2. **Cutover**
   - Set `READ_FROM_POSTGRES_PERCENT=100`
   - Disable in-memory writes (keep reads for rollback)
   - Monitor for 24 hours

3. **Cleanup**
   - Remove in-memory store code
   - Remove dual-write logic
   - Archive final in-memory JSON snapshot

### Rollback Strategy

At each phase:
- **Phase 1 rollback**: Disable PostgreSQL writes, continue in-memory
- **Phase 2 rollback**: Set `READ_FROM_POSTGRES_PERCENT=0`
- **Phase 3 rollback**: Re-enable in-memory mode, restore from JSON snapshot

## Data Persistence Requirements

### Must Persist (Production Critical)

| Store | Data | Rationale |
|-------|------|-----------|
| GraphStore | Projects | Package metadata for dependency analysis |
| GraphStore | Dependencies | Graph structure for coherence scoring |
| GraphStore | Contributors | User identity and payout routing |
| GraphStore | Assets | Contribution tracking, valuation |
| GraphStore | Contributions | Immutable audit trail for payouts |
| AgentTask | All task history | Audit trail, debugging, metrics |

### Can Be Ephemeral (Acceptable Loss)

| Store | Data | Rationale |
|-------|------|-----------|
| None | — | All current data should persist |

**Note**: Even task execution logs should persist for debugging and compliance. The only truly ephemeral data would be runtime caches (not currently implemented).

## Implementation Checklist

- [ ] Create migration scripts: `api/migrations/001_initial_schema.sql`
- [ ] Implement `PostgresGraphStore` adapter
- [ ] Implement `PostgresAgentTaskStore` adapter
- [ ] Add dual-write configuration and logic
- [ ] Add data consistency verification script
- [ ] Add rollback automation script
- [ ] Update deployment docs with database setup
- [ ] Add monitoring and alerting for PostgreSQL health
- [ ] Load test with production-scale data
- [ ] Document connection string formats and pooling config

## Connection Configuration

### Environment Variables

```bash
# PostgreSQL connection
DATABASE_URL=postgresql://user:password@localhost:5432/coherence_network

# Migration control
DUAL_WRITE_MODE=true|false
READ_FROM_POSTGRES_PERCENT=0-100
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=10
```

### Connection Pooling (asyncpg)

```python
from asyncpg import create_pool

pool = await create_pool(
    dsn=os.environ["DATABASE_URL"],
    min_size=10,
    max_size=20,
    max_queries=50000,
    max_inactive_connection_lifetime=300,
)
```

## Performance Considerations

### Indexing Strategy

- **Primary keys**: UUID for contributors, assets, contributions (gen_random_uuid())
- **Composite indexes**: (ecosystem, name) for projects; (status, task_type) for tasks
- **Full-text search**: trigram indexes on project name/description
- **Temporal queries**: DESC indexes on created_at, updated_at

### Query Optimization

- Use `EXPLAIN ANALYZE` for all queries > 100ms
- Batch inserts for bulk operations (e.g., indexing runs)
- Prepared statements for repeated queries
- Connection pooling to prevent connection storms

### Estimated Storage

- **Projects**: ~1MB per 10k projects
- **Dependencies**: ~500KB per 10k edges
- **Contributors**: ~100KB per 1k contributors
- **Assets**: ~200KB per 1k assets
- **Contributions**: ~500KB per 10k contributions
- **Agent Tasks**: ~1MB per 1k tasks (with output)

**Total for 1M indexed packages**: ~100GB (mostly task outputs)

## Testing Plan

### Unit Tests

- [ ] Test PostgresGraphStore CRUD operations
- [ ] Test PostgresAgentTaskStore CRUD operations
- [ ] Test constraint violations (unique, foreign key, check)
- [ ] Test transaction rollback scenarios

### Integration Tests

- [ ] Dual-write consistency test
- [ ] Read switchover test (0% → 100%)
- [ ] Rollback procedure test
- [ ] Performance benchmark (compare to in-memory)

### Load Tests

- [ ] 1000 req/sec sustained for 10 minutes
- [ ] Bulk indexing: 10k projects inserted
- [ ] Concurrent task updates (agent runner load)

## Security Considerations

- **SQL injection**: Use parameterized queries only (asyncpg protects)
- **Credentials**: Never log DATABASE_URL or connection strings
- **Access control**: Use least-privilege database user
- **Encryption**: Require SSL/TLS for production connections
- **Backup**: Daily automated backups with 30-day retention

## Monitoring and Alerts

### Metrics to Track

- Query latency (p50, p95, p99)
- Connection pool utilization
- Failed query rate
- Replication lag (if using read replicas)
- Disk usage growth rate

### Alerts

- Query latency > 500ms (p95)
- Failed queries > 1% of total
- Connection pool exhausted
- Disk usage > 80%
- Replication lag > 10 seconds

## References

- [PostgreSQL asyncpg documentation](https://magicstack.github.io/asyncpg/)
- [SQLAlchemy async support](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Django database configuration](https://docs.djangoproject.com/en/stable/ref/databases/)
