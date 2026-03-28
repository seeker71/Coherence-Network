# Spec 157: Investment UX — Stake CC on Ideas from Web and CLI with Clear Returns

**Spec ID**: 157-investment-ux-stake-cc-on-ideas
**Idea ID**: investment-ux
**Status**: Draft
**Depends on**: Spec 119 (Coherence Credit), Spec 121 (OpenClaw Marketplace), Spec 048 (Value Lineage), Spec 052 (Portfolio Cockpit)
**Depended on by**: Spec 124 (CC Economics), Spec 126 (Portfolio Governance)

---

## Summary

`cc stake` works but the experience is bare. A contributor who wants to put skin in the game can't see what they'll get back, can't track their positions over time, and can't invest anything other than CC tokens. This spec closes that gap with five concrete improvements:

1. **`cc invest <idea> <amount>`** — CLI command with projected ROI shown before confirmation
2. **Web invest button on idea cards** — one-click investment from the ideas browse page
3. **Portfolio view** — shows all investments with current value and unrealized gain/loss
4. **Investment history with CC flow visualization** — timeline of CC staked, spent, and returned
5. **Time investment** — ability to commit hours (review, implementation, testing) that earn CC at the human-hour rate from `exchange_rates.json`

The goal is to make investment feel like participation, not speculation. Contributors see evidence of value before, during, and after they invest.

---

## Problem Statement

The current `cc stake <idea-id> <amount-cc>` command:
- Accepts a stake and creates tasks, but shows no confirmation of projected return
- Provides no way to see what happened to staked CC after the fact
- Has no portfolio-level view aggregating all positions
- Only accepts CC tokens, not time/labor commitments

The web UI has no investment affordance at all — ideas are browsable but not investable from the browser.

Contributors cannot answer the basic question: *"Is my investment working? What's it worth now?"*

---

## Requirements

### R1 — CLI: `cc invest <idea> <amount>` with ROI Confirmation

**Command signature**: `cc invest <idea-id> <amount-cc> [--time <hours>] [--dry-run] [--rationale "<text>"]`

Before executing, the CLI must display a confirmation screen showing:

```
Investing 50 CC in: "GraphQL caching layer"
  Current stage:    specced (1 of 5)
  Tasks queued:     2 (impl × 2)
  Projected ROI:    1.4× — 2.1× (low/high estimate)
  Basis:            coherence score 0.72, 3 prior investments avg 1.6×
  Break-even stage: testing
  Time to return:   2–5 days (estimate based on pipeline velocity)

Confirm? [y/N]
```

The user types `y` to proceed. `--dry-run` prints the projection without prompting.

**ROI Projection Formula** (see §Data Model):
```
projected_low  = base_value_cc * coherence_score
projected_high = base_value_cc * coherence_score * (1 + prior_roi_avg)
```
Where `base_value_cc` = `amount_cc * exchange_rate.cc_per_usd * idea_value_multiplier`.

### R2 — Web: Invest Button on Idea Cards

Each idea card on `/ideas` and the idea detail page `/ideas/<id>` must include:

- **"Invest" button** next to the existing stake/like affordances
- Clicking opens a modal/drawer with:
  - Idea name, stage badge, coherence score
  - Amount input (CC or hours)
  - Projected ROI summary (same data as CLI)
  - "Invest" confirm button
- On success: card shows updated "Total staked: X CC" and a green flash animation
- On error: inline error message (not a page reload)

**Investment modal endpoint**: `GET /api/ideas/{idea_id}/invest-preview` returns projection data.

### R3 — Portfolio View: All Investments with Current Value

**Route**: `/portfolio/investments`
**API**: `GET /api/contributors/{contributor_id}/investments`

Each investment row must show:
```
Idea Name              | Invested | Current Value | Gain/Loss | Stage     | ROI%
-----------------------|----------|---------------|-----------|-----------|------
GraphQL caching layer  | 50 CC    | 68.5 CC       | +18.5 CC  | testing   | +37%
Auth middleware rewrite| 20 CC    | 12.0 CC       | -8.0 CC   | specced   | -40%
```

"Current value" is computed from the idea's progress: completed stages unlock partial returns.
Stage-based unlock schedule (see §Data Model):
- `none → specced`: 0% return
- `specced → implementing`: 10% of projected return unlocked
- `implementing → testing`: 40% unlocked
- `testing → reviewing`: 70% unlocked
- `reviewing → complete`: 100% unlocked

Portfolio summary at top: Total invested, Total current value, Total gain/loss, # active positions.

### R4 — Investment History with CC Flow Visualization

