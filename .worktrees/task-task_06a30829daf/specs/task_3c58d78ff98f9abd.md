# Spec: UX Overhaul — Tabbed Sections, Mobile-First Layout, Novice vs Expert Modes

**Spec ID**: task_3c58d78ff98f9abd  
**Task ID**: task_3c58d78ff98f9abd  
**Status**: draft  
**Priority**: high  
**Author**: product-manager agent  
**Date**: 2026-03-28  

---

## Summary

Coherence Network’s web surface today leans on **long vertical scrolling** for idea detail, lists, and secondary navigation. That pattern hides structure, overloads newcomers, and scales poorly on phones. This spec defines a **unified UX contract**: every major surface uses **tabs (or equivalent view modes)** for content sections; **mobile-first** interaction (bottom tab bar, swipeable cards, collapsible sections); and a **Novice / Expert** presentation mode controlled by stored **per-contributor UI preferences** exposed via `GET`/`PUT /api/preferences/ui`.

**Idea detail** must expose fixed primary tabs: **Overview | Specs | Tasks | Contributors | Edges | History** — one tab panel visible at a time; no single-mile scroll as the only way to reach “History.”

**Ideas list** must support **view modes** (not infinite scroll as the only layout): **Cards | Table | Graph**, persisted in the same preferences object.

**Global navigation** uses **primary tabs**: Ideas, Concepts, Contributors, News, Tasks — with **secondary actions** in a compact dropdown (or overflow menu on narrow widths) so the top bar stays scannable.

**Expert mode** surfaces technical affordances: visible **stable IDs**, optional **raw JSON** toggle for the current resource, and **copyable API URLs** (e.g. `GET https://api.coherencycoin.com/api/ideas/{id}`). **Novice mode** hides IDs and raw payloads by default, uses **guided tooltips** (first-run or dismissible), and prefers **plain-language labels** with technical terms behind “Learn more.”

**CLI** (`cc` and related commands) remains **tab-free by design**; this spec does not add interactive TUI tabs. CLI may read the same preferences for output verbosity in a follow-up if desired.

**Proof over time**: preferences and mode switches are versioned in API responses (`schema_version`, `updated_at`) so clients and audits can tell **whether the contract is live**, when settings last changed, and whether the UI build matches the API schema.

---

## Goals

1. Replace “scroll-only” primary layouts with **shadcn/ui `Tabs`** (or `Tabs` + `DropdownMenu` for secondary nav) on web for idea detail and list views.
2. Ship **mobile-first** patterns: bottom tab bar for primary app sections on `sm` breakpoints; **swipeable** card carousels where lists are browsed horizontally; **collapsible** sections inside tab panels for long content.
3. Implement **Novice** and **Expert** modes as a single `ui_mode` enum plus granular `expert_flags` (see Data model).
4. Persist **per-contributor** UI state via **`/api/preferences/ui`** (read/update); anonymous sessions use client-only defaults until authenticated.
5. Document **exact routes and endpoints** and **verification scenarios** that a reviewer can run against production.

---

## Non-Goals

- Redesigning brand, color tokens, or typography system-wide (use existing shadcn theme).
- Replacing server-side pagination or graph queries — only presentation and navigation shells.
- Building native iOS/Android apps (PWA-friendly web only).
- Changing CLI command structure to mimic tabs.

---

## Requirements

### Layout and navigation

- [ ] **R1** Idea detail page (`/ideas/[id]` or project-equivalent path) renders **six** primary tabs in this order: Overview, Specs, Tasks, Contributors, Edges, History. Changing tabs does not unload the route; state is tab-local where appropriate.
- [ ] **R2** Ideas index (`/ideas`) supports **three** view modes: Cards, Table, Graph. Switching mode updates URL query (e.g. `?view=table`) **and** persists preference server-side when logged in.
- [ ] **R3** Global shell exposes **primary** nav tabs: Ideas, Concepts, Contributors, News, Tasks. Secondary destinations live under a **single** “More” or profile-adjacent dropdown.
- [ ] **R4** At `max-width` below the `md` breakpoint, primary app navigation appears as a **bottom tab bar**; desktop keeps top navigation. Bottom bar items map 1:1 to the same routes as primary tabs.

### Modes: Novice vs Expert

