# Registry Submissions — coherence-mcp-server / coherence-network

Tracks the status of all MCP server and skill registry submissions for the Coherence Network.
Updated manually when submissions are made or listings go live.

Spec: [idea-4deb5bd7c800](../specs/idea-4deb5bd7c800.md)

---

## MCP Server Registries

| Registry | Type | Status | Listing URL | Submitted | Live Date | Notes |
|----------|------|--------|-------------|-----------|-----------|-------|
| Smithery | MCP | pending | — | — | — | Submit at https://smithery.ai/submit; auto-discovers smithery.yaml |
| Glama (awesome-mcp-servers) | MCP | pending | — | — | — | PR to https://github.com/punkpeye/awesome-mcp-servers |
| PulseMCP | MCP | pending | — | — | — | Form at https://pulsemcp.com/submit |
| mcp.so | MCP | pending | — | — | — | Check https://mcp.so for PR vs form process |

## Skill Registries

| Registry | Type | Status | Listing URL | Submitted | Live Date | Notes |
|----------|------|--------|-------------|-----------|-----------|-------|
| skills.sh | Skill | pending | — | — | — | Check https://skills.sh for PR vs form process |
| askill.sh | Skill | pending | — | — | — | Check https://askill.sh for contribution docs |

---

## Status Values

| Value | Meaning |
|-------|---------|
| `pending` | Not yet submitted |
| `submitted` | Submission made, awaiting review/merge |
| `live` | Listing publicly visible at Listing URL |
| `rejected` | Submission declined (see Notes column for reason) |

---

## Submission Artefacts

Ready-to-use submission materials are in `docs/registry-submissions/`:

- `smithery-submission.md` — Smithery instructions
- `glama-awesome-mcp-servers.md` — PR body template for awesome-mcp-servers
- `pulsemcp-submission.json` — PulseMCP form fields
- `mcpso-submission.md` — mcp.so form fields
- `skills-sh-submission.md` — skills.sh submission instructions
- `askill-sh-submission.md` — askill.sh submission instructions

---

## Install / Download Metrics

Consolidated counts are available from the API:

```bash
curl -s https://api.coherencycoin.com/api/registry/metrics | python3 -m json.tool
```

See the [registry metrics API spec](../specs/idea-4deb5bd7c800.md#r3--registry-metrics-api) for details.
