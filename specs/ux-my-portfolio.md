# Spec: My Portfolio — Personal Contributor View (ux-my-portfolio)

**Spec ID**: ux-my-portfolio  
**Status**: Draft (spec-only; implementation follows in a later task)  
**Idea ID**: ux-my-portfolio  
**Author**: product-manager  
**Date**: 2026-03-28  
**Priority**: High  

---

## Summary

Contributors need a **single, trustworthy page** that answers: *What have I done? What did I invest in? Where is my CC? How are my ideas doing?* The experience must work for non-technical users as a **garden** (each “plant” is an idea the person helped grow) and for technical users as a **ledger** with a full audit trail into value lineage, stakes, and task outcomes.

This spec defines the **product contract**: information architecture, authentication model, API and web surfaces, data shapes, drill-down behavior, and **executable verification scenarios** that reviewers can run against production. It builds on existing platform capabilities (`/api/identity/me`, ideas, value lineage, agent tasks, stakes) and adds a **thin aggregation layer** so the client does not need N+1 calls for the dashboard.

### What done looks like (MVP)

- A authenticated web route **`/portfolio`** renders the four main sections: linked identities, CC balance + history chart, ideas contributed, ideas staked, tasks completed — each with drill-down to contribution detail and lineage.
- **`GET /api/portfolio/me`** (and focused sub-resources) return a stable JSON contract for the page and for **`cc portfolio`** CLI parity.
- All read paths enforce **contributor-scoped authorization** (only the authenticated contributor’s data).
- Verification scenarios below pass against a deployment where test data has been seeded per setup instructions.

---

## Problem Statement

Today, a contributor’s signal is scattered across ideas list filters, value lineage records, stake records, treasury/CC movements, and agent task history. There is no **one place** that ties identity → economic position → intellectual contribution → execution history. That gap reduces trust (“where did my CC go?”), reduces retention (“what did I actually ship?”), and makes governance harder (“who is aligned long-term?”).

---

## Goals

1. **Unified narrative**: One screen tells the story of the contributor’s relationship to the network.
2. **Dual metaphor**: Garden (human-friendly) and ledger (audit-ready) are **two views of the same underlying nodes and edges**, not two data models.
3. **Drill-down integrity**: Every aggregate row is clickable to **source records** (idea → my contributions → lineage chain; contribution → CC earned → parent lineage).
4. **Provable over time**: The page exposes **how we know** the feature is working (metrics and freshness), not only static UI.

---

## Requirements

### R1 — Identity strip (top of page)

- Show **all linked identities** for the authenticated contributor (provider, display name, verification state, linked-at).
- Empty state: explain how to link (GitHub, Ethereum signature, etc.) with **link to existing identity flows** (`GET /api/identity/providers` and documented link/verify flows).
- **Must not** show other contributors’ identities.

### R2 — CC balance and earning history

- Show **current CC balance** (or best available ledger aggregate from treasury / internal CC accounting — exact source is implementation detail but must be **one canonical field** in the API response).
- Show a **simple time-series chart** of net CC movement (daily or weekly buckets — configurable granularity query param).
- Support **`view=absolute`** (default) and **`view=network_share`**:
  - **Absolute**: CC amounts as stored (primary for payouts and clarity).
  - **Network share**: contributor’s CC-related position as **percentage of circulating or total network CC** (definition MUST be versioned in API docs; see Data model).
- Empty state: zero balance with explanation and CTA to treasury/deposit docs if applicable.

### R3 — Ideas I contributed to

- Tabular or card list: **idea id/title**, **lifecycle status**, **my contribution type(s)** (spec, code, review, idea authorship, etc.), **current attributed value** (from value lineage / valuation where available).
- Sort default: **recency of my last contribution**, then **value**.
- Click **idea** → navigate to drill-down panel or route showing **only my contributions** to that idea, with links to full idea record (`GET /api/ideas/{id}` or equivalent) and **value lineage** entries involving me.

### R4 — Ideas I staked on

- List: idea, **stake amount (CC)**, **stake timestamp**, **ROI since staking** (ratio or %), and **idea status** at time of query.
- ROI definition MUST match backend stake/valuation semantics (spec references `stake_compute_service` / existing stake endpoints); if ROI cannot be computed, return **`null` with reason code** — never a misleading number.

