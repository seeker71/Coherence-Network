# Spec 186 — My Portfolio: Personal View of Contributions, Stakes, and CC

**Idea**: `my-portfolio-personal-view`
**Status**: Approved — ready for implementation
**Depends on**: Spec 168 (identity/onboarding TOFU), Spec 174 (portfolio models + service), Spec 116 (grounded idea metrics)
**Integrates with**: `portfolio_service`, `me_portfolio` router, `contributors_portfolio` router, `auth_keys`, `contributor_identity_service`

---

## 1. Goal

A contributor needs **one page** that answers four questions at a glance:

1. **What have I done?** — ideas contributed to, tasks completed
2. **What did I invest in?** — ideas staked on, ROI since staking
3. **Where is my CC?** — balance, earning history as a chart
4. **How are my ideas doing?** — health signal, value lineage drill-down

The page is both a **garden** (every plant is an idea you helped grow) and a **ledger** (full audit trail linking every CC credit to the work that earned it).

---

## 2. User Story

> As a contributor, I open `/my-portfolio`, enter my contributor ID or API key, and immediately see my linked identities, CC balance, ideas I worked on, stakes with ROI, and tasks I completed.  I can click any idea to see exactly what I contributed and what that contribution is worth.  I can click any contribution to see the CC earned and the value-lineage chain it belongs to.

---

## 3. Authentication Design

### 3.1 Two Access Modes (non-exclusive)

| Mode | Mechanism | Trust level | Who uses it |
|------|-----------|-------------|-------------|
| **Public** (read-only, by ID) | `GET /api/contributors/{id}/portfolio` — no auth | Anyone who knows the ID | Sharing portfolio links |
| **Authenticated** (private, via API key) | `GET /api/me/portfolio` with `X-API-Key` header | Key holder only | Contributor viewing own data |

### 3.2 Session Strategy

- **No HTTP sessions (cookies/JWT) in MVP.** The `X-API-Key` header is stateless and sufficient.
- API keys are issued at `POST /api/auth/keys` after verifying a contributor identity (Spec 168).
- The web `/my-portfolio` page presents two paths: paste contributor ID (public read) or enter API key (authenticated).
- When an API key is present the UI activates an "authenticated" badge and hides nothing.

### 3.3 Key Lifecycle (existing, referenced here for clarity)

```
POST /api/auth/keys  { contributor_id, provider, provider_id }
→ 201  { api_key, contributor_id, created_at, scopes }
```

The key is stored as SHA-256 hash in `_KEY_STORE`. The raw key is shown once and must be saved by the user.

---

## 4. CC Display: Absolute vs. Percentage

Both are shown:

- **Absolute CC balance** — primary; shown prominently in the summary card.
- **Network percentage** — secondary; shown as `(X.XX% of network)` beneath the balance, derived from `cc_balance / cc_network_total × 100`.
- **CC History chart** — dual y-axis: left = absolute CC earned per period, right = network_pct_at_period_end.

Rationale: Absolute numbers answer "how much did I earn?"; percentage answers "how significant is my stake relative to the whole network?" Both matter.

---

## 5. Proof of Value — Making "Is it Working?" Visible

Each idea card shows a **HealthSignal**:

| Signal | Meaning | Visual |
|--------|---------|--------|
| `active` | Recent commits, API calls, or lineage events in last 30 days | Green dot |
| `slow` | Activity 30–90 days ago | Yellow dot |
| `dormant` | No activity in 90+ days | Gray dot |
| `unknown` | No data yet | Dashed circle |

The drill-down adds:
- **Value lineage summary**: total value flowing through this idea's lineage chain
- **ROI ratio**: `total_value / estimated_cost` (>1.0 = delivering value)
- **Stage events**: count of discrete value-creation events (commits, API calls, user actions)
- **Evidence count**: number of data points backing the health signal

Improvement over time is shown by the CC history series — if the running_total is monotonically increasing, the idea is generating value.

