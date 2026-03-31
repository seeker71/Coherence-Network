# UX Overhaul — Tabs, Mobile-First, Novice & Expert Modes

**Spec ID**: task_49cf0e397bb53ef0
**Status**: Approved
**Type**: Feature
**Created**: 2026-03-28
**Author**: product-manager agent

---

## Summary

Replace the current long-scrolling page layout with a tabbed, mobile-first UX that adapts to two personas:

- **Novice mode** (default): plain vocabulary, guided tooltips, no technical fields
- **Expert mode**: IDs visible, raw JSON toggle, API endpoint links

Preferences are persisted per-contributor via `GET/PUT/PATCH /api/preferences/ui`. The web implementation uses the existing `shadcn/ui` `Tabs` component.

---

## Goal

Every content-heavy page becomes navigable via tabs instead of requiring the user to scroll through sections they don't need. The app becomes genuinely usable on a phone. New users see a friendly surface; power users can flip a switch to expose raw data.

Measured success: the idea-detail page reduces median scroll depth by ≥50% (tracked via analytics). Mobile session length increases. Zero new user support requests about "what does this field mean?"

---

## Motivation & Context

### Current problems

1. `/ideas/[idea_id]` renders 10+ stacked sections — plans, tasks, files, people, questions, raw records — in one continuous scroll. On mobile this is unusable.
2. The ideas list has only one view. Power users want a dense table; explorers want a graph.
3. There is no vocabulary layer: terms like `free_energy_score`, `manifestation_status`, `value_gap` are shown verbatim.
4. `ui_preferences.py` already exists (in-memory store) and models all needed preference fields. It is not wired into any web page yet.
5. Top navigation is a flat list of links with no hierarchy or mobile affordance.

### Design constraints

- `shadcn/ui` is already installed (`components.json` present). Use the existing `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` primitives.
- The API preference store must be promoted from in-memory to PostgreSQL so preferences survive restarts.
- No new external dependencies are permitted.

---

## Scope

### In scope

- Idea detail page → tabbed layout
- Ideas list → view-mode switcher (Cards / Table / Graph)
- Primary navigation → tabs with secondary dropdown
- Mobile → bottom tab bar, swipeable card deck, collapsible sections
- Expert mode → IDs, raw JSON toggle, API links
- Novice mode → friendly labels, tooltip overlay, hide technical fields
- API → promote `ui_preferences` store to PostgreSQL
- API → database persistence for preferences

### Out of scope

- Redesigning individual components (cards, forms) beyond the vocabulary/tooltip layer
- Introducing a new CSS framework or replacing Tailwind
- Changes to CLI (`cc` commands are already tab-free by design)
- Analytics implementation beyond wiring an existing tracker

---

## Requirements

### R1 — Idea Detail: Tabbed Layout

The idea detail page (`/ideas/[idea_id]`) MUST render its content sections as shadcn/ui `Tabs` with the following tab sequence:

| Tab | Slug | Content |
|-----|------|---------|
| Overview | `overview` | Scores panel, description, progress editor, stake/investment |
| Specs | `specs` | Linked spec IDs; create-spec form |
| Tasks | `tasks` | Linked task IDs; quick-create task form |
| Contributors | `contributors` | People who touched this idea, attribution counts |
| Edges | `edges` | Graph edges to/from this node; relationship visualisation |
| History | `history` | Activity timeline (chronological events) |

- Default active tab: `overview`
- The active tab is persisted in the user's UI preferences (`idea_detail_tab` field)
- Switching tabs updates the `idea_detail_tab` preference via `PATCH /api/preferences/ui`
- Deep-linking via hash or query param (`?tab=tasks`) sets the initial active tab

**Expert-only content inside tabs**:
- Idea ID badge visible next to the title
- "Raw JSON" accordion toggle in Overview showing the full API response
- Direct API links (idea, flow, runtime, lineage) moved inside a dedicated "API Links" sub-section in the Overview tab (hidden in novice mode)

### R2 — Ideas List: View Mode Switcher

The ideas list (`/ideas`) MUST expose three view modes via a toggle group:

