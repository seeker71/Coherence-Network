# Registry Submissions — Coherence Network MCP Server & Skill

Tracks the status of submissions to public MCP and skill registries.
Update this file weekly with current install counts.

**npm package:** `coherence-mcp-server`
**npm URL:** https://www.npmjs.com/package/coherence-mcp-server
**GitHub:** https://github.com/seeker71/Coherence-Network
**Homepage:** https://coherencycoin.com

---

## Submission Status

| Registry | Type | Submitted | Status | Listing URL | Weekly Installs | Notes |
|----------|------|-----------|--------|-------------|-----------------|-------|
| [Smithery](https://smithery.ai) | MCP server | 2026-03-28 | pending | — | — | smithery.yaml committed; submit at https://smithery.ai/submit — see docs/registry-submissions/smithery-submission.md |
| [Glama](https://glama.ai) | MCP server | 2026-03-28 | pending | — | — | PR template ready — see docs/registry-submissions/glama-awesome-mcp-servers.md |
| [PulseMCP](https://pulsemcp.com) | MCP server | 2026-03-28 | pending | — | — | Submission JSON ready — see docs/registry-submissions/pulsemcp-submission.json |
| [mcp.so](https://mcp.so) | MCP server | 2026-03-28 | pending | — | — | Submission guide ready — see docs/registry-submissions/mcpso-submission.md |
| [skills.sh](https://skills.sh) | OpenClaw skill | 2026-03-28 | pending | — | — | Submission guide ready — see docs/registry-submissions/skills-sh-submission.md |
| [askill.sh](https://askill.sh) | OpenClaw skill | 2026-03-28 | pending | — | — | Submission guide ready — see docs/registry-submissions/askill-sh-submission.md |

---

## npm Download History

Track weekly via: `https://api.npmjs.org/downloads/point/last-week/coherence-mcp-server`
Live stats: `GET /api/registry/stats`

| Week ending | Weekly downloads | Total (approx) |
|-------------|-----------------|----------------|
| 2026-03-28 | — | — |

---

## Submission Checklist

### Smithery
- [x] `smithery.yaml` added to repo root with all 20 tools
- [ ] Submitted at https://smithery.ai/submit (paste GitHub URL)
- [ ] Listing URL recorded above
- [ ] Smithery badge added to README.md once live

### Glama (awesome-mcp-servers)
- [x] PR template created at `docs/registry-submissions/glama-awesome-mcp-servers.md`
- [ ] Fork https://github.com/punkpeye/awesome-mcp-servers
- [ ] Add entry under "Productivity / Collaboration":
  ```
  - [coherence-mcp-server](https://github.com/seeker71/Coherence-Network) — 20 tools for browsing ideas, tracing value chains, linking identities, recording contributions, and exploring federated nodes.
  ```
- [ ] Open PR and paste PR URL in "Notes" column above

### PulseMCP
- [x] Submission JSON ready at `docs/registry-submissions/pulsemcp-submission.json`
- [ ] Visit https://pulsemcp.com/submit
- [ ] Fill: Name=`coherence-mcp-server`, npm=`coherence-mcp-server`, GitHub URL, description
- [ ] Record listing URL

### mcp.so
- [x] Submission guide at `docs/registry-submissions/mcpso-submission.md`
- [ ] Visit https://mcp.so and submit
- [ ] Record listing URL

### skills.sh
- [x] Submission guide at `docs/registry-submissions/skills-sh-submission.md`
- [ ] Submit `skills/coherence-network/SKILL.md` per skills.sh contribution docs
- [ ] Record listing URL

### askill.sh
- [x] Submission guide at `docs/registry-submissions/askill-sh-submission.md`
- [ ] Submit `skills/coherence-network/SKILL.md` per askill.sh contribution docs
- [ ] Record listing URL

---

## API endpoint

Live stats are served at:
```
GET /api/registry/stats
```

Returns npm weekly/total downloads + status of all 6 registries. See `api/app/routers/registry.py`.

---

## Signals to Watch

Once listings are live, watch these signals weekly:
- npm weekly downloads (via npmjs.org API — objective, automatic)
- Smithery "installs" counter (if exposed by their API)
- GitHub stars on the Coherence-Network repo (indirect signal)
- Search: `site:smithery.ai coherence` and `site:pulsemcp.com coherence` — check ranking

**Target milestones:**
- Week 1 (2026-03-28): All 6 submissions sent
- Week 4 (2026-04-25): ≥3 listings live
- Week 8 (2026-05-23): ≥5 listings live, ≥10 npm weekly downloads
- Month 6 (2026-09-28): ≥50 npm weekly downloads, Smithery installs > 0
