# Spec: My Portfolio (ux-my-portfolio)

**Idea ID:** `ux-my-portfolio`  
**Related implementation:** Contributor portfolio API (`spec 174` references in code), service `portfolio_service`, router `contributors_portfolio`, web routes under `/my-portfolio` and `/contributors/[id]/portfolio`.

## Goal

Give each contributor **one** personal view that answers: *What have I done? What did I invest in? Where is my CC? How are my ideas doing?* The experience should read as a **garden** (non-technical) and expose a **ledger** with audit-friendly aggregates (technical).

## Scope

### In scope

- Linked identities (GitHub, Telegram, wallet, OAuth-linked identities when present).
- CC balance and **network percentage** (optional absolute + `% of network supply`).
- CC earning history as a **time-bucketed series** suitable for a simple chart.
- Ideas contributed to: status, contribution types, attributed CC, health signal.
- Stakes: staked amount, valuation, ROI % when data exists.
- Completed tasks: provider, outcome, CC earned.
- Drill-down: idea → contributions + value lineage summary; nested web routes for deeper views.

### Out of scope (follow-ups)

- Strong authentication binding “me” to a session (see Open questions).
- Full cryptographic or multi-hop **lineage chain** resolution in graph (API models allow `lineage_chain_id`; population may be partial).

## API Endpoints (required)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/contributors/{contributor_id}/portfolio` | Summary: identities, CC, counts |
| GET | `/api/contributors/{contributor_id}/portfolio?include_cc=false` | Summary without CC fields |
| GET | `/api/contributors/{contributor_id}/cc-history` | CC history (`window`, `bucket` query params) |
| GET | `/api/contributors/{contributor_id}/idea-contributions` | Paginated ideas list |
| GET | `/api/contributors/{contributor_id}/idea-contributions/{idea_id}` | Drill-down for one idea |
| GET | `/api/contributors/{contributor_id}/stakes` | Stakes list |
| GET | `/api/contributors/{contributor_id}/tasks` | Tasks (e.g. `status=completed`) |

**Error behavior:** Unknown contributor → **404** on portfolio routes. Idea drill-down with no matching contributions → **403** (documented behavior). Invalid query params (e.g. bad `limit`, unknown `bucket`) → **422** or **404** per validation rules.

## Web Pages (required)

| Path | Purpose |
|------|---------|
| `/my-portfolio` | Entry: contributor ID → redirect to portfolio view |
| `/contributors/[id]/portfolio` | Full portfolio dashboard |
| `/contributors/[id]/portfolio/ideas/[idea_id]` | Idea drill-down |
| `/contributors/[id]/portfolio/stakes/[stake_id]` | Stake drill-down (if implemented) |
| `/contributors/[id]/portfolio/tasks/[task_id]` | Task drill-down (if implemented) |

## Files (reference)

- `api/app/routers/contributors_portfolio.py`
- `api/app/services/portfolio_service.py`
- `api/app/models/portfolio.py`
- `api/app/main.py` (router registration)
- `web/app/my-portfolio/page.tsx`
- `web/app/contributors/[id]/portfolio/page.tsx`
- `web/app/contributors/[id]/portfolio/ideas/[idea_id]/page.tsx`
- `api/tests/test_ux_my_portfolio.py`

## Acceptance Criteria

1. A contributor with graph-backed nodes can load `/my-portfolio`, enter their ID, and see **identities**, **CC balance**, **% of network**, **chart data**, **ideas**, **stakes**, and **tasks** when corresponding nodes exist.
2. API returns **404** for non-existent contributors across all portfolio sub-routes.
3. CC history rejects invalid `bucket` values with a clear error (404/422 as implemented).
4. Idea drill-down returns **403** when the contributor has no contributions for that idea.
5. Tests in `test_ux_my_portfolio.py` pass in CI (pytest).

## Open Questions (product)

