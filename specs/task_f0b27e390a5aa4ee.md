# Spec — UX Overhaul: Tabs, Mobile-First, Novice/Expert Modes (Task `task_f0b27e390a5aa4ee`)

**Task ID**: `task_f0b27e390a5aa4ee`
**Idea ID**: `idea-fecc6d087c4e`
**Spec number**: 192 (next in sequence)
**Status**: specification (product contract)
**Date**: 2026-03-28
**Author**: product-manager agent

---

## Summary

The Coherence Network web UI currently uses long-scrolling pages that become unwieldy on mobile and for users who want to jump to a specific section. This spec defines a **complete UX overhaul** that introduces:

1. **Tab-based navigation** at the page level — every detail page uses tabs, not scrolling walls of content.
2. **Mobile-first layout** — bottom tab bar, swipeable cards, collapsible sections work first on a 375 px viewport.
3. **Novice / Expert mode** — a persistent UI preference toggle that hides or reveals technical fields, IDs, raw JSON, and API links.
4. **Per-contributor UI preferences API** — `GET/PUT /api/preferences/ui` stores mode selection server-side so it follows the user across devices.
5. **Three view modes on the Ideas list** — Cards (default), Table, Graph.

The spec is the **payable verification contract**. Implementation maps to `web/`, `api/app/routers/`, and `api/app/models/`. The CLI is not affected by this change (it is already tab-free by nature).

---

## Open Question: How Can We Prove This Is Working Over Time?

**Problem**: UX improvements are subjective and hard to measure.

**Approach (three signals)**:

1. **UI mode adoption metric** (`GET /api/preferences/ui/stats`) — returns aggregate counts of `{ novice: N, expert: M }` mode selections across all contributors. Growing `expert` share proves power users are finding and using the toggle. Growing `novice` share proves onboarding is reaching new users.
2. **Tab interaction event** (future) — each tab activation fires `POST /api/ideas/{id}/events` with `event_type: "tab_view"` and `tab_name`. A dashboard can then show which tabs receive the most attention, revealing under-valued sections.
3. **Preference persistence test** — the review scenario in section §9 proves that a preference set via API is respected across sessions. A test that sets `novice` mode via API and then checks that the web page (SSR) hides expert fields is the concrete proof.

The **ROI signal**: if `GET /api/preferences/ui/stats` shows a non-zero `total_preferences_set` count after 7 days of production traffic, the system is alive. If the tab-view events accumulate, the sections are being reached.

---

## Background

As of 2026-03-28 the web UI renders idea detail as a single page scroll and the Ideas list as a flat card list. There is no mobile bottom navigation bar, no novice/expert toggle, and no per-contributor preference store. The shadcn/ui component library is already installed in `web/`.

---

## Requirements

### Functional

#### F1 — Idea Detail Page Tabs

The idea detail page (`/ideas/{idea_id}`) MUST render the following tabs in order:

| Tab | Content |
|-----|---------|
| **Overview** | Title, summary, coherence score, concept edges, created date |
| **Specs** | Linked spec documents, spec status badges |
| **Tasks** | Task list with status, assigned contributor, CC reward |
| **Contributors** | Contributor avatars, CC attribution, contribution type |
| **Edges** | Graph edges to related ideas and concepts (table view) |
| **History** | Audit log — creation, updates, status changes, task events |

- Default tab on first visit: **Overview**.
- Active tab MUST be reflected in the URL as a query parameter: `/ideas/{idea_id}?tab=tasks`.
- Navigating back/forward in browser MUST restore the correct tab.
- On mobile (≤ 768 px), tabs MUST scroll horizontally if they overflow, with a fading edge indicator.

#### F2 — Ideas List View Modes

The Ideas list page (`/ideas`) MUST offer three view mode selectors rendered as a toggle group:

| Mode | Description |
|------|-------------|
| **Cards** | Default grid of idea cards with score badge, title, summary |
| **Table** | Sortable, filterable data table (ID, title, score, status, date) |
| **Graph** | Force-directed graph of ideas and concept edges (D3 or Cytoscape, follow-up for full implementation; MVP shows placeholder with "Graph view coming soon") |

- Selected view mode is stored in `localStorage` AND in server-side preferences if authenticated.
- View mode changes MUST not cause a full page reload.

