# Spec 182: Invest Page — Garden Metaphor over Spreadsheet Metrics

**Spec ID**: 182-invest-garden-metaphor
**Idea ID**: fecc6d087c4e
**Status**: Draft
**Depends on**: Spec 157 (Investment UX), Spec 119 (Coherence Credit)
**Web page affected**: `/invest`
**Files affected**:
- `web/app/invest/page.tsx`
- `web/app/invest/InvestBalanceSection.tsx`
- `web/app/invest/GardenCard.tsx` (new)
- `web/app/invest/GrowthSprite.tsx` (new)

---

## Summary

The current Invest page reads like a financial spreadsheet: columns for "Value gap", "Est. cost", and "ROI" with a thin progress bar. This language frames ideas as arbitrage opportunities rather than living things that grow with attention.

This spec replaces the spreadsheet framing with a **garden metaphor**: each idea is a plant at some stage of growth. Investors are gardeners who direct water (CC) toward the plants they believe in. Numbers remain available but are secondary — the primary experience is visual and tactile.

The goal is to make investing *feel like nurturing*, not like filing a trade ticket.

---

## Problem Statement

The existing page:
1. Shows raw financial columns (Value gap, Est. cost, ROI) as the dominant signal
2. Uses a thin progress bar with no semantic meaning — it just represents ROI ratio
3. Has no visual hierarchy that communicates *stage* of an idea
4. Treats each idea identically regardless of whether it is a seedling (new idea) or a tree (near-validated, multi-contributor)
5. Gives no immediate sense of whether prior investment is working

Contributors cannot answer: *"Is this idea flourishing or stalled? Should I water it today?"*

---

## Design Language

### Growth Stages (mapped from `manifestation_status`)

| Status | Garden stage | Visual | Emoji anchor |
|--------|-------------|--------|--------------|
| `idea` / `raw` | Seed | Dormant seed in soil | 🌱 |
| `specced` | Sprout | Single stem, 2 leaves | 🌿 |
| `partial` | Sapling | Multi-branched young tree | 🌳 (small) |
| `validated` | Tree | Full canopy, fruiting | 🌳 (large, amber/gold) |
| `archived` | Wilted | Drooping stem | 🍂 |

The `GrowthSprite` component renders an SVG illustration appropriate to the stage. It is a purely presentational component — no business logic.

### Color palette

- **Seed**: muted slate, low saturation
- **Sprout**: light green (`emerald-400`)
- **Sapling**: medium green (`emerald-600`)
- **Tree**: deep green with amber fruit accents (`emerald-800`, `amber-400`)
- **Wilted**: warm grey with brown leaf (`stone-400`)

### Numbers stay, but move to secondary

Financial data (value gap, estimated cost, ROI ratio) is retained but rendered in a **collapsible "details" row** beneath the plant illustration. The default (collapsed) state shows only:
- Plant illustration
- Idea name (linked)
- Stage badge in garden language
- "Water" (invest/stake) call-to-action button
- A short "growth note" — one sentence describing the idea's most recent activity

Numbers expand on tap/click. On desktop the details row can be permanently visible via a user toggle ("Show numbers").

---

## Requirements

### R1 — GrowthSprite component

`web/app/invest/GrowthSprite.tsx`

- Props: `stage: 'seed' | 'sprout' | 'sapling' | 'tree' | 'wilted'`, `size?: number` (default 64)
- Renders an inline SVG illustration appropriate to the stage
- No external image assets — SVG paths are inline to avoid network requests
- Accessible: includes `aria-label` describing the stage (e.g. "Sapling — idea is in progress")
- Animates on mount: a gentle `scale-in` CSS transition (200 ms ease-out)

### R2 — GardenCard component

`web/app/invest/GardenCard.tsx`

- Props:
  - `idea: IdeaWithScore` (existing type)
  - `showNumbers?: boolean` (default false)
- Renders:
  - Left column: `GrowthSprite` at `size=72`
  - Center column: idea name (link), stage badge (garden language), growth note
  - Right column: "Water" button (styled green, links to `/ideas/<id>`)
  - Expandable row (shown when `showNumbers` or user tapped "Show numbers"): Value gap, Est. cost, ROI ratio — same values as today, but smaller text and muted color
- The "Show numbers" toggle state is kept in component-local state (no server round-trip)
- Hover state: card background shifts to `emerald-950/30`, sprite scale increases by 5%

### R3 — Invest page rewrite

`web/app/invest/page.tsx`

Replace the current card render loop with `GardenCard`. Specifically:

1. Header copy changes from the current text to:
   > *"Your garden. Each idea is a plant — attention makes it grow. Water the ones worth tending."*

2. Sort order stays the same (by ROI descending), but add a secondary sort key: `manifestation_status` progress (tree > sapling > sprout > seed > wilted) so trees are visible without scrolling to confirm the garden is alive.