1. **Authentication:** Today the personal view is keyed by **contributor UUID / handle** entered manually. Sessions or OAuth-to-contributor binding are **not** required for MVP but are the path to true “my” without typing an ID.
2. **CC display:** API exposes **both** absolute balance and `cc_network_pct` (and per-bucket `network_pct_at_period_end`). UI should allow toggling or always show both as in current dashboard.
3. **Proof over time:** Add periodic snapshots or export of portfolio metrics (e.g. weekly CC, idea health) so “is it working?” is visible as a trend, not only a point-in-time.

## Verification Scenarios

### Scenario 1 — Full create-read cycle (contributor + portfolio graph)

- **Setup:** Clean in-memory/API test environment (or production test contributor).
- **Action:**
  1. `curl -sS -X POST "$API/api/contributors" -H "Content-Type: application/json" -d '{"type":"HUMAN","name":"VTest User","email":"vtest@example.com"}'` → capture `id` as `CID`.
  2. Seed graph nodes per test helper (contribution, stake, task linked to `CID`) or use existing seed script.
  3. `curl -sS "$API/api/contributors/$CID/portfolio"`
- **Expected:** HTTP **200**, JSON includes `contributor.id == CID`, non-null `cc_balance` when contributions carry `cost_amount`, `idea_contribution_count` ≥ 1 when ideas linked.
- **Edge:** `GET /api/contributors/00000000-0000-0000-0000-000000000099/portfolio` → **404**, `detail` mentions not found.

### Scenario 2 — CC history and chart inputs

- **Setup:** Contributor `CID` with contributions in the last 90 days.
- **Action:** `curl -sS "$API/api/contributors/$CID/cc-history?window=90d&bucket=7d"`
- **Expected:** HTTP **200**, `series` is a non-empty array of buckets with `cc_earned`, `running_total`, `network_pct_at_period_end` (nullable allowed).
- **Edge:** `curl -sS "$API/api/contributors/$CID/cc-history?bucket=2d"` → **404** (invalid bucket).

### Scenario 3 — Idea list and drill-down

- **Setup:** Contributor with at least one `idea_id` on contributions.
- **Action:**
  1. `curl -sS "$API/api/contributors/$CID/idea-contributions"`
  2. `curl -sS "$API/api/contributors/$CID/idea-contributions/<idea_id>"`
- **Expected:** (1) HTTP **200**, `items[0].idea_id` matches seeded idea. (2) HTTP **200**, `contributions` length ≥ 1, `value_lineage_summary.total_value` equals sum of attributed CC within float tolerance.
- **Edge:** `GET .../idea-contributions/wrong-idea-id` → **403** when no contributions match.

### Scenario 4 — Stakes ROI

- **Setup:** Stake node with `cc_staked` and `cc_valuation`.
- **Action:** `curl -sS "$API/api/contributors/$CID/stakes"`
- **Expected:** HTTP **200**, at least one item with `roi_pct` consistent with \((valuation - staked) / staked \times 100\) when both values present.

### Scenario 5 — Web entry and dashboard

- **Setup:** Browser or `curl -sI` for static deploy.
- **Action:** Open `https://coherencycoin.com/my-portfolio` (or staging); enter known `CID`; navigate to `/contributors/<CID>/portfolio`.
- **Expected:** Page loads without 5xx; dashboard sections “CC Balance”, “Ideas I Contributed To”, “Ideas I Staked On”, “Tasks I Completed” render; links to idea drill-down resolve (HTTP 200 for document).
- **Edge:** Invalid contributor ID shows error state and link back to `/my-portfolio`, not a blank page.

## Risks and Assumptions

- **Graph scale:** `list_nodes(..., limit=10000)` may truncate very large datasets; production may need pagination at the graph layer.
- **CC supply:** Network total is derived from contribution `cost_amount` sum; if definitions change, `%` must be recalibrated.

## Known Gaps and Follow-up Tasks

- Populate `lineage_chain_id` / full lineage from graph when lineage edges exist.
- Session-based auth to avoid manual contributor ID entry.
- Align formal spec number “174” with this document or add cross-link in repo spec registry.
