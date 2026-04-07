---
idea_id: user-surfaces
status: done
source:
  - file: mcp-server/coherence_mcp_server/server.py
    symbols: [MCP server]
  - file: api/app/services/mcp_tool_registry.py
    symbols: [tool handler registry]
  - file: api/app/routers/registry_discovery.py
    symbols: [registry endpoints]
requirements:
  - Registry submissions endpoint returns all six target registries
  - summary.core_requirement_met is true when 5+ registries have assets present
  - GET /api/discovery/registry-stats returns per-registry install/download counts
  - Stats endpoint supports ?refresh=true to bypass 24h cache
  - Unreachable stats API returns 200 with source unavailable, not 500
  - GET /api/discovery/registry-dashboard merges submissions and stats
  - mcp-server/glama.json exists with valid Glama submission metadata
  - All six registries have validators in registry_discovery_service
done_when:
  - registry-submissions returns exactly six items
  - registry-dashboard returns 200 even when stats are fully unavailable
  - pytest api/tests/test_registry_discovery.py passes
---

> **Parent idea**: [user-surfaces](../ideas/user-surfaces.md)
> **Source**: [`mcp-server/coherence_mcp_server/server.py`](../mcp-server/coherence_mcp_server/server.py) | [`api/app/services/mcp_tool_registry.py`](../api/app/services/mcp_tool_registry.py) | [`api/app/routers/registry_discovery.py`](../api/app/routers/registry_discovery.py)

# Spec 180 — Submit to 5+ MCP and Skill Registries for Discovery

**ID:** 180-mcp-skill-registry-submission
**Status:** approved
**Priority:** high
**Category:** distribution / discoverability
**Author:** claude (product-manager)
**Created:** 2026-03-28
**Task:** task_d50a5af0ac05b381

## Goals

| # | Goal |
|---|------|
| G1 | All six target registries are listed and their submission readiness is reported by the API. |
| G2 | The API reports install/download counts per registry, fetched from live sources when available and cached otherwise. |
| G3 | A dashboard panel (web or CLI) surfaces the count data so progress is visible at a glance. |
| G4 | The full pipeline is observable: submission status → asset readiness → download trend — readable in a single API call. |

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

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| Smithery/PulseMCP public stat APIs may change or be removed | Cache ensures last-known counts are always available; `source: "unavailable"` is a safe fallback |
| GitHub rate limits on glama star-count fetch | Use unauthenticated API (`/repos/{owner}/{repo}`) with backoff; 60 req/h is enough for weekly refresh |
| PRs to third-party registries may be delayed or rejected | Submission readiness is tracked independently of actual acceptance; `notes` field explains current state |
| Glama PR requires manual review | Asset-readiness check covers our side; PR URL stored in `notes` once submitted |
| `mcp.so`, `skills.sh`, `askill.sh` have no public count APIs | Marked `unavailable`; `install_count: null` is valid; re-evaluated when APIs emerge |
| `skills.sh` and `askill.sh` may require different manifest formats | Investigate before PR; update `SKILL.md` validators accordingly |

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