3. Add a page-level "Show all numbers" toggle (a small `<button>` in the header area). When active, all cards render with `showNumbers=true`. The toggle state is stored in `localStorage` key `invest_show_numbers` so it persists across page loads.

4. The empty-state copy changes from "No ideas yet. Be the first to share one." to:
   > *"The garden is empty. Plant the first seed."*

5. `InvestBalanceSection` copy: "Your CC Balance" → "Water in reserve" (the input label changes; the underlying functionality is unchanged).

### R4 — Mapping function `statusToGardenStage`

Add a pure function (no side effects) to `web/lib/humanize.ts` (or a new `web/lib/garden.ts` if the maintainer prefers separation):

```typescript
export function statusToGardenStage(
  status: string
): 'seed' | 'sprout' | 'sapling' | 'tree' | 'wilted' {
  const s = status.trim().toLowerCase();
  if (s === 'validated') return 'tree';
  if (s === 'partial') return 'sapling';
  if (s === 'specced') return 'sprout';
  if (s === 'archived' || s === 'rejected') return 'wilted';
  return 'seed'; // idea, raw, unknown
}

export function gardenStageName(stage: ReturnType<typeof statusToGardenStage>): string {
  const names: Record<string, string> = {
    seed: 'Seed',
    sprout: 'Sprout',
    sapling: 'Sapling',
    tree: 'Thriving',
    wilted: 'Dormant',
  };
  return names[stage] ?? stage;
}
```

### R5 — Growth note (derived, not persisted)

The "growth note" shown on each card is **derived from existing data** — no new API fields required:

```
function growthNote(idea: IdeaWithScore): string {
  if (idea.actual_value > 0) return `${formatUsd(idea.actual_value)} value realized so far.`;
  if (idea.actual_cost > 0) return `Work in progress — ${formatUsd(idea.actual_cost)} spent.`;
  if (idea.estimated_cost > 0) return `Needs ${formatUsd(idea.estimated_cost)} to reach the next stage.`;
  return 'Waiting for the first gardener.';
}
```

### R6 — No API changes

This spec is **frontend-only**. The API shape (`/api/ideas`) is unchanged. No new backend endpoints are introduced. The garden framing is a presentation layer on top of existing data.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC1 | Visiting `/invest` shows idea cards using the garden card layout (plant illustration visible by default) |
| AC2 | Each card's plant illustration matches the idea's `manifestation_status` stage |
| AC3 | Financial metrics (Value gap, Est. cost, ROI) are **not** visible in the default collapsed state |
| AC4 | Tapping/clicking "Show numbers" on a card reveals the financial metrics for that card |
| AC5 | The page-level "Show all numbers" toggle makes all cards show metrics and persists in `localStorage` |
| AC6 | The "Water in reserve" CC balance section is functionally identical to the previous "Your CC Balance" section |
| AC7 | The "Water" button on each card links to `/ideas/<id>` (same destination as existing "Stake" button) |
| AC8 | The empty-state renders garden copy when no ideas are available |
| AC9 | `GrowthSprite` is accessible: each SVG has an `aria-label` |
| AC10 | No new API endpoints are added; the page continues to load from `/api/ideas?limit=60` |

---

## Data Model

No schema changes. Existing fields used:

| Field | Garden use |
|-------|-----------|
| `manifestation_status` | Determines growth stage → SVG illustration |
| `free_energy_score` / `confidence` | Could inform future "vitality" indicator (out of scope here) |
| `actual_value`, `actual_cost`, `estimated_cost`, `value_gap` | Shown in collapsed "numbers" section |

---

## Open Questions Addressed

**Q: How can we improve this idea, show whether it is working yet, and make that proof clearer over time?**

The garden metaphor is self-answering: a tree is proof of success; a wilted plant is proof of stagnation. But we need a feedback loop beyond static stage mapping. The following signals should be tracked and eventually surfaced (future spec):

1. **Time-at-stage** — how long has an idea been a "sprout"? A sprout that hasn't become a sapling in 30 days is stalled. Surface this as a subtle "thirsty" indicator (a sun icon instead of raindrop).
2. **Investment velocity** — how much CC was watered in the last 7 days vs. the prior 7 days? Acceleration = growing; deceleration = stalling. Show this as root depth lines beneath the plant.
3. **Contributor count** — how many distinct gardeners are tending this plant? A plant with many gardeners is more resilient. Surface as "X gardeners tending" beneath the stage badge.

