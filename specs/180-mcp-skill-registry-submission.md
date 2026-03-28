# Spec 180 — Submit to 5+ MCP and Skill Registries for Discovery

**ID:** 180-mcp-skill-registry-submission
**Status:** approved
**Priority:** high
**Category:** distribution / discoverability
**Author:** claude (product-manager)
**Created:** 2026-03-28
**Task:** task_d50a5af0ac05b381

---

## Summary

Register the Coherence Network MCP server and skill on Smithery, Glama
(`awesome-mcp-servers` PR), PulseMCP, `mcp.so`, `skills.sh`, and `askill.sh`
(six registries total). Track install and download counts per registry via a
new API endpoint so that growth in discoverability is measurable and provable
over time.

The project already has:
- `GET /api/discovery/registry-submissions` — readiness inventory (6 targets)
- `api/app/services/registry_discovery_service.py` — per-registry asset checks
- `api/app/models/registry_discovery.py` — Pydantic models

**This spec extends those foundations.** It does not replace them.

---

## Goals

| # | Goal |
|---|------|
| G1 | All six target registries are listed and their submission readiness is reported by the API. |
| G2 | The API reports install/download counts per registry, fetched from live sources when available and cached otherwise. |
| G3 | A dashboard panel (web or CLI) surfaces the count data so progress is visible at a glance. |
| G4 | The full pipeline is observable: submission status → asset readiness → download trend — readable in a single API call. |

---

## Target Registries

| Registry ID | Name | Category | Submission Method | Count Source |
|-------------|------|----------|-------------------|--------------|
| `smithery` | Smithery | mcp | `mcp-server/server.json` PR | Smithery API (`/registry/packages/{name}/stats`) |
| `glama` | Glama (awesome-mcp-servers) | mcp | PR to `punkpeye/awesome-mcp-servers` | GitHub stars of linked repo |
| `pulsemcp` | PulseMCP | mcp | GitHub PR to PulseMCP catalog | PulseMCP public API (`/servers`) |
| `mcp-so` | MCP.so | mcp | `mcp-server/server.json` + README | No public API — manual scrape or N/A |
| `skills-sh` | skills.sh | skill | PR to skills.sh registry | No public API — N/A initially |
| `askill-sh` | askill.sh | skill | PR to askill.sh directory | No public API — N/A initially |

**Core requirement:** `summary.core_requirement_met` is `true` when ≥ 5 registries
have status `submission_ready`.

---

## Architecture

### Existing layer (unchanged)

```
GET /api/discovery/registry-submissions
  → registry_discovery_service.build_registry_submission_inventory()
  → checks asset files on disk, validates manifests
```

### New layer

```
GET /api/discovery/registry-stats
  → registry_stats_service.fetch_registry_stats()
  → returns per-registry install/download counts with cache
```

```
GET /api/discovery/registry-dashboard
  → merges submission inventory + stats into one response
```

---

## Data Model

### `RegistryStats` (new Pydantic model)

```python
class RegistryStatSource(str, Enum):
    LIVE = "live"        # fetched from provider API this request
    CACHED = "cached"    # returned from local cache (< 24 h old)
    UNAVAILABLE = "unavailable"  # no public API for this registry

class RegistryStats(BaseModel):
    registry_id: str
    registry_name: str
    install_count: int | None = None   # None when unavailable
    download_count: int | None = None  # None when unavailable
    star_count: int | None = None      # GitHub stars for glama entry
    fetched_at: datetime | None = None
    source: RegistryStatSource
    error: str | None = None

class RegistryStatsSummary(BaseModel):
    total_installs: int
    total_downloads: int
    registries_with_counts: int
    registries_unavailable: int
    last_updated: datetime | None

class RegistryStatsList(BaseModel):
    summary: RegistryStatsSummary
    items: list[RegistryStats]
```

### `RegistryDashboard` (new Pydantic model)

```python
class RegistryDashboardItem(BaseModel):
    registry_id: str
    registry_name: str
    category: str
    status: RegistrySubmissionStatus
    missing_files: list[str]
    install_hint: str
    install_count: int | None
    download_count: int | None
    stat_source: RegistryStatSource

class RegistryDashboard(BaseModel):
    submission_summary: RegistrySubmissionSummary
    stats_summary: RegistryStatsSummary
    items: list[RegistryDashboardItem]
```

---

## API Changes

### Existing endpoint (no change to contract)

```
GET /api/discovery/registry-submissions
```

Returns `RegistrySubmissionInventory`. Must include all six registries:
`smithery`, `glama`, `pulsemcp`, `mcp-so`, `skills-sh`, `askill-sh`.

### New endpoints

```
GET /api/discovery/registry-stats
```
Returns `RegistryStatsList`. Fetches live counts from Smithery and PulseMCP
public APIs; falls back to 24-hour cache; marks others `unavailable`.

Query params:
- `?refresh=true` — bypass cache and fetch live data (default: false)
- `?registry_id=smithery` — filter to one registry

```
GET /api/discovery/registry-dashboard
```
Returns `RegistryDashboard`. Merges submission inventory with stats. Always
available even when stat fetches fail (graceful degradation).

---