| Mode | Icon | Description |
|------|------|-------------|
| Cards | grid icon | Default card grid (current layout) |
| Table | table icon | Dense sortable table (id, name, status, value gap, confidence, energy) |
| Graph | graph icon | Force-directed mini-graph linking related ideas |

- Default mode: `cards`
- Active mode is persisted in `ideas_view` preference
- Switching mode updates the preference via `PATCH /api/preferences/ui`
- Table mode: sortable by `value_gap` and `free_energy_score`; columns use friendly labels in novice mode, raw field names in expert mode
- Graph mode: a static/server-rendered graph is acceptable for v1; interactive is v2

### R3 — Navigation: Primary Tabs + Secondary Dropdown

Top-level navigation MUST be restructured:

**Primary tabs** (always visible on desktop):
1. Ideas
2. Concepts
3. Contributors
4. News
5. Tasks

**Secondary dropdown** (collapsed under "More" on desktop, behind a hamburger/menu on mobile):
- Graph
- Specs
- Pipeline
- Treasury
- Contribute

On mobile (`< 768px`), primary navigation renders as a **bottom tab bar** with icons and labels for the 5 primary tabs. The "More" item opens a bottom sheet.

### R4 — Mobile UX

- Bottom tab bar (`fixed bottom-0`) for primary navigation on mobile
- Swipeable card deck on ideas list when `swipeable_cards: true` (opt-in via preferences)
- Long content sections in tab bodies can be collapsed via a "Show less / Show more" toggle when `collapsible_sections: true` (default `true`)
- Touch targets ≥ 44×44 px on all interactive elements
- No horizontal overflow on any page at 375 px viewport width

### R5 — Expert Mode

When `expert_mode: true`:

- Idea IDs, task IDs, spec IDs, contributor IDs rendered inline in small `<code>` badges
- "Raw JSON" toggle available on any detail page
- All API endpoint links visible (currently hidden in "Raw Records" section)
- Column headers in Table view use API field names (`free_energy_score`, not "Priority score")
- `PATCH /api/preferences/ui?contributor_id=<id>` body: `{"expert_mode": true}` activates expert mode
- A persistent `[Expert]` chip in the header/nav indicates the mode is active

### R6 — Novice Mode (default)

When `expert_mode: false` (default):

- IDs never shown in UI
- Technical fields (`free_energy_score`, `resistance_risk`, `manifestation_status`) displayed with friendly labels from a translation map (see Data Model below)
- Guided tooltip on hover/focus for every labelled metric (implemented via shadcn/ui `Tooltip`)
- "Raw Records" section and API links hidden entirely
- `show_tooltips: true` enables the tooltip overlay (can be toggled off without enabling expert mode)

### R7 — UI Preferences API: PostgreSQL Persistence

The existing `ui_preferences.py` router uses an in-memory `_STORE` dict. This MUST be promoted to PostgreSQL.

**Table**: `ui_preferences`

| Column | Type | Constraints |
|--------|------|-------------|
| contributor_id | TEXT | PRIMARY KEY |
| expert_mode | BOOLEAN | NOT NULL DEFAULT false |
| nav_layout | TEXT | NOT NULL DEFAULT 'top' |
| ideas_view | TEXT | NOT NULL DEFAULT 'cards' |
| idea_detail_tab | TEXT | NOT NULL DEFAULT 'overview' |
| swipeable_cards | BOOLEAN | NOT NULL DEFAULT false |
| collapsible_sections | BOOLEAN | NOT NULL DEFAULT true |
| show_tooltips | BOOLEAN | NOT NULL DEFAULT true |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

- `GET /api/preferences/ui?contributor_id=<id>` — returns preferences or defaults
- `PUT /api/preferences/ui` — full replace (body: `UIPreferences`)
- `PATCH /api/preferences/ui?contributor_id=<id>` — partial update
- `DELETE /api/preferences/ui?contributor_id=<id>` — reset to defaults (204)
- Anonymous / unauthenticated users default to `contributor_id = "anonymous"`

---

## Data Model

### Vocabulary Translation Map (novice ↔ expert)

