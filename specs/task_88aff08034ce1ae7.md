# Spec: My Portfolio — Personal View of Investments and Contributions

**Spec ID**: `task_88aff08034ce1ae7`  
**Idea ID**: `my-portfolio-personal-view` (tracking label; aligns with product narrative “garden vs ledger”)  
**Status**: Draft (product specification; backend portfolio surface largely implemented under internal ref “spec 174”)  
**Depends on**: Spec 119 (Coherence Credit), Spec 048 (Value Lineage), Spec 157 (Investment UX), `specs/168-identity-driven-onboarding-tofu.md` (identity linking), `api/app/services/portfolio_service.py`  
**Related UI**: `web/app/contributors/[id]/portfolio/*`, `web/app/my-portfolio/page.tsx`

---

## Purpose

Contributors need **one coherent place** to answer: *What have I done? What did I invest in? Where is my CC? How are my ideas doing?* Without this, attribution, staking decisions, and trust in the CC economy stay abstract. This spec defines the **end-to-end portfolio experience** (API + web + audit drill-down), maps it to **existing** endpoints where they already exist, and records **explicit gaps** (especially browser authentication to “me” without typing a raw contributor ID). It prevents duplicate or divergent portfolio implementations by anchoring names, payloads, and verification to production-checkable `curl` scenarios.

---

## Summary

“My Portfolio” is the **personal dashboard** for a contributor: linked identities at the top; CC balance plus **time-bucketed earning history** as a chart; **ideas contributed to** with status, contribution types, attributed CC, and health; **stakes** with ROI since staking; **completed agent tasks** with provider and outcome. **Drill-down**: idea → my contributions on that idea → value lineage summary; contribution → CC attributed → **lineage chain** (technical audit). **Metaphor**: non-technical users see a **garden** (ideas as plants, growth signals); technical users see a **ledger** with full audit trail.

Backend models and routes for this portfolio are already present (`api/app/models/portfolio.py`, `api/app/routers/contributors_portfolio.py`, `api/app/routers/me_portfolio.py`). The **web** exposes contributor-scoped pages under `/contributors/{id}/portfolio` and a **landing** `/my-portfolio` that currently only asks for a contributor ID (no API-key session). This spec **locks** the **canonical API list**, **web routes**, **UX acceptance criteria**, and **resolves open product questions** (auth, CC display, proof-over-time) so implementers extend rather than fork.

---

## Open Questions (Resolved in This Spec)

| Question | Decision |
|----------|----------|
| How does a contributor authenticate for a personal view? Identity link is key — do we need sessions? | **Primary (machine/API)**: `X-API-Key` header tied to a `contributor_id` via `GET /api/identity/me` and all `GET /api/me/*` routes (see §API). **Primary (human/web, current)**: Navigate `/my-portfolio` → enter `contributor_id` → `/contributors/{id}/portfolio` (no secret; **read-only public view by ID**). **Target (follow-up)**: Browser session or OAuth-bound contributor + optional stored API key for **private** “me” mode without exposing ID in the URL. Sessions are **not** required for API correctness; they are a **web UX** concern for hiding the contributor id and attaching the key. |
| CC in absolute numbers or % of network? | **Both** in the API: `PortfolioSummary` includes `cc_balance` and optional `cc_network_pct` (`include_cc=true`). UI must show **absolute CC as primary** and **network % as secondary** context (tooltip/subtitle), never the reverse. |
| How do we improve the idea, show whether it is working, and make proof clearer over time? | Reuse **health signals** on idea rows (`HealthSignal`: activity, value delta, evidence count). Link to **grounded metrics** (`specs/116-grounded-idea-portfolio-metrics.md`) and **traceability** (`GET /api/traceability/lineage/{idea_id}`) from drill-down “evidence” links. Portfolio page **must** show “last updated” / data freshness where available. |

---

## Requirements

- [ ] **R1 — Single portfolio hub (web)**  
  `/contributors/{contributor_id}/portfolio` is the **main hub**: sections for identities, CC summary + link to history chart data, idea contributions, stakes, tasks; each section links to existing drill-down routes (`…/ideas/{idea_id}`, `…/contributions/{contribution_id}`, tasks/stakes detail as applicable).

- [ ] **R2 — Identity strip**  
  Top of the hub shows **all linked identities** from `ContributorSummary.identities` (via `GET …/portfolio` or `GET /api/identity/{contributor_id}`). Verified badges must match `LinkedIdentity.verified`.

- [ ] **R3 — CC balance and history chart**  
  Client loads `GET /api/contributors/{id}/cc-history` (or `GET /api/me/cc-history` with API key) and renders **bucketed** series (`CCHistory.series`: `cc_earned`, `running_total`, optional `network_pct_at_period_end`). Empty series must show an explicit empty state, not a broken chart.