**Route**: `/portfolio/history`
**API**: `GET /api/contributors/{contributor_id}/investment-history`

Returns a chronological list of CC movements:

```json
{
  "contributor_id": "alice",
  "events": [
    {
      "ts": "2026-03-20T14:23:00Z",
      "type": "stake",
      "idea_id": "graphql-caching",
      "idea_name": "GraphQL caching layer",
      "amount_cc": 50.0,
      "balance_after": 150.0
    },
    {
      "ts": "2026-03-22T09:11:00Z",
      "type": "compute_charge",
      "idea_id": "graphql-caching",
      "amount_cc": -5.2,
      "balance_after": 144.8,
      "metadata": { "task_id": "t123", "provider": "claude" }
    },
    {
      "ts": "2026-03-24T11:45:00Z",
      "type": "return",
      "idea_id": "graphql-caching",
      "amount_cc": 8.5,
      "balance_after": 153.3,
      "stage_reached": "testing"
    }
  ],
  "running_balance": [...],
  "total_invested": 50.0,
  "total_returned": 8.5,
  "total_spent": 5.2
}
```

**Web visualization**: A sparkline or step-chart showing CC balance over time, color-coded by event type (stake = blue, charge = red, return = green).

### R5 — Time Investment: Commit Hours, Not Just CC

**CLI**: `cc invest <idea-id> --time <hours> [--type review|implement|test]`
**Web**: Modal has a "Commit time instead" toggle showing an hours input.

Time investment creates a `time_pledge` record:

```json
{
  "pledge_id": "tp_abc123",
  "contributor_id": "alice",
  "idea_id": "graphql-caching",
  "hours_pledged": 2.0,
  "pledge_type": "review",
  "cc_equivalent": 1000.0,
  "status": "pending",
  "expires_at": "2026-04-03T00:00:00Z"
}
```

`cc_equivalent = hours * exchange_rate.human_hour_cc` (default: 500 CC/hour).

When a time pledge is fulfilled (contributor submits a PR or review linked to the idea), the system upgrades the pledge to `fulfilled` and issues a return contribution to the contributor's account.

**Fulfillment proof**: Link a `contribution_id` (from `POST /api/contributions`) to the pledge via `POST /api/contributors/{id}/pledges/{pledge_id}/fulfill`.

---

## API Changes

### New Endpoints

#### `GET /api/ideas/{idea_id}/invest-preview`
Returns investment projection for CLI confirmation and web modal.

**Response**:
```json
{
  "idea_id": "graphql-caching",
  "idea_name": "GraphQL caching layer",
  "stage": "specced",
  "coherence_score": 0.72,
  "total_cc_staked": 120.0,
  "prior_investments_count": 3,
  "prior_roi_avg": 1.6,
  "projections": {
    "low_multiplier": 1.4,
    "high_multiplier": 2.1,
    "basis": "coherence_score + prior_roi_avg"
  },
  "stage_unlock_pct": 10,
  "pipeline_velocity_days": [2, 5]
}
```

#### `GET /api/contributors/{contributor_id}/investments`
Returns all investment positions for a contributor.

**Query params**: `?limit=50&offset=0&sort=gain_loss_desc`

**Response**:
```json
{
  "contributor_id": "alice",
  "summary": {
    "total_invested_cc": 200.0,
    "total_current_value_cc": 248.5,
    "total_gain_loss_cc": 48.5,
    "total_positions": 4,
    "active_positions": 3
  },
  "positions": [
    {
      "idea_id": "graphql-caching",
      "idea_name": "GraphQL caching layer",
      "invested_cc": 50.0,
      "current_value_cc": 68.5,
      "gain_loss_cc": 18.5,
      "roi_pct": 37.0,
      "stage": "testing",
      "unlock_pct": 70,
      "staked_at": "2026-03-20T14:23:00Z"
    }
  ]
}
```

#### `GET /api/contributors/{contributor_id}/investment-history`
Returns CC flow timeline for a contributor.

**Query params**: `?limit=100&since=<ISO8601>&idea_id=<optional>`

#### `POST /api/contributors/{contributor_id}/pledges`
Create a time pledge.

**Request**:
```json
{
  "idea_id": "graphql-caching",
  "hours_pledged": 2.0,
  "pledge_type": "review"
}
```

**Response** (201):
```json
{
  "pledge_id": "tp_abc123",
  "cc_equivalent": 1000.0,
  "expires_at": "2026-04-03T00:00:00Z"
}
```

#### `POST /api/contributors/{contributor_id}/pledges/{pledge_id}/fulfill`
Mark a time pledge fulfilled, trigger CC return.

