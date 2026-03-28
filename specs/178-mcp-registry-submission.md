# Spec 178 — Submit to 5+ MCP and Skill Registries for Discovery

**Status:** Draft
**Task ID:** task_e9be0ae57a3a53b4
**Author:** product-manager agent
**Date:** 2026-03-28
**Priority:** High — drives external discovery and installs

---

## Summary

Coherence Network has a working MCP server (`coherence-mcp-server` on npm, v0.3.1) and an
OpenClaw skill (`skills/coherence-network/`). Neither is listed in any public registry.
This spec defines the submission process for six registries, adds an install-count tracking
endpoint, and defines the metrics dashboard that proves discovery is working.

**Goal:** Be findable by anyone searching for MCP tools or AI skills on the six major
registries. Measure and surface install/download counts so growth is visible.

---

## Background

### What already exists

| Asset | Location | State |
|-------|----------|-------|
| npm package `coherence-mcp-server` | `mcp-server/` | Published (v0.3.1) |
| `server.json` (MCP registry manifest) | `mcp-server/server.json` | Written, NOT submitted |
| OpenClaw skill YAML | `skills/coherence-network/SKILL.md` | Written, NOT listed on skills.sh/askill.sh |
| Python MCP server | `api/mcp_server.py` | Running on VPS |
| `mcp-config.json` | `skills/coherence-network/mcp-config.json` | Local config, NOT submitted |

### Registries to target

