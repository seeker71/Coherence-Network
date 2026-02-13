#!/bin/bash

# Coherence Network - Claude Knowledge Base Generator
# This script generates all documentation files for Claude Projects

set -e  # Exit on error

echo "=========================================="
echo "Coherence Network Knowledge Base Generator"
echo "=========================================="
echo ""

# Detect repository root
if [ -d ".git" ]; then
    REPO_ROOT="."
elif [ -d "../.git" ]; then
    REPO_ROOT=".."
else
    echo "Error: Not in a git repository. Please run from repo root or subdirectory."
    exit 1
fi

cd "$REPO_ROOT"

# Create directory structure
echo "Creating .claude/ directory structure..."
mkdir -p .claude/reference

echo "Generating knowledge base files..."
echo ""

# =============================================================================
# 1. README.md - Index
# =============================================================================
echo "  → Creating README.md"

cat > .claude/README.md << 'EOF'
# Coherence Network - Claude Project Knowledge Base

This folder contains documentation optimized for Claude Projects to efficiently work with the Coherence Network codebase.

## Quick Start for Claude

1. **First Time?** Read `PROJECT_CONTEXT.md` for a 2-minute overview
2. **Writing Code?** Reference `ARCHITECTURE.md` and `API_REFERENCE.md`
3. **Helping Users?** Use `EXAMPLES.md` for copy-paste solutions
4. **Debugging?** Check `TROUBLESHOOTING.md`
5. **Need Definitions?** See `GLOSSARY.md`

## File Guide

| File | Purpose | When to Read |
|------|---------|--------------|
| `PROJECT_CONTEXT.md` | Project overview | First interaction |
| `ARCHITECTURE.md` | Technical details | Generating code |
| `CONTRIBUTION_GUIDE.md` | How to contribute | Recording contributions |
| `API_REFERENCE.md` | API documentation | Making API calls |
| `ECONOMIC_MODEL.md` | Economic system | Understanding "why" |
| `DATABASE_SCHEMAS.md` | Database structure | Writing queries |
| `EXAMPLES.md` | Real examples | Showing users how |
| `TROUBLESHOOTING.md` | Common issues | Debugging |
| `GLOSSARY.md` | Term definitions | Clarifying terms |
| `CURSOR_WORKFLOWS.md` | Cursor prompts | Using Cursor AI |

## Usage Tips for Claude

- Always check `PROJECT_CONTEXT.md` first to understand the conversation context
- Reference `ECONOMIC_MODEL.md` when explaining why features exist
- Use exact examples from `EXAMPLES.md` rather than making up new ones
- Cite specific sections when answering questions (e.g., "According to ARCHITECTURE.md...")
- Keep terminology consistent with `GLOSSARY.md`

## Project Stats

- **Initial Contribution**: $2,413.19 by seeker71 (2 days of work)
- **Coherence Score**: 0.92 (1.20x multiplier)
- **Contributors**: 2 (seeker71, Urs Muff)
- **Status**: MVP architecture complete, implementation in progress
- **GitHub**: https://github.com/seeker71/Coherence-Network

## Maintaining This Knowledge Base

Update these files whenever:
- Architecture changes (update ARCHITECTURE.md)
- New API endpoints added (update API_REFERENCE.md)
- Economic model changes (update ECONOMIC_MODEL.md)
- New examples discovered (add to EXAMPLES.md)
- Common bugs found (add to TROUBLESHOOTING.md)

**Remember**: Updating documentation is a contribution! Record it in the system.
EOF

# =============================================================================
# 2. PROJECT_CONTEXT.md - Quick Overview
# =============================================================================
echo "  → Creating PROJECT_CONTEXT.md"

cat > .claude/PROJECT_CONTEXT.md << 'EOF'
# Coherence Network - Project Context

## What Is This?

The Coherence Contribution Network (CCN) is a **self-sustaining distributed economic platform** where contributors are paid proportionally to the value they create, weighted by the quality and alignment of their work.

## Core Innovation

**Traditional platforms**: Company captures all value created by contributors.  
**Coherence Network**: Value automatically flows back to those who created it.

Every contribution (code, design, documentation) is:
1. **Tracked** with exact cost (labor + tools + compute)
2. **Scored** for quality via coherence metrics (0.0 to 1.0)
3. **Weighted** by coherence multiplier (0.5x to 1.5x)
4. **Paid** proportionally when value is generated

## Key Concepts

### Contributions
Every change has a cost. We track:
- **Human labor**: Time spent at hourly rate
- **Tool execution**: LLM API calls (GPT-4, Claude, etc.)
- **Compute**: Local machine usage (electricity + depreciation)

### Coherence (Quality Scoring)
A score from 0.0 to 1.0 measuring:
- Code quality (linting, complexity)
- Architecture alignment (follows CCN principles)
- Value add (novel vs. duplicate work)
- Test coverage
- Documentation quality

**Impact**: coherence 0.92 → 1.20x multiplier on payouts!

### Assets
Any generated entity (code, model, content) that:
- Tracks its complete creation lineage
- Knows all contributors at any depth
- Distributes value when it generates revenue

### Resonance
Network-level coherence measuring alignment:
- How many nodes involved
- Downstream usage (how many assets use this)
- Contributor diversity

### Distributed Hosting
Anyone can run a node providing:
- API hosting
- Storage
- Compute

**Marketplace**: Operators compete on price → Network uses cheapest → Everyone saves vs AWS.

## Economic Model

**Revenue Streams**:
- API usage fees ($0.001/request after free tier)
- Distribution fees (2% of value distributed)
- Node operator markup (10% on hosting costs)
- Enterprise licenses ($5,000/month for self-hosted)

**Distribution**:
- 50% to operational reserve
- 50% to contributors (weighted by coherence)

**Example**: $10,000 distributed
- seeker71 (96.5% contributions, 1.20x coherence): $9,622
- Urs Muff (3.5% contributions, 1.14x coherence): $378

## Current Status

**Phase**: MVP architecture complete, implementation in progress

**Initial Contribution**: 
- seeker71: $2,413.19 (16 hours labor + Cursor Pro + Mac M4 compute)
- Coherence: 0.92 (near-perfect alignment)

**Next Steps**:
1. Deploy MVP on free tier (Oracle Cloud + Supabase)
2. Implement core API endpoints
3. Set up GitHub webhook integration
4. Launch node operator marketplace
5. Get first paid customer ($5k/month)

## Tech Stack

