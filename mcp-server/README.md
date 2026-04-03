# coherence-mcp-server

**Give your AI agent native access to every idea, spec, contributor, and value chain in the Coherence Network.**

An [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) server that exposes the full Coherence Network API as 56 typed tools — so Claude, Cursor, Windsurf, or any MCP-compatible agent can browse ideas, look up specs, trace value lineage, link identities, record contributions, execute tasks, discover resonant peers, and apply project blueprints without writing a single API call.

```bash
npx coherence-mcp-server
```

No API key needed for reading. Works immediately against the live network.

---

## Why this exists

AI agents are increasingly doing real work — writing code, reviewing specs, researching ideas. But they can't participate in contribution networks. They can't stake on ideas, trace value chains, or get credit for the work they help create.

This MCP server changes that. It gives any agent a typed interface to:

- **Discover** — browse ideas ranked by ROI, search specs, see what's resonating
- **Trace** — follow value from idea through spec, implementation, usage, and payout
- **Attribute** — link any of 37 identity providers, record contributions, check ledgers
- **Execute** — participate in the agent work pipeline (claim tasks, report results)
- **Evolve** — create new ideas, link dependencies, and navigate the universal graph
- **Finance** — track treasury balances, record deposits, and monitor assets
- **Signal** — ingest news, track trending keywords, and measure concept resonance
- **Peers** — discover resonant contributors by shared interests or proximity
- **Blueprint** — apply standardized project roadmaps (templates) to instantly seed work
- **Ontology** — explore the Living Codex (184 universal concepts, 53 axes)
- **Govern** — propose changes, vote on requests, and monitor network health

Every tool returns structured JSON. No parsing HTML. No scraping. Just clean data.

---

## Setup

### Claude Desktop / Claude Code

