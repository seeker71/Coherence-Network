# Spec: UX Overhaul — Tabs-First Layout, Mobile-First, Novice and Expert Modes

**Spec ID**: task_2fd886e591f06caa  
**Status**: Draft (awaiting implementation)  
**Author**: product-manager  
**Date**: 2026-03-28  
**Priority**: High  
**Related task**: `task_2fd886e591f06caa`

---

## Purpose

Coherence Network’s web app currently presents many idea and ecosystem surfaces as long vertical
scrolls. That pattern hides structure, overwhelms newcomers, and makes expert workflows (IDs, API
links, raw payloads) noisy for everyone. This spec defines a **tabs-first** information architecture,
**mobile-first** interaction patterns, and **novice vs expert** presentation modes backed by **per-contributor
UI preferences** so the same codebase serves guided onboarding and power-user operations without
forking routes. The outcome is faster orientation, clearer proof of “is this idea working,” and room
to deepen trust signals over time.

---

## Summary

- **Tabs, not endless scroll**: Primary content on key pages is organized into **sections presented as tabs**
  (shadcn/ui `Tabs`), not as a single scrolling column. Above-the-fold always shows navigation of sections;
  only the active section’s body scrolls if needed.
- **Idea detail** (`/ideas/[idea_id]`): tabs **Overview | Specs | Tasks | Contributors | Edges | History**
  (order may be tuned; names are contract-stable for URLs/query).
- **Ideas list** (`/ideas`): view modes **Cards | Table | Graph** (segmented control or tabs; persisted).
- **Global navigation**: primary destinations **Ideas | Concepts | Contributors | News | Tasks** as tabs or
  a stable top bar; **secondary** items in a dropdown (settings, docs, API health, account).
- **Mobile**: **bottom tab bar** for primary nav where viewport is small; **swipeable** cards on list views;
  **collapsible** sections inside tab panels where it reduces vertical churn.
- **Expert mode**: show internal **IDs**, **raw JSON** toggle for API-shaped payloads, **direct API links**
  (copyable URLs to `GET` the same resource).
- **Novice mode**: hide technical fields, use **guided tooltips** and **plain-language labels**; defer
  advanced panels behind “Show details.”
- **API**: **`/api/preferences/ui`** stores and returns per-authenticated **contributor** UI preferences
  (mode, last tab, list view, mobile overrides).
- **Web**: implement with **shadcn/ui** `Tabs`, `Sheet`, `Tooltip`, `Toggle`, `DropdownMenu` as appropriate.
- **CLI**: unchanged by design — **tab-free**; CLI continues to expose structured commands without this spec.

### Open design question (resolved in this spec)

**How can we improve “is this idea working,” show whether it is working yet, and make proof clearer over time?**

- **Working yet**: Idea **Overview** tab MUST surface a compact **status strip** (e.g. lifecycle phase,
  last verified activity, open blockers count) sourced from existing idea/task APIs — no new truth engine
  in v1.
- **Proof over time**: **History** tab MUST show an **append-only timeline** (events already exposed or
  specified elsewhere: activity, task state changes, deployments). Future iterations MAY add explicit
  “proof artifacts” (links to CI, commit evidence JSON) — tracked as follow-up, not blocking MVP.

---

## Requirements

- [ ] **R1 — Tabs-first layout**: On `web/app/ideas/[idea_id]/page.tsx`, the main content area is wrapped in
  shadcn `Tabs`; default tab is **Overview**; each tab has a stable `value` matching the names in this spec
  (slug-safe: `overview`, `specs`, `tasks`, `contributors`, `edges`, `history`).
- [ ] **R2 — Ideas list view modes**: On `web/app/ideas/page.tsx`, the user can switch **Cards | Table | Graph**;
  the selected mode is persisted via `GET /api/preferences/ui` and `PUT /api/preferences/ui` (or
  `PATCH` — see API section).
- [ ] **R3 — Global navigation**: Primary routes **Ideas** (`/ideas`), **Concepts** (`/concepts` or current
  canonical path), **Contributors** (`/contributors`), **News** (`/news` or equivalent), **Tasks** (`/tasks`)
  are reachable from a single primary navigation component; secondary items live in a dropdown.
