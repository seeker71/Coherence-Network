# Spec: My Portfolio — Personal Contributor View

**Idea ID**: `ux-my-portfolio`
**Task ID**: `task_b6913f85c7d03a87`
**Spec number**: 188 (next in sequence)
**Status**: draft
**Date**: 2026-03-28
**Author**: product-manager agent

---

## Summary

A contributor needs a single page that answers four questions in one visit:

> *What have I done? What did I invest in? Where is my CC? How are my ideas doing?*

**My Portfolio** (`/my-portfolio`) is that page. It is a personal ledger + garden view — everything you have touched, staked, or contributed to, presented in a way that is self-explanatory for a newcomer and rich with drill-down for a power user.

The page exists at two levels:

- **Public (read)**: `GET /contributors/{id}/portfolio` — anyone can view a contributor's public profile.
- **Personal (authenticated)**: `GET /me/portfolio` via `X-API-Key` — the owner sees their full private view including CC breakdown percentages.

The web page at `/my-portfolio` routes through one of these two paths depending on whether an API key is supplied.

---

## Background: What Already Exists

As of 2026-03-28 the following is **already implemented** (spec 174):

| Asset | Status |
|---|---|
| `api/app/models/portfolio.py` | Implemented — `PortfolioSummary`, `CCHistory`, `IdeaContributionsList`, `IdeaContributionDrilldown`, `StakesList`, `TasksList` |
| `api/app/services/portfolio_service.py` | Implemented — all aggregation logic |
| `api/app/routers/contributors_portfolio.py` | Implemented — public contributor routes |
| `api/app/routers/me_portfolio.py` | Implemented — authenticated `/me/*` routes |
| `api/app/routers/auth_keys.py` | Implemented — `POST /api/auth/keys` |
| `web/app/my-portfolio/page.tsx` | Partial — entry form only, redirects to `/contributors/{id}/portfolio` |
| `web/app/contributors/[id]/portfolio/` | Partial — status unknown |

This spec defines the **complete product contract**: what the page must show, how authentication works, which API endpoints are the source of truth, what edge cases look like, and the verification scenarios that a reviewer will run against production.

---

## Goals

1. **Single-page personal view** — one URL answers all four contributor questions.
2. **Identity-first authentication** — API key derived from a linked identity (GitHub, Telegram, wallet). No password. No separate session store.
3. **Full drill-down lineage** — click idea → my contributions → CC earned → lineage chain.
4. **Garden metaphor**: each idea is a plant. Healthy = growing. Stale = wilting. Staked = you have skin in the game.
5. **Prove value over time** — CC history chart shows whether the network is paying contributors fairly.

---

## Open Questions — Resolved in This Spec

### Q1: How does a contributor authenticate to see their personal view?

**Resolution**: Identity link is the key. Authentication flow:

1. Contributor links a GitHub/Telegram/wallet identity via `POST /api/contributors/{id}/identities`.
2. Contributor calls `POST /api/auth/keys` with `{contributor_id, provider, provider_id}`.
3. Server verifies the identity link exists, returns a one-time `api_key`.
4. Contributor stores the key. Every personal-view request uses `X-API-Key: <key>` header.
5. **No sessions required for MVP**. The API key IS the session token. Key lifetime is indefinite until rotated by the owner.
6. The `/me/portfolio` endpoint resolves `contributor_id` entirely from the key — the user never types their ID again after key generation.

Web UX: `/my-portfolio` shows a "Connect" form. If the user has an API key stored in localStorage, it is sent automatically and the full portfolio loads. If not, the user is prompted to generate a key.

### Q2: Should the portfolio show CC in absolute numbers or as a percentage of total network value?

**Resolution**: **Both**, user-toggleable.

- Default: absolute CC balance (e.g. `4 820 CC`).
- Toggle: percentage of total network supply (e.g. `0.48%`).
- The `include_cc=true` query param on `GET /me/portfolio` controls whether `cc_network_pct` is computed (adds one DB round-trip). Default: true.
- The chart (`GET /me/cc-history`) includes both `cc_earned` per bucket and `network_pct_at_period_end` per bucket so either view is graphable.

### Q3: How can we improve this idea, show whether it is working, and make proof clearer over time?

**Resolution**: Three concrete proof mechanisms:

