# Spec: UX Overhaul — Tabs, Mobile-First, Novice & Expert Modes

**Spec ID**: `task_c50d4bbc1df581dc`  
**Task ID**: `task_c50d4bbc1df581dc`  
**Status**: Draft (spec-only; implementation follows in a separate task)  
**Author**: product-manager  
**Date**: 2026-03-28  
**Related idea**: UX overhaul — replace long vertical scroll with section tabs, mobile-first layout, and persisted novice/expert presentation modes.

---

## Summary

The web app currently presents dense, vertically stacked content on idea detail and list surfaces (for example `web/app/ideas/[idea_id]/page.tsx` and `web/app/ideas/page.tsx`). That pattern overwhelms newcomers, hides secondary material behind excessive scrolling, and does not adapt cleanly to narrow viewports. This spec defines a **mobile-first** information architecture that uses **tabs and view modes** for primary navigation within a page, a **bottom tab bar** on small screens, **swipeable cards** where appropriate, and **collapsible sections** for tertiary detail. It introduces **Novice** vs **Expert** presentation modes: novice mode hides internal identifiers and technical fields, favors guided tooltips and plain vocabulary, and defaults to fewer simultaneous controls; expert mode surfaces IDs, optional raw JSON inspection, and deep links into the public API. Preferences are **per contributor** and persisted via a new API resource `GET`/`PATCH /api/preferences/ui`. The **CLI** (`cc`) remains intentionally tab-free; this spec applies to the **Next.js + shadcn/ui** web client only, using the **Tabs** primitive from shadcn/ui for desktop and tablet, with responsive fallbacks described below.

**Proof and evolution (open question)**: Ship this feature behind an explicit **UI version** or **feature readiness** field returned from `GET /api/preferences/ui` (for example `ui_bundle_version`, `tabs_nav_enabled`) so dashboards and humans can see whether the new shell is active. Complement with: (1) **Playwright** scenarios keyed to data-testids on each tab panel; (2) **public health** or **readiness** checks that assert required routes return 200; (3) a short **changelog** entry per release tied to the same version string. Over time, aggregate **client-side** optional telemetry (opt-in) for tab switches and mode toggles to validate that users find sections without abandoning the page — out of scope for MVP unless explicitly added later.

---

## Purpose

Reduce cognitive load for first-time contributors while preserving power-user efficiency. Enforce a consistent pattern: **one scroll context per tab panel** (not one endless page), with state restored from the server when the same contributor returns on another device.

---

## Requirements

### R1 — Idea detail: section tabs (desktop/tablet)

On **`/ideas/[idea_id]`**, primary content is organized into **tabs** (shadcn/ui `Tabs`):

| Tab key | Label (novice) | Typical contents |
|--------|----------------|------------------|
| `overview` | Overview | Name, description, value summary, stake CTA, human-readable status |
| `specs` | Specs | Linked specs, DSD/spec builder affordances |
| `tasks` | Tasks | Task list, quick create, progress |
| `contributors` | Contributors | Attribution, portfolio links |
| `edges` | Edges | Graph-adjacent relationships (interfaces, parent/child if present) |
| `history` | History | Timeline of material changes (tasks completed, status shifts) where data exists |

- **Within a tab**, vertical scroll is allowed; **cross-section navigation** uses tabs, not anchor jumps down a single column.
- **Deep links**: support query `?tab=tasks` (and aliases) so shared URLs open the correct panel.
- **Default tab**: `overview`.

### R2 — Ideas list: view modes

On **`/ideas`**, provide **view mode** control (segmented control or tabs):

| Mode | Behavior |
|------|----------|
| `cards` | Current card-first browse (default for novice) |
| `table` | Dense sortable table (expert-friendly) |
| `graph` | Minimal graph or list-graph hybrid placeholder if full graph is not yet wired — must not 500; show empty state with link to docs |

Persist last-selected mode in UI preferences (`ideas_list_view`).

### R3 — Global navigation: primary + secondary

- **Primary** destinations (top on desktop, **bottom tab bar** on mobile ≤ breakpoint defined in implementation, suggest `md`): **Ideas**, **Concepts**, **Contributors**, **News**, **Tasks**.
- **Secondary** actions live in a **dropdown** or “More” sheet (settings, API docs, mode toggle).
- **Active route** highlights the correct primary tab.