- [ ] **R4 — Ideas contributed**  
  List from `GET /api/contributors/{id}/idea-contributions` shows: idea title, status, contribution types, `cc_attributed`, `health`, sort/pagination. Row click navigates to idea drill-down.

- [ ] **R5 — Stakes**  
  List from `GET /api/contributors/{id}/stakes` shows `cc_staked`, valuation, `roi_pct`, `staked_at`, and health. ROI is **since staking** (backend-defined semantics; UI labels must match API field names in tooltips).

- [ ] **R6 — Tasks completed**  
  List from `GET /api/contributors/{id}/tasks` shows provider, outcome, `cc_earned`, `completed_at`, related idea when present.

- [ ] **R7 — Drill-down: idea**  
  `GET /api/contributors/{id}/idea-contributions/{idea_id}` returns `IdeaContributionDrilldown` with per-contribution rows and `value_lineage_summary`. UI links to full lineage APIs where users need technical depth (`/api/traceability/lineage/{idea_id}`).

- [ ] **R8 — Drill-down: contribution lineage**  
  `GET /api/contributors/{id}/contributions/{contribution_id}/lineage` returns `ContributionLineageView` with `cc_attributed`, `lineage_chain_id`, optional `value_lineage_link`. 403 if contributor does not own the contribution.

- [ ] **R9 — Authenticated “me” API**  
  All `GET /api/me/*` routes require `X-API-Key` and return the same shapes as `/api/contributors/{contributor_id}/*` for the key’s contributor. Documented for agents and CLI wrappers.

- [ ] **R10 — Garden vs ledger**  
  Default copy uses **garden** metaphor; **advanced** toggle or tab exposes **ledger** (JSON, chain IDs, lineage links).

---

## Research Inputs (Required)

- `2026-03-28` — Internal: `specs/157-investment-ux-stake-cc-on-ideas.md` — investment flows and ROI language; portfolio tables and history.  
- `2026-03-28` — Internal: `specs/116-grounded-idea-portfolio-metrics.md` — how “is this idea working?” is grounded in observable signals.  
- `2026-03-28` — Internal: `docs/RUNBOOK.md` (Idea Tracking) — contributor and idea attribution expectations.  
- `2026-03-28` — Internal: `api/app/routers/me_portfolio.py`, `api/app/routers/contributors_portfolio.py` — canonical route implementations.

---

## Task Card (Required)

```yaml
goal: Ship a single contributor-facing portfolio hub with full drill-down to lineage, using existing portfolio APIs and filling gaps only where specified in Files to Create/Modify.
files_allowed:
  - web/app/contributors/[id]/portfolio/page.tsx
  - web/app/contributors/[id]/portfolio/ideas/[idea_id]/page.tsx
  - web/app/contributors/[id]/portfolio/contributions/[contribution_id]/page.tsx
  - web/app/my-portfolio/page.tsx
  - api/app/services/portfolio_service.py
  - api/app/routers/me_portfolio.py
  - api/tests/test_portfolio_api.py
done_when:
  - python3 scripts/validate_spec_quality.py --file specs/task_88aff08034ce1ae7.md passes
  - Production verification scenarios in §Verification Scenarios pass against https://api.coherencycoin.com
commands:
  - python3 scripts/validate_spec_quality.py --file specs/task_88aff08034ce1ae7.md
  - cd api && pytest -q api/tests/test_portfolio_api.py
constraints:
  - Do not rename published API paths without a migration spec; prefer additive fields.
```

---

## API Contract

Base URL examples use `$API=https://api.coherencycoin.com`.

### Public contributor-scoped (no auth; knowledge of `contributor_id` required)

| Method | Path | Response model |
|--------|------|----------------|
| GET | `/api/contributors/{contributor_id}/portfolio` | `PortfolioSummary` |
| GET | `/api/contributors/{contributor_id}/cc-history` | `CCHistory` |
| GET | `/api/contributors/{contributor_id}/idea-contributions` | `IdeaContributionsList` |
| GET | `/api/contributors/{contributor_id}/idea-contributions/{idea_id}` | `IdeaContributionDrilldown` |
| GET | `/api/contributors/{contributor_id}/stakes` | `StakesList` |
| GET | `/api/contributors/{contributor_id}/tasks` | `TasksList` |
| GET | `/api/contributors/{contributor_id}/contributions/{contribution_id}/lineage` | `ContributionLineageView` |

Query parameters (as implemented): `include_cc`, `window`, `bucket`, `sort`, `limit`, `offset`, `status`.