1. **CC history chart** — time-series of CC earned shows momentum and plateaus. If you stopped contributing, the chart shows it.
2. **Idea health signal** — each idea card carries `activity_signal` (active / slow / dormant / unknown) computed from recent events. A garden where every plant is labeled.
3. **ROI on stakes** — `roi_pct` on each stake shows whether betting on an idea paid off. Negative ROI is visible, not hidden.
4. **Future (not blocking)**: email/Telegram digest of weekly portfolio delta. Listed under Known Gaps.

---

## Page Structure: `/my-portfolio`

```
┌─────────────────────────────────────────────────────────┐
│  My Portfolio                    [Switch: CC / %]  [⚙️ Key] │
├─────────────────────────────────────────────────────────┤
│  IDENTITIES                                             │
│  🐙 github/handle  ✓  |  📱 telegram/@handle  ✓        │
├─────────────────────────────────────────────────────────┤
│  CC BALANCE        CC EARNED (chart last 90d)           │
│  4 820 CC          ███░░░▓▓▓▓████  ↑12% this month      │
├─────────────────────────────────────────────────────────┤
│  IDEAS I CONTRIBUTED TO                [sort: CC ▼]     │
│  ┌ my-portfolio  ●active  spec,test   120 CC  ▶ │
│  ├ ux-overhaul   ○slow    code        48 CC   ▶ │
│  └ graph-health  ○dormant spec        12 CC   ▶ │
├─────────────────────────────────────────────────────────┤
│  IDEAS I STAKED ON                     [sort: ROI ▼]    │
│  ┌ cc-launch     ● +24% ROI    200 CC staked ▶ │
│  └ ux-overhaul   ○  -4% ROI     50 CC staked ▶ │
├─────────────────────────────────────────────────────────┤
│  TASKS I COMPLETED                     [sort: date ▼]   │
│  ┌ spec(ux-my-portfolio)  claude-sonnet  ✓passed  5 CC  │
│  └ test(graph-health)     gpt-4o         ✓passed  3 CC  │
└─────────────────────────────────────────────────────────┘
```

Clicking any idea row opens a drill-down panel (or navigates to `/contributors/{id}/idea-contributions/{idea_id}`).

---

## Requirements

### API Requirements

- [R1] `GET /api/contributors/{id}/portfolio` — returns `PortfolioSummary` (public).
- [R2] `GET /api/me/portfolio` — returns `PortfolioSummary` (authenticated, `X-API-Key`).
- [R3] `GET /api/contributors/{id}/cc-history?window=90d&bucket=7d` — returns `CCHistory` time-series.
- [R4] `GET /api/me/cc-history` — authenticated version of R3.
- [R5] `GET /api/contributors/{id}/idea-contributions?sort=cc_attributed_desc&limit=20` — returns `IdeaContributionsList`.
- [R6] `GET /api/me/idea-contributions` — authenticated version of R5.
- [R7] `GET /api/contributors/{id}/idea-contributions/{idea_id}` — returns `IdeaContributionDrilldown` with `ValueLineageSummary`.
- [R8] `GET /api/me/idea-contributions/{idea_id}` — authenticated version of R7.
- [R9] `GET /api/contributors/{id}/stakes?sort=roi_desc` — returns `StakesList`.
- [R10] `GET /api/me/stakes` — authenticated version of R9.
- [R11] `GET /api/contributors/{id}/tasks?sort=completed_at_desc` — returns `TasksList`.
- [R12] `GET /api/me/tasks` — authenticated version of R11.
- [R13] `GET /api/me/contributions/{contribution_id}/lineage` — returns `ContributionLineageView` with `value_lineage_link` resolved.
- [R14] `POST /api/auth/keys` — accepts `{contributor_id, provider, provider_id}`, returns `api_key` once; requires verified identity link.

### Web Requirements

- [W1] `/my-portfolio` — Landing entry. If `cc_api_key` exists in localStorage, auto-load authenticated view. Else, show identity-link + key generation form.
- [W2] Authenticated view: renders all five sections (identities, CC balance+chart, idea contributions, stakes, tasks).
- [W3] CC balance section includes toggle: absolute CC ↔ network percentage.
- [W4] Idea contribution cards show: idea title, status badge, contribution types, CC attributed, health signal (active/slow/dormant).
- [W5] Stake cards show: idea title, CC staked, ROI% (positive = green, negative = red), `staked_at` date.
- [W6] Task cards show: task description (truncated), provider, outcome badge (passed/failed/partial), CC earned, date.
- [W7] Clicking an idea card navigates to `/my-portfolio/ideas/{idea_id}` or opens a modal — shows `IdeaContributionDrilldown`.
- [W8] Clicking a contribution within the drill-down shows `ContributionLineageView` with the full lineage chain.
- [W9] Page is responsive — mobile-first, readable on 375px viewport.
- [W10] Empty states are meaningful: "No contributions yet — start by submitting a spec or completing a task."

