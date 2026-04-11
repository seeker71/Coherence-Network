# Coherence Network

[![Thread Gates](https://github.com/seeker71/Coherence-Network/actions/workflows/thread-gates.yml/badge.svg)](https://github.com/seeker71/Coherence-Network/actions/workflows/thread-gates.yml)

An open intelligence platform that traces every idea from inception to payout — with fair attribution, coherence scoring, and federated trust.

<!-- include: docs/shared/lifecycle-diagram.md -->

## Quickstart (< 15 minutes)

```bash
git clone https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network
make dev-setup        # api venv + web npm install
make test             # ~8s flow-centric suite
make api-dev          # http://localhost:8000
make web-dev          # http://localhost:3000
```

## Your first 5 minutes

**Option A — no install, just browse:**

```bash
# See what ideas exist (live network, no key needed)
curl -s https://api.coherencycoin.com/api/ideas?limit=5 | python3 -m json.tool

# Check network health
curl -s https://api.coherencycoin.com/api/health | python3 -m json.tool
```

**Option B — install the CLI:**

```bash
npm i -g coherence-cli
cc status                    # network health, idea count, your identity
cc ideas                     # browse the portfolio ranked by ROI
cc idea <id>                 # deep-dive: scores, open questions, value gaps
```

**Option C — give your AI agent access:**

Add to your Claude/Cursor MCP config:

```json
{
  "mcpServers": {
    "coherence-network": {
      "command": "npx",
      "args": ["coherence-mcp-server"]
    }
  }
}
```

Then ask your agent: *"What ideas have the highest ROI right now?"*

## How to contribute

Every contribution — code, docs, review, design, community — is tracked and fairly attributed.

```bash
# Link your identity (37 providers: GitHub, Discord, Ethereum, Solana, ORCID, ...)
cc identity setup
cc identity link github your-handle

# Submit a new idea
cc share

# Record any contribution
cc contribute

# Or contribute via the API
curl -s https://api.coherencycoin.com/api/contributions/record \
  -X POST -H "Content-Type: application/json" \
  -d '{"provider":"github","provider_id":"your-handle","type":"code","amount_cc":5}'
```

### Contribute to this repo

```bash
git clone https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network
pip install -e api/.[dev]
python3 -m pytest api/tests/ -x -q    # 813+ tests
```

The workflow is: **Spec → Test → Implement → CI → Review → Merge**. Specs live in `specs/`. Tests are written before implementation. Human review is required before merge.

## How to exchange value

**Stake** on ideas you believe in. **Fork** ideas to take them new directions. **Trace** the full value chain from spark to payout.

```bash
cc stake <idea-id> 10       # stake 10 CC on an idea
cc fork <idea-id>           # fork and evolve it

# View the full value chain
curl -s https://api.coherencycoin.com/api/value-lineage/links?limit=5 | python3 -m json.tool

# Preview how payouts are distributed
curl -s https://api.coherencycoin.com/api/value-lineage/links/LINEAGE-ID/payout-preview \
  -X POST -H "Content-Type: application/json" \
  -d '{"total_value": 1000}' | python3 -m json.tool
```

## How governance works

Open governance — anyone can propose changes, anyone can vote. Federated instances operate independently.

```bash
# See open governance proposals
curl -s https://api.coherencycoin.com/api/governance/change-requests | python3 -m json.tool

# See federated nodes and their capabilities
curl -s https://api.coherencycoin.com/api/federation/nodes | python3 -m json.tool
```

## The five pillars

<!-- include: docs/shared/five-pillars.md -->

## Ecosystem

Every part of the network links to every other. Jump in wherever makes sense.

<!-- include: docs/shared/ecosystem-table.md -->

## Tech stack

- **API**: FastAPI (Python) — `api/`
- **Web**: Next.js 15 + shadcn/ui — `web/` — live at [coherencycoin.com](https://coherencycoin.com)
- **Graph**: Neo4j
- **Relational**: PostgreSQL (in-memory store in dev)
- **CLI**: Node.js — `cli/` — [npm: coherence-cli](https://www.npmjs.com/package/coherence-cli)
- **MCP**: Node.js — `mcp-server/` — [npm: coherence-mcp-server](https://www.npmjs.com/package/coherence-mcp-server)

## Documentation

- [Setup](docs/SETUP.md) · [Status](docs/STATUS.md) · [Deploy](docs/DEPLOY.md) · [Runbook](docs/RUNBOOK.md)
- [Spec Coverage](docs/SPEC-COVERAGE.md) · [Spec Tracking](docs/SPEC-TRACKING.md) · [Glossary](docs/GLOSSARY.md)
- [Join the Network](docs/JOIN-NETWORK.md) · [Model Routing](docs/MODEL-ROUTING.md)

## License

MIT