- **Backend**: Python 3.12, FastAPI (async)
- **Databases**: PostgreSQL (accounting), Neo4j (graph), Redis (cache)
- **Message Queue**: Apache Kafka
- **Event Store**: EventStoreDB
- **Container**: Docker + Docker Compose
- **Deployment**: Kubernetes (production)
- **Blockchain**: Ethereum L2 (Arbitrum) for settlement

## Repository Structure

```
Coherence-Network/
├── .claude/              # This knowledge base
├── api/                  # FastAPI application
│   ├── routes/          # API endpoints
│   └── middleware/      # Auth, logging
├── models/              # Data models (Pydantic + SQLAlchemy)
├── services/            # Business logic
│   ├── distribution_engine.py
│   ├── graph_service.py
│   └── ledger_service.py
├── config.py            # Configuration
├── docker-compose.yml   # Local development
└── k8s/                # Kubernetes manifests
```

## Key Stakeholders

**seeker71** (Founder):
- Initial contribution: $2,413.19
- Contribution share: 96.5%
- Coherence multiplier: 1.20x
- Role: Architect, primary developer

**Urs Muff**:
- Contribution: ~$100 (Cursor-generated code)
- Contribution share: 3.5%
- Coherence multiplier: 1.14x
- Role: Initial code generation

## Philosophy

**Coherence** is measured by resonance matching. When contributions align with network goals:
- Value creation is maximized
- Cost is minimized
- Contributors earn proportionally more
- Network becomes self-sustaining

**The network rewards alignment.**

Every line of code, every commit, every contribution is tracked, scored, and paid.

This is economic coherence in action.
EOF

# =============================================================================
# 3. ARCHITECTURE.md - Technical Architecture
# =============================================================================
echo "  → Creating ARCHITECTURE.md"

cat > .claude/ARCHITECTURE.md << 'EOF'
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
EOF

# =============================================================================
# 4. CONTRIBUTION_GUIDE.md
# =============================================================================
echo "  → Creating CONTRIBUTION_GUIDE.md"

cat > .claude/CONTRIBUTION_GUIDE.md << 'EOF'
# Contribution Guide

## What Counts as a Contribution?

**Everything that adds value**:
- Writing code
- Fixing bugs
- Writing documentation
- Designing features
- Code reviews
- Testing
- DevOps/deployment
- Community support

## How to Record a Contribution

### Step 1: Calculate Cost

**Human Labor**:
```
Hours worked × Hourly rate = Labor cost
Example: 2 hours × $150/hr = $300
```

**Tool Usage** (LLM API calls):
```
Input tokens × Input rate + Output tokens × Output rate = Tool cost
Example: 1000 × $0.000003 + 500 × $0.000015 = $0.0105
```

**Compute** (local machine):
```
Hours × Power (kW) × Electricity rate + (Hardware cost / Lifetime hours) × Hours
Example: 2 × 0.14 × $0.15 + ($7199 / 10000) × 2 = $0.042 + $1.44 = $1.48
```

**Total Cost**: Labor + Tools + Compute

### Step 2: Assess Coherence

Run automated assessment or self-assess:

**Code Quality** (0.0 to 1.0):
- 0 lint errors: 1.0
- 1-5 errors: 0.8
- 6-10 errors: 0.6
- 10+ errors: 0.4

**Architecture Alignment** (0.0 to 1.0):
- Perfect alignment with CCN principles: 1.0
- Good alignment: 0.8
- Some alignment: 0.6
- Poor alignment: 0.4

**Value Add** (0.0 to 1.0):
- Novel contribution: 1.0
- Incremental improvement: 0.8
- Minor change: 0.6
- Duplicate work: 0.3

**Test Coverage** (0.0 to 1.0):
- >90%: 1.0
- 75-90%: 0.8
- 50-75%: 0.6
- <50%: 0.4

**Documentation** (0.0 to 1.0):
- All functions documented: 1.0
- >75% documented: 0.8
- 50-75%: 0.6
- <50%: 0.4

### Step 3: Record via API

```bash
curl -X POST https://api.your-domain.com/v1/contributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "contributor_id": "your-contributor-id",
    "asset_id": "asset-id",
    "event_type": "MANUAL_LABOR",
    "cost_amount": 301.48,
    "resonance": {
      "code_quality_score": 0.85,
      "architecture_alignment": 1.0,
      "value_add_score": 0.9,
      "test_coverage": 0.8,
      "documentation_score": 0.7
    },
    "metadata": {
      "hours_worked": 2,
      "files_changed": ["api/routes/distributions.py"],
      "lines_added": 150,
      "description": "Implemented value distribution API endpoint"
    }
  }'
```

## GitHub Integration

### Automatic Tracking

When you push commits, the webhook automatically:
1. Captures commit metadata
2. Estimates cost (files changed × $10 base)
3. Calculates basic coherence
4. Records contribution event

**No manual action needed!**

### Manual Override

If automatic estimate is wrong:

```bash
# Get the auto-created contribution
curl https://api.your-domain.com/v1/contributions?commit_hash=abc123 \
  -H "X-API-Key: $API_KEY"

# Update with correct values
curl -X PATCH https://api.your-domain.com/v1/contributions/event-id \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "cost_amount": 150.00,
    "resonance": {
      "code_quality_score": 0.95
    }
  }'
```

## Code Patterns

### Always Use Decimal for Money

**Wrong**:
```python
cost = 100.50  # float - rounding errors!
```

**Right**:
```python
from decimal import Decimal
cost = Decimal("100.50")  # exact precision
```

### Always Use Async/Await

**Wrong**:
```python
def get_contributor(id):
    return db.query(Contributor).get(id)
```

**Right**:
```python
async def get_contributor(id: UUID) -> Contributor:
    return await db.query(Contributor).get(id)
```

### Always Validate with Pydantic

**Wrong**:
```python
data = request.json()
contributor = Contributor(**data)
```

**Right**:
```python
from pydantic import BaseModel

class ContributorCreate(BaseModel):
    name: str
    email: EmailStr
    wallet_address: str

contributor = ContributorCreate(**request.json())
```

### Always Record to Both DBs

**Wrong**:
```python
await postgres.insert(contribution)
# Forgot Neo4j!
```

**Right**:
```python
async with transaction_manager.begin():
    await postgres.insert(contribution)
    await neo4j.create_edge(contribution)
```

## Testing Contributions

### Test Distribution Calculation