### Authentication Requirements

- [A1] `POST /api/auth/keys` validates that the `(provider, provider_id)` pair is linked to `contributor_id` before issuing a key.
- [A2] `GET /api/me/*` routes return HTTP 401 if `X-API-Key` header is absent.
- [A3] `GET /api/me/*` routes return HTTP 401 if the key is invalid or revoked.
- [A4] `GET /api/me/*` routes return HTTP 403 if the key's `contributor_id` does not match any resource required to be owned.
- [A5] API keys are stored as SHA-256 hashes server-side — the plaintext key is returned exactly once at generation time.
- [A6] Key rotation: `DELETE /api/auth/keys/{key_prefix}` revokes the matching key.

---

## Data Model

All models are defined in `api/app/models/portfolio.py`. Key types:

```python
class PortfolioSummary(BaseModel):
    contributor: ContributorSummary          # id, display_name, identities[]
    cc_balance: Optional[float]              # None if include_cc=false
    cc_network_pct: Optional[float]          # None if include_cc=false
    idea_contribution_count: int
    stake_count: int
    task_completion_count: int
    recent_activity: Optional[datetime]

class CCHistory(BaseModel):
    contributor_id: str
    window: str                              # "90d"
    bucket: str                             # "7d"
    series: list[CCHistoryBucket]           # chronological

class CCHistoryBucket(BaseModel):
    period_start: datetime
    period_end: datetime
    cc_earned: float
    running_total: float
    network_pct_at_period_end: Optional[float]

class IdeaContributionSummary(BaseModel):
    idea_id: str
    idea_title: str
    idea_status: str                        # e.g. "active", "archived"
    contribution_types: list[str]           # ["spec", "test", "code"]
    cc_attributed: float
    contribution_count: int
    last_contributed_at: Optional[datetime]
    health: HealthSignal                    # activity_signal, value_delta_pct

class StakeSummary(BaseModel):
    stake_id: str
    idea_id: str
    idea_title: str
    cc_staked: float
    cc_valuation: Optional[float]
    roi_pct: Optional[float]
    staked_at: Optional[datetime]
    last_valued_at: Optional[datetime]
    health: HealthSignal

class TaskSummary(BaseModel):
    task_id: str
    description: str
    idea_id: Optional[str]
    provider: Optional[str]
    outcome: Optional[str]                  # "passed" | "failed" | "partial"
    cc_earned: float
    completed_at: Optional[datetime]

class ContributionLineageView(BaseModel):
    contributor_id: str
    contribution_id: str
    idea_id: str
    contribution_type: str
    cc_attributed: float
    lineage_chain_id: Optional[str]
    value_lineage_link: Optional[LineageLinkBrief]
    lineage_resolution_note: Optional[str]
```

---

## API Endpoints (Canonical List)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/keys` | Identity link | Generate personal API key |
| DELETE | `/api/auth/keys/{key_prefix}` | Same key | Revoke key |
| GET | `/api/me/portfolio` | X-API-Key | Authenticated portfolio summary |
| GET | `/api/me/cc-history` | X-API-Key | Authenticated CC time-series |
| GET | `/api/me/idea-contributions` | X-API-Key | My idea contribution list |
| GET | `/api/me/idea-contributions/{idea_id}` | X-API-Key | Drill-down for one idea |
| GET | `/api/me/stakes` | X-API-Key | My stakes list |
| GET | `/api/me/tasks` | X-API-Key | My completed tasks |
| GET | `/api/me/contributions/{contribution_id}/lineage` | X-API-Key | Lineage view for one contribution |
| GET | `/api/contributors/{id}/portfolio` | None | Public summary |
| GET | `/api/contributors/{id}/cc-history` | None | Public CC history |
| GET | `/api/contributors/{id}/idea-contributions` | None | Public contribution list |
| GET | `/api/contributors/{id}/idea-contributions/{idea_id}` | None | Public idea drill-down |
| GET | `/api/contributors/{id}/stakes` | None | Public stakes |
| GET | `/api/contributors/{id}/tasks` | None | Public task list |