| Registry | Submission method | What gets listed |
|----------|-------------------|-----------------|
| [Smithery](https://smithery.ai) | Submit via smithery.ai/submit or smithery.yml in repo | MCP server |
| [Glama](https://glama.ai) | PR to `awesome-mcp-servers` repo on GitHub | MCP server |
| [PulseMCP](https://pulsemcp.com) | Submit form at pulsemcp.com/submit | MCP server |
| [mcp.so](https://mcp.so) | Submit form / GitHub PR to mcp.so registry | MCP server |
| [skills.sh](https://skills.sh) | PR or form submission with SKILL.yaml | OpenClaw skill |
| [askill.sh](https://askill.sh) | PR or form submission with SKILL.yaml | OpenClaw skill |

---

## Requirements

### R1 — Smithery submission

1. Add `smithery.yaml` to the repo root per Smithery's schema.
2. The file must contain: `name`, `description`, `version`, `homepage`, `install` block
   pointing to the npm package, and a `tools` array with at least the 14 tools in
   `server.json`.
3. Submit via `https://smithery.ai/submit` — link the GitHub repo URL.
4. Target: the server appears on `https://smithery.ai/servers` within 7 days.

### R2 — Glama (awesome-mcp-servers PR)

1. Fork `punkpeye/awesome-mcp-servers` (or the canonical repo Glama watches).
2. Add a line under the relevant category:
   `[coherence-mcp-server](https://github.com/seeker71/Coherence-Network) — 14 tools for
   browsing ideas, tracing value chains, staking, attribution, and federation.`
3. Open a PR. Link the PR URL in `docs/REGISTRY_SUBMISSIONS.md`.

### R3 — PulseMCP submission

1. Submit via `https://pulsemcp.com/submit` with:
   - Name: `coherence-mcp-server`
   - npm: `coherence-mcp-server`
   - GitHub: `https://github.com/seeker71/Coherence-Network`
   - Description: same as `package.json` description field
2. Track the resulting listing URL in `docs/REGISTRY_SUBMISSIONS.md`.

### R4 — mcp.so submission

1. Submit via `https://mcp.so` (or PR to their open registry if applicable).
2. Same metadata as R3.
3. Track listing URL.

### R5 — skills.sh submission

1. Ensure `skills/coherence-network/SKILL.md` is current (it is as of v0.3.1).
2. Submit per skills.sh instructions (PR or form).
3. Track listing URL.

### R6 — askill.sh submission

1. Same skill file as R5.
2. Submit per askill.sh instructions.
3. Track listing URL.

### R7 — Registry tracking document

Create `docs/REGISTRY_SUBMISSIONS.md` with:
- Date of each submission
- Registry name and URL
- Listing URL (once live)
- Current install/download count (updated weekly by hand or script)
- Status: `pending | live | rejected`

### R8 — API endpoint: registry stats

Add `GET /api/registry/stats` that returns install/download counts pulled from
public sources (npm downloads for npm, Smithery API if available, etc.).

```
GET /api/registry/stats
→ 200 {
    "npm_weekly_downloads": <int>,
    "npm_total_downloads": <int>,
    "registries": [
      { "name": "smithery",  "status": "live|pending|unknown", "listing_url": "...", "installs": null },
      { "name": "glama",     "status": "live|pending|unknown", "listing_url": "...", "installs": null },
      { "name": "pulsemcp",  "status": "live|pending|unknown", "listing_url": "...", "installs": null },
      { "name": "mcp_so",    "status": "live|pending|unknown", "listing_url": "...", "installs": null },
      { "name": "skills_sh", "status": "live|pending|unknown", "listing_url": "...", "installs": null },
      { "name": "askill_sh", "status": "live|pending|unknown", "listing_url": "...", "installs": null }
    ],
    "fetched_at": "<ISO8601>"
  }
```

### R9 — Web dashboard integration

Add a "Registries" card on the web homepage (or `/ecosystem` page) that renders the
`/api/registry/stats` data. Show: npm weekly downloads, number of registries live, a
direct link to each listing (or "pending" label).

### R10 — Smithery badge in README

Once live, add the Smithery install badge to `README.md` and `mcp-server/README.md`.

---

## Data Model

### `docs/REGISTRY_SUBMISSIONS.md` (markdown, checked into git)

Manually maintained. Schema (table):
```
| Registry | Submitted | Status  | Listing URL | Weekly Installs | Notes |
|----------|-----------|---------|-------------|-----------------|-------|
| Smithery | 2026-03-xx| pending | —           | —               | —     |
| ...      |           |         |             |                 |       |
```

### API: `RegistryStats` Pydantic model

```python
class RegistryEntry(BaseModel):
    name: str
    status: Literal["live", "pending", "unknown", "rejected"]
    listing_url: Optional[str]
    installs: Optional[int]

class RegistryStats(BaseModel):
    npm_weekly_downloads: int
    npm_total_downloads: int
    registries: list[RegistryEntry]
    fetched_at: datetime
```

### npm download source

Public endpoint (no auth required):
```
https://api.npmjs.org/downloads/point/last-week/coherence-mcp-server
https://api.npmjs.org/downloads/range/2000-01-01:2099-12-31/coherence-mcp-server
```

---

## Files to Create / Modify

| File | Action | Notes |
|------|--------|-------|
| `smithery.yaml` | **Create** | Smithery submission manifest |
| `docs/REGISTRY_SUBMISSIONS.md` | **Create** | Tracking doc |
| `api/app/routers/registry.py` | **Create** | `GET /api/registry/stats` router |
| `api/app/services/registry_stats_service.py` | **Create** | npm fetch + config-driven registry list |
| `api/app/main.py` | **Modify** | Register `registry` router |
| `api/tests/test_registry_stats.py` | **Create** | Tests for the endpoint |
| `README.md` | **Modify** | Add Smithery badge once live |
| `mcp-server/server.json` | **Modify** | Bump version to match package.json (0.3.1) |
| `web/src/components/RegistryCard.tsx` | **Create** | Dashboard card |

---

## Smithery YAML Schema (reference)

```yaml
# smithery.yaml
name: coherence-mcp-server
description: >
  20 typed tools for AI agents to browse ideas, trace value chains, link identities,
  and record contributions on the Coherence Network.
version: "0.3.1"
homepage: https://coherencycoin.com
license: MIT
repository: https://github.com/seeker71/Coherence-Network
categories:
  - collaboration
  - project-management
  - open-source
install:
  npm:
    package: coherence-mcp-server
    bin: coherence-mcp-server
tools:
  - name: list_ideas
    description: Browse ideas sorted by free energy score
  - name: get_idea
    description: Get idea details including tasks and progress
  - name: create_idea
    description: Share a new idea with the network
  - name: list_specs
    description: Browse registered specs
  - name: list_nodes
    description: List federation compute nodes
  - name: get_coherence_score
    description: Get coherence score with signal breakdown
  - name: ask_question
    description: Ask a question on an idea
  - name: stake
    description: Invest CC in an idea (triggers compute tasks)
  - name: record_contribution
    description: Record a contribution to the network
  - name: list_tasks
    description: List agent tasks by status
  - name: get_resonance
    description: Get recent network activity
  - name: link_identity
    description: Link an external identity to a contributor
  - name: get_portfolio
    description: Get idea portfolio summary
  - name: get_provider_stats
    description: Get provider execution statistics
```

---

## Verification Scenarios

### Scenario 1 — npm download stats are returned

**Setup:** The `coherence-mcp-server` package exists on npm (published).

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/registry/stats
```

**Expected result:**
```json
{
  "npm_weekly_downloads": <integer ≥ 0>,
  "npm_total_downloads": <integer ≥ 0>,
  "registries": [
    {"name": "smithery",  "status": "live|pending|unknown", ...},
    {"name": "glama",     "status": "live|pending|unknown", ...},
    {"name": "pulsemcp",  "status": "live|pending|unknown", ...},
    {"name": "mcp_so",    "status": "live|pending|unknown", ...},
    {"name": "skills_sh", "status": "live|pending|unknown", ...},
    {"name": "askill_sh", "status": "live|pending|unknown", ...}
  ],
  "fetched_at": "<ISO8601 timestamp>"
}
```
HTTP 200. Exactly 6 registry entries, all 6 registry names present.

**Edge case:** npm registry is unreachable → endpoint still returns 200 with
`npm_weekly_downloads: 0` and a `"fetched_error"` field in the response (not 500).

---

### Scenario 2 — Registry status is readable and updateable

**Setup:** `docs/REGISTRY_SUBMISSIONS.md` exists with a `smithery` row set to `pending`.

**Action:** Reviewer reads the file directly:
```bash
cat docs/REGISTRY_SUBMISSIONS.md | grep smithery
```

**Expected result:** A table row containing `smithery`, a submission date, and `pending`.

**Action:** Developer updates Smithery row to `live` + listing URL and commits.

**Expected result:** After next deploy, `GET /api/registry/stats` returns
`{"name": "smithery", "status": "live", "listing_url": "https://smithery.ai/servers/..."}`.

---

### Scenario 3 — `smithery.yaml` is valid and present in repo

**Setup:** Spec has been implemented.

**Action:**
```bash
ls -la smithery.yaml && cat smithery.yaml | python3 -c "import sys,yaml; d=yaml.safe_load(sys.stdin); assert 'name' in d and 'tools' in d and len(d['tools']) >= 14"
```

**Expected result:** File exists, exit code 0. The YAML parses, contains `name` and ≥14
tools.

**Edge case:** Missing required field (e.g., `name` removed) → Python assertion raises
`AssertionError` — clearly signals invalid manifest before submission.

---

### Scenario 4 — Web dashboard shows registry status

**Setup:** `GET /api/registry/stats` returns valid JSON.

**Action:** Browser opens `https://coherencycoin.com` (or `/ecosystem`).

**Expected result:** A "Registries" card is visible showing:
- npm weekly downloads as a number
- A count of "X of 6 live" registries
- Each registry name with either a link (if live) or a "pending" label

**Edge case:** If the API call fails (network error), the card shows a graceful fallback
message ("Registry data unavailable") instead of a broken widget.

---

### Scenario 5 — Full create-read cycle for registry submission record

**Setup:** `docs/REGISTRY_SUBMISSIONS.md` does NOT exist yet (pre-implementation).

**Action (create):**
```bash
# Implementation creates the file with 6 pending rows
cat docs/REGISTRY_SUBMISSIONS.md
```
**Expected:** File has header row + 6 data rows (one per registry), all status `pending`.

**Action (update — simulate live):** Edit one row to `live`, commit, deploy.

**Action (read):**
```bash
curl -s https://api.coherencycoin.com/api/registry/stats | python3 -c \
  "import sys,json; d=json.load(sys.stdin); s=[r for r in d['registries'] if r['name']=='smithery'][0]; assert s['status']=='live', s"
```
**Expected:** Exit code 0, Smithery status is `live`.

**Edge case (bad registry name in config):** If config contains an unrecognised registry
key, the API returns 200 with that entry's `status: "unknown"` rather than 500.

---

## Acceptance Criteria

- [ ] `smithery.yaml` present at repo root, parses cleanly, has ≥14 tools
- [ ] `docs/REGISTRY_SUBMISSIONS.md` created with all 6 registries tracked
- [ ] Smithery submission submitted (PR/form completed, link in tracking doc)
- [ ] Glama PR opened on `awesome-mcp-servers` (link in tracking doc)
- [ ] PulseMCP form submitted (link in tracking doc)
- [ ] mcp.so form/PR submitted (link in tracking doc)
- [ ] skills.sh submission completed (link in tracking doc)
- [ ] askill.sh submission completed (link in tracking doc)
- [ ] `GET /api/registry/stats` returns HTTP 200 with all 6 registries
- [ ] npm download numbers are real (not hardcoded)
- [ ] Web dashboard card renders registry data
- [ ] All tests in `api/tests/test_registry_stats.py` pass
- [ ] `mcp-server/server.json` version matches `package.json` (0.3.1)

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Registry approval takes weeks | High | Submit all 6 day-1; status=pending is acceptable for launch |
| Smithery/Glama reject the submission | Medium | Iterate on description quality; follow their submission guidelines exactly |
| npm download count is always 0 (new package) | High | Expected; display honestly; set alert at 10 downloads/week |
| Registry listing URLs are not machine-readable | High | Tracking doc is the source of truth; API reads it or a companion JSON config |
| skills.sh/askill.sh have limited traffic | High | Include them for completeness; weight npm/Smithery more heavily in reporting |
| Server.json version mismatch confuses registries | Low | Fix in this PR before submission |

---

## Known Gaps and Follow-up Tasks

- **Automated weekly download sync:** A cron task that updates `docs/REGISTRY_SUBMISSIONS.md`
  install counts from npm's public API has not been spec'd. Manual weekly update is
  acceptable for v1.
- **Smithery auto-sync:** Smithery may support a webhook or periodic re-read of the repo.
  Research needed.
- **PyPI submission:** The Python `api/mcp_server.py` server is not on PyPI yet. A separate
  spec should cover `pip install coherence-mcp-server`.
- **Registry analytics dashboard:** A dedicated `/ecosystem` page is a follow-up; the v1
  card on the homepage is sufficient.
- **Glama PR review latency:** The `punkpeye/awesome-mcp-servers` repo has high PR volume.
  Budget 2–4 weeks for merge.