---

## 6. Data Model

All models are already defined in `api/app/models/portfolio.py` (Spec 174). This spec does not add new models but documents them as the canonical contract.

### 6.1 PortfolioSummary (top-level)

```json
{
  "contributor": {
    "id": "alice",
    "display_name": "Alice",
    "identities": [
      {"type": "github", "handle": "alice-gh", "verified": true},
      {"type": "wallet", "handle": "0xabc...", "verified": false}
    ]
  },
  "cc_balance": 142.5,
  "cc_network_pct": 0.83,
  "idea_contribution_count": 7,
  "stake_count": 3,
  "task_completion_count": 12,
  "recent_activity": "2026-03-20T14:00:00Z"
}
```

### 6.2 CCHistory

```json
{
  "contributor_id": "alice",
  "window": "90d",
  "bucket": "7d",
  "series": [
    {
      "period_start": "2026-01-01T00:00:00Z",
      "period_end": "2026-01-08T00:00:00Z",
      "cc_earned": 10.0,
      "running_total": 10.0,
      "network_pct_at_period_end": 0.12
    }
  ]
}
```

### 6.3 IdeaContributionsList

```json
{
  "contributor_id": "alice",
  "total": 7,
  "items": [
    {
      "idea_id": "spec-168",
      "idea_title": "Identity-Driven Onboarding",
      "idea_status": "active",
      "contribution_types": ["code", "spec"],
      "cc_attributed": 25.0,
      "contribution_count": 4,
      "last_contributed_at": "2026-03-15T09:00:00Z",
      "health": {"activity_signal": "active", "value_delta_pct": 12.5, "evidence_count": 8}
    }
  ]
}
```

### 6.4 IdeaContributionDrilldown (click an idea)

```json
{
  "contributor_id": "alice",
  "idea_id": "spec-168",
  "idea_title": "Identity-Driven Onboarding",
  "contributions": [
    {
      "id": "c1",
      "type": "code",
      "date": "2026-03-15T09:00:00Z",
      "asset_id": "commit:abc123",
      "cc_attributed": 10.0,
      "coherence_score": 0.82,
      "lineage_chain_id": "lin-xyz"
    }
  ],
  "value_lineage_summary": {
    "lineage_id": "lin-xyz",
    "total_value": 45.0,
    "roi_ratio": 2.5,
    "stage_events": 12
  }
}
```

### 6.5 ContributionLineageView (click a contribution)

```json
{
  "contributor_id": "alice",
  "contribution_id": "c1",
  "idea_id": "spec-168",
  "contribution_type": "code",
  "cc_attributed": 10.0,
  "lineage_chain_id": "lin-xyz",
  "value_lineage_link": {
    "id": "lin-xyz",
    "idea_id": "spec-168",
    "spec_id": "spec-168",
    "estimated_cost": 18.0
  },
  "lineage_resolution_note": null
}
```

### 6.6 StakesList

```json
{
  "contributor_id": "alice",
  "total": 3,
  "items": [
    {
      "stake_id": "s1",
      "idea_id": "idea-abc",
      "idea_title": "Graph Foundation",
      "cc_staked": 50.0,
      "cc_valuation": 72.0,
      "roi_pct": 44.0,
      "staked_at": "2025-12-01T00:00:00Z",
      "last_valued_at": "2026-03-20T00:00:00Z",
      "health": {"activity_signal": "active", "value_delta_pct": 5.0, "evidence_count": 15}
    }
  ]
}
```

### 6.7 TasksList

```json
{
  "contributor_id": "alice",
  "total": 12,
  "items": [
    {
      "task_id": "task-abc",
      "description": "Implement CC history endpoint",
      "idea_id": "spec-174",
      "idea_title": "Portfolio Service",
      "provider": "claude",
      "outcome": "passed",
      "cc_earned": 5.0,
      "completed_at": "2026-03-18T11:00:00Z"
    }
  ]
}
```

---

