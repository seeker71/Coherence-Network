<!-- AUTO-GENERATED from README.template.md. Edit the template, not this file. -->
# Coherence Network

[![Thread Gates](https://github.com/seeker71/Coherence-Network/actions/workflows/thread-gates.yml/badge.svg)](https://github.com/seeker71/Coherence-Network/actions/workflows/thread-gates.yml)

An open intelligence platform that traces every idea from inception to payout — with fair attribution, coherence scoring, and federated trust.

```
Idea → Research → Spec → Implementation → Review → Usage → Payout
       ↑                                                    ↓
       └────────── coherence scores at every stage ─────────┘
```

Every stage is scored for **coherence** (0.0–1.0) — measuring test coverage, documentation quality, and implementation simplicity. Contributors are paid proportionally to the energy they invested and the coherence they achieved.

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

**Option B — install the CLI (v0.8.0 — 54 commands across 22 modules):**

```bash
npm i -g coherence-cli
cc status                    # network health, idea count, your identity
cc ideas                     # browse the portfolio ranked by ROI
cc idea <id>                 # deep-dive: scores, open questions, value gaps
```

<details>
<summary>Full CLI command list (54 commands)</summary>

| Category | Commands |
|----------|----------|
| **Core** | `cc status`, `cc help`, `cc inbox`, `cc resonance` |
| **Ideas** | `cc ideas`, `cc idea <id>`, `cc share`, `cc stake <id> <cc>`, `cc fork <id>` |
| **Specs** | `cc specs`, `cc spec <id>` |
| **Identity** | `cc identity`, `cc identity setup`, `cc identity link <provider> <handle>`, `cc identity unlink <provider>`, `cc identity lookup <provider> <handle>` |
| **Contributors** | `cc contributors`, `cc contributor <id>`, `cc contributor <id> contributions` |
| **Contributions** | `cc contribute` |
| **Assets** | `cc assets`, `cc asset <id>`, `cc asset create <type> <desc>` |
| **News** | `cc news`, `cc news trending`, `cc news sources`, `cc news source add <url> <name>`, `cc news resonance [contributor]` |
| **Treasury** | `cc treasury`, `cc treasury deposits [contributor]`, `cc treasury deposit <amount> <asset>` |
| **Value lineage** | `cc lineage`, `cc lineage <id>`, `cc lineage <id> valuation`, `cc lineage <id> payout <amount>` |
| **Governance** | `cc governance`, `cc governance <id>`, `cc governance vote <id> <yes\|no>`, `cc governance propose <title> <desc>` |
| **Nodes** | `cc nodes`, `cc msg <node> <text>`, `cc cmd <node> update\|status\|diagnose\|restart\|ping` |
| **Services** | `cc services`, `cc service <id>`, `cc services health`, `cc services deps` |
| **Friction** | `cc friction`, `cc friction events`, `cc friction categories` |
| **Providers** | `cc providers`, `cc providers stats` |
| **Traceability** | `cc trace`, `cc trace coverage`, `cc trace idea <id>`, `cc trace spec <id>` |
| **Diagnostics** | `cc diag`, `cc diag health`, `cc diag issues`, `cc diag runners`, `cc diag visibility` |

</details>

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

| Pillar | In practice |
|--------|-------------|
| **Traceability** | Every unit of value is traceable from idea through spec, implementation, usage, and payout. Nothing is lost. |
| **Trust** | Coherence scores (0.0–1.0) replace subjective judgement with measurable quality. |
| **Freedom** | Fork any idea. Run your own node. Vote on governance. No gatekeepers. |
| **Uniqueness** | Every idea, spec, and contribution is uniquely identified, scored, and ranked. |
| **Collaboration** | Multi-contributor attribution with coherence-weighted payouts. Fair by design. |

## Ecosystem

Every part of the network links to every other. Jump in wherever makes sense.

| Surface | What it is | Link |
|---------|-----------|------|
| **Web** | Browse ideas, specs, contributors, and value chains visually | [coherencycoin.com](https://coherencycoin.com) |
| **API** | 100+ endpoints with full OpenAPI docs — the engine behind everything | [api.coherencycoin.com/docs](https://api.coherencycoin.com/docs) |
| **CLI** | Terminal-first access — `npm i -g coherence-cli` then `cc help` | [npm: coherence-cli](https://www.npmjs.com/package/coherence-cli) |
| **MCP Server** | 20 typed tools for AI agents (Claude, Cursor, Windsurf) | [npm: coherence-mcp-server](https://www.npmjs.com/package/coherence-mcp-server) |
| **OpenClaw Skill** | Auto-triggers inside any OpenClaw instance | [ClawHub: coherence-network](https://clawhub.com/skills/coherence-network) |
| **Join the Network** | Run a node and contribute compute | [JOIN-NETWORK.md](docs/JOIN-NETWORK.md) |

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
