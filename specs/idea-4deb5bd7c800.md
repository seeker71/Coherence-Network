# Spec: Submit to 5+ MCP and Skill Registries for Discovery

**Idea ID**: `idea-4deb5bd7c800`
**Canonical spec**: this file (supersedes early draft; see also `180-mcp-skill-registry-submission.md` for implementation detail)
**Status**: Approved — 2026-03-28
**Author**: product-manager agent
**Priority**: High
**Category**: Distribution / Discoverability

---

## Summary

Coherence Network exposes two discovery-ready artifacts: the MCP server
(`mcp-server/server.json`, `mcp-server/index.mjs`, npm package
`coherence-mcp-server`) and the skill (`skills/coherence-network/SKILL.md`).
Today, six registry targets are tracked in
`api/app/services/registry_discovery_service.py`:
`modelcontextprotocol-registry`, `npm`, `smithery`, `mcp-so`, `clawhub`,
`agentskills`.

**What is missing:**

1. Two of the six task-specified registries — **Glama** (via
   `punkpeye/awesome-mcp-servers` PR) and **PulseMCP** — are not in the
   `_TARGETS` list. `mcp-server/glama.json` and `mcp-server/pulsemcp.json`
   already exist but are not validated by the service.
2. The specifically requested skill registries **skills.sh** and **askill.sh**
   must be confirmed or replaced in `_TARGETS` (current entries are `clawhub`
   and `agentskills`).
3. **Install/download count tracking** does not exist. There is no
   `/api/discovery/registry-stats` endpoint.
4. There is no single-call proof surface showing both submission readiness and
   live discovery counts — making it impossible to answer "is this working?" at
   a glance.

This spec closes those gaps. The core deliverable is observable proof that
Coherence Network is discoverable in at least five external directories, with
a monotonically increasing install count as the primary health signal.

---

## Goals

| # | Goal |
|---|------|
| G1 | All six task-specified registries are tracked in `_TARGETS` with validated asset checklists. |
| G2 | `summary.core_requirement_met = true` when ≥ 5 registries have all required assets present. |
| G3 | A new `/api/discovery/registry-stats` endpoint returns install/download counts per registry. |
| G4 | A new `/api/discovery/registry-dashboard` endpoint merges readiness + counts into one call. |
| G5 | Proof is self-evident and machine-readable: a CI check or cron job can assert the count is non-zero. |

---

## Current State vs. Required State

| Registry | Task Requirement | Current `_TARGETS` ID | Gap |
|----------|-----------------|----------------------|-----|
| Smithery | ✅ required (MCP) | `smithery` | None — already tracked |
| Glama (awesome-mcp-servers) | ✅ required (MCP) | — | **Missing from `_TARGETS`**; `glama.json` exists |
| PulseMCP | ✅ required (MCP) | — | **Missing from `_TARGETS`**; `pulsemcp.json` exists |
| MCP.so | ✅ required (MCP) | `mcp-so` | None — already tracked |
| skills.sh | ✅ required (skill) | `clawhub` (maps to ClawHub) | **Verify** ClawHub ≡ skills.sh or add `skills-sh` target |
| askill.sh | ✅ required (skill) | `agentskills` | **Verify** AgentSkills ≡ askill.sh or add `askill-sh` target |
| MCP Official Registry | bonus | `modelcontextprotocol-registry` | Already tracked — counts as 7th |
| npm | bonus | `npm` | Already tracked — not a discovery registry per se |

**Minimum to close the spec:** ≥ 5 registries from the task list reach
`submission_ready`. That requires adding `glama` and `pulsemcp` to `_TARGETS`
(or confirming the clawhub/agentskills mappings cover skills.sh/askill.sh).

---

## Requirements

### R1 — Registry Coverage

All six task-specified registries must appear in
`registry_discovery_service._TARGETS`:
- `smithery` (MCP) — already present
- `glama` (MCP) — add entry validating `mcp-server/glama.json`
- `pulsemcp` (MCP) — add entry validating `mcp-server/pulsemcp.json`
- `mcp-so` (MCP) — already present
- `skills-sh` or confirmed `clawhub` mapping (skill)
- `askill-sh` or confirmed `agentskills` mapping (skill)

### R2 — Submission Readiness API (existing, extend)

`GET /api/discovery/registry-submissions` must:
- Return all six task-specified registries in `items`
- Set `summary.core_requirement_met = true` when ≥ 5 are `submission_ready`
- Include `install_hint` and `source_paths` per item

### R3 — Stats Tracking API (new)