## 7. API Endpoints

All endpoints below must exist and return the documented shapes. The `contributors/{id}/…` family is unauthenticated (public). The `/me/…` family requires `X-API-Key`.

### 7.1 Public (by contributor ID)

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| GET | `/api/contributors/{id}/portfolio` | `PortfolioSummary` | `?include_cc=true/false` |
| GET | `/api/contributors/{id}/cc-history` | `CCHistory` | `?window=90d&bucket=7d` |
| GET | `/api/contributors/{id}/idea-contributions` | `IdeaContributionsList` | `?sort=cc_attributed_desc&limit=20&offset=0` |
| GET | `/api/contributors/{id}/idea-contributions/{idea_id}` | `IdeaContributionDrilldown` | |
| GET | `/api/contributors/{id}/stakes` | `StakesList` | `?sort=roi_desc&limit=20` |
| GET | `/api/contributors/{id}/tasks` | `TasksList` | `?status=completed&limit=20` |
| GET | `/api/contributors/{id}/contributions/{contribution_id}/lineage` | `ContributionLineageView` | |

### 7.2 Authenticated (my own portfolio)

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| GET | `/api/me/portfolio` | `PortfolioSummary` | Requires `X-API-Key` |
| GET | `/api/me/cc-history` | `CCHistory` | `?window=90d&bucket=7d` |
| GET | `/api/me/idea-contributions` | `IdeaContributionsList` | |
| GET | `/api/me/idea-contributions/{idea_id}` | `IdeaContributionDrilldown` | |
| GET | `/api/me/stakes` | `StakesList` | |
| GET | `/api/me/tasks` | `TasksList` | |
| GET | `/api/me/contributions/{contribution_id}/lineage` | `ContributionLineageView` | |

### 7.3 Auth Key Management

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/auth/keys` | `{contributor_id, provider, provider_id}` | `{api_key, contributor_id, created_at, scopes}` |

---

## 8. Web Pages

| Route | Purpose |
|-------|---------|
| `/my-portfolio` | Entry page — enter contributor ID or API key |
| `/contributors/{id}/portfolio` | Full portfolio view (public) |
| `/contributors/{id}/portfolio/ideas/{idea_id}` | Idea contribution drill-down |
| `/contributors/{id}/portfolio/contributions/{contribution_id}` | Contribution lineage audit |

### 8.1 Page Layout: `/contributors/{id}/portfolio`

```
┌─────────────────────────────────────────────────────────────┐
│  CONTRIBUTOR HEADER                                          │
│  Display name · [github: handle ✓] [wallet: 0x... ⚬]       │
│  Last active: 3 days ago                                     │
├─────────┬─────────────────────────────────────────────────┤
│ CC       │ CC EARNING HISTORY CHART                        │
│ 142.5    │  ▁▂▃▄▅▆▇█  (area chart, 90d, 7d buckets)       │
│ 0.83%   │                                                  │
├─────────┴─────────────────────────────────────────────────┤
│ IDEAS I CONTRIBUTED TO          [sort ▾]                    │
│  [idea card] title · types · cc · last · health-dot →      │
│  [idea card] ...                                            │
├─────────────────────────────────────────────────────────────┤
│ IDEAS I STAKED ON               [sort ▾]                    │
│  [stake card] title · cc_staked → cc_val · ROI% · health → │
├─────────────────────────────────────────────────────────────┤
│ TASKS I COMPLETED               [filter ▾]                  │
│  [task row] description · provider · outcome · cc · date    │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Open Questions — Resolved

| Question | Resolution |
|----------|-----------|
| How does a contributor authenticate? | Two modes: public by ID (no auth), or `X-API-Key` from `POST /api/auth/keys`. No sessions needed in MVP. |
| Absolute CC or percentage? | Both. Absolute is primary; percentage is secondary beneath it. History chart shows dual axis. |
| How to prove value / show improvement? | HealthSignal (active/slow/dormant/unknown) per idea; ROI ratio in drill-down; running_total monotonic chart; evidence_count backing the signal. |