**Request**:
```json
{
  "contribution_id": "contrib_xyz",
  "evidence_url": "https://github.com/org/repo/pull/42"
}
```

### Modified Endpoints

#### `POST /api/ideas/{idea_id}/stake` — Add `dry_run` field
Existing stake endpoint gains:
```json
{ "dry_run": true }
```
When `dry_run: true`, returns the same projection as `invest-preview` without recording the stake. Enables `cc invest --dry-run`.

---

## Data Model

### New Table: `investment_positions`

Materialized per-contributor per-idea position for fast portfolio queries.

```sql
CREATE TABLE investment_positions (
    id              TEXT PRIMARY KEY,
    contributor_id  TEXT NOT NULL,
    idea_id         TEXT NOT NULL,
    invested_cc     REAL NOT NULL DEFAULT 0.0,
    current_value_cc REAL NOT NULL DEFAULT 0.0,
    first_staked_at TEXT NOT NULL,   -- ISO 8601
    last_updated_at TEXT NOT NULL,
    UNIQUE(contributor_id, idea_id)
);
CREATE INDEX inv_pos_contributor ON investment_positions(contributor_id);
CREATE INDEX inv_pos_idea ON investment_positions(idea_id);
```

Position `current_value_cc` is recalculated on each `POST /ideas/{id}/stake` call and on idea stage transitions.

### New Table: `time_pledges`

```sql
CREATE TABLE time_pledges (
    pledge_id       TEXT PRIMARY KEY,
    contributor_id  TEXT NOT NULL,
    idea_id         TEXT NOT NULL,
    hours_pledged   REAL NOT NULL,
    pledge_type     TEXT NOT NULL,   -- 'review' | 'implement' | 'test'
    cc_equivalent   REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'fulfilled' | 'expired'
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    fulfilled_at    TEXT,
    contribution_id TEXT,
    evidence_url    TEXT
);
CREATE INDEX pledge_contributor ON time_pledges(contributor_id);
CREATE INDEX pledge_idea ON time_pledges(idea_id);
```

### Updated: `contribution_ledger` — Add `event_type`

Existing `contribution_type` field is already used. Add `event_subtype` to distinguish `compute_charge` from `compute_generic` and `return` from `stake`.

Existing `stake` records in `contribution_ledger` are the source of truth for all investment history. The `investment_positions` table is a derived materialized cache updated transactionally.

### ROI Projection Formula (canonical)

```python
def project_roi(amount_cc: float, coherence_score: float, prior_roi_avg: float) -> dict:
    base = amount_cc * max(0.5, coherence_score)
    low  = base * (1.0 + prior_roi_avg * 0.5)
    high = base * (1.0 + prior_roi_avg * 1.5)
    return {
        "low_multiplier":  round(low  / amount_cc, 2),
        "high_multiplier": round(high / amount_cc, 2),
    }
```

Prior ROI avg defaults to `1.0` when no prior investments exist.

### Stage Unlock Schedule

| Stage Reached   | % of Projected Return Unlocked |
|-----------------|-------------------------------|
| none            | 0%                            |
| specced         | 5%                            |
| implementing    | 20%                           |
| testing         | 50%                           |
| reviewing       | 80%                           |
| complete        | 100%                          |

---

## Files to Create/Modify

### New Files
- `api/app/routers/investments.py` — All new investment endpoints
- `api/app/services/investment_service.py` — Portfolio positions, ROI projection, history assembly
- `api/app/services/time_pledge_service.py` — Time pledge creation, fulfillment, expiry
- `api/app/models/investment.py` — Pydantic models: InvestmentPosition, Portfolio, TimePledge, InvestmentEvent
- `api/tests/test_investments.py` — pytest tests for all new endpoints
- `web/app/portfolio/investments/page.tsx` — Portfolio positions page
- `web/app/portfolio/history/page.tsx` — CC flow history page
- `web/components/InvestModal.tsx` — Invest button + modal component
- `web/components/CCFlowChart.tsx` — Sparkline visualization of CC balance

### Modified Files
- `api/app/main.py` — Register `investments` router
- `api/app/routers/ideas.py` — Add `dry_run` to StakeRequest; call `investment_service.update_position()` on stake
- `api/app/services/stake_compute_service.py` — Call `investment_service.update_positions_on_stage_change()` on stage transitions
- `web/app/ideas/page.tsx` — Add "Invest" button to idea cards
- `web/app/ideas/[id]/page.tsx` — Add "Invest" button to idea detail header
- `web/app/portfolio/page.tsx` — Link to `/portfolio/investments` and `/portfolio/history`

