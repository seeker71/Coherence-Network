# Spec 181 — Invest Page: Garden Metaphor over Spreadsheet Metrics

**Status**: Draft
**Idea ID**: task_b6a2f4d9ee0781fd
**Author**: product-manager agent
**Date**: 2026-03-29

---

## Summary

The Invest page currently presents ideas through a financial spreadsheet lens: _Value gap_, _Est. cost_, and _ROI_ columns with bare progress bars. This spec reframes the experience entirely using a **garden metaphor** — ideas are seeds that grow through nurturing (investment, compute, contribution). The financial numbers remain accessible but move to a secondary tier; the primary experience is visual and emotional: _what am I growing?_

The change is purely presentational. No API surface, no data model, and no backend business logic changes. The goal is to make the act of investing feel alive rather than transactional.

---

## Goal

Replace the spreadsheet vocabulary and bare progress bars on the Invest page with a garden vocabulary and a **sprout-to-tree visual progression**. Numbers stay visible but do not lead. The visitor should feel they are tending something, not filling a portfolio.

---

## Problem Statement

The current Invest page reads like an internal finance dashboard. Language like:

- "Value gap: $5,200"
- "Est. cost: $240"
- "ROI: 21.7x"

…requires the visitor to already understand the domain model. The ROI bar is visually thin and abstract. First-time visitors bounce because there is nothing to feel — only metrics to parse.

Users who _have_ staked ideas report that the metaphor that clicked for them was organic growth: _"I planted a seed and it's growing."_ We should lead with that.

---

## Design Language

### Vocabulary replacement

| Old term | New term |
|---|---|
| Value gap | Growth potential |
| Est. cost | Nourishment needed |
| ROI | Vitality |
| ROI bar | Growth stage indicator (sprout → sapling → tree) |
| Stake | Nurture |
| Stage (manifestation status) | Season (seed / sprouting / growing / flourishing) |

### Growth stage indicator

Replace the thin progress bar with an emoji/icon progression that reflects maturity:

| Stage | Icon sequence | Condition |
|---|---|---|
| Seed | 🌱 ○ ○ ○ | roi < 2 OR status = "not_started" |
| Sprouting | 🌱 🪴 ○ ○ | roi 2–7 AND any progress |
| Growing | 🌱 🪴 🌳 ○ | roi 7–15 OR status = "partial" |
| Flourishing | 🌱 🪴 🌳 ✨ | roi > 15 OR status = "validated" |

The nodes are rendered as four connected dots/icons. Reached stages are lit; unreached stages are dimmed. This replaces the `<div h-1.5 bg-muted>` progress bar.

### Card redesign

Each idea card should feel like a **plant tag** in a garden center:

- Top section: idea name + season badge (replaces status chip)
- Middle section: growth stage indicator (the four-icon progression)
- Bottom section: two-line summary — _"Growth potential"_ + _"Nourishment needed"_ in soft muted type
- CTA: "Nurture" button (replaces "Stake")

The vitality multiplier (`21.7x`) moves to a small tooltip/hover label on the growth stage indicator, not the default visible state.

---

## Files Changed

| File | Change |
|---|---|
| `web/app/invest/page.tsx` | Full rewrite of card rendering: new vocabulary, growth stage component inline or extracted |
| `web/app/invest/InvestBalanceSection.tsx` | Optional: rename "Your CC Balance" section heading to "Your Garden Fund" |

No new files required unless the growth stage indicator warrants extraction to `web/app/invest/GrowthStageIndicator.tsx` for testability.

---

## Requirements

### R1 — Vocabulary substitution (must)
All occurrences of "Value gap", "Est. cost", and "ROI" on the Invest page must be replaced with the garden vocabulary above. The underlying numeric values remain identical.

### R2 — Growth stage indicator (must)
Each idea card must show a four-stage visual progression (🌱 🪴 🌳 ✨) where:
- Stages are computed from the existing `roi` and `manifestation_status` values — no new API calls.
- Reached stages appear at full opacity; unreached stages appear at ~30% opacity.
- The exact ROI multiplier number is accessible via hover/title attribute on the indicator (not hidden entirely).

### R3 — Season badge (must)
Replace the existing stage chip (e.g., "📋 Not Started") with a season label using the mapping above. Icon + word, e.g., "🌱 Seed". Same styling as current chip.