`GET /api/discovery/registry-stats` must:
- Return one `RegistryStats` item per tracked registry
- Fetch live install/download counts from Smithery and PulseMCP public APIs
- Cache results for 24 hours in `.cache/registry_stats/{registry_id}.json`
- Support `?refresh=true` to bypass cache
- Support `?registry_id=<id>` to filter
- Return HTTP 200 even when upstream APIs are unreachable; mark
  unavailable items with `source: "unavailable"` and `error` field

### R4 — Dashboard API (new)

`GET /api/discovery/registry-dashboard` must:
- Merge submission readiness + stats into one response per registry
- Return HTTP 200 even if stats fetch completely fails
- Show `install_count: null` with `stat_source: "unavailable"` on failure

### R5 — Proof of Working (open question answer)

The system proves it is working when:

1. **Asset check**: `GET /api/discovery/registry-submissions` returns
   `core_requirement_met: true` — all required files are present.
2. **Live counts**: `GET /api/discovery/registry-stats` returns
   `install_count > 0` for at least one live-API registry (Smithery,
   PulseMCP) after a real external install occurs.
3. **Trend over time**: Weekly scheduled calls to
   `/api/discovery/registry-stats?refresh=true` write `fetched_at`
   timestamps; a monotonically non-decreasing `total_installs` across
   successive cache files is the clearest machine-readable proof.
4. **Dashboard single-call**: `GET /api/discovery/registry-dashboard`
   returns both dimensions so a reviewer can confirm the feature works with
   one `curl`.

### R6 — No Scope Creep

Out of scope for this spec:
- OAuth/auth to registry platforms
- Automated PR-creation scripts (follow-up spec)
- Web UI dashboard panel (follow-up spec)
- Analytics database time-series storage (follow-up spec)
- Paid placement

---

## API Changes

### Existing (no contract change)

```
GET /api/discovery/registry-submissions
→ RegistrySubmissionInventory
```

Extend `_TARGETS` to include `glama`, `pulsemcp`, and verify skill mappings.
No changes to response schema.

### New endpoints

```
GET /api/discovery/registry-stats[?refresh=true][?registry_id=<id>]
→ RegistryStatsList
```

```
GET /api/discovery/registry-dashboard
→ RegistryDashboard
```

---

## Data Model

### `RegistryStats` (new)

```python
class RegistryStatSource(str, Enum):
    LIVE = "live"             # fetched from provider API this request
    CACHED = "cached"         # < 24 h cache
    UNAVAILABLE = "unavailable"  # no public API for this registry

class RegistryStats(BaseModel):
    registry_id: str
    registry_name: str
    install_count: int | None = None
    download_count: int | None = None
    star_count: int | None = None      # GitHub stars for Glama entry
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

### `RegistryDashboard` (new)

```python
class RegistryDashboardItem(BaseModel):
    registry_id: str
    registry_name: str
    category: str                          # "mcp" | "skill"
    status: RegistrySubmissionStatus       # existing enum
    missing_files: list[str]
    install_hint: str
    install_count: int | None
    download_count: int | None
    stat_source: RegistryStatSource

class RegistryDashboard(BaseModel):
    submission_summary: RegistrySubmissionSummary  # existing model
    stats_summary: RegistryStatsSummary
    items: list[RegistryDashboardItem]
```

---

## File Changes

| File | Change |
|------|--------|
| `api/app/services/registry_discovery_service.py` | Add `glama` and `pulsemcp` entries to `_TARGETS`; add validators for `glama.json` and `pulsemcp.json`; confirm or rename `clawhub`/`agentskills` to match task registry names |
| `api/app/models/registry_discovery.py` | Add `RegistryStats`, `RegistryStatsSummary`, `RegistryStatsList`, `RegistryDashboardItem`, `RegistryDashboard` models |
| `api/app/services/registry_stats_service.py` | New: fetch Smithery + PulseMCP live counts; 24-h file cache in `.cache/registry_stats/` |
| `api/app/routers/registry_discovery.py` | Add `GET /discovery/registry-stats` and `GET /discovery/registry-dashboard` routes |
| `mcp-server/glama.json` | Verify fields: `name`, `description`, `url`, `homepage`, `license`, `tags`, `install.npx` |
| `mcp-server/pulsemcp.json` | Verify fields: `name`, `slug`, `description`, `repository`, `npm_package`, `tags` |
| `api/tests/test_registry_discovery.py` | New: tests for all registry targets and both new endpoints |

---

## Stats Cache Design

```
.cache/registry_stats/
  smithery.json    { "install_count": N, "fetched_at": "2026-03-28T12:00:00Z" }
  pulsemcp.json    { "install_count": N, "fetched_at": "..." }