| API field | Novice label | Tooltip |
|-----------|-------------|---------|
| `free_energy_score` | Priority score | Higher means there's more value available with less effort right now |
| `manifestation_status` | Proof level | How much real-world evidence exists that this idea is working |
| `value_gap` | Value still available | How much potential value hasn't been captured yet |
| `resistance_risk` | Difficulty | How hard this is likely to be to move forward |
| `confidence` | How sure we are | Our certainty that the potential value estimate is correct |
| `potential_value` | Full potential | Total value if this idea is fully realised |
| `actual_value` | Value so far | Value that has already been measured or confirmed |
| `estimated_cost` | Expected effort | Estimated resource cost to implement |
| `actual_cost` | Effort spent | Resources actually spent so far |

### UIPreferences Pydantic model (current, no change)

```python
class UIPreferences(BaseModel):
    contributor_id: str
    expert_mode: bool = False
    nav_layout: Literal["top", "bottom_bar"] = "top"
    ideas_view: Literal["cards", "table", "graph"] = "cards"
    idea_detail_tab: Literal["overview","specs","tasks","contributors","edges","history"] = "overview"
    swipeable_cards: bool = False
    collapsible_sections: bool = True
    show_tooltips: bool = True
```

---

## API Changes

### Endpoints (existing, behaviour changed)

| Method | Path | Change |
|--------|------|--------|
| GET | `/api/preferences/ui` | Reads from PostgreSQL instead of in-memory dict |
| PUT | `/api/preferences/ui` | Writes to PostgreSQL; returns 422 if `contributor_id` empty |
| PATCH | `/api/preferences/ui` | Partial update in PostgreSQL; `updated_at` refreshed |
| DELETE | `/api/preferences/ui` | Deletes DB row; next GET returns defaults |

### No new endpoints. All changes are to the storage backend.

---

## Web Changes

### Files to create or modify

| File | Change |
|------|--------|
| `web/app/ideas/[idea_id]/page.tsx` | Wrap content sections in `<Tabs>` / `<TabsContent>` |
| `web/app/ideas/page.tsx` | Add view-mode switcher (`ToggleGroup`) |
| `web/components/layout/PrimaryNav.tsx` | New: primary tabs + secondary dropdown + mobile bottom bar |
| `web/components/ideas/IdeaDetailTabs.tsx` | New: client component managing tab state + preference sync |
| `web/components/ui/ExpertModeBadge.tsx` | New: `[Expert]` chip shown in nav when expert mode active |
| `web/components/ui/NoviceTooltip.tsx` | New: wrapper that shows tooltip in novice mode |
| `web/lib/ui-preferences.ts` | New: client-side helper to GET/PATCH preferences |
| `web/app/layout.tsx` | Wire in `PrimaryNav` replacing existing nav |

### shadcn/ui components required

All are already available via `components.json`:
- `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`
- `Tooltip`, `TooltipTrigger`, `TooltipContent`, `TooltipProvider`
- `ToggleGroup`, `ToggleGroupItem`
- `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem`
- `Sheet`, `SheetTrigger`, `SheetContent` (mobile bottom sheet for "More" nav)

---

## Implementation Phases

### Phase 1 — API persistence (unblocks all web work)

1. Write Alembic migration adding `ui_preferences` table
2. Update `ui_preferences.py` to use `AsyncSession` / SQLAlchemy instead of `_STORE`
3. Tests: `tests/test_ui_preferences.py` — CRUD + defaults

### Phase 2 — Idea Detail Tabs

1. Build `IdeaDetailTabs.tsx` client component
2. Refactor `/ideas/[idea_id]/page.tsx` to pass data to tabs
3. Tests: Vitest snapshot + interaction test for tab switching

### Phase 3 — Ideas List View Modes

1. Add `ToggleGroup` to `/ideas/page.tsx`
2. Implement Table view component
3. Implement static Graph view (via `recharts` or `d3`, already in deps)

### Phase 4 — Navigation Restructure