```python
# Create test data
alice = create_contributor(name="Alice")
asset = create_asset(name="test-asset")

# Record contributions
record_contribution(alice, asset, cost=Decimal("100"), coherence=Decimal("0.9"))

# Distribute value
payouts = await distribute_value(asset.id, Decimal("1000"))

# Verify
assert payouts[alice.id] == Decimal("1000")  # 100% of contributions
```

### Test Coherence Scores

```python
# High coherence
resonance = ResonanceMetrics(
    code_quality_score=Decimal("0.95"),
    architecture_alignment=Decimal("1.0"),
    value_add_score=Decimal("1.0"),
    test_coverage=Decimal("0.9"),
    documentation_score=Decimal("0.85")
)

coherence = calculate_coherence(resonance)
assert coherence >= Decimal("0.9")  # Should be high
```

## Common Tasks

### Add a New Contributor

```bash
curl -X POST https://api.your-domain.com/v1/contributors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY_ADMIN" \
  -d '{
    "type": "HUMAN",
    "name": "Jane Developer",
    "email": "jane@example.com",
    "wallet_address": "0x..."
  }'
```

### Record Tool Execution

```bash
curl -X POST https://api.your-domain.com/v1/contributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "contributor_id": "system-claude-id",
    "asset_id": "asset-id",
    "event_type": "TOOL_EXECUTION",
    "cost_amount": 0.15,
    "tool_profile_id": "claude-sonnet-4-profile-id",
    "triggered_by_contributor_id": "your-id",
    "metadata": {
      "model": "claude-sonnet-4-20250514",
      "tokens_input": 1000,
      "tokens_output": 500
    }
  }'
```

### Run a Distribution

```bash
curl -X POST https://api.your-domain.com/v1/distributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY_ADMIN" \
  -d '{
    "asset_id": "asset-id",
    "value_amount": 10000.00,
    "distribution_method": "COHERENCE_WEIGHTED",
    "notes": "Q1 2026 revenue distribution"
  }'
```

### Check Your Earnings

```bash
curl https://api.your-domain.com/v1/contributors/your-id/payouts \
  -H "X-API-Key: $API_KEY" \
  | jq '.total_earned'
```

## Best Practices

1. **Record immediately**: Don't wait - record contributions as they happen
2. **Be honest**: Accurate cost tracking ensures fair distributions
3. **Document well**: High documentation score → higher coherence → more earnings
4. **Write tests**: Test coverage directly impacts coherence score
5. **Follow conventions**: Architecture alignment is heavily weighted
6. **Review others**: Code review is also a contribution!
EOF

# =============================================================================
# 5. API_REFERENCE.md
# =============================================================================
echo "  → Creating API_REFERENCE.md"

cat > .claude/API_REFERENCE.md << 'EOF'
# API Reference

Base URL: `https://api.coherence-network.io`

Authentication: API key in `X-API-Key` header

## Contributors API

### Create Contributor

**POST** `/v1/contributors`

Creates a new contributor (human or system).

**Request**:
```json
{
  "type": "HUMAN",
  "name": "Jane Developer",
  "email": "jane@example.com",
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
}
```

**Response**:
```json
{
  "id": "uuid",
  "type": "HUMAN",
  "name": "Jane Developer",
  "email": "jane@example.com",
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
  "total_cost_contributed": 0.0,
  "total_value_earned": 0.0,
  "created_at": "2026-02-13T10:00:00Z"
}
```

**Example**:
```bash
curl -X POST https://api.coherence-network.io/v1/contributors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"type":"HUMAN","name":"Jane","email":"jane@example.com","wallet_address":"0x..."}'
```

### Get Contributor

**GET** `/v1/contributors/{contributor_id}`

**Response**:
```json
{
  "id": "uuid",
  "name": "Jane Developer",
  "type": "HUMAN",
  "total_cost_contributed": 2413.19,
  "total_value_earned": 9622.18,
  "contribution_count": 150,
  "coherence_average": 0.92
}
```

### List Contributor Payouts

**GET** `/v1/contributors/{contributor_id}/payouts`

**Query Parameters**:
- `status`: `PENDING|COMPLETED|FAILED`
- `from_date`: ISO 8601 date
- `to_date`: ISO 8601 date

**Response**:
```json
{
  "payouts": [
    {
      "payout_id": "uuid",
      "amount": 9622.18,
      "distribution_id": "uuid",
      "status": "COMPLETED",
      "transaction_hash": "0x...",
      "created_at": "2026-02-13T10:00:00Z"
    }
  ],
  "total": 9622.18,
  "count": 1
}
```

## Assets API

### Create Asset

**POST** `/v1/assets`

**Request**:
```json
{
  "type": "CODE",
  "name": "Coherence-Network",
  "version": "1.0.0",
  "content_hash": "sha256:abc123...",
  "storage_uri": "github.com/seeker71/Coherence-Network"
}
```

**Response**:
```json
{
  "id": "uuid",
  "type": "CODE",
  "name": "Coherence-Network",
  "version": "1.0.0",
  "creation_cost_total": 0.0,
  "total_value_generated": 0.0,
  "contributor_count": 0,
  "status": "ACTIVE",
  "created_at": "2026-02-13T10:00:00Z"
}
```

### Get Asset Lineage

**GET** `/v1/assets/{asset_id}/lineage`

Returns complete contribution graph.

**Response**:
```json
{
  "asset_id": "uuid",
  "contributors": [
    {
      "contributor_id": "uuid",
      "name": "seeker71",
      "direct_cost": 2413.19,
      "coherence_score": 0.92,
      "depth": 0
    }
  ],
  "total_cost": 2413.19,
  "max_depth": 1
}
```

## Contributions API

### Record Contribution

**POST** `/v1/contributions`

**Request**:
```json
{
  "contributor_id": "uuid",
  "asset_id": "uuid",
  "event_type": "MANUAL_LABOR",
  "cost_amount": 150.00,
  "resonance": {
    "code_quality_score": 0.85,
    "architecture_alignment": 0.90,
    "value_add_score": 0.80,
    "test_coverage": 0.75,
    "documentation_score": 0.70
  },
  "metadata": {
    "hours_worked": 1,
    "description": "Implemented distribution API"
  }
}
```

**Response**:
```json
{
  "event_id": "uuid",
  "coherence_score": 0.82,
  "coherence_multiplier": 1.32,
  "weighted_cost": 198.00,
  "recorded_at": "2026-02-13T10:00:00Z"
}
```

