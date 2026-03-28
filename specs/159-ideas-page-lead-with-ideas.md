# Spec 159: Ideas Page — Lead with Ideas, Push Dashboard Below

## Summary

The Ideas page currently presents a 3-stat summary band (Total ideas, Value created, Remaining opportunity) above the idea card hierarchy, followed by a collapsible lifecycle dashboard at the bottom. While the stats and lifecycle sections serve returning operators, first-time visitors land on aggregate numbers before they ever see an actual idea. This spec restructures the page so that idea cards are the first meaningful content a visitor encounters — before any operational metrics — and provides concrete "proof of working" signals on each card. The operational dashboard moves to a secondary section that requires intentional scroll or expansion.

## Goal

Restructure `/ideas` so that:
1. Visitors see idea cards immediately after the hero header.
2. Per-idea progress proof (value realized bar, stage badge, open question count) is surfaced on every card.
3. Summary stats and the lifecycle pipeline dashboard are secondary sections, anchored below the full idea list.
4. The page remains useful to returning operators without hiding operational detail — it just requires a scroll.

## Open Questions Addressed

**Q: How can we improve this idea, show whether it is working yet, and make that proof clearer over time?**

Each idea card must show three proof signals:
- **Value bar** — `actual_value / potential_value` rendered as a progress bar with labelled dollar amounts. A bar at 0% vs 30% vs 100% is visceral proof of movement.
- **Stage badge** — a coloured pill showing the lifecycle stage (`Backlog`, `Specced`, `Implementing`, `Testing`, `Reviewing`, `Complete`). Returning visitors can track stage changes across sessions.
- **Open questions answered** — `{answered} / {total} questions resolved` as a fraction. A ratio moving toward 1.0 proves the idea is being worked.

Over time, these three signals compound: stage advances, the value bar fills, and open questions close. Together they tell the story of whether an idea is alive or stalled.

## Requirements

### R1 — Hero flows directly into idea cards
The page `<main>` renders in this order:
1. Hero block: `<h1>Ideas</h1>` + one-sentence subtitle.
2. `<section aria-labelledby="ideas-list-heading">` containing the idea card hierarchy.
3. *(Below the fold)* Summary stats strip (3 stat cards).
4. *(Below the fold)* Lifecycle pipeline dashboard (collapsible `<details>`).
5. Footer nudge + "Where to go next" nav.

The stat strip and lifecycle dashboard must NOT appear before the first idea card in the DOM.

### R2 — Stage badge on every idea card
Every `IdeaHierarchySubtree` card renders a stage badge. The badge color varies by stage:
- `none` / `Backlog` → muted border, grey text
- `specced` → blue/indigo tint
- `implementing` → amber tint
- `testing` → purple tint
- `reviewing` → orange tint
- `complete` → green tint

Badge source: `idea.stage ?? "none"` from the existing `IdeaWithScore` model (added in Spec 138).

### R3 — Open questions answered count on every card
Each card shows `{answered} / {total} questions resolved` where:
- `answered` = count of `open_questions` where `answer` is a non-empty string
- `total` = `open_questions.length`

If `total === 0`, omit the line entirely (do not show "0 / 0 questions resolved").

### R4 — Summary stats strip moves below the idea list
The existing 3-stat strip (Total ideas, Value created, Remaining opportunity) is rendered in a new `<section aria-labelledby="ideas-summary-heading">` that appears **after** the idea list section in the JSX tree.

### R5 — Lifecycle dashboard remains collapsible, stays below stats
The existing `<details>` lifecycle dashboard is unchanged in content. It appears after the summary stats strip. The summary text on the `<summary>` element must include the completion percentage: `Pipeline overview — {completionPct}% complete`.

### R6 — Skeleton / empty state unchanged
If no ideas exist, the existing empty-state card (with "Be the first to share one" link) still renders in the idea list section before the stat strip.

### R7 — No backend changes required
All data needed (stage, open_questions, value figures) is already present in the `GET /api/ideas` response. This is a pure frontend restructure and enhancement.

### R8 — Page title and metadata unchanged
`export const metadata` stays as-is.

## Affected Files