1. Build `PrimaryNav.tsx` with desktop tabs + mobile bottom bar
2. Replace existing nav in `layout.tsx`
3. Visual regression test at 375px, 768px, 1280px

### Phase 5 — Novice / Expert Mode

1. Build `NoviceTooltip.tsx` and `ExpertModeBadge.tsx`
2. Apply vocabulary translation map to ideas list and idea detail
3. Wire expert-mode preference into NoviceTooltip visibility
4. E2E test: toggle expert mode, verify IDs appear/disappear

---

## Verification Scenarios

### VS-1: Preferences CRUD cycle (API)

**Setup**: No preferences stored for `test-user-42`

**Action**:
```bash
API=https://api.coherencycoin.com

# Read defaults
curl -s "$API/api/preferences/ui?contributor_id=test-user-42"
```

**Expected result**: HTTP 200, body:
```json
{
  "contributor_id": "test-user-42",
  "expert_mode": false,
  "nav_layout": "top",
  "ideas_view": "cards",
  "idea_detail_tab": "overview",
  "swipeable_cards": false,
  "collapsible_sections": true,
  "show_tooltips": true
}
```

**Then** — PUT full replace:
```bash
curl -s -X PUT "$API/api/preferences/ui" \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"test-user-42","expert_mode":true,"nav_layout":"bottom_bar","ideas_view":"table","idea_detail_tab":"tasks","swipeable_cards":false,"collapsible_sections":true,"show_tooltips":false}'
```

**Expected**: HTTP 200, body reflects the new values exactly.

**Then** — GET confirms persistence:
```bash
curl -s "$API/api/preferences/ui?contributor_id=test-user-42"
```
**Expected**: same values returned (not defaults), confirming DB write survived.

**Then** — DELETE resets:
```bash
curl -s -X DELETE "$API/api/preferences/ui?contributor_id=test-user-42"
```
**Expected**: HTTP 204 (no body).

**Edge** — GET after DELETE returns defaults again (not 404):
```bash
curl -s "$API/api/preferences/ui?contributor_id=test-user-42"
```
**Expected**: HTTP 200, `expert_mode: false`, `ideas_view: "cards"`.

---

### VS-2: PATCH partial update (API)

**Setup**: Preferences exist for `partial-update-user` with `expert_mode: false, ideas_view: "cards"`

**Action**:
```bash
curl -s -X PATCH "$API/api/preferences/ui?contributor_id=partial-update-user" \
  -H "Content-Type: application/json" \
  -d '{"ideas_view": "table"}'
```

**Expected**: HTTP 200, `ideas_view: "table"`, `expert_mode: false` (unchanged).

**Edge** — PATCH with empty `contributor_id` query param:
```bash
curl -s -X PATCH "$API/api/preferences/ui?contributor_id=" \
  -H "Content-Type: application/json" \
  -d '{"ideas_view":"table"}'
```
**Expected**: HTTP 422 with detail `"contributor_id query param is required"`.

**Edge** — PATCH with invalid `ideas_view` value:
```bash
curl -s -X PATCH "$API/api/preferences/ui?contributor_id=partial-update-user" \
  -H "Content-Type: application/json" \
  -d '{"ideas_view": "invalid-value"}'
```
**Expected**: HTTP 422 validation error.

---

### VS-3: Idea Detail Tabs render (Web)

**Setup**: At least one idea exists in the system (any ID from `GET /api/ideas`)

**Action**: Navigate browser to `https://coherencycoin.com/ideas/<any-idea-id>`

**Expected**:
- Page renders 6 tabs: **Overview**, **Specs**, **Tasks**, **Contributors**, **Edges**, **History**
- Default active tab is **Overview**
- Clicking **Tasks** makes Tasks content visible; Overview content is hidden
- Page title visible above tabs
- No horizontal scroll at 375px width

**Expert mode variation**:
- Navigate to `https://coherencycoin.com/ideas/<any-idea-id>?tab=tasks`
- Expected: Tasks tab is active on load (deep-link respected)

**Edge** — Non-existent idea:
- Navigate to `https://coherencycoin.com/ideas/does-not-exist-xyz`
- Expected: 404 page (not a crash)