### Web Pages

| Route | Description |
|---|---|
| `/my-portfolio` | Entry page — auto-detects API key or shows onboarding |
| `/my-portfolio/ideas/{idea_id}` | Idea drill-down within my portfolio context |
| `/contributors/{id}/portfolio` | Public portfolio view for any contributor |

---

## Verification Scenarios

The reviewer will RUN each of these scenarios against production (`$API=https://api.coherencycoin.com`).

### Scenario 1: API key generation and authenticated portfolio load

**Setup**: A contributor `test-alice` exists with a GitHub identity linked (`provider=github`, `provider_id=alice-oss`).

**Action**:
```bash
# Step 1: Generate key
RESP=$(curl -s -X POST $API/api/auth/keys \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"test-alice","provider":"github","provider_id":"alice-oss"}')
KEY=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")

# Step 2: Load portfolio with key
curl -s -H "X-API-Key: $KEY" $API/api/me/portfolio
```

**Expected result**:
- Step 1: HTTP 201, `{"api_key": "...", "contributor_id": "test-alice", "scopes": [...]}`.
- Step 2: HTTP 200, `{"contributor": {"id": "test-alice", "identities": [{"type": "github", "handle": "alice-oss", "verified": true}]}, "cc_balance": <number>, "idea_contribution_count": <int>, ...}`.
- `cc_balance` is a float >= 0 (not null if `include_cc=true`).
- `cc_network_pct` is a float between 0.0 and 100.0 (or null if supply is zero).

**Edge — missing key**:
```bash
curl -s $API/api/me/portfolio
```
Expected: HTTP 401, `{"detail": "Missing X-API-Key header"}`.

**Edge — invalid key**:
```bash
curl -s -H "X-API-Key: invalid-key-xyz" $API/api/me/portfolio
```
Expected: HTTP 401, `{"detail": "Invalid API key"}`.

**Edge — key for unknown identity**:
```bash
curl -s -X POST $API/api/auth/keys \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"test-alice","provider":"github","provider_id":"not-linked"}'
```
Expected: HTTP 422 or HTTP 403, error message indicating identity not verified.

---

### Scenario 2: CC history time-series with two display modes

**Setup**: Contributor `test-alice` has earned CC across multiple weeks. API key `$KEY` exists.

**Action**:
```bash
# Absolute mode (default)
curl -s -H "X-API-Key: $KEY" "$API/api/me/cc-history?window=90d&bucket=7d"

# 30-day narrow window
curl -s -H "X-API-Key: $KEY" "$API/api/me/cc-history?window=30d&bucket=1d"
```

**Expected result**:
- Both return HTTP 200 with `{"contributor_id": "test-alice", "window": "...", "series": [...]}`.
- `series` is a list of `CCHistoryBucket` objects, each with `period_start`, `period_end`, `cc_earned` (float >= 0), `running_total` (non-decreasing).
- `network_pct_at_period_end` is either a float 0.0–100.0 or null.
- `series` length for `90d/7d` <= 13 buckets.
- `series` length for `30d/1d` <= 30 buckets.

**Edge — invalid window**:
```bash
curl -s -H "X-API-Key: $KEY" "$API/api/me/cc-history?window=bad"
```
Expected: HTTP 422 with validation error, NOT a 500.

---

### Scenario 3: Idea contribution drill-down and lineage chain

**Setup**: Contributor `test-alice` has contributed to idea `ux-my-portfolio` (at least one spec contribution exists). API key `$KEY` exists.

**Action**:
```bash
# Step 1: List my contributions
CONTS=$(curl -s -H "X-API-Key: $KEY" "$API/api/me/idea-contributions?sort=cc_attributed_desc&limit=5")
echo $CONTS | python3 -c "import sys,json; [print(i['idea_id'],i['cc_attributed']) for i in json.load(sys.stdin)['items']]"

# Step 2: Drill down into ux-my-portfolio
DETAIL=$(curl -s -H "X-API-Key: $KEY" "$API/api/me/idea-contributions/ux-my-portfolio")
echo $DETAIL | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['idea_id'], len(d['contributions']), d['value_lineage_summary'])"

# Step 3: Lineage view for the first contribution
CONTRIB_ID=$(echo $DETAIL | python3 -c "import sys,json; print(json.load(sys.stdin)['contributions'][0]['id'])")
curl -s -H "X-API-Key: $KEY" "$API/api/me/contributions/$CONTRIB_ID/lineage"
```