---

## 10. Files

### API (existing — verify correct)
- `api/app/models/portfolio.py` — all Pydantic models
- `api/app/services/portfolio_service.py` — data aggregation logic
- `api/app/routers/contributors_portfolio.py` — public routes
- `api/app/routers/me_portfolio.py` — authenticated routes
- `api/app/routers/auth_keys.py` — key issue + verification
- `api/app/main.py` — router registration

### Web (existing — verify correct)
- `web/app/my-portfolio/page.tsx` — entry page
- `web/app/contributors/[id]/portfolio/page.tsx` — full view
- `web/app/contributors/[id]/portfolio/ideas/[idea_id]/page.tsx` — idea drill-down
- `web/app/contributors/[id]/portfolio/contributions/[contribution_id]/page.tsx` — lineage audit

### Tests
- `api/tests/test_ux_my_portfolio.py` — existing acceptance tests
- `api/tests/test_ux_my_portfolio_acceptance.py` — existing acceptance tests

---

## 11. Acceptance Criteria

All criteria must pass for the feature to be considered done.

- [ ] AC-1: `GET /api/contributors/{id}/portfolio` returns `PortfolioSummary` with `contributor.identities` list (may be empty), `cc_balance`, `cc_network_pct`, and counts.
- [ ] AC-2: `GET /api/contributors/{id}/cc-history?window=90d&bucket=7d` returns `CCHistory` with a `series` array (may be empty, not null).
- [ ] AC-3: `GET /api/contributors/{id}/idea-contributions` returns `IdeaContributionsList` with `health.activity_signal` populated on each item.
- [ ] AC-4: `GET /api/contributors/{id}/idea-contributions/{idea_id}` returns `IdeaContributionDrilldown` with `value_lineage_summary.roi_ratio` (null is ok if no lineage data).
- [ ] AC-5: `GET /api/contributors/{id}/stakes` returns `StakesList` with `roi_pct` computed (null if no valuation).
- [ ] AC-6: `GET /api/contributors/{id}/tasks?status=completed` returns `TasksList` with `provider` and `outcome` fields.
- [ ] AC-7: `GET /api/contributors/{id}/contributions/{contribution_id}/lineage` returns `ContributionLineageView` with `lineage_chain_id` (null if no lineage link exists).
- [ ] AC-8: `GET /api/me/portfolio` returns 401 with no `X-API-Key` header.
- [ ] AC-9: `GET /api/me/portfolio` with a valid API key returns the same shape as AC-1, scoped to the key holder.
- [ ] AC-10: `POST /api/auth/keys` with valid `contributor_id`, `provider`, `provider_id` returns 201 with `api_key` and `scopes`.
- [ ] AC-11: Web page `/my-portfolio` renders without error and accepts a contributor ID input.
- [ ] AC-12: Web page `/contributors/{id}/portfolio` renders the CC balance, history chart area, idea contributions, stakes, and tasks sections without crashing on empty data.
- [ ] AC-13: Unknown contributor ID on any API endpoint returns 404, not 500.
- [ ] AC-14: `include_cc=false` query param causes `cc_balance` and `cc_network_pct` to be null.
- [ ] AC-15: Pagination — `limit=5&offset=5` on idea-contributions returns at most 5 items and `total` reflects the full count.

---

## 12. Verification Scenarios

The reviewer will run these against production (`$API = https://api.coherencycoin.com`).

---

### Scenario 1 — Full Portfolio Round-trip for Known Contributor

**Setup**: A contributor with ID `alice` has been registered and has at least one idea contribution recorded in the system.

**Action**:
```bash
API=https://api.coherencycoin.com
curl -s "$API/api/contributors/alice/portfolio" | python3 -m json.tool
```

