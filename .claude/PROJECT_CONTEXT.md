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
