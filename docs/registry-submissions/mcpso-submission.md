# mcp.so Submission — coherence-mcp-server

## Submission target
https://mcp.so (check current submission process — may be form or GitHub PR)

## Package metadata

| Field | Value |
|-------|-------|
| Name | coherence-mcp-server |
| npm | `coherence-mcp-server` |
| GitHub | https://github.com/seeker71/Coherence-Network |
| Homepage | https://coherencycoin.com |
| License | MIT |
| Install | `npx coherence-mcp-server` |
| Tools | 20 |
| Auth required | No (read-only); optional for writes |

## Short description (150 chars)

20 tools for AI agents: browse ideas, trace value chains, link identities, record contributions. Open intelligence platform with fair attribution.

## Long description

coherence-mcp-server gives AI agents (Claude, Cursor, Windsurf) direct access to the Coherence Network — an open platform that tracks every idea from the moment it's captured through research, spec, implementation, usage, and payout.

**What agents can do:**
- Browse and rank ideas by ROI and free-energy score
- Trace the full value chain: idea → spec → implementation → usage → payout
- Link external identities (GitHub, Discord, Ethereum, 37+ providers)
- Record contributions and earn coherence credits
- Explore federation nodes and governance change requests
- Surface friction signals and runtime telemetry

**No API key required** for read operations. Identity linking unlocks contribution recording.

## MCP config

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

## After submission
Record the listing URL in `docs/REGISTRY_SUBMISSIONS.md` under the mcp.so row.
