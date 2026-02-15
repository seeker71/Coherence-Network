# Coherence Network

[![Test](https://github.com/seeker71/Coherence-Network/actions/workflows/test.yml/badge.svg)](https://github.com/seeker71/Coherence-Network/actions/workflows/test.yml)
[![API](https://img.shields.io/badge/API-Live-green)](https://coherence-network-production.up.railway.app/api/health)

**Intelligence platform for open-source ecosystem health, contribution tracking, and fair value distribution.**

Coherence Network analyzes OSS projects, tracks contributor impact, scores contribution quality, and calculates fair payouts weighted by coherence—enabling data-driven decisions about where to invest time, money, and trust.

---

## What Can You Do With This?

### 🔍 Analyze OSS Project Health
Query coherence scores, dependencies, and contributor patterns for any OSS project:
```bash
# Get project details and coherence metrics
curl https://coherence-network-production.up.railway.app/api/projects/npm/react

# Search for projects by ecosystem
curl https://coherence-network-production.up.railway.app/api/search?q=graphql&ecosystem=npm
```

### 📊 Track Contributions & Impact
Record contributions (time, code, effort) with automatic coherence scoring:
```bash
# Record a contribution
curl -X POST https://coherence-network-production.up.railway.app/api/contributions \
  -H "Content-Type: application/json" \
  -d '{
    "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
    "asset_id": "660e8400-e29b-41d4-a716-446655440000",
    "cost_amount": 150.00,
    "metadata": {"has_tests": true, "has_docs": true}
  }'

# Get all contributions to an asset
curl https://coherence-network-production.up.railway.app/api/assets/{asset_id}/contributions
```

### 💰 Calculate Fair Value Distribution
Distribute value proportionally to contributions, weighted by quality:
```bash
# Calculate payouts for an asset
curl -X POST https://coherence-network-production.up.railway.app/api/distributions \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "660e8400-e29b-41d4-a716-446655440000",
    "value_amount": 1000.00
  }'

# Returns: proportional payouts based on (cost × coherence_score)
```

### 🚦 Validate Release Readiness
Check if PRs meet quality gates before merging:
```bash
# Check if PR is ready for production
curl "https://coherence-network-production.up.railway.app/api/gates/pr-to-public?branch=feature-branch"

# Verify merged commit meets deployment contract
curl "https://coherence-network-production.up.railway.app/api/gates/merged-contract?sha=abc123"
```

### 💡 Prioritize Ideas by ROI
Rank ideas using free energy scoring (value × confidence / cost):
```bash
# List ideas ranked by ROI
curl https://coherence-network-production.up.railway.app/api/ideas

# Update idea after validation
curl -X PATCH https://coherence-network-production.up.railway.app/api/ideas/{id} \
  -H "Content-Type: application/json" \
  -d '{"actual_value": 85.0, "manifestation_status": "validated"}'
```

---

## Quick Start

### 1️⃣ Try the Live API
The API is live at **[coherence-network-production.up.railway.app](https://coherence-network-production.up.railway.app/api/health)**

```bash
# Check API health
curl https://coherence-network-production.up.railway.app/api/health

# Explore the full API docs (interactive Swagger UI)
open https://coherence-network-production.up.railway.app/docs
```

### 2️⃣ Run Locally

**Prerequisites**: Python 3.11+, PostgreSQL, Neo4j

```bash
# Clone and install
git clone https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network/api
pip install -r requirements.txt

# Start the API
uvicorn app.main:app --reload --port 8000

# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### 3️⃣ Run the Autonomous Pipeline
```bash
# Start the overnight pipeline (autonomous execution)
cd api && ./scripts/run_autonomous.sh

# Monitor pipeline health
curl http://localhost:8000/api/agent/metrics
```

---

## How It Works

### Coherence Scoring
Contributions are automatically scored (0.0–1.0) based on quality signals:
- **+0.2** for including tests
- **+0.2** for documentation
- **+0.1** for low complexity
- Baseline: 0.5

Higher coherence = higher value multiplier in distributions.

### Fair Distribution Algorithm
```
weighted_cost = cost_amount × (0.5 + coherence_score)
payout = (contributor_weighted / total_weighted) × value_amount
```

Contributors with higher coherence get proportionally larger payouts.

### Free Energy Prioritization
Ideas ranked by: `(potential_value × confidence) / (estimated_cost + resistance_risk)`

Surfaces highest-ROI opportunities first.

---

## Use Cases

- **🏢 Organizations**: Track internal OSS contributions, calculate fair bonuses
- **💸 Grant Programs**: Data-driven allocation based on contributor impact
- **🔬 Researchers**: Analyze OSS ecosystem health and contributor patterns
- **🚀 Startups**: Prioritize feature development by ROI
- **🤝 DAOs**: Transparent value distribution to contributors

---

## Tech Stack

- **API**: FastAPI (Python)
- **Web**: Next.js 15 ([coherence-network.vercel.app](https://coherence-network.vercel.app))
- **Graph DB**: Neo4j
- **Relational DB**: PostgreSQL
- **Data Sources**: deps.dev, Libraries.io, GitHub API

---

## API Reference

Full API documentation available at:
- **Production**: [coherence-network-production.up.railway.app/docs](https://coherence-network-production.up.railway.app/docs)
- **Local**: http://localhost:8000/docs

### Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | API health check |
| `GET /api/projects/{ecosystem}/{name}` | Project details & coherence |
| `POST /api/contributions` | Record contribution |
| `POST /api/distributions` | Calculate fair payouts |
| `GET /api/ideas` | List ideas ranked by ROI |
| `GET /api/gates/pr-to-public` | Check PR readiness |
| `GET /api/contributors` | List contributors |
| `GET /api/assets` | List assets |

Full specs available in [`specs/`](specs/) directory.

---

## Development

### Workflow
**Spec → Test → Implement → CI → Review → Merge**

1. Specs in [`specs/`](specs/) define API contracts
2. Tests are written before implementation
3. Implementation satisfies tests
4. CI validates correctness
5. Human review before merge

### Contributing

We use a spec-driven development process. To contribute:

1. Check existing specs in [`specs/`](specs/)
2. Propose new specs for missing features
3. Tests must pass before merge
4. Follow [CLAUDE.md](CLAUDE.md) conventions

### Documentation

- [Setup Guide](docs/SETUP.md) — Local development setup
- [Status](docs/STATUS.md) — Implementation status
- [Plan](docs/PLAN.md) — Project roadmap
- [Spec Coverage](docs/SPEC-COVERAGE.md) — Spec-to-implementation mapping
- [Runbook](docs/RUNBOOK.md) — Operational procedures
- [Deploy](docs/DEPLOY.md) — Deployment instructions

---

## Deployments

| Service | Platform | URL | Status |
|---------|----------|-----|--------|
| **API** | Railway | [coherence-network-production.up.railway.app](https://coherence-network-production.up.railway.app) | ✅ Live |
| **Web** | Vercel | [coherence-network.vercel.app](https://coherence-network.vercel.app) | ✅ Live |

---

## License

MIT

---

## Questions?

- 📖 Check the [docs/](docs/) directory
- 🐛 Report issues on [GitHub Issues](https://github.com/seeker71/Coherence-Network/issues)
- 💬 Start a [Discussion](https://github.com/seeker71/Coherence-Network/discussions)