**Expected**:
- HTTP 200
- `contributor.id == "alice"`
- `cc_balance` is a number ≥ 0 (not null if include_cc defaults to true)
- `idea_contribution_count` ≥ 0 (integer)
- `contributor.identities` is an array (possibly empty, not null)

**Then**:
```bash
curl -s "$API/api/contributors/alice/cc-history?window=90d&bucket=7d" | python3 -m json.tool
```
- `series` is an array (not null)
- Each item has `cc_earned`, `running_total`, `period_start`, `period_end`

**Edge case**: Unknown contributor
```bash
curl -s "$API/api/contributors/nonexistent-contributor-xyz/portfolio"
```
- HTTP 404
- Body contains `"detail"` key, not 500 Internal Server Error

---

### Scenario 2 — Authenticated /me Endpoints (API Key Flow)

**Setup**: A contributor with ID `testuser` exists (or is created for test).

**Action — Issue key**:
```bash
curl -s -X POST "$API/api/auth/keys" \
  -H "Content-Type: application/json" \
  -d '{"contributor_id": "testuser", "provider": "github", "provider_id": "testuser-gh"}' \
  | python3 -m json.tool
```
- HTTP 201
- Response has `api_key` (non-empty string), `contributor_id == "testuser"`, `scopes` array

**Action — Use key**:
```bash
KEY="<api_key from above>"
curl -s "$API/api/me/portfolio" -H "X-API-Key: $KEY" | python3 -m json.tool
```
- HTTP 200
- `contributor.id == "testuser"`
- Same shape as public endpoint

**Edge case — No key**:
```bash
curl -s "$API/api/me/portfolio"
```
- HTTP 401
- Body: `{"detail": "Missing X-API-Key header"}`

**Edge case — Invalid key**:
```bash
curl -s "$API/api/me/portfolio" -H "X-API-Key: invalid-garbage-key"
```
- HTTP 401
- Body: `{"detail": "Invalid API key"}`

---

### Scenario 3 — Idea Contribution Drill-down

**Setup**: Contributor `alice` has contributed to idea `spec-168`.

**Action**:
```bash
curl -s "$API/api/contributors/alice/idea-contributions" \
  -G --data-urlencode "sort=cc_attributed_desc" --data-urlencode "limit=5" \
  | python3 -m json.tool
```
- HTTP 200
- `total` ≥ 0, `items` array is present
- Each item has `idea_id`, `idea_title`, `health.activity_signal` ∈ {active, slow, dormant, unknown}

**Then drill down**:
```bash
curl -s "$API/api/contributors/alice/idea-contributions/spec-168" | python3 -m json.tool
```
- HTTP 200
- `contributions` array present (possibly empty)
- `value_lineage_summary.roi_ratio` present (null ok if no lineage)

**Edge case — Wrong idea**:
```bash
curl -s "$API/api/contributors/alice/idea-contributions/nonexistent-idea-xyz"
```
- HTTP 404

---

### Scenario 4 — Contribution Lineage Audit

**Setup**: Contributor `alice` has at least one contribution with a known `contribution_id` (e.g., `c1` from previous calls).

**Action**:
```bash
CONTRIB_ID=$(curl -s "$API/api/contributors/alice/idea-contributions" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('items', [])
if items:
    print(items[0].get('idea_id', ''))
")
curl -s "$API/api/contributors/alice/contributions/${CONTRIB_ID}/lineage" | python3 -m json.tool
```

**Expected**:
- HTTP 200 or 404 (404 acceptable if no contributions exist yet)
- If 200: body has `contribution_id`, `idea_id`, `contribution_type`, `cc_attributed` ≥ 0
- `lineage_chain_id` may be null if no lineage link has been created for this contribution

**Edge case — Nonexistent contribution**:
```bash
curl -s "$API/api/contributors/alice/contributions/nonexistent-c-xyz/lineage"
```
- HTTP 404

---

### Scenario 5 — Pagination and CC Include Toggle

