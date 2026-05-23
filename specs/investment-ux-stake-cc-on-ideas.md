---
idea_id: identity-and-onboarding
status: done
source:
  - file: api/app/services/stake_compute_service.py
    symbols: [compute_next_tasks_for_idea()]
  - file: api/app/services/contribution_ledger_service.py
    symbols: [CC ledger]
  - file: api/app/services/investment_service.py
    symbols: [compute_positions(), compute_portfolio(), compute_preview(), compute_history()]
  - file: api/app/services/time_pledge_service.py
    symbols: [create_pledge(), fulfill_pledge(), cc_equivalent_for_hours()]
  - file: api/app/routers/investments.py
    symbols: [invest-preview, investments, investment-history, pledges, pledges/fulfill]
  - file: api/app/routers/ideas.py
    symbols: [stake_on_idea() with dry_run]
  - file: web/components/InvestModal.tsx
    symbols: [InvestModal, InvestButton]
  - file: web/app/portfolio/investments/page.tsx
    symbols: [portfolio positions page]
  - file: web/app/invest/page.tsx
    symbols: [investment garden UI]
requirements:
  - GET /api/ideas/{idea_id}/invest-preview returns ROI projection
  - GET /api/contributors/{id}/investments returns all positions with summary
  - GET /api/contributors/{id}/investment-history returns CC flow timeline
  - POST /api/contributors/{id}/pledges creates time pledge with cc_equivalent
  - POST stake endpoint supports dry_run returning projection without recording
  - Web invest modal shows ROI data before confirmation
  - Portfolio page renders positions with gain/loss and ROI percent
done_when:
  - coh invest --dry-run returns ROI projection against live API
  - Web /ideas shows Invest button opening modal with ROI data
  - /portfolio/investments page renders without errors
  - pytest api/tests/test_investments.py passes
  - 'file_exists("api/app/services/stake_compute_service.py")'
  - 'symbol_in_file("api/app/services/stake_compute_service.py", "compute_next_tasks_for_idea")'
  - 'file_exists("api/app/services/contribution_ledger_service.py")'
  - 'symbol_in_file("api/app/services/contribution_ledger_service.py", "CC")'
  - 'file_exists("api/app/services/investment_service.py")'
  - 'symbol_in_file("api/app/services/investment_service.py", "compute_positions")'
  - 'symbol_in_file("api/app/services/investment_service.py", "compute_portfolio")'
  - 'symbol_in_file("api/app/services/investment_service.py", "compute_preview")'
  - 'symbol_in_file("api/app/services/investment_service.py", "compute_history")'
  - 'file_exists("api/app/services/time_pledge_service.py")'
  - 'symbol_in_file("api/app/services/time_pledge_service.py", "create_pledge")'
  - 'symbol_in_file("api/app/services/time_pledge_service.py", "fulfill_pledge")'
  - 'symbol_in_file("api/app/services/time_pledge_service.py", "cc_equivalent_for_hours")'
  - 'file_exists("api/app/routers/investments.py")'
  - 'symbol_in_file("api/app/routers/investments.py", "invest-preview")'
  - 'symbol_in_file("api/app/routers/investments.py", "investments")'
  - 'symbol_in_file("api/app/routers/investments.py", "investment-history")'
  - 'symbol_in_file("api/app/routers/investments.py", "pledges")'
  - 'file_exists("api/app/routers/ideas.py")'
  - 'symbol_in_file("api/app/routers/ideas.py", "stake_on_idea")'
  - 'file_exists("web/components/InvestModal.tsx")'
  - 'symbol_in_file("web/components/InvestModal.tsx", "InvestModal")'
  - 'symbol_in_file("web/components/InvestModal.tsx", "InvestButton")'
  - 'file_exists("web/app/portfolio/investments/page.tsx")'
  - 'symbol_in_file("web/app/portfolio/investments/page.tsx", "portfolio")'
  - 'file_exists("web/app/invest/page.tsx")'
  - 'symbol_in_file("web/app/invest/page.tsx", "investment")'
notes: |
  Live (2026-05-22): web/app/invest/page.tsx renders at /invest. The full
  investment surface now exists end-to-end:
  - GET /api/ideas/{idea_id}/invest-preview returns ROI projection
  - GET /api/contributors/{id}/investments returns positions + summary
  - GET /api/contributors/{id}/investment-history returns CC flow timeline
  - POST /api/contributors/{id}/pledges creates a time pledge with cc_equivalent
  - POST /api/contributors/{id}/pledges/{pledge_id}/fulfill records CC return
  - POST /api/ideas/{idea_id}/stake supports dry_run (body or query)
  - web/components/InvestModal.tsx opens from /ideas cards with ROI preview
  - web/app/portfolio/investments/page.tsx renders positions table
  Underlying contract carried by api/app/services/investment_service.py
  (pure position-computer over the ledger) and time_pledge_service.py
  (hours -> CC at 500 CC/hour). 6 strange-minimal flow tests live in
  api/tests/test_investments.py. Status returned to done.
---

> **Parent idea**: [identity-and-onboarding](../ideas/identity-and-onboarding.md)
> **Source**: [`api/app/services/stake_compute_service.py`](../api/app/services/stake_compute_service.py) | [`api/app/services/contribution_ledger_service.py`](../api/app/services/contribution_ledger_service.py) | [`web/app/invest/page.tsx`](../web/app/invest/page.tsx)

# Investment UX — Stake CC on Ideas from Web and CLI with Clear Returns