```

- Cache TTL: **24 hours**
- On cache miss or `?refresh=true`: fetch live, write to cache
- On live fetch failure: return last cached value with `source: "cached"`;
  if no cache exists, return `source: "unavailable"` with `error` populated
- Cache directory must be gitignored

---

## Glama and PulseMCP Submission Formats

### `mcp-server/glama.json` (already exists, verify)

```json
{
  "name": "coherence-network",
  "description": "Coherence Network MCP server — publish ideas, query the knowledge graph, record resonance measurements, and collaborate with AI nodes via the Model Context Protocol.",
  "url": "https://github.com/seeker71/Coherence-Network",
  "homepage": "https://coherencycoin.com",
  "license": "MIT",
  "tags": ["knowledge-graph", "ideas", "resonance", "collaboration", "neo4j"],
  "install": { "npx": "coherence-mcp-server" }
}
```

### `mcp-server/pulsemcp.json` (already exists, verify)

```json
{
  "name": "Coherence Network",
  "slug": "coherence-network",
  "description": "Publish ideas, query the knowledge graph, record resonance, and collaborate with AI nodes.",
  "repository": "https://github.com/seeker71/Coherence-Network",
  "npm_package": "coherence-mcp-server",
  "tags": ["knowledge-graph", "resonance", "ideas"],
  "verified": false
}
```

---

## Verification Scenarios

### Scenario 1 — All task-specified registries appear in submission inventory

**Setup:** API running with updated `_TARGETS` including `glama` and `pulsemcp`.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-submissions | \
  python3 -c "import sys,json; d=json.load(sys.stdin); ids=[i['registry_id'] for i in d['items']]; print(ids); print('glama' in ids, 'pulsemcp' in ids)"
```

**Expected:**
```
['modelcontextprotocol-registry', 'npm', 'smithery', 'glama', 'pulsemcp', 'mcp-so', 'clawhub', 'agentskills']
True True
```
(exact order may vary; both `glama` and `pulsemcp` must be present)

**Edge — missing glama.json:** Delete `mcp-server/glama.json` →
`glama` item shows `status: "missing_assets"` and
`missing_files: ["mcp-server/glama.json"]`. `core_requirement_met` drops
to `false` if this causes < 5 ready.

---

### Scenario 2 — Core requirement met when all assets are present

**Setup:** All required asset files exist in the repo tree.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-submissions | \
  python3 -c "import sys,json; d=json.load(sys.stdin); s=d['summary']; print(s['core_requirement_met'], s['submission_ready_count'])"
```

**Expected:**
```
True 6
```
(or `True 5` if exactly one registry is legitimately blocked)

**Edge — skill SKILL.md deleted:** `clawhub` and `agentskills` both show
`status: "missing_assets"`. `submission_ready_count` drops to 4 or fewer.
`core_requirement_met` becomes `false`.

---

### Scenario 3 — Stats endpoint returns structured results with correct source labels

**Setup:** Fresh deployment, no `.cache/registry_stats/` files present.

**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats" | \
  python3 -c "
import sys, json
d = json.load(sys.stdin)
for i in d['items']:
    print(i['registry_id'], i['source'], i['install_count'])
print('HTTP_200_OK')
"
```

**Expected:**
- Each item has `source` in `["live", "cached", "unavailable"]`
- `mcp-so`, `clawhub`, `agentskills`, `glama` show `source: "unavailable"`
  (no public stat API)
- `smithery` and `pulsemcp` show `source: "live"` or `source: "cached"`
- No item triggers HTTP 500
- `HTTP_200_OK` is printed (overall response is 200)

**Edge — Smithery API down:** `smithery` item returns `source: "unavailable"`,
`install_count: null`, `error` contains a non-empty message.
All other items are unaffected. HTTP 200 still returned.

---

### Scenario 4 — Cache refresh behaviour

**Setup:** `.cache/registry_stats/smithery.json` exists with
`fetched_at` from 23 hours ago.

**Action (no refresh — should use cache):**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); s=[i for i in d['items'] if i['registry_id']=='smithery'][0]; print(s['source'])"
```
**Expected:** `cached`

**Action (force refresh):**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats?refresh=true" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); s=[i for i in d['items'] if i['registry_id']=='smithery'][0]; print(s['source'], s['fetched_at'])"
```
**Expected:** `live <ISO-8601 timestamp>` (cache was bypassed and updated)

**Edge — cache older than 24 h:** Auto-refreshes on next regular call.
`source` is `live` even without `?refresh=true`.

---

### Scenario 5 — Dashboard merges readiness + stats in one call

**Setup:** At least 5 registries are `submission_ready`; stats cache populated.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/registry-dashboard | \
  python3 -c "
import sys, json
d = json.load(sys.stdin)
print('core_requirement_met:', d['submission_summary']['core_requirement_met'])
print('total_installs:', d['stats_summary']['total_installs'])
for i in d['items']:
    print(i['registry_id'], i['status'], i['install_count'])