```
web/app/ideas/page.tsx    (primary — restructure + add stage badge + open-question count)
```

No API changes. No database migrations.

## Visual Structure (Before / After)

### Before
```
[Header]
[Stat strip: total | value created | remaining]
[Portfolio hierarchy heading]
  [Idea cards]
[<details> lifecycle dashboard]
[Footer nudge]
```

### After
```
[Header]
[Idea cards — immediate, no metric gate]
  Stage badge + value bar + questions answered on each card
[Stat strip: total | value created | remaining]   ← below fold
[<details> lifecycle dashboard]                   ← below fold
[Footer nudge]
```

## Stage Badge Colour Map

| Stage | Tailwind classes (badge) |
|-------|--------------------------|
| none / Backlog | `border-border/40 bg-muted/30 text-muted-foreground` |
| specced | `border-indigo-500/30 bg-indigo-500/10 text-indigo-400` |
| implementing | `border-amber-500/30 bg-amber-500/10 text-amber-400` |
| testing | `border-purple-500/30 bg-purple-500/10 text-purple-400` |
| reviewing | `border-orange-500/30 bg-orange-500/10 text-orange-400` |
| complete | `border-green-500/30 bg-green-500/10 text-green-400` |

## API Contract

No new endpoints. Existing endpoints used:
- `GET /api/ideas` — returns `IdeasResponse` with `ideas[]` (each with `stage`, `open_questions`, `actual_value`, `potential_value`)
- `GET /api/ideas/progress` — returns `ProgressDashboard` (used in lifecycle dashboard, unchanged)

## Verification Scenarios

### Scenario 1 — Ideas appear above stats on the page (DOM order)

