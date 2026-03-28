# Spec: Submit to 5+ MCP and Skill Registries for Discovery

**Idea ID:** idea-4deb5bd7c800
**Type:** Distribution / Growth
**Status:** Draft
**Date:** 2026-03-28

---

## Summary

Register the Coherence Network's MCP server (`coherence-mcp-server`) and skill (`coherence-network`) on at least six public discovery registries: **Smithery**, **Glama** (via `awesome-mcp-servers` GitHub PR), **PulseMCP**, **mcp.so**, **skills.sh**, and **askill.sh**. After each registration is live, track install/download counts through a new `/api/registry/metrics` endpoint that consolidates counts from npm, Smithery, and other sources into a single observable dashboard.

### Why this matters

Discovery is the top-of-funnel for adoption. An MCP server that nobody can find earns zero contributions. Every registry listing is a permanent inbound channel. Tracking install counts converts vague "is anyone using this?" uncertainty into a concrete, time-series signal that the team can act on.

---

## Goals

1. Achieve verified listings on all six registries by deploying the artefacts already prepared in `docs/registry-submissions/`.
2. Surface install/download metrics on the API so dashboards and the runner can alert when counts stagnate.
3. Make the proof of "this is working" objective: a badge, a number, and a trend line.

---

## Out of Scope

- Building a custom web scraper or crawler.
- Paying for sponsored listings.
- Auto-submitting on behalf of human maintainers (submission steps require maintainer action on external sites).

---

## Background

The following submission artefacts already exist in `docs/registry-submissions/`:

| File | Registry | Status |
|------|----------|--------|
| `smithery-submission.md` | Smithery | Pending human submit |
| `glama-awesome-mcp-servers.md` | Glama / awesome-mcp-servers | Pending PR |
| `pulsemcp-submission.json` | PulseMCP | Pending form fill |
| `mcpso-submission.md` | mcp.so | Pending form fill |
| `skills-sh-submission.md` | skills.sh | Pending PR/form |
| `askill-sh-submission.md` | askill.sh | Pending submission |

`smithery.yaml` is in the repo root. `skills/coherence-network/SKILL.md` is the canonical skill file.

---

## Requirements

### R1 — Registry Listings (human-executed steps, tracked via spec)

Each registry must have a confirmed listing URL before this spec is considered Done.

| # | Registry | Artefact | Submit URL |
|---|----------|----------|------------|
| 1 | Smithery | `smithery.yaml` (auto-discovered) | https://smithery.ai/submit |
| 2 | Glama (awesome-mcp-servers) | `docs/registry-submissions/glama-awesome-mcp-servers.md` | PR to https://github.com/punkpeye/awesome-mcp-servers |
| 3 | PulseMCP | `docs/registry-submissions/pulsemcp-submission.json` | https://pulsemcp.com/submit |
| 4 | mcp.so | `docs/registry-submissions/mcpso-submission.md` | https://mcp.so (form or PR) |
| 5 | skills.sh | `docs/registry-submissions/skills-sh-submission.md` | https://skills.sh |
| 6 | askill.sh | `docs/registry-submissions/askill-sh-submission.md` | https://askill.sh |

### R2 — Registry Tracking Document

Create `docs/REGISTRY_SUBMISSIONS.md` — a machine-readable + human-readable status file:

```markdown
# Registry Submissions — coherence-mcp-server / coherence-network

| Registry   | Type  | Status   | Listing URL | Submitted | Live Date |
|------------|-------|----------|-------------|-----------|-----------|
| Smithery   | MCP   | pending  | —           | —         | —         |
| Glama      | MCP   | pending  | —           | —         | —         |
| PulseMCP   | MCP   | pending  | —           | —         | —         |
| mcp.so     | MCP   | pending  | —           | —         | —         |
| skills.sh  | Skill | pending  | —           | —         | —         |
| askill.sh  | Skill | pending  | —           | —         | —         |
```

Fields:
- `Status`: `pending` | `submitted` | `live` | `rejected`
- `Listing URL`: canonical URL of the live listing (blank until live)
- `Submitted`: ISO 8601 date the submission was made
- `Live Date`: ISO 8601 date the listing appeared publicly

### R3 — Registry Metrics API

New endpoint: `GET /api/registry/metrics`

Returns consolidated install/download counts aggregated from available sources.

**Response schema (Pydantic):**

```python
class RegistryMetricSource(BaseModel):
    source: str           # "npm", "smithery", "pulsemcp", etc.
    count: int            # raw install/download count
    fetched_at: str       # ISO 8601 UTC
    listing_url: str | None

class RegistryMetricsResponse(BaseModel):
    total_installs: int
    sources: list[RegistryMetricSource]
    as_of: str            # ISO 8601 UTC — time of most recent fetch
```