### R5 — Tasks I completed

- List: task id, **direction/summary**, **executor/provider used**, **terminal status** (`completed`, `failed`, `needs_decision`, etc.), **completed_at** if present.
- Filter chips: provider, outcome, date range (web); query params on API.

### R6 — Drill-down: garden ↔ ledger

- **Idea row** → contributions I made to that idea → **full value lineage** graph slice (nodes/edges involving me).
- **Contribution row** → **CC earned** (if applicable) + **lineage chain id** + link to **`GET /api/value-lineage/links/{id}`** (and child resources such as valuation / usage-events as already implemented).
- Preserve **deep links**: `/portfolio?idea={id}&tab=contributions` (or dedicated nested route — exact routing is implementation choice but must be in the web table below).

### R7 — Non-functional

- **P95 API latency** for `GET /api/portfolio/me` < **800ms** with warm cache on production-sized fixture (documented in verification).
- **Accessibility**: chart has textual fallback (table of same data); primary actions keyboard-reachable.

---

## Open Questions (resolved for MVP direction)

| Question | Decision for this spec | Follow-up |
|----------|------------------------|-----------|
| How does a contributor authenticate? | **Primary**: `X-API-Key` header resolving to `contributor_id` (existing **`GET /api/identity/me`** behavior). **Web**: session cookie or bearer from same key store — implementation phase picks Next.js pattern; **no anonymous portfolio**. | If we add OAuth-only browser users, add **`GET /api/identity/me` session variant** without duplicating portfolio logic. |
| Do we need sessions? | **Yes for browser UX**, but **sessions are not the source of truth** — they bind to `contributor_id`. API keys remain valid for automation and `cc` CLI. | Document session TTL in web spec slice. |
| Absolute CC vs % of network? | **Both**: default absolute; optional **network_share** view with **documented denominator** (`network_cc_total` field in response). | Governance must approve denominator definition before showing network_share in prod. |
| How do we improve the idea and prove it works? | Ship **Portfolio Health** subsection: freshness timestamps, count of lineage-linked ideas, % tasks succeeded, last stake ROI update. Re-use **`manifestation_status`** / idea health fields where present. | Add analytics events (`portfolio_view`, `portfolio_drilldown`) in implementation spec. |

---

## API Contract

### Existing endpoints (unchanged; consumed by portfolio)

| Method | Path | Role in portfolio |
|--------|------|-------------------|
| GET | `/api/identity/me` | Resolve contributor from API key; identity count |
| GET | `/api/identity/providers` | Help content / link flows |
| GET | `/api/ideas` | Idea metadata; filter client-side until server filter exists |
| GET | `/api/ideas/{idea_id}` | Idea detail drill-down |
| GET | `/api/value-lineage/links` | Discover lineage IDs (filter by contributor in implementation) |
| GET | `/api/value-lineage/links/{id}` | Lineage detail |
| GET | `/api/value-lineage/links/{id}/valuation` | Value / ROI context |
| GET | `/api/agent/tasks` | Task history (filter by contributor in implementation) |

### New endpoints (MVP — to be implemented in a follow-on task)

All require **`X-API-Key`** unless otherwise noted for session-auth web proxy.

#### `GET /api/portfolio/me`

**Query**

| Param | Type | Description |
|-------|------|-------------|
| `view` | enum | `absolute` (default) \| `network_share` |
| `cc_bucket` | enum | `day` \| `week` (for embedded series) |

**Response 200** (`application/json`)