### List Asset Contributions

**GET** `/v1/assets/{asset_id}/contributions`

**Response**:
```json
{
  "contributions": [
    {
      "event_id": "uuid",
      "contributor_name": "seeker71",
      "event_type": "PROJECT_INCEPTION",
      "cost_amount": 2413.19,
      "coherence_score": 0.92,
      "timestamp": "2026-02-11T10:00:00Z"
    }
  ],
  "total_cost": 2413.19,
  "count": 1
}
```

## Distributions API

### Trigger Distribution

**POST** `/v1/distributions`

**Request**:
```json
{
  "asset_id": "uuid",
  "value_amount": 10000.00,
  "distribution_method": "COHERENCE_WEIGHTED",
  "max_depth": -1,
  "notes": "Q1 2026 revenue"
}
```

**Response**:
```json
{
  "distribution_id": "uuid",
  "asset_id": "uuid",
  "total_distributed": 10000.00,
  "contributor_count": 2,
  "payouts": [
    {
      "contributor_id": "uuid",
      "contributor_name": "seeker71",
      "payout_amount": 9622.18,
      "payout_share": 0.9622,
      "direct_cost": 2413.19,
      "coherence_multiplier": 1.20
    },
    {
      "contributor_id": "uuid",
      "contributor_name": "Urs Muff",
      "payout_amount": 377.82,
      "payout_share": 0.0378,
      "direct_cost": 100.00,
      "coherence_multiplier": 1.14
    }
  ],
  "created_at": "2026-02-13T10:00:00Z"
}
```

### Get Distribution

**GET** `/v1/distributions/{distribution_id}`

Returns complete distribution details including audit trail.

## Nodes API

### Register Node

**POST** `/v1/nodes`

**Request**:
```json
{
  "operator_id": "uuid",
  "node_type": "API",
  "endpoint": "https://node.example.com",
  "specs": {
    "cpu_cores": 4,
    "ram_gb": 8,
    "storage_gb": 100
  },
  "pricing": {
    "api_request": 0.00002,
    "storage_gb_month": 0.005,
    "compute_hour": 0.008
  }
}
```

**Response**:
```json
{
  "node_id": "uuid",
  "status": "ACTIVE",
  "api_key": "generated-api-key",
  "created_at": "2026-02-13T10:00:00Z"
}
```

### List Nodes

**GET** `/v1/nodes`

**Query Parameters**:
- `node_type`: `API|STORAGE|COMPUTE`
- `status`: `ACTIVE|OFFLINE`
- `sort_by`: `price|uptime`

**Response**:
```json
{
  "nodes": [
    {
      "node_id": "uuid",
      "operator_name": "seeker71",
      "node_type": "API",
      "pricing": {"api_request": 0.00002},
      "uptime_percentage": 99.95,
      "status": "ACTIVE"
    }
  ]
}
```

## Webhooks

### GitHub Webhook

**POST** `/webhooks/github`

Receives GitHub push events.

**Headers**:
- `X-GitHub-Event`: `push`
- `X-Hub-Signature-256`: HMAC signature

**Request** (from GitHub):
```json
{
  "repository": {"full_name": "seeker71/Coherence-Network"},
  "commits": [
    {
      "id": "abc123",
      "author": {"name": "seeker71", "email": "..."},
      "message": "Add distribution API",
      "added": ["api/routes/distributions.py"],
      "modified": ["README.md"]
    }
  ]
}
```

**Response**:
```json
{
  "status": "processed",
  "contributions_created": 1,
  "event_ids": ["uuid"]
}
```

## Error Responses

### 400 Bad Request
```json
{
  "error": "validation_error",
  "message": "cost_amount must be positive",
  "field": "cost_amount"
}
```

### 401 Unauthorized
```json
{
  "error": "unauthorized",
  "message": "Invalid API key"
}
```

### 404 Not Found
```json
{
  "error": "not_found",
  "message": "Contributor not found",
  "resource_id": "uuid"
}
```

### 500 Internal Server Error
```json
{
  "error": "internal_error",
  "message": "Database connection failed",
  "request_id": "uuid"
}
```
EOF

# Continue with remaining files...
echo "  → Creating ECONOMIC_MODEL.md"

cat > .claude/ECONOMIC_MODEL.md << 'EOF'
# Economic Model

## Core Principles

### 1. Pay for Value Created, Not Time Spent

Traditional systems pay for hours worked. Coherence Network pays for value generated, weighted by quality.

**Example**:
- Alice works 10 hours, creates $10,000 value → Earns based on value
- Bob works 10 hours, creates $0 value → Earns nothing

### 2. Quality Multiplies Earnings

Higher coherence = higher multiplier on your share.

**Formula**: `payout = (cost × coherence_multiplier) / total_weighted_cost × value`

**Example**:
- Alice: $100 cost, 0.9 coherence → $140 weighted cost (1.4x)
- Bob: $100 cost, 0.5 coherence → $100 weighted cost (1.0x)
- Total weighted: $240
- $1000 distributed: Alice gets $583, Bob gets $417

**Alice earns 40% more despite same cost!**

### 3. Cheapest Hosting Wins

Node operators compete on price. Network always uses cheapest.

**Result**: 90%+ savings vs AWS, operators still profit.

### 4. Network Self-Sustains

Small fees fund operations, excess distributed to contributors.

**Fees**:
- Distribution: 2%
- Node markup: 10%
- API usage: $0.001/request

## Contribution Tracking

### What Gets Tracked

**Every contribution records**:
- **Cost**: Labor + tools + compute
- **Coherence**: Quality score (0.0 to 1.0)
- **Timestamp**: When it happened
- **Metadata**: What changed