- [ ] **R5** **Novice** (default for new contributors): hide raw IDs in copy surfaces; show **tooltips** on first hover/focus for: Coherence score, edges, “Spec,” “Task,” and investment terms; glossary links optional.
- [ ] **R6** **Expert**: show **IDs** inline (idea id, contributor id, task id where applicable); show **“Raw JSON”** toggle on detail pages that pretty-prints the current resource payload from the API; show **“API”** links opening documented `GET` URLs in a new tab.
- [ ] **R7** Mode is toggleable from a **visible control** in the header or user menu (not only deep in settings).

### API

- [ ] **R8** `GET /api/preferences/ui` returns the authenticated contributor’s UI preferences. If unauthenticated, **401** (no silent fake server-side defaults for anonymous users).
- [ ] **R9** `PUT /api/preferences/ui` replaces or merges (documented) preferences with validation; **422** on invalid enum values; **400** on malformed JSON body.

### Accessibility and motion

- [ ] **R10** Tabs are keyboard-navigable (roving tabindex pattern per WAI-ARIA Authoring Practices). Swipe gestures on cards do not remove keyboard or screen-reader paths.
- [ ] **R11** Respect `prefers-reduced-motion`: disable non-essential slide animations for tab and carousel transitions.

### CLI

- [ ] **R12** No new tab-based TUI; document that CLI remains stream-oriented. Optional future: `cc config get ui.mode` — out of scope unless a follow-up spec is filed.

---

## API Changes

### `GET /api/preferences/ui`

**Auth**: Required — `Authorization` bearer or session cookie as used elsewhere in the API.

**Response 200**
```json
{
  "schema_version": 1,
  "contributor_id": "contrib-uuid",
  "updated_at": "2026-03-28T12:00:00Z",
  "ui_mode": "novice",
  "ideas_list_view": "cards",
  "idea_detail_tab": "overview",
  "primary_nav_collapsed": false,
  "expert": {
    "show_ids": false,
    "show_raw_json": false,
    "show_api_links": false
  },
  "mobile": {
    "bottom_nav_enabled": true,
    "card_swipe_hints_dismissed": false
  }
}
```

**Response 401** — not authenticated.

---

### `PUT /api/preferences/ui`

**Request body** (partial update allowed; server merges by field)

```json
{
  "ui_mode": "expert",
  "ideas_list_view": "graph",
  "idea_detail_tab": "history",
  "expert": {
    "show_ids": true,
    "show_raw_json": true,
    "show_api_links": true
  }
}
```

**Validation**

| Field | Type | Allowed values |
|-------|------|----------------|
| `ui_mode` | string | `novice`, `expert` |
| `ideas_list_view` | string | `cards`, `table`, `graph` |
| `idea_detail_tab` | string | `overview`, `specs`, `tasks`, `contributors`, `edges`, `history` |
| `expert.show_*` | boolean | — |

**Response 200** — full merged object (same shape as GET).

**Response 422** — e.g. `"ui_mode must be 'novice' or 'expert'"`.

**Response 400** — body not JSON.

**Concurrency**: Last-write-wins per contributor; optional `If-Match` / ETag in a future revision.

---

## Data Model

### Persistent store (relational or JSON column)

```yaml
ContributorUIPreferences:
  contributor_id: { type: string, pk, fk contributors.id }
  schema_version: { type: integer, default: 1 }
  payload: { type: jsonb }  # full nested object matching GET response minus contributor_id/updated_at
  updated_at: { type: timestamptz }
```

### In-memory / client defaults (until login)

- `ui_mode`: `novice`
- `ideas_list_view`: `cards`
- `idea_detail_tab`: `overview`
- All `expert.*`: `false`

Client may cache GET results with `localStorage` key `cn_ui_prefs_v1` only as a **cache**, not source of truth.

---

## Web Routes and Pages

| Route | Purpose |
|-------|---------|
| `/ideas` | Ideas list with Cards / Table / Graph modes |
| `/ideas/[id]` | Idea detail with six tabs |
| `/concepts` | Concepts primary tab content |
| `/contributors` | Contributors directory |
| `/news` | News feed |
| `/tasks` | Tasks surface |

Component library: **shadcn/ui** `Tabs`, `DropdownMenu`, `Sheet` (mobile overflow), `Tooltip`, `Toggle`.

---

## Files to Create or Modify (implementation follow-up)

**API**

