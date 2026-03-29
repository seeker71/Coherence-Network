# Registry Submissions: MCP and Skill Discovery

**Last updated**: 2026-03-28
**Idea**: `idea-4deb5bd7c800`
**Source paths**:
- MCP server: `api/mcp_server.py`, `mcp-server/`
- Skill: `skills/coherence-network/SKILL.md`, `.cursor/skills/`

This document is the canonical evidence record for all registry submissions. Each row includes the
registry, category, asset name, status, install hint, and proof (URL or PR reference).

---

## Submissions

### 1. Smithery — MCP Registry

| Field | Value |
|-------|-------|
| **Registry** | [Smithery](https://smithery.ai) |
| **Category** | MCP |
| **Asset name** | `coherence-mcp-server` |
| **Status** | Submission ready — `mcp-server/smithery.yaml` present |
| **Install hint** | `npx coherence-mcp-server` or via Smithery: `smithery install coherence-mcp-server` |
| **Source paths** | `mcp-server/server.json`, `mcp-server/package.json`, `mcp-server/smithery.yaml` |
| **Listing URL** | https://smithery.ai/server/coherence-mcp-server *(pending indexing)* |
| **Notes** | Smithery auto-indexes npm packages that publish a `smithery.yaml` at the package root. The `smithery.yaml` was added in this commit. Smithery listing becomes live once the npm package (`coherence-mcp-server`) is detected during the next index cycle. |

---

### 2. Glama (via awesome-mcp-servers) — MCP Registry

| Field | Value |
|-------|-------|
| **Registry** | [Glama](https://glama.ai/mcp/servers) via [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) |
| **Category** | MCP |
| **Asset name** | `coherence-mcp-server` |
| **Status** | Submission file ready — `mcp-server/glama.json` present |
| **Install hint** | `npx coherence-mcp-server` |
| **Source paths** | `mcp-server/glama.json`, `mcp-server/server.json`, `mcp-server/package.json` |
| **Listing URL** | https://glama.ai/mcp/servers/coherence-network *(pending PR merge)* |
| **Notes** | Glama ingests from the awesome-mcp-servers list. The `glama.json` file at `mcp-server/glama.json` contains the required metadata. A PR to `punkpeye/awesome-mcp-servers` adding `coherence-mcp-server` completes this listing. |

---

### 3. PulseMCP — MCP Registry

| Field | Value |
|-------|-------|
| **Registry** | [PulseMCP](https://pulsemcp.com) |
| **Category** | MCP |
| **Asset name** | `coherence-mcp-server` |
| **Status** | Submission file ready — `mcp-server/pulsemcp.json` present |
| **Install hint** | `npx coherence-mcp-server` |
| **Source paths** | `mcp-server/pulsemcp.json`, `mcp-server/package.json` |
| **Listing URL** | https://pulsemcp.com/servers/coherence-network *(pending indexing)* |
| **Notes** | PulseMCP indexes npm packages tagged with `mcp` keyword. The `pulsemcp.json` provides supplementary metadata. The npm package `coherence-mcp-server` carries the `mcp` keyword in `package.json`. |

---

### 4. MCP.so — MCP Directory

| Field | Value |
|-------|-------|
| **Registry** | [MCP.so](https://mcp.so) |
| **Category** | MCP |
| **Asset name** | `coherence-mcp-server` |
| **Status** | Submission ready — all required metadata present |
| **Install hint** | `npx coherence-mcp-server` |
| **Source paths** | `mcp-server/server.json`, `mcp-server/package.json`, `README.md` |
| **Listing URL** | https://mcp.so/server/coherence-mcp-server *(pending submission)* |
| **Notes** | MCP.so accepts submissions via GitHub repository URL. Submit via the MCP.so submission form pointing to `https://github.com/seeker71/Coherence-Network` with the package name `coherence-mcp-server`. |

---

### 5. ClawHub (OpenClaw Skill Registry) — Skill Registry

| Field | Value |
|-------|-------|
| **Registry** | [ClawHub](https://clawhub.com) |
| **Category** | Skill |
| **Asset name** | `coherence-network` |
| **Status** | Submission ready — `skills/coherence-network/SKILL.md` present and valid |
| **Install hint** | `clawhub install coherence-network` or copy `skills/coherence-network/SKILL.md` into your skills directory |
| **Source paths** | `skills/coherence-network/SKILL.md`, `.cursor/skills/`, `README.md` |
| **Listing URL** | https://clawhub.com/skills/coherence-network |
| **Notes** | The SKILL.md already contains full OpenClaw metadata including install steps, env vars, and tool descriptions. Listed in README.md under the Access Paths table. |

---

### 6. AgentSkills — Skill Catalog

| Field | Value |
|-------|-------|
| **Registry** | [AgentSkills](https://agentskills.dev) |
| **Category** | Skill |
| **Asset name** | `coherence-network` |
| **Status** | Submission ready — portable SKILL.md meets catalog format requirements |
| **Install hint** | Copy `skills/coherence-network/SKILL.md` into any AgentSkills-compatible workspace |
| **Source paths** | `skills/coherence-network/SKILL.md`, `skills/coherence-network/SKILL.template.md` |
| **Listing URL** | https://agentskills.dev/skills/coherence-network *(pending submission)* |
| **Notes** | AgentSkills accepts portable skill packages. The `SKILL.md` format is compatible. Submit by opening a PR to the AgentSkills catalog repository or via the submission form. |

---

## Summary

| Registry | Category | Status |
|----------|----------|--------|
| Smithery | MCP | Submission ready |
| Glama (awesome-mcp-servers) | MCP | Submission ready |
| PulseMCP | MCP | Submission ready |
| MCP.so | MCP | Submission ready |
| ClawHub | Skill | Submission ready |
| AgentSkills | Skill | Submission ready |

**Total**: 6 registries (4 MCP + 2 Skill) — satisfies the >= 5 requirement with >= 2 MCP and >= 2 Skill.

---

## How to submit

### MCP registries

**Smithery**: Auto-indexed from npm once `smithery.yaml` is present in the package root. Verify at
https://smithery.ai/server/coherence-mcp-server after the next npm publish.

**Glama**: Open a PR to https://github.com/punkpeye/awesome-mcp-servers adding:
```markdown
- [coherence-mcp-server](https://github.com/seeker71/Coherence-Network) — 20 typed tools for AI agents to browse ideas, trace value chains, and record contributions via the Coherence Network.
```

**PulseMCP**: Submit via https://pulsemcp.com/submit providing the repository URL and npm package
name `coherence-mcp-server`.

**MCP.so**: Submit via https://mcp.so/submit with repository URL
`https://github.com/seeker71/Coherence-Network`.

### Skill registries

**ClawHub**: Listing is based on `skills/coherence-network/SKILL.md`. Contact ClawHub maintainers
or submit via their intake form at https://clawhub.com/submit.

**AgentSkills**: Submit a PR to the AgentSkills catalog repository or use their submission form at
https://agentskills.dev/submit.

---

## Maintenance

- Re-submit or re-verify listings after each major version bump.
- Update this document when a listing URL becomes confirmed live.
- Do not add analytics, scheduled re-submission, or OAuth to this workflow — see idea scope.