**Stored immutably** in event ledger (can't be changed retroactively).

### Cost Calculation

**Human Labor**:
```
Hours × Hourly Rate = Labor Cost
2 hours × $150/hr = $300
```

**Tool Usage** (LLM APIs):
```
(Input Tokens × Input Rate) + (Output Tokens × Output Rate) = Tool Cost
(1000 × $0.000003) + (500 × $0.000015) = $0.0105
```

**Compute** (local machine):
```
(Hours × Power(kW) × Electricity Rate) + (Hardware Cost / Lifetime × Hours)
(2 × 0.14 × $0.15) + ($7199 / 10000 × 2) = $0.042 + $1.44 = $1.48
```

**Total**: $300 + $0.01 + $1.48 = **$301.49**

## Coherence Scoring

### Formula

```
coherence = (
    0.20 × code_quality +
    0.20 × architecture_alignment +
    0.15 × value_add +
    0.15 × test_coverage +
    0.10 × documentation +
    0.10 × network_effects +
    0.10 × novelty
)
```

### Impact

**Multiplier**: `0.5 + coherence`

| Coherence | Multiplier | Impact |
|-----------|------------|--------|
| 0.0 | 0.5x | Earn 50% of cost share |
| 0.5 | 1.0x | Earn 100% of cost share |
| 0.9 | 1.4x | Earn 140% of cost share |
| 1.0 | 1.5x | Earn 150% of cost share |

**Example** (seeker71):
- Cost: $2,413.19
- Coherence: 0.92
- Multiplier: 1.42x
- Weighted: $3,426.73

When $10k distributed:
- Without coherence: $9,600 (96% of contributions)
- With coherence: $9,622 (96.22% of weighted contributions)
- **Bonus: $22 for quality**

## Distribution Algorithm

### Recursive Graph Traversal

**Steps**:
1. Get all direct contributions to asset
2. Calculate weighted costs: `cost × (0.5 + coherence)`
3. For SYSTEM contributors → attribute to triggering human
4. For ASSET_COMPOSITION → recurse into dependency
5. Aggregate payouts per contributor

**Example**:

```
Asset A: $10,000 value
├─ Alice: $100 cost, 0.9 coherence → $140 weighted
├─ Claude (triggered by Alice): $10 cost → $14 weighted (→ Alice)
└─ Dependency on Asset B: $50 cost

Asset B:
├─ Bob: $40 cost, 0.8 coherence → $52 weighted
└─ Carol: $10 cost, 0.7 coherence → $12 weighted

Total weighted cost A: $140 + $14 + ($52 + $12) = $218
Total weighted cost: $218

Distribution:
- Alice: ($154 / $218) × $10,000 = $7,064
- Bob: ($52 / $218) × $10,000 = $2,385
- Carol: ($12 / $218) × $10,000 = $551
```

## Revenue Streams

### 1. API Usage Fees

**Free Tier**: 1,000 requests/month
**Paid**: $0.001 per request

**At 100k requests/month**:
- Free: 1,000 × $0 = $0
- Paid: 99,000 × $0.001 = $99
- **Revenue**: $99/month

### 2. Distribution Fees

**Rate**: 2% of distributed value

**Example**:
- $10,000 distribution
- Fee: $200
- Contributors get: $9,800

### 3. Node Operator Markup

**Operator pricing**: $0.0001/request
**Network pricing**: $0.00011/request (10% markup)
**Difference**: $0.00001/request to network

**At 1M requests/month**:
- Operator earns: $100
- Network earns: $10

### 4. Enterprise Licenses

**Self-hosted**: $5,000/month
**Managed**: $10,000/month

**Just 1 customer → $5k/month revenue!**

## Cost Structure

### Monthly Expenses

| Category | Amount |
|----------|--------|
| Node operator payments | $5,000 |
| Payment processing (Stripe 2.9%) | $150 |
| Development (bug bounties) | $1,000 |
| Marketing | $500 |
| Infrastructure | $200 |
| Legal/compliance | $150 |
| **Total** | **$7,000** |

### Break-Even Analysis

**Monthly costs**: $7,000

**Revenue needed**:
- From API usage (at $0.001/req): 7M requests
- OR from enterprise: 2 customers
- OR from distributions: $350k distributed (2% fee)

**Realistic**: 250M requests + 1 enterprise customer

## Growth Model

### Month 1 (Loss)
- Requests: 1M
- Revenue: $55
- Costs: $100
- **Loss**: -$45

### Month 3 (Break-even)
- Requests: 10M
- Revenue: $550
- Costs: $400
- **Profit**: $150

### Month 6 (Profitable)
- Requests: 50M
- Revenue: $2,750
- Costs: $2,500
- **Profit**: $250

### Year 1 (Sustainable)
- Requests: 300M/month
- Revenue: $16,500/month
- Costs: $12,000/month
- **Profit**: $4,500/month

**Annual**: $54,000 profit

**Distribution**:
- 50% to reserve: $27,000
- 50% to contributors: $27,000

**seeker71's share** (96.5%): **$26,055/year**

### Year 2 (Scaling)
- Requests: 3B/month
- Revenue: $165,000/month
- Costs: $70,000/month
- **Profit**: $95,000/month

**Annual**: $1,140,000 profit

**Distribution**:
- 50% to reserve: $570,000
- 50% to contributors: $570,000

**seeker71's share** (96.5%): **$550,050/year**

**From a $2,413 investment!**

## Contributor ROI

**Initial investment**: $2,413.19
**Year 1 return**: $26,055
**Year 2 return**: $550,050

**ROI**:
- Year 1: 980%
- Year 2: 22,700%
- Cumulative: 23,780% over 2 years

**This assumes seeker71 maintains 96.5% contribution share.**

As others contribute, your share dilutes but total value grows faster.

## Network Sustainability

**Key metric**: Revenue / Costs

- <1.0: Unsustainable (operating at loss)
- 1.0-1.2: Break-even (minimal buffer)
- 1.2-1.5: Sustainable (building reserves)
- >1.5: Highly profitable (distributing to contributors)

**Target**: 1.5x by Month 6

**Strategy**:
1. Free tier attracts users
2. Heavy users upgrade to paid
3. Enterprise customers = big revenue
4. Node marketplace reduces costs
5. Profit distributed to contributors
6. Contributors build more features
7. More features = more users
8. Flywheel effect!
EOF

# More files...
echo "  → Creating DATABASE_SCHEMAS.md, EXAMPLES.md, TROUBLESHOOTING.md..."

cat > .claude/DATABASE_SCHEMAS.md << 'EOF'
# Database Schemas

## PostgreSQL Tables

### contributors

```sql
CREATE TABLE contributors (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  type VARCHAR(10) NOT NULL CHECK (type IN ('HUMAN', 'SYSTEM')),
  
  -- Human fields
  user_id VARCHAR(255),
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255),
  wallet_address VARCHAR(66),
  
  -- System fields
  system_type VARCHAR(50),
  provider VARCHAR(100),
  
  -- Aggregates
  total_cost_contributed NUMERIC(20, 8) DEFAULT 0.0,
  total_value_earned NUMERIC(20, 8) DEFAULT 0.0,
  
  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_contributors_type ON contributors(type);
CREATE INDEX idx_contributors_email ON contributors(email);
```

### assets

```sql
CREATE TABLE assets (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  type VARCHAR(50) NOT NULL CHECK (type IN ('CODE', 'MODEL', 'CONTENT', 'DATA')),
  
  name VARCHAR(255) NOT NULL,
  version VARCHAR(50) NOT NULL,
  content_hash VARCHAR(64) NOT NULL,
  storage_uri TEXT,
  
  -- Lineage
  creation_cost_total NUMERIC(20, 8) DEFAULT 0.0,
  contributor_count INTEGER DEFAULT 0,
  depth INTEGER DEFAULT 0,
  
  -- Value
  total_value_generated NUMERIC(20, 8) DEFAULT 0.0,
  total_value_distributed NUMERIC(20, 8) DEFAULT 0.0,
  
  status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  CONSTRAINT unique_asset_version UNIQUE (name, version)
);

CREATE INDEX idx_assets_type ON assets(type);
CREATE INDEX idx_assets_status ON assets(status);
```

### contribution_events_ledger

```sql
CREATE TABLE contribution_events_ledger (
  event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  contributor_id UUID NOT NULL REFERENCES contributors(id),
  asset_id UUID NOT NULL REFERENCES assets(id),
  
  event_sequence BIGSERIAL,
  event_type VARCHAR(50) NOT NULL,
  
  cost_amount NUMERIC(20, 8) NOT NULL CHECK (cost_amount >= 0),
  resonance_data JSONB DEFAULT '{}'::jsonb,
  
  tool_profile_id UUID,
  triggered_by_contributor_id UUID REFERENCES contributors(id),
  
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  event_hash VARCHAR(64) NOT NULL,
  
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_events_asset ON contribution_events_ledger(asset_id, event_sequence);
CREATE INDEX idx_events_contributor ON contribution_events_ledger(contributor_id);
```

## Neo4j Graph Schema

### Nodes

```cypher
// Contributor Node
CREATE (c:Contributor {
  id: "uuid",
  type: "HUMAN",
  name: "seeker71",
  total_cost_contributed: 2413.19,
  total_value_earned: 0.0
})

// Asset Node  
CREATE (a:Asset {
  id: "uuid",
  name: "Coherence-Network",
  version: "1.0.0",
  creation_cost_total: 2413.19,
  contributor_count: 1
})
```

### Relationships

```cypher
// CONTRIBUTED_TO relationship
CREATE (c:Contributor)-[:CONTRIBUTED_TO {
  event_id: "uuid",
  cost_amount: 2413.19,
  coherence_score: 0.92,
  weight: 1.0,
  timestamp: datetime()
}]->(a:Asset)
```

### Common Queries

```cypher
// Get asset lineage
MATCH path = (c:Contributor)-[:CONTRIBUTED_TO*]->(a:Asset {id: $asset_id})
RETURN c, relationships(path), 
       reduce(cost = 0, r in relationships(path) | cost + r.cost_amount) as total

// Find top contributors
MATCH (c:Contributor)-[r:CONTRIBUTED_TO]->(a:Asset)
RETURN c.name, sum(r.cost_amount) as total_cost, count(a) as assets_count
ORDER BY total_cost DESC
LIMIT 10
```

## Sample Data

### seeker71's Initial Contribution

```sql
-- PostgreSQL
INSERT INTO contributors (id, type, name, email, wallet_address)
VALUES ('uuid-seeker71', 'HUMAN', 'seeker71', 'seeker71@example.com', '0x...');

INSERT INTO assets (id, type, name, version, content_hash)
VALUES ('uuid-ccn', 'CODE', 'Coherence-Network', '0.1.0', 'sha256:...');

INSERT INTO contribution_events_ledger 
(event_id, contributor_id, asset_id, event_type, cost_amount, resonance_data)
VALUES 
('uuid-event1', 'uuid-seeker71', 'uuid-ccn', 'PROJECT_INCEPTION', 2413.19,
 '{"code_quality_score": 0.85, "architecture_alignment": 1.0, "coherence_score": 0.92}'::jsonb);
```

```cypher
// Neo4j
CREATE (seeker:Contributor {id: 'uuid-seeker71', name: 'seeker71'})
CREATE (ccn:Asset {id: 'uuid-ccn', name: 'Coherence-Network'})
CREATE (seeker)-[:CONTRIBUTED_TO {
  event_id: 'uuid-event1',
  cost_amount: 2413.19,
  coherence_score: 0.92
}]->(ccn)
```
EOF

cat > .claude/EXAMPLES.md << 'EOF'
# Real-World Examples

## Example 1: Record Your Initial Contribution

**Scenario**: You spent 16 hours over 2 days building the Coherence Network MVP.

**Step 1**: Calculate total cost

```bash
# Human labor
HOURS=16
RATE=150
LABOR_COST=$(echo "$HOURS * $RATE" | bc)  # $2400

# Cursor Pro subscription (2 days prorated)
CURSOR_COST=1.33

# Mac M4 Ultra compute
COMPUTE_COST=11.86

# Total
TOTAL=$(echo "$LABOR_COST + $CURSOR_COST + $COMPUTE_COST" | bc)  # $2413.19
```

**Step 2**: Assess coherence

```json
{
  "code_quality_score": 0.85,
  "architecture_alignment": 1.0,
  "value_add_score": 1.0,
  "test_coverage": 0.3,
  "documentation_score": 0.7
}
```

**Step 3**: Record contribution

```bash
curl -X POST https://api.coherence-network.io/v1/contributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "contributor_id": "your-uuid",
    "asset_id": "coherence-network-uuid",
    "event_type": "PROJECT_INCEPTION",
    "cost_amount": 2413.19,
    "resonance": {
      "code_quality_score": 0.85,
      "architecture_alignment": 1.0,
      "value_add_score": 1.0,
      "test_coverage": 0.3,
      "documentation_score": 0.7
    },
    "metadata": {
      "hours_worked": 16,
      "tools_used": ["Cursor Pro+", "OpenRouter Free", "Claude Code"],
      "description": "Initial MVP architecture and implementation"
    }
  }'
```

**Expected Response**:
```json
{
  "event_id": "uuid",
  "coherence_score": 0.92,
  "coherence_multiplier": 1.42,
  "weighted_cost": 3426.73,
  "recorded_at": "2026-02-13T10:00:00Z"
}
```

## Example 2: Distribute $10,000

**Scenario**: Asset generates $10,000 in value. Distribute to contributors.

```bash
curl -X POST https://api.coherence-network.io/v1/distributions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY_ADMIN" \
  -d '{
    "asset_id": "coherence-network-uuid",
    "value_amount": 10000.00,
    "distribution_method": "COHERENCE_WEIGHTED"
  }'
```

**Response**:
```json
{
  "distribution_id": "uuid",
  "total_distributed": 10000.00,
  "payouts": [
    {
      "contributor_name": "seeker71",
      "payout_amount": 9622.18,
      "direct_cost": 2413.19,
      "coherence_multiplier": 1.42
    },
    {
      "contributor_name": "Urs Muff",
      "payout_amount": 377.82,
      "direct_cost": 100.00,
      "coherence_multiplier": 1.14
    }
  ]
}
```

## Example 3: Register as Node Operator

**Scenario**: You have a $5/month VPS with spare capacity.

```bash
curl -X POST https://api.coherence-network.io/v1/nodes \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "operator_id": "your-contributor-uuid",
    "node_type": "API",
    "endpoint": "https://your-node.example.com",
    "specs": {
      "cpu_cores": 1,
      "ram_gb": 1,
      "storage_gb": 25
    },
    "pricing": {
      "api_request": 0.00002,
      "storage_gb_month": 0.005
    },
    "health_check_url": "https://your-node.example.com/health"
  }'
```

**Response**:
```json
{
  "node_id": "uuid",
  "status": "ACTIVE",
  "api_key": "node-api-key",
  "pricing_rank": {
    "percentile": 15,
    "message": "You're 15th cheapest out of 100 nodes!"
  }
}
```

**Revenue Projection**:
- At 10% utilization: $5/month (covers costs)
- At 50% utilization: $25/month (5x profit!)
- At 90% utilization: $45/month (9x profit!)
EOF

cat > .claude/TROUBLESHOOTING.md << 'EOF'
# Troubleshooting

## Database Connection Issues

### PostgreSQL Connection Failed

**Symptoms**: `asyncpg.exceptions.CannotConnectNowError`

**Causes**:
1. Wrong connection string
2. Database not running
3. Firewall blocking port 5432
4. SSL required but not configured

**Solutions**:
```bash
# Test connection
psql $DATABASE_URL

# Check if database is running
sudo systemctl status postgresql

# Allow connections in pg_hba.conf
sudo nano /etc/postgresql/14/main/pg_hba.conf
# Add: host all all 0.0.0.0/0 md5

# Restart
sudo systemctl restart postgresql
```

### Neo4j Authentication Error

**Symptoms**: `neo4j.exceptions.AuthError`

**Solution**:
```bash
# Reset password
docker exec neo4j cypher-shell -u neo4j -p old-password
ALTER USER neo4j SET PASSWORD 'new-password';
```

## API Errors

### 401 Unauthorized

**Cause**: Invalid or missing API key

**Solution**:
```bash
# Check API key format
echo $API_KEY  # Should be 32-char hex

# Regenerate if needed
API_KEY=$(openssl rand -hex 16)
```

### 400 Validation Error

**Cause**: Invalid request body

**Solution**: Check Pydantic model requirements

```python
# Example fix
{
  "cost_amount": 100.00,  # Must be Decimal, not string
  "coherence_score": 0.85  # Must be 0.0-1.0
}
```

## Distribution Errors

### Cycle Detected

**Symptoms**: Distribution fails with "circular dependency"

**Cause**: Asset depends on itself (A → B → A)

**Solution**: Check contribution graph
```cypher
MATCH path = (a:Asset)-[:CONTRIBUTED_TO*]->(a)
RETURN path
```

### Payout Sum Mismatch

**Symptoms**: Sum of payouts ≠ distribution amount

**Cause**: Floating point rounding (using float instead of Decimal)

**Solution**: Always use Decimal
```python
# Wrong
cost = 100.50  # float

# Right
from decimal import Decimal
cost = Decimal("100.50")
```

## Performance Issues

### Slow Distribution

**Symptoms**: Distribution takes >30 seconds

**Causes**:
1. Deep graph (>10 levels)
2. Many contributors (>1000)
3. Missing indexes

**Solutions**:
```sql
-- Add indexes
CREATE INDEX IF NOT EXISTS idx_events_asset ON contribution_events_ledger(asset_id);

-- Limit depth
POST /v1/distributions
{"max_depth": 5}  # Limit to 5 levels
```

### Database Connection Pool Exhausted

**Symptoms**: `asyncpg.exceptions.TooManyConnectionsError`

**Solution**: Increase pool size
```python
# config.py
DB_POOL_MIN_SIZE = 10
DB_POOL_MAX_SIZE = 50  # Increase from 20
```
EOF

cat > .claude/GLOSSARY.md << 'EOF'
# Glossary

**Asset**: Any generated entity (code, model, content, data) that tracks its creation lineage and can distribute value to contributors.

**Coherence**: A quality score (0.0 to 1.0) measuring how well a contribution aligns with network goals and quality standards.

**Coherence Multiplier**: Factor applied to cost (0.5 + coherence) that weights payout share. Range: 0.5x to 1.5x.

**Contribution Event**: An immutable record of work done, including cost, coherence score, and metadata.

**Contributor**: A person (HUMAN) or system (SYSTEM) that contributes to assets.

**Creation Distribution Ledger**: The complete DAG of all contributions to an asset, used for value distribution.

**Distribution**: The act of routing generated value back to contributors proportionally.

**Event Sourcing**: Storing state as a sequence of immutable events rather than current state.

**Graph Lineage**: The tree/DAG structure showing how an asset was created from contributions.

**Node Operator**: A contributor who provides hosting resources (API, storage, compute) to the network.

**Payout**: An individual payment to a contributor from a distribution.

**Resonance**: Network-level coherence measuring alignment across the entire system.

**Tool Attribution**: Attributing system/AI tool costs to the human who triggered them.

**Treasury**: Network's reserve fund for operational costs and distributions.

**Value Generation**: When an asset produces revenue or utility that can be distributed.

**Weighted Cost**: A contribution's cost multiplied by its coherence multiplier.
EOF

cat > .claude/CURSOR_WORKFLOWS.md << 'EOF'
# Cursor Workflows

## Generate New API Endpoint

**Prompt**:
```
Create a new FastAPI endpoint for listing all distributions with pagination.

Requirements:
- Route: GET /v1/distributions
- Query params: page (int), page_size (int, max 100), status filter
- Response: list of distributions with pagination metadata
- Include contributor names in results
- Add to api/routes/distributions.py
- Use async/await
- Validate with Pydantic
- Add error handling
```

**Files Created**:
- `api/routes/distributions.py` (updated)
- `models/distribution.py` (updated)

## Add Database Migration

**Prompt**:
```
Create an Alembic migration to add a 'reputation_score' column to contributors table.

Requirements:
- Column: reputation_score INTEGER DEFAULT 0
- Index on reputation_score for leaderboard queries
- Include upgrade and downgrade functions
- Follow existing migration pattern
```

**Command**:
```bash
cursor chat "Create Alembic migration for reputation_score column"
alembic revision --autogenerate -m "add_reputation_score"
alembic upgrade head
```

## Implement Distribution Method

**Prompt**:
```
Add a new distribution method 'TIME_WEIGHTED' that gives more weight to recent contributions.

Requirements:
- In services/distribution_engine.py
- Add TimeWeightedDistribution class
- Weight formula: cost × (0.5 + coherence) × (1 + days_ago / 365)
- Use exponential decay for very old contributions
- Add tests in tests/test_distribution.py
```
EOF

# Create reference JSON files
echo "  → Creating reference JSON files"

cat > .claude/reference/initial_contribution.json << 'EOF'
{
  "event_id": "uuid-seeker71-initial",
  "contributor_id": "uuid-seeker71",
  "asset_id": "uuid-coherence-network",
  "event_type": "PROJECT_INCEPTION",
  "cost_breakdown": {
    "human_labor": {
      "hours": 16,
      "hourly_rate": 150.00,
      "total": 2400.00
    },
    "tool_usage": {
      "cursor_pro_subscription": {
        "monthly_cost": 20.00,
        "days_used": 2,
        "prorated_cost": 1.33
      },
      "cursor_auto": {
        "requests": 500,
        "cost": 0.00,
        "note": "Included in Pro subscription, hit limit"
      }
    },
    "compute": {
      "hardware": "MacBook M4 Ultra",
      "hours": 16,
      "electricity": {
        "power_watts": 140,
        "rate_per_kwh": 0.15,
        "cost": 0.34
      },
      "depreciation": {
        "purchase_price": 7199.00,
        "useful_life_hours": 10000,
        "cost": 11.52
      },
      "total": 11.86
    },
    "total_cost": 2413.19
  },
  "resonance": {
    "code_quality_score": 0.85,
    "architecture_alignment": 1.0,
    "value_add_score": 1.0,
    "test_coverage": 0.3,
    "documentation_score": 0.7,
    "coherence_score": 0.92,
    "coherence_multiplier": 1.42
  },
  "timestamp": "2026-02-11T10:00:00Z"
}
EOF

cat > .claude/reference/distribution_example.json << 'EOF'
{
  "distribution_id": "uuid-dist-1",
  "asset_id": "uuid-coherence-network",
  "value_amount": 10000.00,
  "distribution_method": "COHERENCE_WEIGHTED",
  "contributors": [
    {
      "contributor_id": "uuid-seeker71",
      "name": "seeker71",
      "direct_cost": 2413.19,
      "coherence_score": 0.92,
      "coherence_multiplier": 1.42,
      "weighted_cost": 3426.73,
      "payout_share": 0.9622,
      "payout_amount": 9622.18
    },
    {
      "contributor_id": "uuid-urs-muff",
      "name": "Urs Muff",
      "direct_cost": 100.00,
      "coherence_score": 0.64,
      "coherence_multiplier": 1.14,
      "weighted_cost": 114.00,
      "payout_share": 0.0378,
      "payout_amount": 377.82
    }
  ],
  "total_weighted_cost": 3540.73,
  "total_distributed": 10000.00,
  "distribution_timestamp": "2026-02-13T10:00:00Z"
}
EOF

cat > .claude/reference/node_pricing_examples.json << 'EOF'
{
  "node_operators": [
    {
      "node_id": "uuid-node-hobbyist",
      "operator": "College Student",
      "setup": "$5/month VPS (free with GitHub Student Pack)",
      "pricing": {
        "api_request": 0.00002,
        "storage_gb_month": 0.005,
        "compute_hour": 0.008
      },
      "expected_revenue": {
        "10_percent_utilization": 5.00,
        "50_percent_utilization": 25.00,
        "90_percent_utilization": 45.00
      },
      "costs": 0.00,
      "profit_at_90_percent": 45.00
    },
    {
      "node_id": "uuid-node-pro",
      "operator": "Professional Developer",
      "setup": "$20/month VPS with monitoring",
      "pricing": {
        "api_request": 0.00005,
        "storage_gb_month": 0.010,
        "compute_hour": 0.015
      },
      "expected_revenue": {
        "10_percent_utilization": 25.00,
        "50_percent_utilization": 125.00,
        "90_percent_utilization": 225.00
      },
      "costs": 20.00,
      "profit_at_90_percent": 205.00
    }
  ]
}
EOF

echo ""
echo "=========================================="
echo "✅ Knowledge base generated successfully!"
echo "=========================================="
echo ""
echo "Files created in .claude/:"
echo "  ✓ README.md"
echo "  ✓ PROJECT_CONTEXT.md"
echo "  ✓ ARCHITECTURE.md"
echo "  ✓ CONTRIBUTION_GUIDE.md"
echo "  ✓ API_REFERENCE.md"
echo "  ✓ ECONOMIC_MODEL.md"
echo "  ✓ DATABASE_SCHEMAS.md"
echo "  ✓ EXAMPLES.md"
echo "  ✓ TROUBLESHOOTING.md"
echo "  ✓ GLOSSARY.md"
echo "  ✓ CURSOR_WORKFLOWS.md"
echo ""
echo "Reference files created:"
echo "  ✓ reference/initial_contribution.json"
echo "  ✓ reference/distribution_example.json"
echo "  ✓ reference/node_pricing_examples.json"
echo ""
echo "Next steps:"
echo "  1. Review generated files"
echo "  2. git add .claude/"
echo "  3. git commit -m 'Add Claude Project knowledge base'"
echo "  4. git push origin main"
echo "  5. Add files to your Claude Project"
echo ""
echo "Total size: ~80KB (2-3% of Claude's context window)"
echo ""