---

## Verification Scenarios

### Scenario 1: CLI dry-run shows ROI projection without staking

**Setup**: Idea `test-idea-001` exists with `coherence_score=0.72`, stage `specced`, 3 prior investments with avg ROI 1.6×.

**Action**:
```bash
cc invest test-idea-001 50 --dry-run
```

**Expected result**:
- Output contains "Projected ROI:" with a numeric range (e.g., `1.4× — 2.1×`)
- Output contains "Confirm?" NOT present (dry-run, no prompt)
- `GET /api/ideas/test-idea-001/invest-preview` returns `projections.low_multiplier >= 1.0` and `projections.high_multiplier > projections.low_multiplier`
- No new stake record created: `GET /api/contributors/alice/investments` does NOT show `test-idea-001`

**Edge case**: `cc invest nonexistent-idea 50 --dry-run` returns error: "Idea not found" (exit code 1, no crash).

---

### Scenario 2: Web invest modal opens, confirm creates stake

**Setup**: Logged-in contributor "bob". Idea `graphql-caching` on `/ideas` page.

**Action** (browser):
1. Navigate to `https://coherencycoin.com/ideas`
2. Click "Invest" button on the `graphql-caching` card
3. Modal opens showing ROI projection
4. Enter `25` in the CC amount field
5. Click "Invest" button in modal

**Expected result**:
- Modal shows idea name, stage, coherence score, and ROI range before confirmation
- After click: HTTP 200 from `POST /api/ideas/graphql-caching/stake` with `{ "stake": { "amount_cc": 25.0 } }`
- Card updates: "Total staked" counter increments by 25 CC (no page reload)
- Modal closes with success state

**Edge case**: Enter `0` in amount field → "Invest" button disabled, inline validation "Amount must be > 0".
**Edge case**: Enter `99999` when contributor has only 100 CC → error "Insufficient balance".

---

### Scenario 3: Portfolio view shows current value after stage transition

**Setup**:
- "alice" staked 50 CC on `auth-rewrite` when it was at stage `none`
- Idea `auth-rewrite` has since progressed to stage `testing` (50% unlock)

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/contributors/alice/investments
```

**Expected result**:
```json
{
  "positions": [{
    "idea_id": "auth-rewrite",
    "invested_cc": 50.0,
    "current_value_cc": <value >= 25.0>,
    "stage": "testing",
    "unlock_pct": 50,
    "roi_pct": <number>
  }]
}
```
- `current_value_cc` must be ≥ 25.0 (50% of invested, minimum unlock for `testing` stage)
- `roi_pct` must equal `(current_value_cc - 50.0) / 50.0 * 100` (computed correctly)
- Summary `total_current_value_cc` must equal sum of all position `current_value_cc`

**Edge case**: `GET /api/contributors/alice/investments` when alice has no stakes → returns `{"positions": [], "summary": {"total_positions": 0}}` (not 404, not 500).

---

### Scenario 4: Time pledge creation and fulfillment

**Setup**: Contributor "carol" wants to pledge 2 hours of review on idea `api-caching`, current human_hour_cc = 500.

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/contributors/carol/pledges \
  -H "Content-Type: application/json" \
  -d '{"idea_id": "api-caching", "hours_pledged": 2.0, "pledge_type": "review"}'
```

**Expected result**:
- HTTP 201
- Response contains `pledge_id`, `cc_equivalent: 1000.0`, `status: "pending"`, `expires_at` = ~7 days from now
- `GET /api/contributors/carol/pledges` shows the pledge

**Fulfillment action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/contributors/carol/pledges/<pledge_id>/fulfill \
  -H "Content-Type: application/json" \
  -d '{"contribution_id": "contrib_xyz", "evidence_url": "https://github.com/org/repo/pull/42"}'
```

**Expected result**:
- HTTP 200, `status: "fulfilled"`, `fulfilled_at` set
- A new `contribution_ledger` record created for carol with `amount_cc: 1000.0`, `contribution_type: "return"`

**Edge case**: Fulfill a pledge that's already fulfilled → HTTP 409 "Pledge already fulfilled".
**Edge case**: Fulfill a pledge with `pledge_id` from different contributor → HTTP 403.

---

### Scenario 5: Investment history returns ordered CC flow events

**Setup**: "dave" has staked on 2 ideas, had compute charges deducted, and received one partial return.

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/contributors/dave/investment-history?limit=50"
```