- [ ] **R4 — Mobile shell**: At `md` breakpoint and below, primary navigation uses a **bottom tab bar** pattern
  (fixed, safe-area aware); list pages support **horizontal swipe** between cards where feasible without
  breaking accessibility (keyboard + screen reader).
- [ ] **R5 — Novice mode**: When `ui_mode` is `novice`, hide raw IDs, JSON toggles, and internal field names;
  show **tooltips** on first hover/focus for key terms (copy from a single i18n-friendly map).
- [ ] **R6 — Expert mode**: When `ui_mode` is `expert`, show IDs, **raw JSON** toggle for API-shaped payloads,
  and **copy** buttons for API URLs.
- [ ] **R7 — Preferences API**: Implement `GET`, `PUT`, and `PATCH` on `/api/preferences/ui` with the JSON
  shape in **Data model**; unauthenticated requests return **401**; malformed body returns **422**.
- [ ] **R8 — Accessibility**: Tab order and ARIA roles for `Tabs` match shadcn defaults; focus visible in both
  modes; no information exists only via color.
- [ ] **R9 — Performance**: Lazy-load heavy tab panels (e.g. Graph) so first paint of Overview is not blocked
  by chart bundles.

---

## Research Inputs (Required)

- `2024-2024` - [shadcn/ui Tabs](https://ui.shadcn.com/docs/components/tabs) — Radix-based tabs for accessible
  section switching aligned with project stack.
- `2026-03-28` - Coherence Network internal: `specs/ux-homepage-readability.md` — precedent for concrete web
  UX specs with verification commands.
- `2026-03-28` - Coherence Network internal: `specs/TEMPLATE.md` — required spec sections and task cards.

---

## Task Card (Implementation Handoff)

```yaml
goal: Ship tabs-first, mobile-first, novice/expert UX with persisted UI preferences via /api/preferences/ui.
files_allowed:
  - api/app/routers/preferences_ui.py
  - api/app/models/preferences_ui.py
  - api/app/services/preferences_ui_service.py
  - api/app/main.py
  - api/tests/test_preferences_ui.py
  - web/app/ideas/[idea_id]/page.tsx
  - web/app/ideas/page.tsx
  - web/components/layout/AppNav.tsx
  - web/components/ui/tabs.tsx
  - web/lib/ui-preferences.ts
done_when:
  - pytest api/tests/test_preferences_ui.py passes
  - npm run build succeeds in web/
  - Manual verification scenarios 1–5 in this spec pass against staging or production
commands:
  - cd api && pytest -q tests/test_preferences_ui.py
  - cd web && npm run build
```

If additional files are required (e.g. new `web/components/ideas/IdeaDetailTabs.tsx`), a follow-up spec edit
must list them before implementation.

---

## API Changes

### `GET /api/preferences/ui`

**Auth**: Requires authenticated contributor (Bearer token or session as used elsewhere in API).

**Response 200**

```json
{
  "contributor_id": "uuid-or-string",
  "ui_mode": "novice",
  "idea_detail_tab": "overview",
  "ideas_list_view": "cards",
  "mobile_bottom_nav": true,
  "raw_json_expanded": false,
  "updated_at": "2026-03-28T12:00:00Z"
}
```

**Response 401**: Not authenticated.

**Response 404**: Preferences row not yet created — **MUST** be treated as “defaults” by returning **200**
with default values (preferred) or creating row on first read; implementation must choose one and document
in OpenAPI.

### `PUT /api/preferences/ui`

**Request body** (full replace)

```json
{
  "ui_mode": "expert",
  "idea_detail_tab": "history",
  "ideas_list_view": "graph",
  "mobile_bottom_nav": true,
  "raw_json_expanded": true
}
```

**Response 200**: Same shape as GET with `updated_at` refreshed.

**Response 422**: Validation error (invalid enum, unknown keys if `extra` forbidden).

### `PATCH /api/preferences/ui`

**Request body** (partial)

```json
{
  "ideas_list_view": "table"
}
```

**Response 200**: Full merged document.

---

## Data Model

```yaml
UiPreferences:
  properties:
    contributor_id: { type: string, description: "Stable contributor identifier" }
    ui_mode: { type: string, enum: ["novice", "expert"] }
    idea_detail_tab:
      type: string
      enum: ["overview", "specs", "tasks", "contributors", "edges", "history"]
    ideas_list_view: { type: string, enum: ["cards", "table", "graph"] }
    mobile_bottom_nav: { type: boolean }
    raw_json_expanded: { type: boolean }
    updated_at: { type: string, format: date-time }
```

Storage: PostgreSQL table `contributor_ui_preferences` keyed by `contributor_id` (or equivalent existing
user/contributor table FK). If the project uses SQLite for local dev, mirror schema in migrations used by
the API.

---

## Files to Create/Modify

- `api/app/routers/preferences_ui.py` — FastAPI routes for `GET`/`PUT`/`PATCH` `/api/preferences/ui`.
- `api/app/models/preferences_ui.py` — Pydantic request/response models.
- `api/app/services/preferences_ui_service.py` — persistence and defaults.
- `api/app/main.py` — register router.
- `api/tests/test_preferences_ui.py` — contract tests (auth, CRUD cycle, validation).
- `web/app/ideas/[idea_id]/page.tsx` — refactor to tabs; lazy panels.
- `web/app/ideas/page.tsx` — view mode switcher; persist via preferences API.
- `web/components/layout/AppNav.tsx` (or create if missing) — primary + secondary nav + mobile bottom bar.
- `web/lib/ui-preferences.ts` — client fetch/cache helpers for preferences.
- `web/app/globals.css` — safe-area / bottom-nav spacing tokens if needed.

---

## Acceptance Criteria

- Automated: `api/tests/test_preferences_ui.py` covers **full create-read-update** for preferences
  (default → PUT → PATCH → GET) and **401/422** paths.
- Manual: `npm run build` completes without TypeScript errors after tab refactor.
- Manual validation: **Verification** section scenarios executed in browser or via `curl` against a running
  API with valid credentials.

---

## Verification

Run the following before merge:

```bash
cd api && pytest -q tests/test_preferences_ui.py
cd web && npm run build
```

### Verification Scenarios

These scenarios are **contract** checks for reviewers; production base URL is `https://api.coherencycoin.com`
or `API_URL` from environment.

#### Scenario 1 — Preferences full CRUD cycle (authenticated)

- **Setup**: Contributor account exists; auth token `TOKEN` available; no prior row or clean defaults.
- **Action**:

```bash
curl -sS -X GET "$API_URL/api/preferences/ui" -H "Authorization: Bearer $TOKEN" -H "Accept: application/json"
```

- **Expected**: HTTP **200**, JSON includes `ui_mode`, `ideas_list_view`, `idea_detail_tab`, `updated_at`.

```bash
curl -sS -X PUT "$API_URL/api/preferences/ui" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ui_mode":"expert","idea_detail_tab":"history","ideas_list_view":"graph","mobile_bottom_nav":true,"raw_json_expanded":true}'
```

- **Expected**: HTTP **200**, all fields echo stored values; `updated_at` changes.

```bash
curl -sS -X PATCH "$API_URL/api/preferences/ui" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ideas_list_view":"table"}'
```

- **Expected**: HTTP **200**, `ideas_list_view` is `table`, other fields preserved.

```bash
curl -sS -X GET "$API_URL/api/preferences/ui" -H "Authorization: Bearer $TOKEN"
```

- **Expected**: HTTP **200**, `ideas_list_view` is `table`.

- **Edge (bad input)**: `PUT` with `{"ui_mode":"invalid"}` → HTTP **422**, body contains validation detail.

- **Edge (unauthorized)**: `GET` without `Authorization` → HTTP **401**.

#### Scenario 2 — Idea detail tabs in browser

- **Setup**: Dev server running; idea `IDEA_ID` exists in environment.
- **Action**: Open `http://localhost:3000/ideas/IDEA_ID` (or production web URL).
- **Expected**: Visible tab list **Overview | Specs | Tasks | Contributors | Edges | History**; clicking each
  switches content without full page reload; URL reflects tab via **query** `?tab=history` or hash `#history`
  (implementation choice — must be documented in web PR).
- **Edge**: Direct navigation to `?tab=nonsense` → falls back to **Overview** with no error overlay.

#### Scenario 3 — Ideas list view modes persist

- **Setup**: Same `TOKEN`; preferences default or cleared.
- **Action**: In browser at `/ideas`, switch **Cards → Table → Graph**; reload page.
- **Expected**: Last selected mode restored after reload (from API preferences).
- **Edge**: If API unreachable, UI falls back to local `localStorage` with a single console warning (optional)
  or safe default **Cards** — behavior must be documented; no infinite spinner.

#### Scenario 4 — Novice vs expert visibility

- **Setup**: `ui_mode` set to `novice` via API.
- **Action**: Open idea detail; observe fields and tooltips.
- **Expected**: No raw UUIDs in body copy; no JSON toggle. Switch to `expert` via API or UI toggle.

```bash
curl -sS -X PATCH "$API_URL/api/preferences/ui" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"ui_mode":"expert"}'
```

- **Expected**: IDs visible; JSON toggle appears for API-shaped payloads; API link buttons visible.
- **Edge**: Toggling modes does not lose unsaved form edits — forms either warn or scope to tab (document in
  implementation notes).

#### Scenario 5 — Mobile bottom navigation

- **Setup**: DevTools responsive mode width ≤ 768px.
- **Action**: Navigate to Ideas, Concepts, Contributors, News, Tasks via bottom bar.
- **Expected**: Primary destinations reachable; no horizontal page overflow from nav; focus moves into page
  content on route change.
- **Edge**: Rotating device / resizing restores desktop layout without stuck open mobile sheet.

---

## Out of Scope

- Changing backend business logic for ideas, tasks, or graph data beyond presentation and preference storage.
- Redesigning the public marketing homepage (`/`) unless a follow-up spec links it to the same nav shell.
- Native mobile apps; PWA enhancements beyond responsive web.
- Replacing CLI workflows with tabbed TUI.

---

## Risks and Assumptions

- **Risk**: Tab-heavy UI can hurt keyboard users if focus management is wrong — **Mitigation**: use Radix
  primitives via shadcn; test with keyboard and axe.
- **Risk**: Graph view may be expensive — **Mitigation**: lazy import + loading skeleton; optional feature flag.
- **Assumption**: An authenticated **contributor** identity already exists in the API session model; if not,
  preferences must be keyed by a stable anonymous token — would require a spec amendment.

---

## Known Gaps and Follow-up Tasks

- Explicit **proof artifacts** (CI badges, commit evidence JSON) in History tab — **Follow-up task**: tie to
  `docs/system_audit/` evidence pipeline once linked in API.
- Federated or multi-tenant contributor IDs — verify FK matches existing `contributors` table; **Follow-up
  task**: migration review with backend owner.

---

## Failure/Retry Reflection

- **Failure mode**: Preferences API returns 500 on first write — **Blind spot**: migration not applied in env.
  **Next action**: run migrations, health-check DB connectivity, surface clear error in UI toast.

---

## Decision Gates

- Product must confirm **exact** routes for Concepts, News, and Tasks if they differ from `/concepts`, `/news`,
  `/tasks` in current web app.
- Security review if preferences ever store non-UI data (must not).

---

## Concurrency Behavior

- **Read**: Preferences reads are safe concurrent.
- **Write**: **Last-write-wins** for MVP; optional `ETag`/`If-Match` follow-up if users report clobbering.

---

## CLI (Reference)

- No new CLI commands. Existing `cc` workflows remain **tab-free**; CLI users rely on structured output
  and filters.

---

## Web Pages (Contract)

| Path | Purpose |
|------|---------|
| `/ideas` | Ideas list with Cards / Table / Graph |
| `/ideas/[idea_id]` | Idea detail with section tabs |
| `/concepts` | Concepts (primary nav) |
| `/contributors` | Contributors directory |
| `/news` | News / updates |
| `/tasks` | Tasks |

If a route is not yet implemented, the nav entry may link to a placeholder page with a single “Coming soon”
tab — **follow-up**, but nav labels must not 404 silently without messaging.