## Required Assets (Submission Checklist)

For each registry, the following files must exist in the repo before submission:

### MCP registries (Smithery, Glama, PulseMCP, MCP.so)

| File | Purpose |
|------|---------|
| `mcp-server/server.json` | MCP manifest with `$schema`, `name`, npm package entry |
| `mcp-server/package.json` | npm package with `name: coherence-mcp-server`, `bin` entry |
| `mcp-server/README.md` | Human-readable install guide |
| `README.md` | Top-level README with `## Install` section referencing `npx coherence-mcp-server` |

### Skill registries (skills.sh, askill.sh)

| File | Purpose |
|------|---------|
| `skills/coherence-network/SKILL.md` | Skill manifest with `name`, `metadata`, `cc inbox` example |
| `README.md` | Top-level README with `## Skills` section referencing `clawhub install coherence-network` |

### Glama-specific

| File | Purpose |
|------|---------|
| `mcp-server/glama.json` | Glama-format metadata file (`name`, `description`, `url`, `tags`) |

---

## File Changes

| File | Change |
|------|--------|
| `api/app/models/registry_discovery.py` | Add `RegistryStats`, `RegistryStatsSummary`, `RegistryStatsList`, `RegistryDashboard*` models |
| `api/app/services/registry_discovery_service.py` | Extend `_TARGETS` with `glama`, `pulsemcp`, `skills-sh`, `askill-sh`; add Glama-specific validator |
| `api/app/services/registry_stats_service.py` | New: fetch live counts from Smithery and PulseMCP APIs, with 24-h file cache in `.cache/registry_stats/` |
| `api/app/routers/registry_discovery.py` | Add `GET /registry-stats` and `GET /registry-dashboard` routes |
| `mcp-server/server.json` | Ensure Glama, PulseMCP fields populated |
| `mcp-server/glama.json` | New: Glama submission metadata file |
| `skills/coherence-network/SKILL.md` | Ensure skills.sh and askill.sh compatible fields present |
| `api/tests/test_registry_discovery.py` | New: tests for all six registries and new endpoints |

---

## Stats Cache Design

```
.cache/registry_stats/
  smithery.json    { "install_count": N, "fetched_at": "..." }
  pulsemcp.json    { "install_count": N, "fetched_at": "..." }
```

- Cache TTL: **24 hours**
- On cache miss or `?refresh=true`: fetch live, write cache
- On fetch failure: return last cached value with `source: "cached"`; if no cache
  exists, return `source: "unavailable"` with `error` field populated

---

## Glama Submission Format

File: `mcp-server/glama.json`

```json
{
  "name": "coherence-network",
  "description": "Coherence Network MCP server — publish ideas, query the knowledge graph, record resonance measurements, and collaborate with AI nodes via the Model Context Protocol.",
  "url": "https://github.com/Coherence-Network/coherence-network",
  "homepage": "https://coherencycoin.com",
  "license": "MIT",
  "tags": ["knowledge-graph", "ideas", "resonance", "collaboration", "neo4j"],
  "install": {
    "npx": "coherence-mcp-server"
  }
}
```

---

## PulseMCP Submission Format

PulseMCP accepts GitHub PRs to its catalog. The PR must add an entry to the
servers list with:

```json
{
  "name": "Coherence Network",
  "slug": "coherence-network",
  "description": "Publish ideas, query the knowledge graph, record resonance, and collaborate with AI nodes.",
  "repository": "https://github.com/Coherence-Network/coherence-network",
  "npm_package": "coherence-mcp-server",
  "tags": ["knowledge-graph", "resonance", "ideas"],
  "verified": false
}
```

---

## How This Proves It Is Working

The primary proof surfaces are:

1. **`GET /api/discovery/registry-submissions`** — `summary.core_requirement_met = true`
   means ≥ 5 registries have all required assets present.

2. **`GET /api/discovery/registry-stats`** — non-zero `install_count` or
   `download_count` for at least one live-API registry (Smithery, PulseMCP)
   proves real external discovery is happening.

3. **`GET /api/discovery/registry-dashboard`** — single-call proof of the full
   picture: asset readiness + live counts side by side.

4. **Trend over time** — because counts are cached with `fetched_at` timestamps,
   successive calls to `/registry-stats?refresh=true` (run weekly via cron) build
   a time series. A monotonically increasing `total_installs` is the clearest
   possible proof.

---

## Verification Scenarios

### Scenario 1 — All six registries appear in submission inventory

**Setup:** API is running with the extended `_TARGETS` list.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-submissions | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print([i['registry_id'] for i in d['items']])"
```

**Expected:** Output contains all six:
```
['smithery', 'glama', 'pulsemcp', 'mcp-so', 'skills-sh', 'askill-sh']
```
(order may vary)

**Edge — missing asset:** Delete `mcp-server/server.json`, call again →
`smithery` item has `status: "missing_assets"` and `missing_files: ["mcp-server/server.json"]`.
`summary.core_requirement_met` is `false` if ≥ 2 registries are affected.

---

### Scenario 2 — Core requirement met when all assets present

**Setup:** All required files exist in the repo.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-submissions | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['summary']['core_requirement_met'], d['summary']['submission_ready_count'])"
```