```json
{
  "contributor_id": "alice",
  "generated_at": "2026-03-28T12:00:00Z",
  "schema_version": 1,
  "identities": [
    {
      "provider": "github",
      "provider_id": "octocat",
      "display_name": "Alice",
      "verified": true,
      "linked_at": "2026-01-15T10:00:00Z"
    }
  ],
  "cc": {
    "balance_cc": 1250.5,
    "network_cc_total": 1000000.0,
    "network_share_pct": 0.00012505,
    "history": [
      { "period_start": "2026-03-01T00:00:00Z", "net_cc": 12.0, "bucket": "week" }
    ]
  },
  "ideas_contributed": [
    {
      "idea_id": "ux-my-portfolio",
      "title": "My Portfolio",
      "status": "implementing",
      "contribution_types": ["spec", "product"],
      "attributed_value_cc": 42.0,
      "last_contribution_at": "2026-03-28T11:00:00Z"
    }
  ],
  "ideas_staked": [
    {
      "idea_id": "portfolio-governance",
      "amount_cc": 100.0,
      "staked_at": "2026-02-01T00:00:00Z",
      "roi_since_stake": 0.12,
      "roi_unavailable_reason": null
    }
  ],
  "tasks_completed": [
    {
      "task_id": "task_cc2f6e510bb5cd91",
      "direction": "Write portfolio spec",
      "executor": "cursor",
      "status": "completed",
      "completed_at": "2026-03-28T12:30:00Z"
    }
  ],
  "health": {
    "lineage_linked_ideas": 3,
    "tasks_succeeded_pct": 87.5,
    "data_freshness_s": 120
  }
}
```

**Response 401**: missing or invalid API key.  
**Response 503**: aggregation dependency unavailable (explicit JSON `detail` + `retry_after` optional).

#### `GET /api/portfolio/me/ideas/{idea_id}/contributions`

Returns **only this contributor’s** contributions for the idea, with pointers to lineage link ids.

#### `GET /api/portfolio/me/lineage`

Returns lineage link summaries where **this contributor** appears in `contributors` map or equivalent attribution.

*(Exact split between one fat `GET /api/portfolio/me` vs sub-resources is an implementation tradeoff; MVP **must** ship `GET /api/portfolio/me` and **at least one** drill-down endpoint for contributions or lineage.)*

---

## Web surfaces

| Route | Purpose |
|-------|---------|
| `/portfolio` | Main dashboard (garden + ledger toggle) |
| `/portfolio/ideas/{idea_id}` | My contributions to one idea + lineage |
| `/portfolio/lineage/{lineage_id}` | Full lineage audit view filtered to “my role” |

Deep links must be shareable **only to the owning contributor** (same auth gate); if unauthenticated → redirect to login / API key instructions.

---

## CLI surfaces

| Command | Behavior |
|---------|----------|
| `cc portfolio` | Print summary: balance, idea counts, last tasks (JSON with `--json`) |
| `cc portfolio ideas` | List ideas contributed |
| `cc portfolio tasks` | List tasks with provider |
| `cc portfolio lineage` | List lineage links involving me |

CLI uses the same **`X-API-Key`** / keystore resolution as other `cc` commands (implementation phase wires to `~/.coherence-network/keys.json` or env).

---

## Data model (logical)

```yaml
PortfolioSnapshot:
  contributor_id: string
  generated_at: datetime (UTC ISO 8601)
  schema_version: int
  identities: LinkedIdentity[]
  cc: CCPosition
  ideas_contributed: IdeaContributionRow[]
  ideas_staked: StakeRow[]
  tasks_completed: TaskCompletionRow[]
  health: PortfolioHealth

LinkedIdentity:
  provider: string
  provider_id: string
  display_name: string | null
  verified: bool
  linked_at: datetime | null

CCPosition:
  balance_cc: float
  network_cc_total: float | null   # null if denominator unavailable
  network_share_pct: float | null
  history: CCHistoryBucket[]

CCHistoryBucket:
  period_start: datetime
  net_cc: float
  bucket: enum [day, week]

IdeaContributionRow:
  idea_id: string
  title: string
  status: string
  contribution_types: string[]
  attributed_value_cc: float | null
  last_contribution_at: datetime | null

StakeRow:
  idea_id: string
  amount_cc: float
  staked_at: datetime
  roi_since_stake: float | null
  roi_unavailable_reason: string | null

TaskCompletionRow:
  task_id: string
  direction: string
  executor: string
  status: string
  completed_at: datetime | null

PortfolioHealth:
  lineage_linked_ideas: int
  tasks_succeeded_pct: float | null
  data_freshness_s: int | null
```

---

## Files to Create / Modify (implementation phase — not in this spec task)