**Data sources (implemented incrementally):**

| Source | How to fetch | Priority |
|--------|-------------|----------|
| npm downloads | `GET https://api.npmjs.org/downloads/point/last-month/coherence-mcp-server` | P0 |
| Smithery installs | Smithery API or scrape listing page | P1 |
| GitHub stars (proxy) | `GET https://api.github.com/repos/seeker71/Coherence-Network` → `stargazers_count` | P1 |
| PulseMCP | Manual update or scrape | P2 |

The endpoint must always return 200 even if some sources fail; failed sources are included with `count: -1` and an `error` field.

### R4 — README Badges

`README.md` must include:
1. Smithery badge: `[![Smithery](https://smithery.ai/badge/coherence-mcp-server)](https://smithery.ai/server/coherence-mcp-server)`
2. npm downloads badge: `[![npm downloads](https://img.shields.io/npm/dm/coherence-mcp-server)](https://www.npmjs.com/package/coherence-mcp-server)`

Badges should appear in the "Install" section near the top of the README.

### R5 — Idea Progress Tracking

The idea `idea-4deb5bd7c800` must be updated in the system with:
- `status: in_progress` while submissions are pending
- `status: done` once all 6 registries reach `live` status in `docs/REGISTRY_SUBMISSIONS.md`

---

## Data Model Changes

### New API file

`api/app/routers/registry_metrics.py` — implements `GET /api/registry/metrics`

### New service file

`api/app/services/registry_metrics_service.py` — fetches counts from npm and GitHub, returns `RegistryMetricsResponse`.

### Router registration

Register `/api/registry/metrics` in `api/app/main.py` (or the app factory).

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `docs/REGISTRY_SUBMISSIONS.md` | Create — status tracking table |
| `api/app/routers/registry_metrics.py` | Create — `GET /api/registry/metrics` |
| `api/app/services/registry_metrics_service.py` | Create — fetch npm + GitHub stats |
| `api/app/models/registry_metrics.py` | Create — Pydantic models |
| `api/app/main.py` | Modify — register new router |
| `README.md` | Modify — add Smithery + npm badges |

---

## API Specification

### `GET /api/registry/metrics`

**Auth:** None required (public read)

**Response 200:**

```json
{
  "total_installs": 142,
  "as_of": "2026-03-28T09:00:00Z",
  "sources": [
    {
      "source": "npm",
      "count": 138,
      "fetched_at": "2026-03-28T09:00:00Z",
      "listing_url": "https://www.npmjs.com/package/coherence-mcp-server"
    },
    {
      "source": "github_stars",
      "count": 4,
      "fetched_at": "2026-03-28T09:00:00Z",
      "listing_url": "https://github.com/seeker71/Coherence-Network"
    }
  ]
}
```

**Response 200 (with partial failure):**

```json
{
  "total_installs": 138,
  "as_of": "2026-03-28T09:00:00Z",
  "sources": [
    {
      "source": "npm",
      "count": 138,
      "fetched_at": "2026-03-28T09:00:00Z",
      "listing_url": "https://www.npmjs.com/package/coherence-mcp-server"
    },
    {
      "source": "smithery",
      "count": -1,
      "fetched_at": "2026-03-28T09:00:00Z",
      "listing_url": null,
      "error": "Smithery listing not yet live"
    }
  ]
}
```

**Never returns 4xx or 5xx** — partial failures degrade gracefully.

---

## Verification Scenarios

### Scenario 1 — Registry metrics endpoint exists and returns valid structure

**Setup:** API deployed with the new router registered.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/registry/metrics | python3 -m json.tool
```

**Expected result:**
- HTTP 200
- Response contains `total_installs` (integer ≥ 0)
- Response contains `sources` array with at least one entry
- Each source entry has `source`, `count`, `fetched_at`, `listing_url` fields
- `as_of` is a valid ISO 8601 UTC timestamp

**Edge case:** Even if npm is unreachable, endpoint returns HTTP 200 with `count: -1` for that source, never HTTP 500.

---

### Scenario 2 — npm download count is a real number

**Setup:** `coherence-mcp-server` npm package exists and has been downloaded at least once.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/registry/metrics | python3 -c \
  "import sys, json; d=json.load(sys.stdin); npm=[s for s in d['sources'] if s['source']=='npm'][0]; print(npm['count'])"
```

**Expected result:**
- Prints a non-negative integer
- Value matches (within ±5) the count from `https://api.npmjs.org/downloads/point/last-month/coherence-mcp-server`

