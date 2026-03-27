<!-- AUTO-GENERATED from README.template.md. Edit the template, not this file. -->
# coherence-mcp-server

**Give your AI agent native access to every idea, spec, contributor, and value chain in the Coherence Network.**

An [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) server that exposes the full Coherence Network API as 20 typed tools — so Claude, Cursor, Windsurf, or any MCP-compatible agent can browse ideas, look up specs, trace value lineage, link identities, and record contributions without writing a single API call.

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
- **Govern** — view change requests, federation nodes, and network health

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

## Tools (20)

### Ideas — the portfolio engine

| Tool | What it does |
|------|-------------|
| `coherence_list_ideas` | Browse ideas ranked by ROI and free-energy score. Filter with `search`, limit with `limit`. |
| `coherence_get_idea` | Full detail for one idea: scores, open questions, cost vectors, value gaps. |
| `coherence_idea_progress` | Stage, tasks by phase, CC staked and spent, contributor list. |
| `coherence_select_idea` | Let the portfolio engine pick the next highest-ROI idea. `temperature` controls explore vs exploit. |
| `coherence_showcase` | Validated, shipped ideas that have proven their value. |
| `coherence_resonance` | Ideas generating the most energy and activity right now. |

### Specs — from vision to blueprint

| Tool | What it does |
|------|-------------|
| `coherence_list_specs` | Specs with ROI metrics and value gaps. Searchable. |
| `coherence_get_spec` | Full spec: summary, implementation plan, pseudocode, estimated ROI. |

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

### Network health & governance

| Tool | What it does |
|------|-------------|
| `coherence_status` | API health, uptime, idea count, federation node count. |
| `coherence_friction_report` | Where the pipeline struggles — friction signals over a time window. |
| `coherence_list_change_requests` | Open governance proposals. |
| `coherence_list_federation_nodes` | Federated nodes and their capabilities. |

---

## Example conversations

Once connected, you can ask your agent things like:

- *"What ideas have the highest ROI right now?"*
- *"Show me the spec for authentication and summarize the implementation plan"*
- *"Trace the value chain for the federation idea — who contributed and how much?"*
- *"Link my GitHub identity and record a code contribution for the CLI work I did"*
- *"What's the network friction report for the last 30 days?"*
- *"Pick the next best idea for me to work on"*

The agent calls the right tools, gets structured data, and responds naturally.

---

## How coherence scoring works

Every idea and contribution is scored 0.0–1.0:

- **1.0** — Tests pass, docs clear, implementation simple, value proven
- **0.5** — Partial coverage, work in progress
- **0.0** — No evidence of quality or value

Payouts are weighted by coherence. Higher-quality work earns proportionally more. The score is a signal, not a grade — it tells the network how much trust the work has earned.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COHERENCE_API_URL` | `https://api.coherencycoin.com` | API base URL. Override to point at a local node. |
| `COHERENCE_API_KEY` | *(none)* | Required for write operations (governance, spec creation, federation). Reads work without a key. |

---

## The five pillars

| Pillar | What it means for agents |
|--------|-------------------------|
| **Traceability** | Every tool call traces back to real ideas, real specs, real contributors. |
| **Trust** | Coherence scores give agents objective quality signals — no guessing. |
| **Freedom** | Federated nodes, open governance. No single point of control. |
| **Uniqueness** | Every entity is uniquely identified. No duplicate ideas, no ambiguous specs. |
| **Collaboration** | Agents and humans contribute side by side, credited fairly. |

---

## The Coherence Network ecosystem

Every part of the network links to every other. Jump in wherever makes sense.

| Surface | What it is | Link |
|---------|-----------|------|
| **Web** | Browse ideas, specs, and contributors visually | [coherencycoin.com](https://coherencycoin.com) |
| **API** | 100+ endpoints, full OpenAPI docs, the engine behind everything | [api.coherencycoin.com/docs](https://api.coherencycoin.com/docs) |
| **CLI** | Terminal-first access — `npm i -g coherence-cli` then `cc help` | [npm: coherence-cli](https://www.npmjs.com/package/coherence-cli) |
| **MCP Server** | This package — 20 typed tools for AI agents | [npm: coherence-mcp-server](https://www.npmjs.com/package/coherence-mcp-server) |
| **OpenClaw Skill** | Auto-triggers in any OpenClaw instance for ideas, specs, coherence | [ClawHub: coherence-network](https://clawhub.com/skills/coherence-network) |
| **GitHub** | Source code, specs, issues, and contribution tracking | [github.com/seeker71/Coherence-Network](https://github.com/seeker71/Coherence-Network) |

---

## Get involved

Coherence Network is open source. Every contribution — human or agent — is tracked and fairly attributed.

- **Start exploring**: Add the MCP server to your agent and ask *"What ideas need work?"*
- **GitHub**: [github.com/seeker71/Coherence-Network](https://github.com/seeker71/Coherence-Network)

---

## License

MIT