**Expected:**
```
True 6
```
(or `True 5` if exactly one registry is legitimately blocked)

**Edge — partial assets:** Create all MCP assets but delete
`skills/coherence-network/SKILL.md`. Result: `skills-sh` and `askill-sh` both
report `missing_assets`. `submission_ready_count` drops to 4.
`core_requirement_met` becomes `false`.

---

### Scenario 3 — Stats endpoint returns counts with correct source labels

**Setup:** Fresh deployment, no cache files present.

**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); [print(i['registry_id'], i['source'], i['install_count']) for i in d['items']]"
```

**Expected:** Each item has `source` in `["live", "cached", "unavailable"]`.
`mcp-so`, `skills-sh`, `askill-sh` show `source: "unavailable"` (no public API).
Smithery and PulseMCP show `source: "live"` or `source: "cached"`.
No item returns HTTP 500.

**Edge — Smithery API unreachable:** When Smithery's stats API is down, the
Smithery item returns `source: "unavailable"`, `install_count: null`,
`error: "upstream timeout"`. All other items are unaffected. HTTP 200 still
returned.

---

### Scenario 4 — Cache refresh behaviour

**Setup:** `smithery.json` cache file exists with `fetched_at` = 23 hours ago.

**Action (no refresh):**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); smithery=[i for i in d['items'] if i['registry_id']=='smithery'][0]; print(smithery['source'])"
```
**Expected:** `cached`

**Action (force refresh):**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats?refresh=true" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); smithery=[i for i in d['items'] if i['registry_id']=='smithery'][0]; print(smithery['source'])"
```
**Expected:** `live` (cache is bypassed and rewritten)

**Edge — cache older than 24 h:** Auto-refreshes on next regular call.
`source` will be `live` even without `?refresh=true`.

---

### Scenario 5 — Dashboard merges submission + stats in one call

**Setup:** At least one registry is `submission_ready`, stats cache populated.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-dashboard | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['submission_summary']['core_requirement_met']); [print(i['registry_id'], i['status'], i['install_count']) for i in d['items']]"
```

**Expected:** One line per registry with `registry_id`, `status` (e.g.
`submission_ready` or `missing_assets`), and `install_count` (integer or `null`).
`core_requirement_met` is `true` or `false` matching `/registry-submissions`.

**Edge — stats fetch completely fails:** Dashboard still returns HTTP 200. All
`install_count` fields are `null`, `stat_source` is `unavailable`. Submission
data is unaffected.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| Smithery/PulseMCP public stat APIs may change or be removed | Cache ensures last-known counts are always available; `source: "unavailable"` is a safe fallback |
| GitHub rate limits on glama star-count fetch | Use unauthenticated API (`/repos/{owner}/{repo}`) with backoff; 60 req/h is enough for weekly refresh |
| PRs to third-party registries may be delayed or rejected | Submission readiness is tracked independently of actual acceptance; `notes` field explains current state |
| Glama PR requires manual review | Asset-readiness check covers our side; PR URL stored in `notes` once submitted |
| `mcp.so`, `skills.sh`, `askill.sh` have no public count APIs | Marked `unavailable`; `install_count: null` is valid; re-evaluated when APIs emerge |
| `skills.sh` and `askill.sh` may require different manifest formats | Investigate before PR; update `SKILL.md` validators accordingly |

---

## Known Gaps and Follow-up Tasks

- [ ] Once Smithery/PulseMCP install counts are live and non-zero, add a weekly
  cron job to record the time series in PostgreSQL for trend graphing.
- [ ] `mcp.so` submission requires a manual web form; document the URL and last
  submission date in `mcp-server/README.md`.
- [ ] Verify `skills.sh` and `askill.sh` accept the existing `SKILL.md` format
  or require a distinct manifest.
- [ ] Spec 181: web dashboard panel `/discovery` that renders `RegistryDashboard`
  with color-coded status badges and a sparkline for install counts.
- [ ] Spec 182: automated PR-creation script for Glama and PulseMCP catalog repos,
  triggered when `submission_ready_count >= 5`.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC1 | `GET /api/discovery/registry-submissions` returns exactly six items covering `smithery`, `glama`, `pulsemcp`, `mcp-so`, `skills-sh`, `askill-sh`. |
| AC2 | `summary.core_requirement_met` is `true` when all required asset files are present. |
| AC3 | `GET /api/discovery/registry-stats` returns one item per registry, each with `source` in `["live","cached","unavailable"]`. |
| AC4 | `?refresh=true` forces a live fetch and updates the cache file. |
| AC5 | When a stats API is unreachable, the endpoint returns HTTP 200 with `source: "unavailable"` and `error` set — no 500. |
| AC6 | `GET /api/discovery/registry-dashboard` merges both datasets and returns HTTP 200 even if stats are fully unavailable. |
| AC7 | `mcp-server/glama.json` exists and is valid JSON with required Glama fields. |
| AC8 | All six registries have validators in `registry_discovery_service.py` that correctly reflect their required asset lists. |
| AC9 | All new endpoints are covered by pytest tests with both happy-path and failure-mode cases. |