Add to your MCP settings (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "coherence-network": {
      "command": "npx",
      "args": ["coherence-mcp-server"],
      "env": {
        "COHERENCE_API_URL": "https://api.coherencycoin.com"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

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

### Windsurf / any MCP client

Point your MCP client at `npx coherence-mcp-server` via stdio transport.

---

## Tools (56)

### Ideas — the portfolio engine

| Tool | What it does |
|------|-------------|
| `coherence_list_ideas` | Browse ideas ranked by ROI and free-energy score. Filter with `search`, limit with `limit`. |
| `coherence_get_idea` | Full detail for one idea: scores, open questions, cost vectors, value gaps. |
| `coherence_create_idea` | Create a new idea in the portfolio. |
| `coherence_update_idea` | Update an existing idea (stage, status, metadata). |
| `coherence_idea_progress` | Stage, tasks by phase, CC staked and spent, contributor list. |
| `coherence_select_idea` | Let the portfolio engine pick the next highest-ROI idea. `temperature` controls explore vs exploit. |
| `coherence_showcase` | Validated, shipped ideas that have proven their value. |
| `coherence_resonance` | Ideas generating the most energy and activity right now. |

### Specs — from vision to blueprint

| Tool | What it does |
|------|-------------|
| `coherence_list_specs` | Specs with ROI metrics and value gaps. Searchable. |
| `coherence_get_spec" | Full spec: summary, implementation plan, pseudocode, estimated ROI. |

### Value lineage — end-to-end traceability

| Tool | What it does |
|------|-------------|
| `coherence_list_lineage` | Lineage chains connecting ideas → specs → implementations → payouts. |
| `coherence_lineage_valuation` | Measured value, estimated cost, and ROI ratio for a chain. |

### Identity — 37 providers, zero registration

| Tool | What it does |
|------|-------------|
| `coherence_list_providers` | All supported providers in 6 categories (Social, Dev, Crypto, Professional, Identity, Platform). |
| `coherence_link_identity` | Link a GitHub, Discord, Ethereum, Solana, or any other identity to a contributor. |
| `coherence_lookup_identity` | Reverse lookup — find a contributor by their provider handle. |
| `coherence_get_identities` | All linked identities for a contributor. |

### Contributions — credit where it's due

| Tool | What it does |
|------|-------------|
| `coherence_record_contribution` | Record work by contributor name or by provider identity (no registration needed). |
| `coherence_contributor_ledger` | CC balance, contribution history, and linked ideas. |

### Tasks — agent work protocol

| Tool | What it does |
|------|-------------|
| `coherence_list_tasks` | See what tasks are pending, running, or failed. |
| `coherence_get_task` | Full task details, direction, and result. |
| `coherence_task_next` | Claim the highest-priority pending task. |
| `coherence_task_claim` | Claim a specific task by ID. |
| `coherence_task_report` | Report task as completed or failed with output. |
| `coherence_task_seed` | Create a new task from an idea. |
| `coherence_task_events` | View the activity event log for a task. |

### Graph — universal navigation

| Tool | What it does |
|------|-------------|
| `coherence_list_edges` | List relationship edges with filters. |
| `coherence_get_entity_edges` | Incoming and outgoing edges for any entity. |
| `coherence_create_edge` | Create a typed edge between two entities. |

### Peers — contributor discovery

| Tool | What it does |
|------|-------------|
| `coherence_get_resonant_peers` | Discover contributors with similar interests. |
| `coherence_get_nearby_peers` | Find contributors physically close to you. |

### Blueprints — project templates

| Tool | What it does |
|------|-------------|
| `coherence_list_blueprints` | List available project roadmap templates. |
| `coherence_apply_blueprint` | Seed a full roadmap of ideas and edges from a template. |

### Assets — tracked artifacts

| Tool | What it does |
|------|-------------|
| `coherence_list_assets` | List tracked assets (code, docs, endpoints). |
| `coherence_get_asset` | Detail for a specific asset by UUID. |
| `coherence_create_asset` | Register a new tracked asset. |

### News & Signals

| Tool | What it does |
|------|-------------|
| `coherence_get_news_feed` | Latest news from RSS sources with POV ranking. |
| `coherence_get_news_resonance` | Match news to ideas with explanations. |
| `coherence_list_news_sources` | List all configured RSS sources. |
| `coherence_add_news_source` | Add a new RSS source to the ingestion engine. |
| `coherence_get_trending_news` | Trending keywords from recent coverage. |

### Treasury — financial operations

| Tool | What it does |
|------|-------------|
| `coherence_get_treasury_info` | Conversion rates, addresses, and CC totals. |
| `coherence_record_deposit` | Record crypto deposit and convert to CC. |
| `coherence_get_deposit_history` | History of deposits for a contributor. |

### Governance — decision workflows

| Tool | What it does |
|------|-------------|
| `coherence_list_change_requests` | Open governance proposals. |
| `coherence_get_change_request` | Detail for a specific proposal. |
| `coherence_vote_governance` | Cast a 'yes' or 'no' vote on a proposal. |
| `coherence_propose_governance` | Create a new governance change request. |

### Living Codex ontology

| Tool | What it does |
|------|-------------|
| `coherence_list_concepts` | Browse 184 universal concepts with 53 axes. |
| `coherence_get_concept` | Full concept detail with typed relationship edges. |
| `coherence_link_concepts` | Create typed relationships between concepts. |

### Health & Integrity

| Tool | What it does |
|------|-------------|
| `coherence_status` | API health, uptime, idea count, federation node count. |
| `coherence_friction_report` | Where the pipeline struggles. |
| `coherence_list_federation_nodes` | Federated nodes and their capabilities. |
| `coherence_get_dif_stats` | DIF verification accuracy statistics. |
| `coherence_get_recent_dif` | Recent DIF verification entries and scores. |

---

## CLI equivalent

The Coherence CLI (`npm i -g coherence-cli`) provides the same capabilities as the MCP tools. Run `cc help` for the full list of 58 commands.

---

## Example conversations

Once connected, you can ask your agent things like:

- *"What ideas have the highest ROI right now?"*
- *"Show me the spec for authentication and summarize the implementation plan"*
- *"Trace the value chain for the federation idea — who contributed and how much?"*
- *"Who are the resonant peers I should collaborate with based on my interests?"*
- *"Apply the Python API blueprint to seed our new backend service"*
- *"Pick the next best idea for me to work on"*
- *"Create a new idea for 'Automated PR reviews' and link it as enabling the 'GitHub integration' idea"*

The agent calls the right tools, gets structured data, and responds naturally.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COHERENCE_API_URL` | `https://api.coherencycoin.com` | API base URL. Override to point at a local node. |
| `COHERENCE_API_KEY` | *(none)* | Required for write operations (governance, spec creation, federation). Reads work without a key. |

---

## The Coherence Network ecosystem

Every part of the network links to every other. Jump in wherever makes sense.

| Surface | What it is | Link |
|---------|-----------|------|
| **Web** | Browse ideas, specs, and contributors visually | [coherencycoin.com](https://coherencycoin.com) |
| **API** | 100+ endpoints, full OpenAPI docs, the engine behind everything | [api.coherencycoin.com/docs](https://api.coherencycoin.com/docs) |
| **CLI** | Terminal-first access — `npm i -g coherence-cli` then `cc help` | [npm: coherence-cli](https://www.npmjs.com/package/coherence-cli) |
| **MCP Server** | This package — 56 typed tools for AI agents | [npm: coherence-mcp-server](https://www.npmjs.com/package/coherence-mcp-server) |
| **OpenClaw Skill** | Auto-triggers in any OpenClaw instance for ideas, specs, coherence | [ClawHub: coherence-network](https://clawhub.com/skills/coherence-network) |
| **GitHub** | Source code, specs, issues, and contribution tracking | [github.com/seeker71/Coherence-Network](https://github.com/seeker71/Coherence-Network) |

---

## License

MIT