- `api/app/routers/portfolio.py` — new router; register in `app/main.py`
- `api/app/services/portfolio_service.py` — aggregation, contributor scoping
- `api/app/models/portfolio.py` — Pydantic models (`schema_version` for forward compatibility)
- `web/app/portfolio/page.tsx` — dashboard
- `web/app/portfolio/ideas/[ideaId]/page.tsx` — drill-down
- `web/components/portfolio/*.tsx` — chart, tables, garden visualization
- `api/tests/test_portfolio.py` — contract tests
- Optional: `scripts/cc_cmd/portfolio.py` or extension of existing `cc` plugin tree

**This spec task only adds** `specs/ux-my-portfolio.md`.

---

## Acceptance criteria

- [ ] `/portfolio` (web) shows all five sections with real or seeded data in staging.
- [ ] `GET /api/portfolio/me` returns `schema_version` and passes JSON schema tests.
- [ ] No response leaks another contributor’s tasks, stakes, or CC history.
- [ ] Drill-down from idea → contributions → lineage works without 404s for valid ids.
- [ ] `cc portfolio` returns non-empty summary when key is configured.
- [ ] Accessibility: chart data duplicated as sortable table.

---

## Verification Scenarios

### Scenario VS1 — Authenticated read: full portfolio snapshot

**Setup**: Contributor `alice` exists; API key in keystore maps to `alice`. At least one idea lists `alice` as contributor; at least one agent task completed by `alice`; optional stake and lineage link including `alice`.

**Action**:

```bash
export API=https://api.coherencycoin.com
curl -sS -H "X-API-Key: $COHERENCE_API_KEY" "$API/api/portfolio/me?view=absolute&cc_bucket=week"
```

**Expected result**:

- HTTP **200**.
- JSON includes `"contributor_id":"alice"`, numeric `"schema_version"`, ISO `"generated_at"`.
- Arrays `ideas_contributed`, `tasks_completed` each have **≥ 1** item when setup data exists; `cc.balance_cc` is a **finite number** (not NaN).
- `health.data_freshness_s` is **non-null** integer ≥ 0.

**Edge case**: Omit `X-API-Key` → HTTP **401** with JSON `detail` containing `Missing` or `Invalid` (not 500).

---

### Scenario VS2 — Create–read cycle for lineage drill-down (proves audit trail)

**Setup**: Clean dev DB or isolated test DB; `alice` key present.

**Action**:

```bash
# 1) Create lineage link (existing API; uses write key)
curl -sS -X POST "$API/api/value-lineage/links" -H "Content-Type: application/json" -H "X-API-Key: $COHERENCE_API_KEY" \
  -d '{"idea_id":"ux-my-portfolio","spec_id":"ux-my-portfolio","implementation_refs":["commit:test"],"contributors":{"idea":"alice","spec":"alice","implementation":"alice"},"estimated_cost":10}'

# 2) Capture id from response LINEAGE_ID then:
curl -sS -H "X-API-Key: $COHERENCE_API_KEY" "$API/api/portfolio/me/lineage"
```

**Expected result**:

- Step 1 returns **201** with `"id"` present.
- Step 2 returns **200** and a list containing an object with `lineage_id` equal to **LINEAGE_ID** and `idea_id` **ux-my-portfolio**.

**Edge case**: `GET /api/portfolio/me/ideas/nonexistent-idea/contributions` → **404** (not 500).

---

### Scenario VS3 — Network share view and denominator missing

**Setup**: Same as VS1; optionally force `network_cc_total` unavailable in staging (feature flag).

**Action**:

```bash
curl -sS -H "X-API-Key: $COHERENCE_API_KEY" "$API/api/portfolio/me?view=network_share"
```

**Expected result**:

- HTTP **200**.
- If denominator available: `cc.network_share_pct` is between **0** and **1** (inclusive).
- If unavailable: `cc.network_cc_total` and `cc.network_share_pct` are **`null`** and **`view` does not fabricate percentages**.

**Edge case**: Invalid `view=foo` → **422** validation error.

---

### Scenario VS4 — Web page load and deep link

**Setup**: Staging web with auth cookie or dev API key proxy.