---

### VS-4: Ideas List View Mode Switcher (Web)

**Setup**: At least 3 ideas exist

**Action**: Navigate to `https://coherencycoin.com/ideas`, click the **Table** view icon

**Expected**:
- View switches from cards to a table with columns: Name, Proof level, Value available, Priority, Confidence
- In novice mode, column headers use friendly names (not raw field names)
- Toggling to **Cards** switches back
- Selected view mode persists: reload the page, Table mode is still selected

**Expert mode variation**:
- Enable expert mode (`PATCH /api/preferences/ui?contributor_id=<id>` with `expert_mode: true`)
- Reload `/ideas`
- **Expected**: Table column headers show raw API field names (`free_energy_score`, `value_gap`, etc.) and idea ID badges are visible on each row

**Edge** — Graph view with zero ideas: renders an empty graph placeholder, not an error.

---

### VS-5: Novice / Expert Mode Toggle (Web + API)

**Setup**: Logged-in contributor with `contributor_id = "ux-test-user"`

**Action sequence**:

1. `GET /api/preferences/ui?contributor_id=ux-test-user` → confirm `expert_mode: false`
2. On `/ideas`, verify the ID badge is absent on any idea card
3. `PATCH /api/preferences/ui?contributor_id=ux-test-user` with `{"expert_mode": true}`
4. Reload `/ideas`

**Expected after step 4**:
- `[Expert]` chip visible in the top navigation bar
- Each idea card shows the idea ID in a small `<code>` badge
- The metric label "Priority score" is replaced with `free_energy_score`

**Reverse** — PATCH back to `expert_mode: false`:
- Reload page
- `[Expert]` chip disappears
- IDs hidden again
- Friendly labels restored

**Edge** — `expert_mode: true` + `show_tooltips: false`: tooltips disabled and no IDs shown (confirm tooltips are a separate control from expert mode).

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| In-memory `_STORE` preferences lost on API restart (current behaviour) | Certain | Phase 1 migration to PostgreSQL fixes this |
| shadcn/ui `Tabs` not yet installed in web project | Low | `components.json` present; run `npx shadcn@latest add tabs` if missing |
| Deep-linking via `?tab=` conflicts with Next.js `searchParams` | Medium | Use `useSearchParams` hook in client component; fallback to `idea_detail_tab` preference |
| Mobile bottom bar overlaps page content on short screens | Medium | Add `pb-16` padding to main content when `nav_layout: bottom_bar` |
| Anonymous users sharing preferences (`contributor_id = "anonymous"`) | Medium | Phase 2: derive contributor_id from session/cookie; for now anonymous is a single shared bucket |
| Graph view (ideas list) requires a graph library | Medium | Use `recharts` (already in package.json); static layout acceptable for v1 |
| PostgreSQL migration breaks existing in-memory tests | Low | Use `pytest.mark.db` to isolate; existing unit tests mock the router's `_STORE` directly |

---

## Known Gaps and Follow-up Tasks

- **Anonymous identity**: `contributor_id = "anonymous"` is a shared bucket. A session-derived ID (cookie or auth token) is needed for per-user persistence in a multi-user context. Filed as a separate idea.
- **Graph view (ideas list)**: v1 is static (server-rendered). Interactive force-directed graph requires a dedicated `d3`/`vis.js` client component and is deferred to v2.
- **Keyboard navigation**: Tab panel focus management and `aria-` attributes should be audited after implementation. Filed as a follow-up accessibility task.
- **Analytics**: Measuring scroll-depth reduction requires an analytics event. The hook point (`onTabChange`) is defined but the analytics sink is not specified here.
- **Swipeable card deck**: `swipeable_cards: true` preference exists in the API but the gesture handler (`react-swipeable` or equivalent) is not yet installed. Confirm package before implementing.
- **Proof of "working"**: This spec itself is evidence the feature is specced. Proof of working is measured by VS-3/VS-4/VS-5 passing against production. The open question — "how do we show the spec is working over time?" — is answered by the preference persistence test (VS-1): if preferences survive a pod restart, the DB layer is live.