"
```

**Expected:**
- `core_requirement_met: True`
- One line per registry showing `registry_id`, `status` (e.g.
  `submission_ready` or `missing_assets`), and `install_count` (int or `null`)
- HTTP 200

**Edge — stats fetch completely fails:** Dashboard still returns HTTP 200.
All `install_count` fields are `null`, `stat_source` is `"unavailable"`.
Submission data (`status`, `missing_files`) is unaffected.

---

## How to Show It Is Working Over Time (open question answer)

| Signal | How to observe | Frequency |
|--------|---------------|-----------|
| Assets ready | `GET /api/discovery/registry-submissions` → `core_requirement_met: true` | Every deploy CI check |
| First install | `GET /api/discovery/registry-stats?refresh=true` → `total_installs > 0` for Smithery or PulseMCP | After each registry PR merges |
| Growth trend | Compare successive cache files in `.cache/registry_stats/` — `install_count` must be non-decreasing | Weekly cron |
| Glama/MCP.so visibility | Manual: open each public listing URL and confirm the entry appears | One-time at submission |
| Submission PR state | Store merged PR URL in `notes` field of each `_RegistryTarget`; visible in `/registry-submissions` response | Updated at PR merge time |

A **zero install count does not mean the feature is broken** — it means no
external agent has installed yet. The spec is closed when the asset-readiness
check passes and all endpoints return correct structure. Growing counts are the
business health signal, not the spec close criterion.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC1 | `GET /api/discovery/registry-submissions` returns items for `smithery`, `glama`, `pulsemcp`, `mcp-so`, and at least one skill registry. |
| AC2 | `summary.core_requirement_met = true` when all required asset files are present. |
| AC3 | `summary.core_requirement_met = false` when any required file is deleted. |
| AC4 | `GET /api/discovery/registry-stats` returns one item per registry with `source` in `["live","cached","unavailable"]`. |
| AC5 | `?refresh=true` forces live fetch and updates the cache file timestamp. |
| AC6 | Stats API returns HTTP 200 (not 500) when Smithery/PulseMCP APIs are unreachable. |
| AC7 | `GET /api/discovery/registry-dashboard` returns HTTP 200 with merged data even if stats are fully unavailable. |
| AC8 | `mcp-server/glama.json` is valid JSON with `name`, `description`, `url`, `license`, `tags`, `install.npx`. |
| AC9 | `mcp-server/pulsemcp.json` is valid JSON with `name`, `slug`, `description`, `repository`, `npm_package`. |
| AC10 | All new endpoints covered by pytest tests with happy-path and failure-mode cases. |

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| Smithery/PulseMCP stat APIs may change shape | Cache design uses a thin wrapper; schema change only breaks live fetch — cached values still served |
| GitHub rate limits on Glama star-count fetch | Use unauthenticated API; backoff; 60 req/h is enough for weekly refresh |
| Third-party registry PRs delayed or rejected | Submission readiness is tracked independently of acceptance; `notes` field captures PR URL |
| `mcp.so`, `clawhub`, `agentskills` have no public count APIs | Marked `unavailable`; `install_count: null` is valid |
| `skills.sh` and `askill.sh` may require distinct manifest formats | Investigate before PR; update validators accordingly |
| Assumption: ≥ 5 suitable registries remain open at implementation time | If not, escalate with a blocker note rather than expanding scope |

---

## Known Gaps and Follow-up Tasks

- [ ] Once Smithery/PulseMCP counts are non-zero, add weekly PostgreSQL time-series recording for trend graphing (follow-up spec).
- [ ] Web dashboard panel `/discovery` rendering `RegistryDashboard` with status badges and sparklines (Spec 181).
- [ ] Automated PR-creation script for Glama and PulseMCP, triggered when `submission_ready_count >= 5` (Spec 182).
- [ ] `mcp.so` requires manual web-form submission; document URL and last submission date in `mcp-server/README.md`.
- [ ] `skills.sh`/`askill.sh` specific manifest requirements to be verified before PR submission.

---

## Verification (CI-ready summary)

```bash
# 1. Asset readiness
curl -sf https://api.coherencycoin.com/api/discovery/registry-submissions | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert d['summary']['core_requirement_met'], 'FAIL: core_requirement_met is false'; print('PASS: registry submissions ready')"

# 2. Stats endpoint structure
curl -sf https://api.coherencycoin.com/api/discovery/registry-stats | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert all('source' in i for i in d['items']), 'FAIL: missing source field'; print('PASS:', len(d['items']), 'registries tracked')"

# 3. Dashboard single-call proof
curl -sf https://api.coherencycoin.com/api/discovery/registry-dashboard | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert 'submission_summary' in d and 'stats_summary' in d, 'FAIL: missing summary fields'; print('PASS: dashboard merges both datasets')"
```