**Action**:

1. Browser: open `https://coherencycoin.com/portfolio`
2. Click first idea in “Ideas I contributed”
3. Address bar should match `/portfolio/ideas/{idea_id}` pattern

**Expected result**:

- Page loads **200** (no blank SSR error).
- Idea drill-down shows **only** current contributor’s contributions (spot-check: no other GitHub handles in rows).

**Edge case**: Logged out user → **redirect** to login or **401** boundary page (not infinite spinner).

---

### Scenario VS5 — Task list provider and outcome

**Setup**: At least one task with `executor` field set (e.g. `cursor`) and status `completed`.

**Action**:

```bash
curl -sS -H "X-API-Key: $COHERENCE_API_KEY" "$API/api/portfolio/me" | jq '.tasks_completed[0] | {task_id, executor, status}'
```

**Expected result**:

- Object includes non-empty **`executor`** string and **`status`** in allowed terminal set (`completed`, `failed`, `needs_decision`, …).

**Edge case**: Contributor with **zero** tasks → `tasks_completed` is **`[]`**, still HTTP 200.

---

## Verification (automated commands — post-implementation)

```bash
cd api && pytest -q tests/test_portfolio.py
cd web && npm run build
```

---

## Concurrency behavior

- Portfolio reads are **read-only**; eventual consistency acceptable (stale `generated_at` up to cache TTL).
- Writes (stakes, tasks) remain on their respective endpoints; portfolio **never** mutates state.

---

## Out of scope (MVP)

- Cross-contributor comparison leaderboards.
- Tax / legal export of earnings.
- Mobile native apps.
- Real-time websocket updates (polling or SWR refresh is enough).

---

## Risks and assumptions

- **Assumption**: Contributor attribution in value lineage and tasks is **consistent** (`contributor_id` strings match across stores). If not, aggregation shows gaps — mitigation: normalization layer in `portfolio_service`.
- **Risk**: `network_cc_total` definition is contentious — wrong denominator erodes trust — mitigation: feature-flag `network_share` until governance signs off.
- **Risk**: N+1 queries slow the dashboard — mitigation: server-side aggregation + short TTL cache keyed by `contributor_id`.

---

## Known gaps and follow-up tasks

- Define **exact** CC ledger source of truth if multiple subsystems exist (treasury vs internal balance).
- Add **E2E Playwright** spec for `/portfolio` when web implementation lands.
- Align **ROI** display with finance review for stakes.

---

## Failure / retry reflection

- **Failure mode**: Upstream Neo4j/Postgres timeout during aggregation.  
- **Blind spot**: Partial data returned without error — **must** use `health.data_freshness_s` and explicit `degraded: true` field (add in implementation if needed).  
- **Next action**: Return **503** or partial JSON with `503` subcode — product decision in implementation.

---

## Research inputs (required)

- `2026-03-28` — Internal: `api/app/routers/contributor_identity.py` (`GET /api/identity/me`) — establishes API-key → contributor resolution for portfolio auth.
- `2026-03-28` — Internal: `api/tests/test_value_lineage.py` — proves lineage create/read path for VS2.
- `2026-03-28` — Internal: `specs/TEMPLATE.md` — spec structure alignment.

---

## Task card (implementation follow-on)

```yaml
goal: Ship authenticated GET /api/portfolio/me and /portfolio web dashboard per specs/ux-my-portfolio.md.
files_allowed:
  - api/app/routers/portfolio.py
  - api/app/services/portfolio_service.py
  - api/app/models/portfolio.py
  - api/app/main.py
  - api/tests/test_portfolio.py
  - web/app/portfolio/page.tsx
done_when:
  - pytest api/tests/test_portfolio.py passes
  - curl GET /api/portfolio/me returns 200 with schema_version for a keyed contributor
  - npm run build succeeds for web
commands:
  - cd api && pytest -q tests/test_portfolio.py
  - cd web && npm run build
constraints:
  - Do not leak other contributors data in any portfolio endpoint
```

---

## Decision gates

- **Approve denominator** for `network_share_pct` before enabling in production (governance).
- **Approve browser session** mechanism (cookie vs bearer) for web — security review.