**Action — Pagination**:
```bash
curl -s "$API/api/contributors/alice/idea-contributions?limit=2&offset=0" | python3 -c "
import sys, json; d = json.load(sys.stdin); print('total:', d['total'], 'items_count:', len(d['items']))
"
```
- `items_count` ≤ 2
- `total` reflects full count (may be > 2)

**Action — Skip CC**:
```bash
curl -s "$API/api/contributors/alice/portfolio?include_cc=false" | python3 -c "
import sys, json; d = json.load(sys.stdin); print('cc_balance:', d.get('cc_balance'))
"
```
- Output: `cc_balance: None`

**Edge case — Bad limit**:
```bash
curl -s "$API/api/contributors/alice/idea-contributions?limit=999"
```
- HTTP 422 (limit max is 100 per schema constraint)

---

## 13. Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| `_KEY_STORE` is in-memory — keys lost on restart | Acceptable for MVP; follow-up: persist to DB or Redis |
| `portfolio_service` may return empty data for contributors with no graph entries | Service returns zero-count shapes, not 404; only truly unknown contributors return 404 |
| `cc_balance` depends on a CC ledger that may not exist yet | Return `null` if CC data is unavailable; `include_cc=false` provides a safe bypass |
| Lineage links may not exist for all contributions | `lineage_chain_id: null` and `value_lineage_link: null` are valid; `lineage_resolution_note` explains why |
| Web `/my-portfolio` currently only redirects to the public view by ID | API-key flow in the web is planned but not required for spec acceptance |
| Health signal depends on observable data (commits, API calls) | Falls back to `unknown` gracefully; system won't crash on missing data |

---

## 14. Known Gaps and Follow-up Tasks

- **Session persistence for API keys** — `_KEY_STORE` resets on restart; persist to PostgreSQL (follow-up spec)
- **Authenticated web UI** — `/my-portfolio` currently accepts a contributor ID; add API key input + store key in localStorage for `/me/…` calls (follow-up spec)
- **Stake valuation engine** — `roi_pct` and `cc_valuation` currently null for most stakes until a valuation job runs (follow-up spec)
- **Export / share** — contributor may want a shareable URL or PDF export of their portfolio (follow-up spec)
- **CC dual-axis chart polish** — web chart currently single-axis; add `network_pct_at_period_end` overlay (follow-up)
- **Filtering idea contributions by type** — currently only sort is supported; add `?type=code` filter (follow-up)

---

## Task Card

```yaml
id: my-portfolio-personal-view
spec: 186-my-portfolio-personal-view
goal: >
  A single page showing a contributor's identities, CC balance + earning chart,
  ideas contributed to (with health), stakes (with ROI), and tasks completed —
  with full drill-down to contribution-level lineage audit.
files_allowed:
  - api/app/models/portfolio.py
  - api/app/services/portfolio_service.py
  - api/app/routers/contributors_portfolio.py
  - api/app/routers/me_portfolio.py
  - api/app/routers/auth_keys.py
  - api/app/main.py
  - web/app/my-portfolio/page.tsx
  - web/app/contributors/[id]/portfolio/page.tsx
  - web/app/contributors/[id]/portfolio/ideas/[idea_id]/page.tsx
  - web/app/contributors/[id]/portfolio/contributions/[contribution_id]/page.tsx
  - api/tests/test_ux_my_portfolio.py
  - api/tests/test_ux_my_portfolio_acceptance.py
done_when:
  - All 15 acceptance criteria pass
  - All 5 verification scenarios pass against production
  - pytest api/tests/test_ux_my_portfolio.py -v and api/tests/test_ux_my_portfolio_acceptance.py -v pass with no failures
commands:
  - cd api && python -m pytest tests/test_ux_my_portfolio.py tests/test_ux_my_portfolio_acceptance.py -v
constraints:
  - No schema migrations without explicit approval
  - Do not break existing /api/contributors/{id}/portfolio routes
  - Keep _KEY_STORE in-memory for MVP — do not add DB dependency in this spec
```