### Authenticated “me” (requires `X-API-Key` header)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/me/portfolio` | Same as `…/contributors/{id}/portfolio` |
| GET | `/api/me/cc-history` | |
| GET | `/api/me/idea-contributions` | |
| GET | `/api/me/idea-contributions/{idea_id}` | |
| GET | `/api/me/stakes` | |
| GET | `/api/me/tasks` | |
| GET | `/api/me/contributions/{contribution_id}/lineage` | |

### Identity helpers

| Method | Path |
|--------|------|
| GET | `/api/identity/me` — `X-API-Key` → contributor + linked account count |
| GET | `/api/identity/{contributor_id}` — list linked identities |

### Lineage / traceability (technical audit)

| Method | Path |
|--------|------|
| GET | `/api/traceability/lineage/{idea_id}` — full chain for technical users |

**Error handling**:  
- Missing/invalid API key on `/api/me/*` → **401** with `detail` message.  
- Unknown contributor or empty portfolio store where applicable → **404** (as implemented).  
- Contribution lineage for another contributor’s contribution → **403**.

---

## Web Routes (Exact)

| Route | Role |
|-------|------|
| `/my-portfolio` | Landing: enter contributor id (or future: authenticate). |
| `/contributors/{id}/portfolio` | **Main hub** (this spec’s “one page” center of gravity). |
| `/contributors/{id}/portfolio/ideas/{idea_id}` | Idea drill-down. |
| `/contributors/{id}/portfolio/contributions/{contribution_id}` | Contribution → CC + lineage. |
| `/contributors/{id}/portfolio/stakes/{stake_id}` | Stake detail (if populated). |
| `/contributors/{id}/portfolio/tasks/{task_id}` | Task detail. |

---

## CLI (Optional parity)

| Command | Purpose |
|---------|---------|
| `cc contribute --type … --cc … --desc …` | Records work that should later appear in portfolio/ledger narratives. |
| `cc stake <idea_id> <cc>` | Creates stake positions surfaced under `…/stakes`. |

**Note**: A dedicated `cc portfolio` alias may wrap `GET /api/me/*` when `X-API-Key` is configured; not required for this spec’s acceptance if API scenarios pass.

---

## Data Model (Aggregated)

Key entities already defined in `api/app/models/portfolio.py`:

- `PortfolioSummary` — `contributor`, `cc_balance`, `cc_network_pct`, counts, `recent_activity`.  
- `CCHistory` / `CCHistoryBucket` — time series for charts.  
- `IdeaContributionSummary`, `IdeaContributionDrilldown`, `ContributionDetail`, `ValueLineageSummary`.  
- `StakeSummary`, `TaskSummary`.  
- `ContributionLineageView` — audit trail for one contribution.

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `specs/task_88aff08034ce1ae7.md` | This spec (authoritative for product requirements). |
| `web/app/contributors/[id]/portfolio/page.tsx` | Ensure hub sections + empty states match R1–R6. |
| `web/app/my-portfolio/page.tsx` | Future: optional API-key storage / session; document until implemented. |
| `api/tests/test_portfolio_api.py` | Extend if new endpoints or fields; must cover error paths in scenarios. |

*No backend file changes are required for spec approval if production already exposes the listed routes.*

---

## Acceptance Tests

- `api/tests/test_portfolio_api.py` (or equivalent) — **GET** portfolio, cc-history, idea-contributions, stakes, tasks; **401** on `/api/me/portfolio` without key; **404** for unknown contributor; **403/404** on lineage when contribution not owned.  
- Web: manual or Playwright — hub loads for a known `contributor_id` with network mocked or staging.