**Expected result**:
- Step 1: HTTP 200, list of `IdeaContributionSummary` items sorted by `cc_attributed` descending. Each item has `idea_id`, `idea_title`, `idea_status`, `contribution_types` (non-empty list), `health.activity_signal`.
- Step 2: HTTP 200, `IdeaContributionDrilldown` with `contributions` list. Each `ContributionDetail` has `id`, `type`, `cc_attributed >= 0`. `value_lineage_summary` has `total_value >= 0`.
- Step 3: HTTP 200, `ContributionLineageView` with `contributor_id`, `contribution_type`, `cc_attributed >= 0`. `lineage_chain_id` may be null if lineage not yet linked.

**Edge — idea I never contributed to**:
```bash
curl -s -H "X-API-Key: $KEY" "$API/api/me/idea-contributions/idea-that-does-not-exist"
```
Expected: HTTP 404, `{"detail": "..."}`.

---

### Scenario 4: Stakes with ROI and public read

**Setup**: Contributor `test-alice` has staked 100 CC on idea `cc-launch` at some point. The idea has been valued since staking.

**Action**:
```bash
# Authenticated stakes view
curl -s -H "X-API-Key: $KEY" "$API/api/me/stakes?sort=roi_desc&limit=10"

# Public stakes view (no key)
curl -s "$API/api/contributors/test-alice/stakes?sort=roi_desc&limit=10"
```

**Expected result**:
- Both return HTTP 200 with `{"contributor_id": "test-alice", "total": <int>, "items": [...]}`.
- Each `StakeSummary` has `stake_id`, `idea_id`, `cc_staked > 0`, `staked_at` ISO datetime.
- `roi_pct` is a float (positive or negative) or null if not yet valued.
- Items are sorted by `roi_pct` descending (nulls last).
- Both authenticated and public views return the same stakes data for the same contributor.

**Edge — contributor with no stakes**:
```bash
curl -s "$API/api/contributors/new-contributor-no-stakes/stakes"
```
Expected: HTTP 200, `{"contributor_id": "new-contributor-no-stakes", "total": 0, "items": []}` (NOT 404).

---

### Scenario 5: Full create-read cycle — task completion and portfolio update

**Setup**: A task `task_test_001` is marked completed for contributor `test-alice` with `provider=claude-sonnet`, `outcome=passed`, `cc_earned=5.0`.

**Action**:
```bash
# Register task completion
curl -s -X POST $API/api/contributors/test-alice/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_id":"task_test_001","description":"spec(test-task): test scenario","provider":"claude-sonnet","outcome":"passed","cc_earned":5.0,"idea_id":"ux-my-portfolio"}'

# Read back via authenticated view
curl -s -H "X-API-Key: $KEY" "$API/api/me/tasks?sort=completed_at_desc&limit=5"

# Confirm portfolio summary reflects the task
curl -s -H "X-API-Key: $KEY" "$API/api/me/portfolio"
```

**Expected result**:
- Task registration returns HTTP 201 (or 200) with the created task record.
- `GET /api/me/tasks` includes `task_test_001` with `provider="claude-sonnet"`, `outcome="passed"`, `cc_earned=5.0`.
- `GET /api/me/portfolio` shows `task_completion_count >= 1`.

**Edge — duplicate task registration**:
```bash
curl -s -X POST $API/api/contributors/test-alice/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_id":"task_test_001","description":"spec(test-task): test scenario","provider":"claude-sonnet","outcome":"passed","cc_earned":5.0}'
```
Expected: HTTP 409 (conflict) or idempotent HTTP 200 — must NOT create a duplicate entry.

---

## Task Card

