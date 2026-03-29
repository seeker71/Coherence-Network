# coherence-mcp-server (Python)

**Give your AI agent native access to every idea, spec, contributor, and value chain in the Coherence Network.**

An [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) server that exposes the full Coherence Network API as 22 typed tools — so Claude, Cursor, Windsurf, or any MCP-compatible agent can browse ideas, look up specs, trace value lineage, link identities, and record contributions without writing a single API call.

```bash
# Install and run via uvx (recommended)
uvx coherence-mcp-server

# Or pip install
pip install coherence-mcp-server
coherence-mcp-server
```

No API key needed for reading. Works immediately against the live network.

---

## Setup

### Claude Desktop / Claude Code

Add to your MCP settings (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "coherence-network": {
      "command": "uvx",
      "args": ["coherence-mcp-server"],
      "env": {
        "COHERENCE_API_URL": "https://api.coherencycoin.com"
      }
    }
  }
}
```

Or with pip:

```json
{
  "mcpServers": {
    "coherence-network": {
      "command": "coherence-mcp-server"
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
      "command": "uvx",
      "args": ["coherence-mcp-server"]
    }
  }
}
```

### npm alternative

If you prefer Node.js: `npx coherence-mcp-server`

---

## Tools (22)

### Ideas — the portfolio engine

| Tool | What it does |
|------|-------------|
| `coherence_list_ideas` | Browse ideas ranked by ROI and free-energy score |
| `coherence_get_idea` | Full detail for one idea |
| `coherence_idea_progress` | Stage, tasks, CC staked, contributors |
| `coherence_select_idea` | Portfolio engine picks next highest-ROI idea |
| `coherence_showcase` | Validated, shipped ideas |
| `coherence_resonance` | Ideas generating the most energy right now |

### Specs

| Tool | What it does |
|------|-------------|
| `coherence_list_specs` | Specs with ROI metrics and value gaps |
| `coherence_get_spec` | Full spec: summary, implementation plan, ROI |

### Value lineage

| Tool | What it does |
|------|-------------|
| `coherence_list_lineage` | Lineage chains idea → spec → implementation → payout |
| `coherence_lineage_valuation` | Measured value, cost, and ROI ratio for a chain |

### Identity — 37 providers, zero registration

| Tool | What it does |
|------|-------------|
| `coherence_list_providers` | All providers in 6 categories |
| `coherence_link_identity` | Link GitHub, Discord, Ethereum, etc. |
| `coherence_lookup_identity` | Reverse lookup — find contributor by handle |
| `coherence_get_identities` | All linked identities for a contributor |

### Contributions

| Tool | What it does |
|------|-------------|
| `coherence_record_contribution` | Record work by name or provider identity |
| `coherence_contributor_ledger` | CC balance and contribution history |

### Network health & governance

| Tool | What it does |
|------|-------------|
| `coherence_status` | API health, uptime, idea count, federation nodes |
| `coherence_friction_report` | Where the pipeline struggles |
| `coherence_list_change_requests` | Open governance proposals |
| `coherence_list_federation_nodes` | Federated nodes and capabilities |

### Living Codex ontology

| Tool | What it does |
|------|-------------|
| `coherence_list_concepts` | Browse 184 universal concepts with 53 axes |
| `coherence_get_concept` | Full concept detail with typed relationship edges |
| `coherence_link_concepts` | Create typed relationships between concepts |

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COHERENCE_API_URL` | `https://api.coherencycoin.com` | API base URL. Override to point at a local node. |
| `COHERENCE_API_KEY` | *(none)* | API key for write operations. Reads work without a key. |

---

## The Coherence Network ecosystem

| Surface | Link |
|---------|------|
| **Web** | [coherencycoin.com](https://coherencycoin.com) |
| **API** | [api.coherencycoin.com/docs](https://api.coherencycoin.com/docs) |
| **CLI** | `npm i -g coherence-cli` → `cc help` |
| **MCP Server (npm)** | `npx coherence-mcp-server` |
| **MCP Server (PyPI)** | `uvx coherence-mcp-server` (this package) |
| **GitHub** | [github.com/seeker71/Coherence-Network](https://github.com/seeker71/Coherence-Network) |

---

## License

MIT