### R4 — Mobile-specific

- **Bottom tab bar** for primary nav with safe-area padding.
- **Swipeable cards** on list views where cards are shown (horizontal swipe between cards or carousel — implementation chooses one pattern; must be keyboard-accessible fallback).
- **Collapsible sections** inside tab panels for long subsections (accordion within tab).

### R5 — Novice vs Expert mode

| Aspect | Novice | Expert |
|--------|--------|--------|
| IDs | Hidden unless copy-debug | Shown inline |
| Raw payload | Hidden | Toggle “Raw JSON” for the current resource |
| API | Generic “Learn more” | Per-entity `curl` or link to `https://api.coherencycoin.com/api/...` |
| Vocabulary | Plain labels (e.g. “Confidence”) | Same labels plus technical hints in tooltips |
| Tooltips | Guided strings | Optional shorter technical tips |

Toggle persists in preferences (`ui_mode`: `novice` | `expert`).

### R6 — API: per-contributor UI preferences

New resource under **`/api/preferences/ui`**:

- Authenticated as the **current contributor** (reuse existing API auth patterns; if unauthenticated, return 401 on `PATCH` and optional 401 or empty defaults on `GET` per security review — **default in this spec**: `GET` returns anonymous defaults without persistence, `PATCH` requires auth).

### R7 — Web implementation

- Use **shadcn/ui `Tabs`** for tab strip and panels on `md+`.
- On small screens, idea detail may use **scrollable tab list** or **select** for tab choice; behavior must match the same tab keys as desktop.
- **No** requirement to change CLI; document as N/A.

### R8 — Accessibility

- Tab panels associated with `role="tabpanel"` and labelled by triggers.
- Focus order documented in implementation notes; skip links for main content.

### R9 — Performance

- Lazy-load heavy panels (e.g. graph) when first activated.
- Preserve tab state in URL query to avoid re-fetching on trivial navigation.

---

## API Changes

### `GET /api/preferences/ui`

**Purpose**: Return merged UI preferences for the authenticated contributor, or anonymous defaults.

**Response 200** (example shape — exact field names are normative):

```json
{
  "contributor_id": "contrib_abc or null",
  "ui_mode": "novice",
  "ideas_list_view": "cards",
  "idea_detail_default_tab": "overview",
  "last_opened_tabs": {
    "idea:idea-123": "tasks"
  },
  "feature_flags": {
    "tabs_nav_enabled": true,
    "graph_view_beta": false
  },
  "ui_bundle_version": "2026.03.28"
}
```

### `PATCH /api/preferences/ui`

**Purpose**: Update allowed keys (partial update).

**Request** (JSON merge; only listed keys accepted):

```json
{
  "ui_mode": "expert",
  "ideas_list_view": "table",
  "idea_detail_default_tab": "specs"
}
```

**Response 200**: Full merged object as in `GET`.

**Response 400**: Unknown keys or invalid enum values.

**Response 401**: Not authenticated (when persistence requires auth).

**Response 422**: Validation error body per FastAPI conventions.

### `GET /api/ideas` and `GET /api/ideas/{id}`

No breaking schema changes required for MVP; expert **Raw JSON** toggle displays existing API responses client-side. Optional follow-up: `?expand=` query — out of scope unless added in a later spec.

---

## Data Model

**Store**: PostgreSQL JSON column or key-value table keyed by `contributor_id` (align with existing contributor identity tables).

```yaml
UiPreferences:
  contributor_id: { type: string, pk, fk contributors }
  payload: { type: jsonb }
  updated_at: { type: timestamptz }
```

**`payload` keys** (minimum):

- `ui_mode`: enum `novice` | `expert`
- `ideas_list_view`: enum `cards` | `table` | `graph`
- `idea_detail_default_tab`: string (one of tab keys)
- `last_opened_tabs`: object map `string -> tab_key` (bounded size, e.g. last 50 entries)

**Indexes**: primary key on `contributor_id`.

---

## Files to Create / Modify (implementation task — listed for planning)

