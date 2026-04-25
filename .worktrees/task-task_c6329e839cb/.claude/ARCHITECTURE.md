# Coherence Network - Technical Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Application Layer                   │
│  (Event Processing, API Gateway, Distribution Engine)   │
└─────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│  Graph Database │ │ Event Store │ │   PostgreSQL    │
│   (Lineage)     │ │ (Immutable  │ │  (Accounting)   │
│                 │ │  Ledger)    │ │                 │
└─────────────────┘ └─────────────┘ └─────────────────┘
```

## Data Layer

### PostgreSQL - Accounting Ledger
**Why**: ACID guarantees, exact decimal arithmetic, mature tooling

**Tables**:
- `contributors`: Human and system contributors
- `assets`: Generated entities with lineage
- `contribution_events_ledger`: Immutable event log
- `value_distributions`: Distribution records
- `contributor_payouts`: Individual payout records
- `tool_profiles`: LLM and tool pricing
- `nodes`: Node operator registry

**Critical**: Always use `NUMERIC` type for money (never FLOAT)

### Neo4j - Contribution Graph
**Why**: Native graph traversal, variable-depth queries, relationship-first model

**Nodes**:
- `Contributor` (type: HUMAN or SYSTEM)
- `Asset` (type: CODE, MODEL, CONTENT, DATA)

**Relationships**:
- `CONTRIBUTED_TO` (properties: cost_amount, weight, coherence_score)

**Queries**: Recursive lineage traversal in <10ms for 1000-node subgraph

### Redis - Cache Layer
**Why**: Sub-millisecond latency, hot data access

**Cached**:
- Contributor balances
- Active sessions
- Node health status
- Recent distributions

**TTL**: 5 minutes for balances, 30 seconds for node health

### EventStoreDB - Event Sourcing
**Why**: Immutable append-only log, time-travel queries, event versioning

**Streams**:
- `asset-{id}`: All events for an asset
- `contributor-{id}`: All events for a contributor
- `distributions`: All value distributions

## Application Layer

### FastAPI - REST API
**File**: `api/main.py`

**Endpoints**:
- `/v1/contributors` - CRUD operations
- `/v1/assets` - Asset management
- `/v1/contributions` - Record contribution events
- `/v1/distributions` - Trigger value distributions
- `/v1/nodes` - Node operator registry
- `/webhooks/github` - GitHub integration

**Middleware**:
- Authentication (API key)
- Rate limiting (100 req/hour per key)
- Request logging
- CORS

**Example**:
```python
@app.post("/v1/contributions")
async def create_contribution(
    event: ContributionEventCreate,
    current_user: Contributor = Depends(get_current_user)
):
    async with transaction_manager.begin() as tx:
        # Write to event store
        event_id = await event_store.append(event)
        
        # Update graph
        await graph_db.create_contribution_edge(event)
        
        # Update ledger
        await postgres.insert_contribution_event(event)
        
        await tx.commit()
    
    return {"event_id": event_id}
```

### Distribution Engine
**File**: `services/distribution_engine.py`

**Algorithm**: Recursive graph traversal with coherence weighting

**Steps**:
1. Get all contributions to asset
2. Calculate weighted costs: `cost × (0.5 + coherence)`
3. For SYSTEM contributors, attribute to triggering human
4. For ASSET_COMPOSITION, recurse into dependencies
5. Aggregate payouts per contributor

**Example**:
```python
async def distribute_value(
    asset_id: UUID,
    value_amount: Decimal
) -> Dict[UUID, Decimal]:
    payouts = {}
    visited = set()
    
    await _distribute_recursive(
        asset_id, value_amount, 0, -1,
        payouts, visited, []
    )
    
    return payouts
```

**Complexity**: O(N × D) where N = nodes, D = max depth

### Load Balancer
**File**: `services/load_balancer.py`

**Purpose**: Route requests to cheapest available node

**Algorithm**:
1. Get eligible nodes (status=ACTIVE, uptime>99%)
2. Sort by price (ascending)
3. Select first with capacity
4. Forward request
5. Track usage for billing
6. Retry on failure (next cheapest)

**Example**:
```python
async def route_request(request_type: str) -> Response:
    nodes = await get_eligible_nodes(request_type)
    cheapest = sorted(nodes, key=lambda n: n.pricing)[0]
    
    try:
        response = await forward_to_node(cheapest, request)
        await record_usage(cheapest, request_type, cost)
        return response
    except NodeError:
        return await route_request(request_type)  # Retry