### R4 — "Nurture" CTA (must)
The "Stake" button label is replaced with "Nurture". Link target unchanged (`/ideas/${idea.id}`).

### R5 — Numeric secondary tier (must)
Growth potential and Nourishment needed remain visible as smaller muted text below the growth stage indicator — not hidden, not primary.

### R6 — Empty state (should)
The empty-state copy "No ideas yet. Be the first to share one." may remain unchanged. Optionally add: _"Your garden is waiting."_

### R7 — Balance section (should)
The "Your CC Balance" heading in `InvestBalanceSection.tsx` may be renamed to "Your Garden Fund". This is optional polish, not a blocker for acceptance.

### R8 — No layout regressions (must)
The page must remain functional on mobile (max-w-4xl, responsive grid). All existing links must continue to resolve.

---

## How We Know It's Working

This is a UX metaphor change. Proof that it is _working_ (not just deployed) means two things:

1. **Deployed correctly**: The garden vocabulary and growth stage icons render as specified.
2. **Resonance signal**: Over time, watch whether Invest page engagement (clicks to ideas, nurture-button clicks) increases. This spec does not instrument analytics, but the existing "stake" interaction flow at `/ideas/{id}` is unchanged and already trackable.

For immediate proof, the Verification Scenarios below are the acceptance contract.

---

## Verification Scenarios

### Scenario 1 — Garden vocabulary renders (happy path)

**Setup**: At least one idea exists in the system with a computed ROI value.

**Action**: Browser — navigate to `https://coherencycoin.com/invest`

**Expected**:
- Page title "Invest" is present.
- No visible text matching "Value gap", "Est. cost", or "ROI" (case-insensitive).
- At least one card contains the text "Growth potential".
- At least one card contains the text "Nourishment needed".
- At least one card contains the text "Nurture".

**Edge**: If zero ideas exist, the page shows the empty-state message and no card content renders — garden vocabulary absence is expected and acceptable.

---

### Scenario 2 — Growth stage indicator renders correct stage

**Setup**: Ideas with varying ROI exist — at least one with ROI < 2 and one with ROI > 15.

**Action**: Browser — navigate to `https://coherencycoin.com/invest`

**Expected**:
- For the low-ROI idea: the card shows 🌱 lit and 🪴 🌳 ✨ at reduced opacity.
- For the high-ROI idea: all four icons (🌱 🪴 🌳 ✨) appear at full opacity.
- The raw ROI multiplier (e.g., "21.7x") is NOT visible in the default card view (it may appear on hover/title only).

**Edge**: If all ideas have identical ROI values, at least the 🌱 icon must be present on every card; stage progression must not crash or render empty.

---

### Scenario 3 — Season badge replaces status chip

**Setup**: At least one idea with manifestation_status = "validated" and one with status = "not_started".

**Action**: Browser — navigate to `https://coherencycoin.com/invest`

**Expected**:
- For the validated idea: badge reads "✨ Flourishing" (or equivalent season label).
- For the not-started idea: badge reads "🌱 Seed".
- No badge contains raw status strings like "not_started", "partial", "validated".

**Edge**: Unknown manifestation_status values fall back to "🌱 Seed" without throwing an error or rendering blank.

---

### Scenario 4 — "Nurture" CTA links correctly

**Setup**: At least one idea exists with a known ID (e.g., "my-test-idea").

**Action**: Browser — on the Invest page, click "Nurture" on any card.

**Expected**: Browser navigates to `/ideas/{idea_id}` — the existing idea detail page. No 404.

**Edge**: If idea ID contains special characters (e.g., spaces, unicode), `encodeURIComponent` encoding is preserved — same as before the rename.

---

### Scenario 5 — Error handling: API down

**Setup**: Temporarily unreachable API (or dev environment with mock returning empty).

**Action**: Browser — navigate to `https://coherencycoin.com/invest`

**Expected**: The page renders the empty-state message ("No ideas yet. Be the first to share one.") — not a blank white page, not a JavaScript error in the console.

**Edge**: `loadIdeas()` returns `[]` on any fetch failure. This is already implemented and must not regress.

---

## API Endpoints Required

This spec makes **no API changes**. All data is sourced from the existing:

```
GET /api/ideas?limit=60
```