---

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/task_88aff08034ce1ae7.md
cd api && pytest -q tests/test_portfolio_api.py
```

Manual / production (see §Verification Scenarios):

```bash
export API=https://api.coherencycoin.com
curl -sS "$API/api/contributors/<contributor_id>/portfolio" | head -c 500
curl -sS -H "X-API-Key: <key>" "$API/api/me/portfolio" | head -c 500
```

---

## Verification Scenarios

These scenarios are the **contract** for reviewers; vague scenarios are considered **spec failure**.

### Scenario 1 — Full read cycle for portfolio hub (happy path)

- **Setup**: A contributor `<CID>` exists with at least one linked identity, non-zero CC balance or history, ≥1 idea contribution, ≥1 stake or task (seeded or real production user).  
- **Action**:  
  `curl -sS "$API/api/contributors/<CID>/portfolio"`  
  then  
  `curl -sS "$API/api/contributors/<CID>/cc-history?window=90d&bucket=7d"`  
  then  
  `curl -sS "$API/api/contributors/<CID>/idea-contributions?limit=5"`  
- **Expected**: HTTP **200** for each; JSON `contributor.id == "<CID>"`; `CCHistory.series` is a JSON array (may be empty but key present); `IdeaContributionsList.items` is an array.  
- **Edge**: `limit=0` or invalid → **422** validation error (FastAPI); `contributor_id` unknown → **404** with detail string.

### Scenario 2 — Drill-down create-read: idea → contributions → lineage

- **Setup**: Known `<CID>`, `<IDEA>` such that the contributor has contributions.  
- **Action**:  
  `curl -sS "$API/api/contributors/<CID>/idea-contributions/<IDEA>"`  
  Pick `contributions[0].id` as `<CONTR>`.  
  `curl -sS "$API/api/contributors/<CID>/contributions/<CONTR>/lineage"`  
- **Expected**: First call returns `IdeaContributionDrilldown` with `contributions` list; second returns `ContributionLineageView` with matching `contribution_id` and `cc_attributed` ≥ 0.  
- **Edge**: Wrong `contribution_id` → **404**; another contributor’s contribution id → **403** or **404** per implementation (must not leak foreign data).

### Scenario 3 — Authenticated “me” mirror (API key)

- **Setup**: Valid `X-API-Key` whose `contributor_id` is `<CID>`.  
- **Action**:  
  `curl -sS -H "X-API-Key: $KEY" "$API/api/me/portfolio"`  
  Compare to  
  `curl -sS "$API/api/contributors/<CID>/portfolio"`  
- **Expected**: Both **200**; material fields (`contributor.id`, `cc_balance` if included) **match**.  
- **Edge**: Missing header → **401** `{"detail":"Missing X-API-Key header"}`; invalid key → **401**.

### Scenario 4 — Identity and session question (no session required for API)

- **Setup**: Same `$KEY`.  
- **Action**:  
  `curl -sS -H "X-API-Key: $KEY" "$API/api/identity/me"`  
- **Expected**: **200**; JSON includes `"contributor_id":"<CID>"` and `linked_accounts` ≥ 0.  
- **Edge**: No header → **401**. Proves identity is keyed off API key **without** browser session.

### Scenario 5 — Error handling and bad input

- **Setup**: None.  
- **Action**:  
  `curl -sS -o /tmp/body -w "%{http_code}" "$API/api/contributors/does-not-exist-xyz/portfolio"`  
  `curl -sS "$API/api/contributors/<CID>/idea-contributions/not-a-real-idea-id-12345"`  
- **Expected**: First returns **404**; second returns **404** or empty drill-down per API rules — **must not** return **500**.  
- **Edge**: Malformed `limit=abc` → **422**.

---

## Concurrency Behavior

- **Read operations**: Safe; portfolio aggregates are point-in-time.  
- **Writes** (identity link, stake, contribute): eventual consistency; portfolio reads may lag until ledger refresh. Clients should not assume instantaneous consistency across CC balance and history buckets.

---

## Out of Scope

- New blockchain settlement or treasury bridge (see `specs/122-crypto-treasury-bridge.md`).  
- Replacing grounded metrics formulas (spec 116 owns computation).  
- Full OAuth web session implementation (captured as follow-up).  
- Renaming `/api/contributors/...` paths.

---

## Risks and Assumptions

- **Risk**: Public `GET /api/contributors/{id}/…` exposes portfolio to anyone who knows the id. **Mitigation**: Document as **non-secret**; sensitive deployments must rely on **unlisted ids** + future private mode.  
- **Assumption**: `portfolio_service` data sources (ledger, tasks store) are populated by real usage; empty portfolios are common for new users.  
- **Assumption**: Production API is deployed at `https://api.coherencycoin.com` for reviewer scenarios.

---

## Known Gaps and Follow-up Tasks

- **Web private mode**: Session or magic-link login so `/my-portfolio` does not require typing contributor id; store API key client-side only with clear security warning, or server-side session.  
- **Unified route**: Optional `GET /portfolio` redirect when authenticated (single URL).  
- **CLI**: `cc portfolio` wrapping `/api/me/*` for parity with web.  
- **Deeper proof**: Surface links from portfolio to `GET /api/traceability/lineage/{idea_id}` in UI copy.

---

## Failure/Retry Reflection

- **Failure mode**: Empty charts or zeros after heavy usage — user distrust.  
- **Blind spot**: Stale `recent_activity` or missing evidence counts.  
- **Next action**: Cross-check `HealthSignal.evidence_count` and data freshness fields in UI; link to grounded metrics spec.

---

## Decision Gates

- Product approval on **public-by-contributor-id** semantics for default web flow.  
- Security review before **storing API keys** in browser localStorage for “me” mode.