#### F3 — Mobile Layout

- **Bottom tab bar** (fixed, 56 px): Primary navigation items — Ideas, Concepts, Contributors, News, Tasks.
- **Top bar**: Logo + page title only. Secondary actions (search, filter) move to an inline bar below the title on scroll.
- **Swipeable cards**: On the Ideas list (Cards mode), horizontal swipe on a card reveals quick-action buttons (Stake, View Detail, Share).
- **Collapsible sections**: On detail pages, sections not rendered as tabs (e.g., sidebar metadata) MUST be collapsible accordions on mobile.
- Viewport breakpoints: mobile ≤ 768 px, tablet 769–1024 px, desktop ≥ 1025 px.

#### F4 — Navigation Structure

**Desktop (≥ 1025 px)**:
- Top navigation bar with primary tabs: **Ideas | Concepts | Contributors | News | Tasks**.
- Each primary tab MAY have a secondary dropdown for sub-pages (e.g., Ideas → My Ideas, Trending, Backlog).

**Mobile (≤ 768 px)**:
- Bottom tab bar replaces the top nav for primary navigation.
- Top bar retains Logo + page title + hamburger for secondary nav (Settings, My Profile, Expert Mode toggle).

#### F5 — Novice Mode

When `ui_mode = "novice"`:
- Hide all fields labeled as `technical` in the display schema (ID strings, `source_hash`, `spec_ref`, raw JSON toggle, API link chips).
- Show guided tooltips on hover/tap for terms: *Coherence Score*, *CC*, *Lens*, *Edge*, *Contributor*.
- Replace ID references with display names wherever possible (e.g., show contributor name, not `contributor_id`).
- Simplify labels: "Coherence Score" → "How aligned is this idea?", "Edges" tab → "Related Ideas".
- Show an onboarding banner on first visit explaining the three core concepts (Ideas, Contributors, CC).

#### F6 — Expert Mode

When `ui_mode = "expert"`:
- Show all ID fields inline.
- Show a **Raw JSON** toggle on idea detail (Overview tab) that renders the full API response in a code block.
- Show **API Link** chips next to resource names (e.g., `GET /api/ideas/{id}` clickable badge).
- Show spec_ref, source_hash, task_id fields in task and idea cards.
- Show the **UI Preferences** API endpoint in the settings panel.

#### F7 — Preferences API

New endpoints (see §6 for schema):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/preferences/ui` | Get current contributor's UI preferences |
| `PUT` | `/api/preferences/ui` | Upsert contributor's UI preferences |
| `GET` | `/api/preferences/ui/stats` | Aggregate mode counts (public, no auth required) |

- Authentication via `X-API-Key` header.
- Unauthenticated reads fall back to `localStorage` on the client.
- PUT is idempotent: calling it twice with the same body returns 200 both times.

#### F8 — shadcn/ui Implementation

- **Tabs component**: use `@/components/ui/tabs` (shadcn Tabs, TabsList, TabsTrigger, TabsContent).
- **Toggle Group**: use `@/components/ui/toggle-group` for view mode selector.
- **Accordion**: use `@/components/ui/accordion` for mobile collapsible sections.
- **Tooltip**: use `@/components/ui/tooltip` for novice mode guided tooltips.
- **Navigation Menu**: use `@/components/ui/navigation-menu` for desktop top nav with secondary dropdowns.

### Non-Functional

- **Performance**: Tab switching MUST be < 100 ms (client-side only, no extra network request unless tab content is lazy-loaded).
- **Accessibility**: All tabs MUST have `aria-label`, be keyboard-navigable (arrow keys), and announce tab changes to screen readers.
- **SSR**: Preferred tab MUST be readable from URL query params on server render so deep links work without hydration flash.
- **Progressive enhancement**: If JS fails, the first tab's content MUST still be visible (no blank page).
- **Persistence**: UI mode preference MUST survive page refresh. Server-side preference wins over localStorage when authenticated.

---

## API Changes

### New Router: `api/app/routers/preferences.py`

```python
# Endpoints:
GET  /api/preferences/ui         -> UIPreferences (auth required)
PUT  /api/preferences/ui         -> UIPreferences (auth required)
GET  /api/preferences/ui/stats   -> UIPreferencesStats (no auth)
```

### Existing Router Changes

No existing routers are modified. The preferences router is registered in `api/app/main.py`.

---

## Data Model

### `api/app/models/ui_preferences.py`

```python
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