```

## Integration Layer

### GitHub Webhooks
**Endpoint**: `/webhooks/github`

**Flow**:
1. GitHub sends push event
2. Verify HMAC signature
3. Extract commit metadata
4. Estimate cost (files × $10 base)
5. Calculate coherence (has tests? +0.2)
6. Create contribution event
7. Return 200 OK

**Security**: HMAC-SHA256 signature verification

### Stripe Integration
**Purpose**: Payment processing for API usage fees

**Flow**:
1. Track usage per API key
2. Calculate monthly bill
3. Generate invoice
4. Process payment via Stripe
5. Update account balance

## Key Algorithms

### Coherence Calculation

```python
def calculate_coherence(resonance: ResonanceMetrics) -> Decimal:
    weights = {
        'quality': Decimal('0.20'),
        'architecture': Decimal('0.20'),
        'value_add': Decimal('0.15'),
        'test_coverage': Decimal('0.15'),
        'documentation': Decimal('0.10'),
        'network': Decimal('0.10'),
        'novelty': Decimal('0.10')
    }
    
    coherence = (
        weights['quality'] * resonance.code_quality_score +
        weights['architecture'] * resonance.architecture_alignment +
        weights['value_add'] * resonance.value_add_score +
        weights['test_coverage'] * resonance.test_coverage +
        weights['documentation'] * resonance.documentation_score +
        weights['network'] * calculate_network_score(resonance) +
        weights['novelty'] * calculate_novelty_score(resonance)
    )
    
    return min(coherence, Decimal('1.0'))
```

### Distribution Weighting

```python
# Base cost
cost = Decimal("100.00")

# Coherence score
coherence = Decimal("0.92")

# Multiplier (0.5 to 1.5)
multiplier = Decimal("0.5") + coherence  # 1.42

# Weighted cost
weighted_cost = cost * multiplier  # $142.00

# Payout share
share = weighted_cost / total_weighted_cost

# Final payout
payout = value_amount * share
```

### Cheapest Node Selection

```python
def select_cheapest_node(
    node_type: str,
    min_uptime: float = 0.99
) -> Node:
    eligible = [
        n for n in nodes 
        if n.status == 'ACTIVE' 
        and n.uptime >= min_uptime
        and n.node_type == node_type
    ]
    
    if not eligible:
        raise NoNodesAvailable()
    
    return min(eligible, key=lambda n: n.pricing[node_type])
```

## File Structure

```
api/
├── __init__.py
├── main.py              # FastAPI app
├── routes/
│   ├── __init__.py
│   ├── contributors.py  # /v1/contributors
│   ├── assets.py        # /v1/assets
│   ├── contributions.py # /v1/contributions
│   ├── distributions.py # /v1/distributions
│   ├── nodes.py         # /v1/nodes
│   └── webhooks.py      # /webhooks/*
└── middleware/
    ├── auth.py          # API key auth
    └── logging.py       # Request logging

models/
├── __init__.py
├── contributor.py       # Pydantic + SQLAlchemy
├── asset.py
├── contribution.py
└── distribution.py

services/
├── __init__.py
├── graph_service.py     # Neo4j operations
├── ledger_service.py    # PostgreSQL operations
├── distribution_engine.py
├── load_balancer.py
└── payout_processor.py
```

## Deployment Architecture

**Development**: Docker Compose (localhost)
**Staging**: Kubernetes on DigitalOcean
**Production**: Kubernetes on AWS/GCP with auto-scaling

**Containers**:
- `api` (3+ replicas, load balanced)
- `postgres` (StatefulSet with replication)
- `neo4j` (StatefulSet, causal clustering)
- `redis` (Deployment, 3 replicas)
- `nginx` (Ingress controller)

**Auto-scaling**: CPU > 70% → scale up, CPU < 30% → scale down

## Security

**API Authentication**: API key in `X-API-Key` header
**Database Encryption**: TLS for all connections
**Event Integrity**: SHA-256 hash chaining
**Secrets Management**: Kubernetes Secrets + HashiCorp Vault
**Rate Limiting**: 100 requests/hour per API key (free tier)

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| API P95 latency | <200ms | TBD |
| Distribution time | <5s for 100 contributors | TBD |
| Graph query time | <10ms for 1000 nodes | TBD |
| Database writes/sec | >1000 | TBD |
| Uptime | 99.9% | TBD |

## Monitoring

**Metrics**: Prometheus + Grafana
**Logging**: ELK Stack (Elasticsearch + Logstash + Kibana)
**Tracing**: Jaeger
**Alerting**: AlertManager → PagerDuty

**Key Alerts**:
- API error rate > 1%
- P95 latency > 500ms
- Database connection pool exhausted
- Node operator offline
- Treasury balance < operational buffer