- `api/app/routers/preferences.py` (or extend existing profile router) — register `/api/preferences/ui`
- `api/app/models/preferences_ui.py` — Pydantic request/response models
- `api/app/services/preferences_service.py` — persistence
- `api/tests/test_preferences_ui.py` — contract tests

**Web**

- `web/app/layout.tsx` or shell component — primary tabs + secondary dropdown; responsive bottom bar
- `web/app/ideas/[id]/page.tsx` (or modular subcomponents) — tabbed detail
- `web/app/ideas/page.tsx` — view mode switcher
- Shared `web/components/ui/tabs.tsx` (shadcn) if not already present

*Exact paths may differ; implementation spec should list final paths in its Task Card.*

---

## Verification Scenarios

Each scenario is runnable by a reviewer against **production** (`https://api.coherencycoin.com`, `https://coherencycoin.com`) once shipped.

### Scenario 1 — Full create-read-update cycle for UI preferences (API)

**Setup**: Authenticated test contributor exists; token available. No prior custom UI prefs **or** known clean state documented in test data.

**Action**:

```bash
export API="https://api.coherencycoin.com"
export TOKEN="<bearer token for test contributor>"

curl -sS -X GET "$API/api/preferences/ui" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json"
```

**Expected**: HTTP **200**, JSON includes `schema_version`, `ui_mode`, `ideas_list_view`, `expert` object, `updated_at` ISO-8601 UTC.

**Then**:

```bash
curl -sS -X PUT "$API/api/preferences/ui" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ui_mode":"expert","ideas_list_view":"table","expert":{"show_ids":true,"show_raw_json":true,"show_api_links":true}}'
```

**Expected**: HTTP **200**, response reflects `ui_mode: "expert"`, `ideas_list_view: "table"`, all three `expert` flags `true`.

**Then**:

```bash
curl -sS -X GET "$API/api/preferences/ui" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: Same values as PUT (persisted read).

**Edge (bad input)**: PUT with `{"ui_mode":"guru"}` → HTTP **422**, detail mentions allowed values.

**Edge (duplicate idempotent behavior)**: Same PUT body twice in a row → HTTP **200** both times; `updated_at` second time ≥ first time.

---

### Scenario 2 — Error handling: unauthenticated and malformed body

**Setup**: No `Authorization` header.

**Action**:

```bash
curl -sS -o /dev/stderr -w "%{http_code}" -X GET "https://api.coherencycoin.com/api/preferences/ui"
```

**Expected**: HTTP **401** (not 500).

**Action**:

```bash
curl -sS -X PUT "https://api.coherencycoin.com/api/preferences/ui" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d 'not-json'
```

**Expected**: HTTP **400** or **422** with parse error (not 500).

---

### Scenario 3 — Idea detail tabs in the browser

**Setup**: At least one public idea id `IDEA_ID` visible in production.

**Action** (manual or Playwright):

1. Open `https://coherencycoin.com/ideas/IDEA_ID`
2. Locate tab list containing **Overview**, **Specs**, **Tasks**, **Contributors**, **Edges**, **History**
3. Click **History** (or keyboard: arrow keys to focus tabs then Enter)

**Expected**: URL may update hash or query `tab=history`; main panel shows History content without full-page navigation away from the idea. No single vertical page is the only way to reach History.

**Edge**: Deep-link `?tab=history` loads with History selected on first paint.

---

### Scenario 4 — Ideas list view modes

**Setup**: Logged-in user with PUT from Scenario 1 optionally setting `ideas_list_view` to `graph`.

**Action**: Open `https://coherencycoin.com/ideas?view=graph`

**Expected**: Graph layout is visible (not silently ignored). Switching to Table updates URL and, when authenticated, persists via API on next save or immediate debounced PUT (implementation choice documented in release notes).

**Edge**: Invalid `?view=foo` falls back to `cards` and does not 500.

---

### Scenario 5 — Expert mode surfaces IDs and API links

**Setup**: User sets Expert mode via UI toggle or API as in Scenario 1.

**Action**: On `ideas/IDEA_ID`, enable Expert if not already; observe page header or metadata row.

**Expected**: **Idea ID** string visible; **Raw JSON** toggle reveals JSON; **API** link targets `GET https://api.coherencycoin.com/api/ideas/IDEA_ID` (path must match OpenAPI).