```yaml
goal: >
  Ship the full "My Portfolio" personal contributor view: web page + authenticated API
  + drill-down lineage. A contributor visits /my-portfolio, sees all five sections, can
  drill into any idea or contribution, and can toggle CC absolute vs percentage.

idea_id: ux-my-portfolio

files_allowed:
  # API
  - api/app/routers/contributors_portfolio.py
  - api/app/routers/me_portfolio.py
  - api/app/routers/auth_keys.py
  - api/app/models/portfolio.py
  - api/app/services/portfolio_service.py
  - api/app/services/contributor_identity_service.py
  - api/tests/test_my_portfolio.py
  # Web
  - web/app/my-portfolio/page.tsx
  - web/app/my-portfolio/ideas/[idea_id]/page.tsx
  - web/app/contributors/[id]/portfolio/page.tsx
  - web/components/portfolio/

done_when:
  - All 5 verification scenarios pass against production
  - GET /api/me/portfolio returns 401 without X-API-Key
  - GET /api/me/portfolio returns full PortfolioSummary with valid X-API-Key
  - /my-portfolio web page renders all five sections for an authenticated user
  - Drill-down to /my-portfolio/ideas/{id} shows ContributionDetail list
  - CC toggle works (absolute vs percentage, both values rendered correctly)
  - pytest api/tests/test_my_portfolio.py passes

commands:
  - cd api && python -m pytest tests/test_my_portfolio.py -x -v

constraints:
  - Do not modify existing contributor or idea schemas
  - No new database tables without explicit approval
  - Coherence scores 0.0-1.0 convention maintained
  - API keys stored as SHA-256 hashes only (never plaintext in DB)
  - No sessions: X-API-Key header is the sole auth mechanism for /me/* routes
```

---

## Risks and Assumptions

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **In-memory key store** — `_KEY_STORE` in `auth_keys.py` is lost on API restart | High (confirmed) | High — all user API keys invalidated on deploy | MVP: persist key hashes to PostgreSQL `contributor_api_keys` table before launch. Tracked as follow-up. |
| **No key rotation endpoint** — once issued, keys cannot be revoked without server restart | Medium | High (security) | Add `DELETE /api/auth/keys/{key_prefix}` before public launch. |
| **portfolio_service returns empty data** if graph DB has no real stake/task events | High (likely for new contributors) | Medium | Empty states handled gracefully; never 500. |
| **CC percentage calc** requires network total > 0; division by zero if supply is zero | Low | Low (would 500) | Guard in service: if `network_total == 0`, return `cc_network_pct=null`. |
| **Rate limiting absent** on `/me/*` routes | High | Medium (DoS via key brute-force) | Rate-limit key verification endpoint before public launch. |
| **Public routes expose contributor data without consent gate** | Medium | Medium | Ensure contributor creation flow includes explicit public-profile opt-in. |

---

## Known Gaps and Follow-up Tasks

1. **Key persistence to PostgreSQL** — in-memory `_KEY_STORE` must be replaced before public launch. Create table `contributor_api_keys (key_hash TEXT PK, contributor_id TEXT, created_at TIMESTAMPTZ, revoked_at TIMESTAMPTZ)`.
2. **Key revocation endpoint** — `DELETE /api/auth/keys/{key_prefix}` not yet implemented.
3. **Web UI authentication flow** — `/my-portfolio` currently only redirects to public view; API-key-authenticated flow needs implementing in React.
4. **CC chart component** — no React chart component for CC history time-series. Use a lightweight library (recharts/shadcn) with sparkline for summary and full chart on drill-down.
5. **Notification digest** — weekly email/Telegram summary of portfolio delta (CC earned, new ideas, stake ROI changes). Follow-up idea, not MVP.
6. **Contribution lineage endpoint** — `GET /api/me/contributions/{id}/lineage` not yet routed; needs adding to `me_portfolio.py` router.
7. **Task registration endpoint** — `POST /api/contributors/{id}/tasks` may not exist yet; needed for Scenario 5.
8. **Mobile drill-down UX** — modal vs. page navigation for idea drill-down needs design decision (use page navigation for MVP).

---

## Research Inputs

- `2026-03-28` — `api/app/models/portfolio.py` — Pydantic models for portfolio views (spec 174).
- `2026-03-28` — `api/app/routers/me_portfolio.py` — Authenticated `/me/*` route handlers.
- `2026-03-28` — `api/app/routers/contributors_portfolio.py` — Public contributor route handlers.
- `2026-03-28` — `api/app/services/portfolio_service.py` — Aggregation service.
- `2026-03-28` — `api/app/routers/auth_keys.py` — API key generation and verification.
- `2026-03-28` — `web/app/my-portfolio/page.tsx` — Existing (partial) web entry page.
- `2026-03-28` — `specs/052-portfolio-cockpit-ui.md` — Earlier portfolio UI spec.
- `2026-03-28` — `specs/116-grounded-idea-portfolio-metrics.md` — Grounded metrics feeding idea health.
- `2026-03-28` — `specs/126-portfolio-governance-effectiveness.md` — Governance effectiveness metrics.