**Setup:** At least one idea exists in the system (e.g., on https://coherencycoin.com/ideas).

**Action:**
```bash
curl -s https://coherencycoin.com/ideas | grep -n "ideas-list-heading\|ideas-summary-heading\|Portfolio hierarchy"
```

**Expected result:**
- The `ideas-list-heading` anchor appears at a **lower** line number than `ideas-summary-heading`.
- If the old heading "Portfolio hierarchy" was removed, no `Portfolio hierarchy` text appears before the stat grid HTML.
- The stat card containing "Total ideas" appears after the first idea `<article>` element in the HTML.

**Edge case:** If the API returns zero ideas, the empty-state card still renders before the stat strip (DOM order preserved).

---

### Scenario 2 — Stage badge renders on idea cards

**Setup:** An idea exists with `stage = "implementing"` (or any non-null stage).

**Action (browser):** Navigate to `https://coherencycoin.com/ideas` and inspect an idea card for a coloured pill showing the stage label.

**Action (curl):**
```bash
curl -s https://coherencycoin.com/ideas | grep -i "implementing\|specced\|reviewing\|complete\|Backlog"
```

**Expected result:** The page HTML contains stage label text inside a `<span>` with stage-specific colour classes (e.g., `text-amber-400` for implementing). At minimum one stage badge is present if any idea has a non-null stage.

**Edge case:** If `idea.stage` is `null` or `undefined`, the badge renders "Backlog" with muted styling — no crash, no empty badge.

---

### Scenario 3 — Open questions count renders correctly

**Setup:** An idea exists with 3 open questions, 2 of which have non-empty `answer` strings.

**Action (browser):** Open the Ideas page and find the card for that idea. The card should show "2 / 3 questions resolved".

**Action (API check):**
```bash
curl -s https://api.coherencycoin.com/api/ideas | python3 -c "
import sys, json
data = json.load(sys.stdin)
for idea in data['ideas']:
    total = len(idea.get('open_questions', []))
    answered = sum(1 for q in idea.get('open_questions', []) if q.get('answer'))
    if total > 0:
        print(f\"{idea['id']}: {answered}/{total} answered\")
        break
"
```

**Expected result:** The script outputs at least one idea with non-zero question count. Visiting the `/ideas` page for that idea shows the matching `N / M questions resolved` line.

**Edge case:** Ideas with `open_questions = []` or `open_questions` absent show NO questions line — not "0 / 0 questions resolved".

---

### Scenario 4 — Lifecycle dashboard is below stats (page section order)

**Setup:** Any populated Ideas page.

**Action:**
```bash
curl -s https://coherencycoin.com/ideas | grep -n "ideas-summary-heading\|Pipeline overview\|Show lifecycle"
```

**Expected result:**
- The summary heading (`ideas-summary-heading`) appears at a lower line number than the `<details>` lifecycle section (`Pipeline overview` or `Show lifecycle`).
- Both sections appear after the idea list section in the HTML.

**Edge case:** If `GET /api/ideas/progress` returns a non-200, the lifecycle dashboard falls back to locally-computed progress (existing behaviour preserved); the section still renders below stats.

---

### Scenario 5 — Page renders without crash when API is healthy

**Setup:** Production API at https://api.coherencycoin.com is reachable.

**Action:**
```bash
curl -s -o /dev/null -w "%{http_code}" https://coherencycoin.com/ideas
```

**Expected result:** HTTP 200.

**Action (structure check):**
```bash
curl -s https://coherencycoin.com/ideas | grep -c "<article"
```

**Expected result:** Count is equal to the number of ideas in `GET /api/ideas`. If N ideas exist in the API, N `<article>` elements appear on the page.

**Edge case:** If the API returns 500, the page should render an error state or empty ideas list rather than a 500 page crash. (Existing `throw new Error` behaviour; this spec does not change error handling.)

## Risks and Assumptions

| Risk | Mitigation |
|------|------------|
| Stat strip moving below fold reduces immediate dashboard scannability for operators | Operators are returning users who know to scroll; the page header still communicates totals via idea count implicit in list length |
| Stage badge data requires Spec 138 to be deployed | Defensive fallback: `idea.stage ?? "none"` — badge renders "Backlog" if stage is absent |
| Open question count may mislead if answers are stale | Out of scope; answer staleness is a data quality problem, not a UI structure problem |
| Regression: stat strip HTML removed from above-fold could break automated tests that check for "Total ideas" in the first 30 lines | Update any such tests to check existence of the stat strip on the page, not its position |

## Known Gaps and Follow-up Tasks

- **Gap:** The value bar on each card shows absolute USD amounts that may be `$0 / $0` for most ideas in early portfolio stage. A future spec should add a tooltip or note when both values are zero to prevent the bar from looking broken.
- **Gap:** No sort/filter control is exposed on the Ideas page. As the idea list grows, users will need to filter by stage or search by name. Defer to a follow-up spec.
- **Gap:** Stage badges are read-only here; advancing a stage requires API calls. A future spec could add an inline "advance" button for authenticated operators.
- **Follow-up:** Once this restructure ships, instrument click-through rate on "Open idea →" links vs "View progress" links to measure whether the ideas-first layout increases engagement.

## Research Inputs

- `2026-03-27` — [Spec 138: Idea Lifecycle Management](specs/138-idea-lifecycle-management.md) — defines IdeaStage enum, stage field on IdeaWithScore, and GET /api/ideas/progress
- `2026-03-27` — [Spec 075: Web Ideas Pages](specs/075-web-ideas-specs-usage-pages.md) — original Ideas page implementation
- `2026-03-27` — Current `web/app/ideas/page.tsx` — live implementation being restructured

## Task Card

```yaml
goal: >
  Restructure /ideas page so idea cards appear before stats/dashboard.
  Add stage badge + open-question count to each card.
files_allowed:
  - web/app/ideas/page.tsx
done_when:
  - Idea card section renders before stat strip in the DOM
  - Stage badge visible on each idea card with stage-appropriate colour
  - Open-question answered count visible on cards that have questions
  - Stat strip (Total ideas / Value created / Remaining opportunity) appears after idea list
  - Lifecycle <details> dashboard appears after stat strip
  - All existing idea card features (value bar, confidence bar, hierarchy nesting, links) preserved
  - Page returns HTTP 200 on production
commands:
  - cd web && npm run build
constraints:
  - Backend changes: none
  - No new npm packages
  - No changes to API response shapes
  - Do not remove the stat strip — only relocate it
  - Do not remove the lifecycle dashboard — only relocate it
  - Coherence scores remain 0.0–1.0
```