**API**

- `api/app/routers/preferences_ui.py` — routes for GET/PATCH
- `api/app/services/preferences_ui_service.py` — persistence
- `api/app/models/preferences_ui.py` — Pydantic request/response
- `api/app/main.py` — include router
- `api/tests/test_preferences_ui.py` — contract tests

**Web**

- `web/app/ideas/page.tsx` — view mode tabs + persistence hook
- `web/app/ideas/[idea_id]/page.tsx` — section tabs, query sync
- `web/components/layout/AppShell.tsx` (or equivalent) — primary nav + mobile bottom bar
- `web/components/ui/tabs.tsx` — ensure shadcn Tabs present / extended
- `web/lib/preferences-ui.ts` — client fetch/cache helper

**Out of scope for first slice** unless specified: Concepts, News, Tasks **page internals** beyond tab shell placement (may be stub routes with empty states).

---

## Acceptance Criteria

1. **`GET /api/preferences/ui`** returns 200 with documented JSON keys; anonymous users receive defaults and `contributor_id: null`.
2. **`PATCH /api/preferences/ui`** with valid body updates stored preferences and returns merged JSON; invalid enum returns 400 or 422.
3. **`/ideas/[idea_id]`** renders six section tabs; changing tab updates URL query; reload preserves tab.
4. **`/ideas`** supports three view modes; selection survives reload (via API for authed users).
5. **Novice mode** hides raw IDs in list and detail; **Expert mode** shows IDs and Raw JSON toggle for the loaded entity.
6. **Mobile viewport** shows bottom primary navigation; no horizontal overflow on tab strip (scroll or select fallback).
7. **Accessibility**: axe-critical violations addressed on changed pages (manual or automated in CI when available).

---

## Verification Scenarios

### Scenario A — Full preference read-update-read cycle

**Setup**: Test API base `API=https://api.coherencycoin.com` (or local `http://localhost:8000`). Authenticated contributor token available as `TOKEN` (Bearer). No prior row for this contributor **or** known clean state.

**Action**:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/preferences/ui"
```

**Expected**: HTTP 200, JSON includes `"ui_mode":"novice"` (or stored value), `"ideas_list_view":"cards"`, numeric or string `"ui_bundle_version"`.

**Then**:

```bash
curl -sS -X PATCH "$API/api/preferences/ui" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ui_mode":"expert","ideas_list_view":"table"}'
```

**Expected**: HTTP 200, body reflects `expert` and `table`.

**Then**:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/preferences/ui"
```

**Expected**: Same values persisted.

**Edge (bad input)**:

```bash
curl -sS -o /dev/stderr -w "%{http_code}" -X PATCH "$API/api/preferences/ui" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ui_mode":"god_mode"}'
```

**Expected**: HTTP 400 or 422, no change to stored preferences on subsequent GET.

**Edge (unauthorized PATCH)**:

```bash
curl -sS -o /dev/stderr -w "%{http_code}" -X PATCH "$API/api/preferences/ui" \
  -H "Content-Type: application/json" \
  -d '{"ui_mode":"expert"}'
```

**Expected**: HTTP 401.

---

### Scenario B — Idea detail tab deep link in browser

**Setup**: Production or local web at `WEB=https://coherencycoin.com`, existing idea id `IDEA_ID` from `GET /api/ideas`.

**Action**: Open `WEB/ideas/IDEA_ID?tab=tasks` in Chromium.

**Expected**: Tasks panel is visible; other section panels are not shown as primary content; page title still reflects idea name.

**Edge**: Open `WEB/ideas/IDEA_ID?tab=nope` — **Expected**: fallback to `overview` without 500; invalid query stripped or normalized client-side.

---

### Scenario C — Ideas list view mode persistence (authenticated)

**Setup**: Logged-in contributor in browser; starting `ideas_list_view` is `cards`.

**Action**: Switch view mode to **Table** via UI control; hard refresh `/ideas`.

**Expected**: Table mode remains after reload (verified by DOM structure or data-testid).

**Edge**: Session expires mid-use — **Expected**: UI falls back to anonymous default `cards` without crash; optional banner to sign in again.

---