These are recorded here as **follow-up tasks** for the next sprint, not requirements of this spec.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| SVG inline illustrations add render weight | Low | All sprites are simple geometric shapes (<2 KB per variant); no photos or raster images |
| Users don't discover "Show numbers" | Medium | Add a single-line hint: "Financial details hidden by default — tap to expand" in the page header |
| Garden metaphor feels whimsical in a serious investment context | Low | Numbers remain accessible; the metaphor augments rather than replaces financial data |
| `manifestation_status` values differ from documented set | Low | `statusToGardenStage` defaults unknown values to `'seed'` — safe fallback |
| LocalStorage unavailable (SSR, private browsing) | Low | Wrap localStorage access in try/catch; default to `showNumbers=false` |

---

## Known Gaps and Follow-up Tasks

- [ ] **Vitality indicator** — time-at-stage + investment velocity visualized as root depth (Spec 183)
- [ ] **Contributor count badge** — "X gardeners" shown per card (requires new API field or count query)
- [ ] **Animated watering action** — when user taps "Water", a droplet animation falls onto the plant before navigation
- [ ] **Mobile-first sprite sizing** — sprites default to 72px but should collapse to 48px on screens < 380px
- [ ] **Dark mode palette** — sprites use CSS variables so they invert correctly in dark mode (verify in Chromatic)

---

## Verification Scenarios

### Scenario 1 — Garden cards render on page load

**Setup**: Production `/invest` page with at least one idea in the database (`manifestation_status` = `specced`).

**Action**:
```
curl -sI https://coherencycoin.com/invest
```
Then open `https://coherencycoin.com/invest` in a browser (or Playwright screenshot).

**Expected result**:
- HTTP 200
- DOM contains an element with `aria-label` matching `"Sprout"` (or "Sapling", "Seed" depending on data)
- No element with text "Value gap" is visible without user interaction (collapsed state)
- A "Water" button is present per card

**Edge**: If no ideas exist, page renders "The garden is empty. Plant the first seed." without a JS error.

---

### Scenario 2 — Stage-to-plant mapping is correct

**Setup**: An idea exists with `manifestation_status = "validated"`.

**Action**: Open `/invest` in browser, find that idea's card.

**Expected result**:
- The card's `GrowthSprite` has `aria-label` containing `"Thriving"` (the garden name for `validated`)
- The stage badge shows "Thriving", not "validated" or "✅ Validated"

**Edge**: An idea with `manifestation_status = "archived"` renders a `GrowthSprite` with `aria-label` containing `"Dormant"` and muted/brown color styling.

---

### Scenario 3 — Numbers hidden by default, revealed on toggle

**Setup**: Visit `/invest` with a fresh browser session (no localStorage).

**Action**: Inspect the DOM for text "Value gap".

**Expected result**: "Value gap" text is NOT in the visible DOM (or has `display:none` / is inside a collapsed `<details>` element).

**Then**: Click "Show numbers" on any card.

**Expected result**: The metrics row for that card appears, showing "Value gap", "Est. cost", and a ROI figure.

**Edge**: Reload the page — the card that was expanded collapses back (per-card state is not persisted; only the page-level toggle via localStorage is).

---

### Scenario 4 — Page-level "Show all numbers" toggle persists

**Setup**: Visit `/invest` with a fresh browser session.

**Action**: Click the page-level "Show all numbers" toggle.

**Expected result**: All cards immediately show their metrics rows.

**Then**: Reload the page.

**Expected result**: All cards still show their metrics rows (localStorage key `invest_show_numbers` = `"true"` was written).

**Edge**: Open a private/incognito window where localStorage is cleared. The page loads with all cards collapsed (default). No JS error thrown from the localStorage read.

---

### Scenario 5 — "Water in reserve" balance section works

**Setup**: A contributor ID with known CC balance exists (e.g., contributor `"test-gardener"` has 42.5 CC).

**Action**:
```
curl -s https://api.coherencycoin.com/api/contributions/ledger/test-gardener
```

**Expected result**:
```json
{"balance": {"total": 42.5, ...}}
```

**Then**: On `/invest`, enter `"test-gardener"` in the "Water in reserve" input and click Save.

**Expected result**: Balance displays as `42.5 CC` (label reads "Water in reserve", not "Your CC Balance").

**Edge**: Enter a non-existent contributor ID. Balance section shows "Unavailable" (same behavior as before); no 500 error or unhandled promise rejection.

---

## Implementation Notes

- All three new files (`GardenCard.tsx`, `GrowthSprite.tsx`, and the mapping functions) are **client-side or pure utility**. They require no server-side logic.
- The existing `InvestBalanceSection.tsx` needs only a label string change; its logic is untouched.
- The sort order change in `page.tsx` (secondary sort by stage) requires a `stageOrder` lookup — keep it as a local constant in `page.tsx`.
- TypeScript `strict` mode is assumed; all props must be typed.
- No third-party libraries are needed beyond what is already in `package.json` (Tailwind CSS, React, Next.js 15).

---

*Spec authored by product-manager agent, task_bb5f5e8fef6e0ab8, 2026-03-28.*