**Edge**: Novice mode hides IDs again after toggle back; no stale Expert-only DOM nodes with `aria-hidden` violations.

---

## Verification (automated, development)

```bash
cd api && pytest -q api/tests/test_preferences_ui.py
cd web && npm run build
```

---

## How We Improve the Idea, Show Whether It Is Working, and Clarify Proof Over Time

1. **Instrumentation**: Client emits `ui_tab_change`, `ui_view_mode_change`, and `ui_mode_toggle` analytics events (privacy-preserving, no PII) with `schema_version` — allows dashboards to show adoption of tabs vs scroll-fallback.
2. **API truth**: `GET /api/preferences/ui` includes `schema_version` and `updated_at` so support and CI can assert the deployment matches the spec version.
3. **Release health**: After deploy, smoke test Scenario 1–2 in CI against staging; production checklist runs Scenario 3 manually weekly until E2E stable.
4. **User-visible “proof”**: Expert mode shows API URLs that return live JSON — reviewers can click and compare to UI; Novice mode shows human summaries only, reducing confusion.
5. **Iteration**: Follow-up specs can add `ETag`, optimistic locking, and A/B labels for tooltip copy without breaking `schema_version: 1` clients.

---

## Risks and Assumptions

- **Risk**: Tab explosion on small screens — **Mitigation**: bottom bar limits to five items; “News” may roll into “More” on the smallest breakpoints while preserving route.
- **Risk**: Graph view mode is heavy — **Mitigation**: lazy-load graph bundle; show skeleton in tab/view mode until data arrives.
- **Assumption**: Contributors authenticate with the same identity model as existing portfolio endpoints — if not, preferences must be keyed by auth subject as implemented in `contributors` table.
- **Assumption**: shadcn `Tabs` are already approved in the repo; if not, add dependency in web package with lockfile update in implementation PR.

---

## Known Gaps and Follow-up Tasks

- ETag / optimistic concurrency for `PUT /api/preferences/ui`.
- Federated instances: whether preferences replicate — needs decision.
- Playwright E2E for Scenario 3–5 in CI once stable selectors exist.

---

## Out of Scope (this spec)

- Changing OpenAPI definitions for ideas/concepts beyond preferences.
- Telegram or email notifications for preference changes.

---

## Task Card (implementation handoff)

```yaml
goal: Ship tabbed idea detail and list view modes with novice/expert UI and persisted GET/PUT /api/preferences/ui.
files_allowed:
  - api/app/routers/preferences.py
  - api/app/models/preferences_ui.py
  - api/app/services/preferences_service.py
  - api/tests/test_preferences_ui.py
  - web/app/ideas/[id]/page.tsx
  - web/app/ideas/page.tsx
  - web/components/layout/app-shell.tsx
done_when:
  - pytest api/tests/test_preferences_ui.py passes
  - npm run build succeeds for web
  - Manual Scenario 3 passes on staging
commands:
  - cd api && pytest -q tests/test_preferences_ui.py
  - cd web && npm run build
constraints:
  - Use shadcn/ui Tabs; no mock stores in API tests — use real store or test DB per project norms
```

---

## Failure/Retry Reflection

- **Failure mode**: Contributors open many tabs quickly; race on PUT.  
- **Blind spot**: Without ETag, last write wins may feel random.  
- **Next action**: Ship MVP with debounced client PUT; add ETag if user reports clobbering.

---

## Research Inputs (Required)

- `2024` - [WAI-ARIA APG — Tabs Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) — keyboard and accessibility baseline for tabbed interfaces.
- `2024` - [shadcn/ui Tabs](https://ui.shadcn.com/docs/components/tabs) — implementation alignment for Next.js + Radix.

---

## Acceptance Criteria (summary)

| ID | Criterion |
|----|-----------|
| AC1 | Idea detail uses six named tabs; content is partitioned per tab |
| AC2 | Ideas list supports Cards, Table, Graph; preference persists via API when logged in |
| AC3 | Global nav uses primary tabs + secondary dropdown; mobile uses bottom bar |
| AC4 | Novice/Expert behaviors match Requirements R5–R7 |
| AC5 | GET/PUT `/api/preferences/ui` behave as in Verification Scenarios 1–2 |
| AC6 | Verification Scenarios 3–5 pass on staging/production after implementation |