**Spec ID**: 157-investment-ux-stake-cc-on-ideas
**Idea ID**: investment-ux
**Status**: done (see frontmatter `notes:` for what's live)
**Depends on**: Spec 119 (Coherence Credit), Spec 121 (OpenClaw Marketplace), Spec 048 (Value Lineage), Spec 052 (Portfolio Cockpit)
**Depended on by**: Spec 124 (CC Economics), Spec 126 (Portfolio Governance)

## Purpose

Give contributors a clear, observable answer to "is my investment working?" — staking CC on an idea shows ROI projection before confirmation, holds a portfolio view of all positions with gain/loss and ROI%, surfaces a CC flow timeline, and accepts time pledges as labor-equivalent commitments. The web surface gains an Invest modal on every idea card; the CLI gains a dry-run that returns the same projection without recording.

## Requirements

- [x] GET /api/ideas/{idea_id}/invest-preview returns ROI projection (low/high multiplier, coherence score, stage unlock, prior investor count)
- [x] GET /api/contributors/{id}/investments returns all positions with portfolio summary (total invested, current value, gain/loss, active vs all)
- [x] GET /api/contributors/{id}/investment-history returns CC flow timeline including stakes, returns, compute, and pledges
- [x] POST /api/contributors/{id}/pledges creates a time pledge with cc_equivalent at the current hour rate
- [x] POST /api/contributors/{id}/pledges/{pledge_id}/fulfill marks pledge fulfilled and records matching CC return contribution
- [x] POST /api/ideas/{idea_id}/stake accepts dry_run (body or query) returning preview without recording
- [x] web/components/InvestModal.tsx opens from /ideas cards with live ROI preview before confirmation
- [x] web/app/portfolio/investments/page.tsx renders positions table with gain/loss and ROI% (mobile + desktop)
- [x] All chrome strings flow through web/messages/<locale>.json — no hardcoded English

## Acceptance Tests

Flow-centric tests in `api/tests/test_investments.py`:

- `test_zero_positions_for_new_contributor` — empty portfolio + zero summary
- `test_one_position_has_basic_roi_and_dry_run_matches` — one stake produces one position; preview reflects same idea state
- `test_stake_dry_run_returns_preview_without_recording` — dry_run via body or query returns projection without recording; portfolio stays empty
- `test_time_pledge_creates_cc_equivalent_and_fulfills` — 2h pledge = 1000 CC; fulfill records return contribution; re-fulfill = 409; wrong contributor = 403/409
- `test_history_timeline_orders_newest_first_and_includes_pledges` — history includes stakes + pledges; filter by idea_id works
- `test_invest_preview_404_for_missing_idea` — preview endpoint 404s for nonexistent idea

## Verification

```bash
# Run the focused test file
pytest api/tests/test_investments.py -v

# Run the full suite to confirm no regression
pytest api/tests/

# Web build sanity
cd web && npm run build

# Prod curl after deploy
curl -s https://api.coherencycoin.com/api/ideas/agent-pipeline/invest-preview | jq .
curl -s https://api.coherencycoin.com/api/contributors/urs-muff/investments | jq .summary
curl -sI https://coherencycoin.com/portfolio/investments | head -1
```

## Out of Scope

- Automated time pledge fulfillment via GitHub PR merge detection (Phase 2)
- CC return distribution triggers when idea reaches `complete` (Phase 2)
- Investment alerts via email/Telegram (Phase 2)
- Secondary market for transferring positions (Phase 2)
- Governance around expired pledges (follow-up spec)

## Risks and Assumptions

- Default hour rate (500 CC/hour) is honest until calibration against real labor flows; surfaced in every pledge response as `cc_per_hour_rate` so callers see what they're paying.
- ROI projection formula calibrated manually until 50+ completed ideas exist; the response carries `basis: "coherence_score + prior_roi_avg"` so the formula is legible.
- Position `current_value_cc` uses `1 + (stage_unlock_pct / 100) * coherence_score` as the multiplier — a defensible default, not an attested measurement; the gap closes when real returns accrue and `prior_roi_avg` carries them.

## Problem Statement

The current `coh stake <idea-id> <amount-cc>` command:
- Accepts a stake and creates tasks, but shows no confirmation of projected return
- Provides no way to see what happened to staked CC after the fact
- Has no portfolio-level view aggregating all positions
- Only accepts CC tokens, not time/labor commitments

The web UI has no investment affordance at all — ideas are browsable but not investable from the browser.

Contributors cannot answer the basic question: *"Is my investment working? What's it worth now?"*

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
When `dry_run: true`, returns the same projection as `invest-preview` without recording the stake. Enables `coh invest --dry-run`.

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

## Evidence of Realization

The feature is considered realized when all five items below can be independently verified:

1. **CLI dry-run** — `coh invest <any-idea-id> 1 --dry-run` returns a ROI projection (not an error) against the live API at `https://api.coherencycoin.com`
2. **Web modal** — `https://coherencycoin.com/ideas` shows an "Invest" button on at least one idea card; clicking it opens a modal with ROI data
3. **Portfolio page** — `https://coherencycoin.com/portfolio/investments` renders without 404/500 for any signed-in contributor
4. **History API** — `GET https://api.coherencycoin.com/api/contributors/{id}/investment-history` returns valid JSON with `events` array
5. **Time pledge API** — `POST https://api.coherencycoin.com/api/contributors/{id}/pledges` accepts `hours_pledged` and returns HTTP 201 with `cc_equivalent`

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