**Expected result**:
- HTTP 200
- `events` array is ordered by `ts` ascending
- Each event has: `ts`, `type` (one of `stake|compute_charge|return|pledge_fulfilled`), `idea_id`, `amount_cc`, `balance_after`
- `balance_after` is monotonically consistent: each event's `balance_after` equals previous `balance_after + amount_cc`
- `running_balance` array has same length as `events`

**Edge case**: `?since=2099-01-01T00:00:00Z` (future date) → `events: []`, HTTP 200 (not 404).
**Edge case**: `?idea_id=nonexistent` → `events: []`, HTTP 200 (not 404).

---

## Evidence of Realization

The feature is considered realized when all five items below can be independently verified:

1. **CLI dry-run** — `cc invest <any-idea-id> 1 --dry-run` returns a ROI projection (not an error) against the live API at `https://api.coherencycoin.com`
2. **Web modal** — `https://coherencycoin.com/ideas` shows an "Invest" button on at least one idea card; clicking it opens a modal with ROI data
3. **Portfolio page** — `https://coherencycoin.com/portfolio/investments` renders without 404/500 for any signed-in contributor
4. **History API** — `GET https://api.coherencycoin.com/api/contributors/{id}/investment-history` returns valid JSON with `events` array
5. **Time pledge API** — `POST https://api.coherencycoin.com/api/contributors/{id}/pledges` accepts `hours_pledged` and returns HTTP 201 with `cc_equivalent`

---

## Risks and Assumptions

| Risk | Severity | Mitigation |
|------|----------|-----------|
| ROI projection is speculative — contributors may over-invest expecting guaranteed returns | High | Display clear disclaimer: "Projected, not guaranteed. Based on historical pipeline velocity." |
| `investment_positions` cache drifts from `contribution_ledger` source of truth | Medium | Recalculate positions from ledger on startup; expose `/api/admin/investments/recalculate` endpoint |
| Time pledge fulfillment has no automated verification — relies on contributor honesty | Medium | Phase 1: manual review. Phase 2: link to git commit hash and auto-verify via GitHub API |
| Portfolio page shows stale data if positions table not updated on stage transitions | Medium | Add `investment_service.update_positions_on_stage_change()` call to all idea stage transition code paths |
| CC amount input allows fractional values — portfolio arithmetic must use consistent rounding | Low | All CC amounts rounded to 4 decimal places throughout |
| Multi-stakeholder: multiple contributors invest in same idea | Low | Positions are per-contributor — no aggregation confusion |

---

## Known Gaps and Follow-up Tasks

- **Phase 2**: Automated time pledge fulfillment via GitHub PR merge detection
- **Phase 2**: CC return distribution triggers (when idea reaches `complete`, distribute returns proportionally to all investors)
- **Phase 2**: Investment alerts — notify investors by email/Telegram when their idea progresses stages
- **Phase 2**: Social proof on invest modal — show "3 contributors already invested"
- **Phase 2**: Secondary market — allow contributors to transfer their investment position to another contributor
- **Follow-up spec**: Governance around time pledge expiry — what happens to expired pledges, any penalty?
- **Known gap**: No backtesting data for ROI projection formula; formula calibrated manually until enough historical data exists (target: 50+ completed ideas)

---

## How This Proves the Idea Is Working Over Time

The spec addresses the open question: *"How can we improve this idea, show whether it is working yet, and make that proof clearer over time?"*

**Evidence signals built into the feature**:

1. **Portfolio ROI% column** is the primary proof signal. A contributor can see at a glance whether their investments are positive or negative. If the median ROI% across the network is > 0 over 30 days, the feature is working.

2. **Stage unlock progression** shows the investment is alive and moving. An investment stuck at 0% unlock for 14 days signals a pipeline blockage — this is surfaced visually in the portfolio with a "stalled" badge.

3. **History flow chart** lets contributors trace exactly where CC went: into which tasks, at what cost, and what came back. If cost exceeds return, that's a clear failure signal visible to the investor and the network.

4. **Time pledge fulfillment rate** is a secondary health metric: if pledges are being created but not fulfilled, labor participation is low. This appears in a new metric `GET /api/metrics/pledge-fulfillment-rate`.

5. **Network-level proof**: the ideas leaderboard (`GET /api/ideas?sort=roi_desc`) shows which ideas generated the highest ROI for investors. Any outside observer can verify this list is grounded in real CC flows through the contribution ledger.

The combination of live portfolio positions + historical CC flows + public idea ROI ranking creates a self-reinforcing proof loop: ideas that generate real returns attract more investment, which generates more tasks, which generates more evidence, which improves the ROI projection accuracy over time.