**Edge case:** If npm API is temporarily unreachable, `count` is -1 and an `error` field is present; `total_installs` excludes the failed source.

---

### Scenario 3 — REGISTRY_SUBMISSIONS.md reflects submission state

**Setup:** `docs/REGISTRY_SUBMISSIONS.md` exists in the repo.

**Action:**
```bash
cat docs/REGISTRY_SUBMISSIONS.md
```

**Expected result:**
- File contains a Markdown table with rows for all 6 registries: Smithery, Glama, PulseMCP, mcp.so, skills.sh, askill.sh
- Each row has `Status` field that is one of: `pending`, `submitted`, `live`, `rejected`
- Once submissions are made, at least one row has `Status: submitted` or `Status: live`

**Edge case:** If a registry rejects the submission, that row shows `Status: rejected` with a note — the spec is still "done" for that registry's effort (rejection is a terminal state, not a blocker).

---

### Scenario 4 — README badges are present

**Setup:** Latest `README.md` on `main` branch.

**Action:**
```bash
grep -c "smithery.ai/badge" README.md && grep -c "shields.io/npm" README.md
```

**Expected result:**
- Both commands print `1` (at least one match each)

**Edge case:** If README structure changes, badges must appear in the first 150 lines.

---

### Scenario 5 — Graceful degradation when all external sources fail

**Setup:** Temporarily block outbound HTTP in a test environment (or mock all HTTP clients to raise exceptions).

**Action:**
```bash
# Unit test / pytest scenario:
# Mock httpx.AsyncClient to raise httpx.ConnectError for all requests
# Call GET /api/registry/metrics
```

**Expected result:**
- HTTP 200
- `total_installs: 0`
- All entries in `sources` have `count: -1`
- Response includes `error` field per failing source
- No unhandled exception, no 500

---

## Risks and Assumptions

| Risk | Mitigation |
|------|------------|
| Registry sites change their submission process | Submission docs are templates, not scripts — maintainer checks the form/PR process at submit time |
| npm package name squatting | `coherence-mcp-server` already published; verify ownership before submitting |
| Smithery auto-discovery fails if `smithery.yaml` is malformed | Validate with Smithery's schema checker before submitting |
| awesome-mcp-servers PR may take weeks to merge | Status in `REGISTRY_SUBMISSIONS.md` tracks `submitted` vs `live` separately |
| External API rate limits | Registry metrics endpoint is not cached in v1; add caching (5-minute TTL) in follow-up |
| mcp.so and skills.sh submission processes are undocumented | Maintainer checks each site's contribution guide; falls back to opening a GitHub issue on their repos |

---

## Known Gaps and Follow-up Tasks

1. **Smithery install count API** — Smithery does not have a documented public API for install counts. Until one is found, Smithery source returns `count: -1` with a note. Follow-up: poll Smithery's listing page HTML.
2. **Metrics caching** — The v1 endpoint fetches live on every request. A 5-minute in-memory or Redis cache should be added to avoid hammering npm's API.
3. **Trend history** — This spec delivers point-in-time counts. A time-series store (e.g., one daily row in PostgreSQL) is a logical follow-up for trend dashboards.
4. **Automated badge generation** — Shields.io badges are static; a dynamic badge served from `/api/registry/metrics/badge.svg` would always show the current count.
5. **Registry rejection handling** — If Glama's PR is not merged within 60 days, consider alternative discovery registries (e.g., mcp-get, modelcontextprotocol.io).

---

## Acceptance Criteria

- [ ] `docs/REGISTRY_SUBMISSIONS.md` exists with rows for all 6 registries
- [ ] `GET /api/registry/metrics` returns HTTP 200 with valid JSON matching the schema
- [ ] npm source returns a real download count (≥ 0) when npm API is reachable
- [ ] All 6 submissions have been made (status ≥ `submitted` in tracking doc)
- [ ] At least 3 registries show `Status: live`
- [ ] README has Smithery badge and npm downloads badge
- [ ] All Verification Scenarios pass against production

---

## Implementation Order

1. Create `docs/REGISTRY_SUBMISSIONS.md` (tracking table, all rows `pending`)
2. Implement `api/app/models/registry_metrics.py`
3. Implement `api/app/services/registry_metrics_service.py`
4. Implement `api/app/routers/registry_metrics.py`
5. Register router in `api/app/main.py`
6. Add badges to `README.md`
7. Write tests in `tests/test_registry_metrics.py`
8. Human step: execute each submission using the artefacts in `docs/registry-submissions/`
9. Update `docs/REGISTRY_SUBMISSIONS.md` as submissions go live