Returns `IdeaWithScore[]` including `roi`, `manifestation_status`, `value_gap`, `estimated_cost`. These fields continue to drive the new garden vocabulary — just with different labels and visual treatment.

The one optional API touch: if the "Your Garden Fund" balance section rename is implemented, it calls the existing:

```
GET /api/contributions/ledger/{contributor_id}
```

No changes to that endpoint.

---

## Web Pages

| Path | Change |
|---|---|
| `/invest` | Garden metaphor, growth stage icons, season badges, Nurture CTA |

---

## CLI / MCP

No CLI or MCP changes required.

---

## Data Model

No schema changes. All transformations are computed at render time from existing `IdeaWithScore` fields.

---

## Implementation Notes

### Growth stage computation (TypeScript)

```typescript
type GrowthStage = "seed" | "sprouting" | "growing" | "flourishing";

function growthStage(roi: number, status: string): GrowthStage {
  const s = status.trim().toLowerCase();
  if (s === "validated" || roi > 15) return "flourishing";
  if (s === "partial" || roi >= 7) return "growing";
  if (roi >= 2) return "sprouting";
  return "seed";
}

const STAGE_ICONS = ["🌱", "🪴", "🌳", "✨"];

const STAGE_INDEX: Record<GrowthStage, number> = {
  seed: 0,
  sprouting: 1,
  growing: 2,
  flourishing: 3,
};
```

Render each icon with `opacity-100` if `iconIndex <= stageIndex`, else `opacity-30`.

### Season badge mapping

```typescript
function seasonLabel(status: string, roi: number): string {
  const stage = growthStage(roi, status);
  return {
    seed:        "🌱 Seed",
    sprouting:   "🌿 Sprouting",
    growing:     "🌳 Growing",
    flourishing: "✨ Flourishing",
  }[stage];
}
```

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|---|---|---|
| Garden metaphor feels patronizing to finance-savvy users | Low | Numbers remain visible; no financial data is hidden |
| Icon rendering varies across OS/browser (emoji) | Medium | Use consistent Unicode emoji; test on Chrome + Firefox + iOS Safari |
| "Nurture" verb feels unfamiliar for token staking | Low | The link target is unchanged; confusion resolves on the detail page |
| ROI tooltip visibility on mobile (hover doesn't exist) | Medium | Add a `title` attribute for desktop; consider making the number visible in small text on mobile |
| Layout breaks on very long idea names | Low | Existing `min-w-0 flex-1` truncation applies; unchanged |

- Garden metaphor may feel unfamiliar — numbers remain visible and accessible
- Emoji rendering varies — test on Chrome, Firefox, Safari, iOS

---

## Known Gaps and Follow-up Tasks

- Follow-up task: Analytics instrumentation — no click tracking on "Nurture" vs old "Stake"; add event emission (`POST /api/events`) in a follow-up spec.
- Follow-up task: Mobile ROI disclosure — hover tooltips don't work on touch; follow-up may render vitality multiplier as small text on mobile.
- Follow-up task: Sorting label — surface "Sorted by vitality" to users.
- Follow-up task: Dark mode emoji contrast — 🌱 may have poor contrast; add text fallback.
- Follow-up task: Balance section rename — "Your Garden Fund" is optional polish.

---

## Purpose

Replace the financial spreadsheet metaphor on the Invest page with a garden metaphor so ideas feel like living things to nurture rather than financial instruments to evaluate. No API or data model changes are required.

## Files to Modify

- `web/app/invest/page.tsx` — Rewrite card rendering with garden vocabulary, growth stage icons, season badges, and Nurture CTA
- `web/app/invest/InvestBalanceSection.tsx` — Optional: rename balance section to "Your Garden Fund"

## Acceptance Criteria

Manual validation (no automated tests for this UI-only change):
- Navigate to `https://coherencycoin.com/invest` and confirm no "Value gap", "Est. cost", or "ROI" labels appear in the primary card layout
- Verify "Growth potential", "Nourishment needed", and "Nurture" appear on idea cards
- Verify the growth stage indicator (🌱 🪴 🌳 ✨) renders with correct opacity per stage

## Out of Scope

- API endpoint changes — purely presentational update
- Backend data model changes — all values derived from existing `IdeaWithScore` fields
- CLI command changes for the investment workflow
- Analytics/event tracking for "Nurture" clicks (follow-up spec)