UIMode = Literal["novice", "expert"]
IdeasViewMode = Literal["cards", "table", "graph"]

class UIPreferences(BaseModel):
    contributor_id: str
    ui_mode: UIMode = "novice"
    ideas_view_mode: IdeasViewMode = "cards"
    last_updated: datetime

class UIPreferencesUpdate(BaseModel):
    ui_mode: Optional[UIMode] = None
    ideas_view_mode: Optional[IdeasViewMode] = None

class UIPreferencesStats(BaseModel):
    total_preferences_set: int
    novice_count: int
    expert_count: int
    cards_count: int
    table_count: int
    graph_count: int
    as_of: datetime
```

### PostgreSQL Table

```sql
CREATE TABLE IF NOT EXISTS ui_preferences (
    contributor_id TEXT PRIMARY KEY,
    ui_mode        TEXT NOT NULL DEFAULT 'novice'
                   CHECK (ui_mode IN ('novice', 'expert')),
    ideas_view_mode TEXT NOT NULL DEFAULT 'cards'
                   CHECK (ideas_view_mode IN ('cards', 'table', 'graph')),
    last_updated   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Web Components

### New / Modified Files

| File | Change |
|------|--------|
| `web/app/ideas/[idea_id]/page.tsx` | Replace scroll layout with `<Tabs>` wrapping Overview, Specs, Tasks, Contributors, Edges, History |
| `web/app/ideas/page.tsx` | Add view-mode `<ToggleGroup>` (Cards / Table / Graph) |
| `web/components/ideas/IdeaLensPanel.tsx` | Existing — keep, integrate into Overview tab |
| `web/components/layout/BottomTabBar.tsx` | **New** — mobile bottom navigation |
| `web/components/layout/TopNav.tsx` | **New** — desktop top nav with NavigationMenu and dropdown |
| `web/components/ui/ExpertModeToggle.tsx` | **New** — toggle switch stored in preferences |
| `web/components/ui/NoviceTooltip.tsx` | **New** — guided tooltip wrapper for novice mode |
| `web/hooks/useUIPreferences.ts` | **New** — hook that reads from API + localStorage fallback |
| `web/lib/preferences.ts` | **New** — client functions for `GET/PUT /api/preferences/ui` |
| `web/components/ideas/IdeaTable.tsx` | **New** — sortable table for Ideas list Table mode |

### Tab URL Synchronization

```typescript
// /ideas/[idea_id]/page.tsx
const searchParams = useSearchParams();
const defaultTab = searchParams.get('tab') ?? 'overview';

// On tab change:
router.replace(`/ideas/${idea_id}?tab=${tabValue}`, { scroll: false });
```

### Mobile Bottom Tab Bar

```tsx
// BottomTabBar.tsx — renders only when viewport width ≤ 768px
const navItems = [
  { label: 'Ideas',        href: '/ideas',        icon: <LightbulbIcon /> },
  { label: 'Concepts',     href: '/concepts',     icon: <NetworkIcon /> },
  { label: 'Contributors', href: '/contributors', icon: <UsersIcon /> },
  { label: 'News',         href: '/news',         icon: <NewspaperIcon /> },
  { label: 'Tasks',        href: '/tasks',        icon: <CheckSquareIcon /> },
];
```

---

## Affected Files (Full List)

### API

- `api/app/models/ui_preferences.py` — **new** (data model)
- `api/app/routers/preferences.py` — **new** (router)
- `api/app/services/preferences_service.py` — **new** (business logic)
- `api/app/main.py` — **modified** (register preferences router)

### Web

- `web/app/ideas/[idea_id]/page.tsx` — **modified** (tabs)
- `web/app/ideas/page.tsx` — **modified** (view mode toggle)
- `web/components/layout/BottomTabBar.tsx` — **new**
- `web/components/layout/TopNav.tsx` — **new**
- `web/components/ui/ExpertModeToggle.tsx` — **new**
- `web/components/ui/NoviceTooltip.tsx` — **new**
- `web/hooks/useUIPreferences.ts` — **new**
- `web/lib/preferences.ts` — **new**
- `web/components/ideas/IdeaTable.tsx` — **new**

### Tests

- `api/tests/test_preferences.py` — **new** (pytest coverage for preferences endpoints)

---

## Verification Scenarios

These scenarios are runnable against production at `https://api.coherencycoin.com`. Replace `$API` with that base URL. Replace `$KEY` with a valid contributor API key.

---

### Scenario 1 — Create and Read UI Preferences (Create-Read-Update cycle)

**Setup**: Contributor has a valid API key. No preferences row exists yet.

**Action (Create)**:
```bash
curl -s -X PUT $API/api/preferences/ui \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"ui_mode": "expert", "ideas_view_mode": "table"}'
```

**Expected**: HTTP 200, response body:
```json
{
  "contributor_id": "<contributor-id>",
  "ui_mode": "expert",
  "ideas_view_mode": "table",
  "last_updated": "<ISO 8601 timestamp>"
}
```

**Action (Read)**:
```bash
curl -s $API/api/preferences/ui -H "X-API-Key: $KEY"
```

**Expected**: HTTP 200, same body as above — `ui_mode` is `"expert"`, `ideas_view_mode` is `"table"`.

**Action (Update)**:
```bash
curl -s -X PUT $API/api/preferences/ui \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"ui_mode": "novice"}'
```

**Expected**: HTTP 200, `ui_mode` is now `"novice"`, `ideas_view_mode` unchanged (`"table"`).

**Edge — Idempotency**: Calling PUT twice with `{"ui_mode": "novice"}` returns HTTP 200 both times; no duplicate row is created; `last_updated` is refreshed.

---

### Scenario 2 — Stats Endpoint (No Auth Required)

**Setup**: At least one contributor has set preferences (from Scenario 1).

**Action**:
```bash
curl -s $API/api/preferences/ui/stats
```

**Expected**: HTTP 200, response body:
```json
{
  "total_preferences_set": 1,
  "novice_count": 1,
  "expert_count": 0,
  "cards_count": 0,
  "table_count": 1,
  "graph_count": 0,
  "as_of": "<ISO 8601 timestamp>"
}
```

Counts reflect stored rows. As additional contributors set preferences, `total_preferences_set` increases monotonically.

**Edge**: `GET /api/preferences/ui/stats` with no API key still returns HTTP 200 (public endpoint). Including an invalid API key also returns 200 (stats are public; auth is not checked for stats).

---

### Scenario 3 — Error Handling: Bad Input and Missing Auth

**Action (invalid ui_mode value)**:
```bash
curl -s -X PUT $API/api/preferences/ui \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"ui_mode": "super-ultra-expert"}'
```

**Expected**: HTTP 422, response body contains `"loc": ["body", "ui_mode"]` and a message indicating the value is not one of `["novice", "expert"]`.

**Action (missing API key on GET)**:
```bash
curl -s $API/api/preferences/ui
```

**Expected**: HTTP 401 or HTTP 403 — NOT 200, NOT 500. Response body indicates authentication is required.

**Action (missing API key on PUT)**:
```bash
curl -s -X PUT $API/api/preferences/ui \
  -H "Content-Type: application/json" \
  -d '{"ui_mode": "expert"}'
```

**Expected**: HTTP 401 or HTTP 403 — preferences are NOT written for anonymous callers.

---

### Scenario 4 — Tab URL Persistence (Web, Browser)

**Setup**: A known idea ID exists in the system (e.g., `idea-fecc6d087c4e`).

**Action**:
```
Browser: navigate to https://coherencycoin.com/ideas/idea-fecc6d087c4e?tab=tasks
```

**Expected**:
- The page renders with the **Tasks** tab active (not Overview).
- The tab panel for Tasks is visible; Overview panel is hidden.
- The URL in the browser address bar remains `...?tab=tasks`.
- Pressing browser Back navigates to the previous URL, not to Overview tab.

**Action (deep link)**:
```
Browser: open a new tab and navigate directly to .../ideas/idea-fecc6d087c4e?tab=contributors
```

**Expected**: Page loads with Contributors tab active on initial render (no flash of Overview tab).

**Edge — unknown tab value**:
```
Browser: navigate to .../ideas/idea-fecc6d087c4e?tab=doesnotexist
```

**Expected**: Page renders with default **Overview** tab active. No 404, no error boundary.

---

### Scenario 5 — Novice/Expert Mode Toggle (Web, Integration)

**Setup**: Contributor is authenticated. Preferences set to `ui_mode: "novice"`.

**Action**:
```
Browser: open https://coherencycoin.com/ideas/idea-fecc6d087c4e
```

**Expected**:
- The "Edges" tab label displays as **"Related Ideas"** (novice vocabulary).
- No `contributor_id` raw ID is visible in the Contributors tab (only display names).
- No "Raw JSON" toggle is visible in the Overview tab.
- Hovering over "Coherence Score" shows a tooltip: "How aligned is this idea?".

**Action (switch to expert)**:
```
Browser: click Expert Mode toggle in the page header/settings
```

**Expected**:
- Toggle fires `PUT /api/preferences/ui` with `{"ui_mode": "expert"}` → HTTP 200.
- Page re-renders: "Related Ideas" tab reverts to "Edges", raw `contributor_id` fields appear, "Raw JSON" toggle appears in Overview.
- Refreshing the page preserves expert mode (loaded from server preferences on next SSR).

**Edge — unauthenticated user**:
```
Browser (no API key set): toggle Expert Mode
```

**Expected**: Mode is stored in `localStorage` only. On refresh, expert mode persists within the same browser. No call to `PUT /api/preferences/ui` is made (or if made, it returns 401 and is silently ignored, with localStorage as fallback).

---

## Risks and Assumptions

| Risk | Mitigation |
|------|------------|
| Tab URL sync causes deep-link failures on SSR | Read `tab` from `searchParams` in server component; render correct tab before hydration |
| Mobile bottom bar conflicts with OS gestures (iOS Safari) | Add `pb-safe` padding (env(safe-area-inset-bottom)) to bottom bar container |
| Expert mode Raw JSON reveals internal server-side IDs | Raw JSON is client-side only (re-renders the API response the page already received); no additional server request needed |
| PostgreSQL `ui_preferences` table migration | Migration script must be idempotent (`CREATE TABLE IF NOT EXISTS`); run before router is activated |
| Graph view (D3/Cytoscape) is expensive to implement | MVP ships "Graph view coming soon" placeholder; tab and toggle UI is the deliverable |
| `ideas_view_mode: "graph"` is a valid enum value but renders placeholder | Spec explicitly calls this out as follow-up; validator still accepts the value so future implementation is non-breaking |
| `localStorage` and server prefs diverge on shared devices | Server prefs always win when authenticated; localStorage is overwritten on login |

---

## Known Gaps and Follow-up Tasks

1. **Graph view implementation** — Force-directed graph for Ideas list is out of scope for MVP. Placeholder component with "coming soon" message is required. Full graph implementation is a follow-up spec.
2. **Swipeable card gestures** — Horizontal swipe on mobile Cards is defined in F3 but requires a gesture library (`react-swipeable` or similar). Deferred to follow-up if gesture lib is not already in `package.json`.
3. **Tab-view event tracking** — `POST /api/ideas/{id}/events` with `event_type: "tab_view"` is defined as a future ROI signal. Not required for MVP.
4. **News and Concepts tabs** — Primary navigation tabs for `/news` and `/concepts` pages are not individually specced here. Their mobile bottom bar icons are defined (F3) but the internal tab structure of those pages is out of scope for this spec.
5. **Rate limiting on preferences PUT** — No rate limiting is specified for MVP. A contributor could spam PUT to bump `last_updated`. Follow-up spec should add per-IP or per-contributor rate limiting.
6. **Migration script** — `api/migrations/add_ui_preferences_table.sql` must be written as a follow-up or included in the implementation task.

---

## Verification — Proof of Working Over Time

The **minimum viable proof** that this feature is working in production:

1. `GET /api/preferences/ui/stats` returns `total_preferences_set > 0` after 7 days of live traffic.
2. `GET /api/preferences/ui` with a valid key returns the last PUT value (preferences persist).
3. Browser test: `/ideas/{id}?tab=tasks` renders Tasks tab without flash.
4. Browser test: Expert Mode toggle renders Raw JSON button.

These are observable without access to the database. A reviewer can run all four checks in under 5 minutes.
