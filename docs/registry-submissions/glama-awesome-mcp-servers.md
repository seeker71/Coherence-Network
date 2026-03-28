# Glama / awesome-mcp-servers PR Template

## Target repo
https://github.com/punkpeye/awesome-mcp-servers

## PR title
Add coherence-mcp-server — 20 tools for ideas, value chains, identity, and attribution

## PR body

### What is this?

`coherence-mcp-server` is an MCP server for the [Coherence Network](https://coherencycoin.com) — an open intelligence platform that traces every idea from inception to payout with fair attribution and coherence scoring.

### Entry to add

Under **"Productivity / Collaboration"** (or **"Project Management"**) section:

```markdown
- [coherence-mcp-server](https://github.com/seeker71/Coherence-Network/tree/main/mcp-server) - 20 typed tools for AI agents to browse ideas, trace value chains, link identities, record contributions, and explore federated nodes on the Coherence Network. Works with Claude, Cursor, Windsurf, and any MCP client. `npm install coherence-mcp-server`
```

### npm package

https://www.npmjs.com/package/coherence-mcp-server

### Tool list (20 tools)

| Tool | Description |
|------|-------------|
| `coherence_list_ideas` | Browse ideas sorted by free energy score |
| `coherence_get_idea` | Get idea details including tasks and progress |
| `coherence_idea_progress` | Get progress breakdown for an idea |
| `coherence_select_idea` | Auto-select the highest-ROI idea to work on next |
| `coherence_showcase` | Get showcase of highest-value validated ideas |
| `coherence_resonance` | Get recent network activity and resonance signals |
| `coherence_list_specs` | Browse registered feature specs |
| `coherence_get_spec` | Get spec details including implementation summary |
| `coherence_list_lineage` | List value lineage links connecting ideas to payouts |
| `coherence_lineage_valuation` | Get ROI valuation for a lineage link |
| `coherence_list_providers` | List available AI provider execution statistics |
| `coherence_link_identity` | Link external identity (GitHub, Discord, ETH, etc.) |
| `coherence_lookup_identity` | Reverse-lookup a contributor by provider identity |
| `coherence_get_identities` | Get all linked identities for a contributor |
| `coherence_record_contribution` | Record a contribution and earn coherence credits |
| `coherence_contributor_ledger` | Get full contribution ledger for a contributor |
| `coherence_status` | Check API health and network operational status |
| `coherence_friction_report` | Surface friction signals and runtime telemetry |
| `coherence_list_change_requests` | List open governance change requests |
| `coherence_list_federation_nodes` | List all federation compute nodes |

### MCP client config

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

No API key required for read operations. Full attribution and contribution recording available with identity linking.

---

## How to submit

1. Fork https://github.com/punkpeye/awesome-mcp-servers
2. Add the entry above in the appropriate section of `README.md`
3. Open a PR with the title and body above
4. Paste the PR URL into `docs/REGISTRY_SUBMISSIONS.md`