### Scenario D — Novice vs Expert visibility

**Setup**: Idea detail page loaded; mode **Novice**.

**Action**: Confirm UUID-style id is not shown in page chrome (copy link may still contain id in URL — acceptable).

**Expected**: No inline “ID:” row in overview tab.

**Then**: Toggle **Expert** via settings; reload same URL.

**Expected**: Inline id visible; “Raw JSON” toggle appears; toggling shows pretty-printed JSON matching `GET /api/ideas/IDEA_ID` fields.

**Edge**: Toggle Raw JSON while offline — **Expected**: Cached last response or clear error message, no uncaught exception.

---

### Scenario E — Mobile bottom navigation routing

**Setup**: Chrome device emulation iPhone 12; paths `/ideas`, `/tasks` exist.

**Action**: Tap each bottom primary tab.

**Expected**: Route changes; active tab styled; no content hidden under home indicator (safe-area).

**Edge**: Rotate to landscape — **Expected**: Bottom bar remains usable; tab labels may truncate with tooltips.

---

## Verification (automated commands — post-implementation)

```bash
cd api && pytest -q tests/test_preferences_ui.py
cd web && npm run build
```

Optional when Playwright exists:

```bash
cd web && npx playwright test e2e/ux-tabs.spec.ts
```

---

## Task Card (for implementer)

```yaml
goal: Ship tab-based section navigation, mobile shell, novice/expert modes, and persisted UI preferences API.
files_allowed:
  - api/app/routers/preferences_ui.py
  - api/app/services/preferences_ui_service.py
  - api/app/models/preferences_ui.py
  - api/app/main.py
  - api/tests/test_preferences_ui.py
  - web/app/ideas/page.tsx
  - web/app/ideas/[idea_id]/page.tsx
  - web/components/layout/AppShell.tsx
  - web/components/ui/tabs.tsx
  - web/lib/preferences-ui.ts
done_when:
  - pytest tests/test_preferences_ui.py passes
  - npm run build succeeds
  - Manual Scenario B and E pass on staging
commands:
  - cd api && pytest -q tests/test_preferences_ui.py
  - cd web && npm run build
constraints:
  - Do not remove existing public API fields
  - CLI unchanged
```

---

## Out of Scope (MVP)

- Full graph visualization dataset beyond placeholder for `graph` mode.
- Rewriting all secondary pages (Concepts, News) content — shell only unless already trivial.
- Server-driven feature flags service separate from preferences JSON.
- Mandatory telemetry.

---

## Risks and Assumptions

- **Assumption**: Contributor authentication exists for PATCH; if not, implement auth gate before enabling persistence.
- **Risk**: Tab-heavy UI can harm SEO for public idea pages — mitigate with server-rendered `overview` tab content in HTML and `metadata` unchanged.
- **Risk**: URL query proliferation — document canonical URLs without `tab` for sharing novice-friendly links.
- **Mitigation**: Feature flag `tabs_nav_enabled` allows gradual rollout.

---

## Known Gaps and Follow-up Tasks

- Define exact **history** data source for idea timeline (tasks API vs audit log).
- Confirm **News** route path in Next.js app router (`/news` vs existing).
- Add **E2E** tests and `data-testid` contract in a follow-up spec if not bundled with implementation.
- Resolve whether anonymous `GET` may leak bundle version timing — acceptable as non-secret.

---

## Research Inputs

- `2026-03-28` — shadcn/ui Tabs — [https://ui.shadcn.com/docs/components/tabs](https://ui.shadcn.com/docs/components/tabs) — baseline component for tab strip and panels.
- `2026-03-28` — Existing app routes `web/app/ideas/page.tsx`, `web/app/ideas/[idea_id]/page.tsx` — current scroll-heavy layout to be refactored.

---

## Failure / Retry Reflection

- **Failure mode**: Contributors lose tab state across devices if PATCH fails silently.
- **Blind spot**: Client-only state without server merge.
- **Next action**: Surface toast on preference save failure; retry with exponential backoff.

---

## See Also

- `specs/ux-homepage-readability.md` — complementary first-run readability work.
- `docs/STATUS.md` — implementation tracking once picked up.
