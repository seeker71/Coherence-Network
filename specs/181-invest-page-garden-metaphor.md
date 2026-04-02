# Spec 181: Invest Page — Garden Metaphor over Spreadsheet Metrics

**Spec ID**: 181-invest-page-garden-metaphor
**Idea ID**: task_57f054c23b57dbbd
**Status**: Draft
**Depends on**: Spec 157 (Investment UX), Spec 052 (Portfolio Cockpit)
**Depended on by**: Spec 186 (My Portfolio — Garden vs Ledger) — ✅ Implemented

---

## Purpose

The current `/invest` page uses spreadsheet language — "Value gap", "Est. cost", "ROI" — and a bare
horizontal progress bar. This framing positions ideas as financial instruments to be evaluated, not
living things to be nurtured. Contributors who see language like "4.2x ROI" and "Est. cost $120"
feel like they're reading an analyst report, not participating in something alive.

This spec replaces that framing with a **garden metaphor** throughout the Invest page. Each idea
becomes a plant at a stage of growth. Contributors don't "assess ROI" — they "water a seedling" or
"tend a sapling". Numbers remain accessible but appear in a secondary detail layer, not the primary
visual signal. Growth potential is shown as an animated sprout-to-tree stage indicator rather than a
progress bar.

The change is **additive and non-breaking**: no API changes are required. The underlying data fields
(`value_gap`, `estimated_cost`, `free_energy_score`, `manifestation_status`) drive the same
calculations but are displayed through new labels and visual metaphors.

## Files to Modify

- `web/app/invest/page.tsx`
- `web/app/invest/InvestBalanceSection.tsx`

## Acceptance Criteria

- Manual validation on `/invest` confirms garden-language labels are primary visible copy, with the previous spreadsheet terms demoted to secondary accessible context only.
- Manual validation confirms every invest card renders a stage strip derived from `manifestation_status`, an expected-yield cue, and a garden description derived from `free_energy_score`.
- Manual validation confirms the balance section renders as "Seeds available" while preserving the existing balance data and contributor-change flow.

## Out Of Scope

- No backend or database changes.
- No new API endpoints.
- No CLI wording changes for `cc invest` or `cc portfolio`.
- No cross-page metaphor rollout beyond the invest page and its balance section.

---

## Problem Statement

The current invest page:

1. Leads with financial jargon: "Value gap $42,000 · Est. cost $8,000 · ROI 5.2x"
2. Uses a bare `<div>` progress bar that communicates nothing about what the progress represents
3. Has no visual differentiation between ideas at different stages of growth
4. Provides no emotional signal for whether an idea is thriving or withering
5. The "Stake" button label is neutral/transactional — it doesn't invite nurturing

A contributor who cares deeply about an idea feels nothing when they look at "ROI: 5.2x". A
contributor who sees a seedling asking to be watered feels something.

---

## Goal

Replace the spreadsheet metaphor with a garden metaphor on `/invest`:

- **Stage indicator**: Sprout → Seedling → Sapling → Tree → Flowering, mapped to `manifestation_status`
- **Growth potential**: Replace the ROI progress bar with an animated plant growth visual
- **Garden language**: Replace "Value gap" / "Est. cost" / "ROI" with "Growth potential" / "Water needed" / "Expected yield"
- **Numbers secondary**: Financial figures accessible via expand/hover, not primary display
- **Action verb**: Replace "Stake" with contextual garden verbs ("Water", "Tend", "Plant")
- **CC Balance framing**: Replace "Your CC Balance" with "Seeds available"

The page must still be navigable, accessible (WCAG AA), and fast. No backend changes.

---

## Requirements

- [ ] Replace primary visible invest-page ledger language with garden-language labels while keeping the underlying data fields intact.
- [ ] Render a stage indicator and expected-yield treatment for every invest card using existing idea fields only.
- [ ] Preserve accessible numeric detail access, contributor balance lookup, and `/ideas/{idea_id}` navigation behavior.

### R1 — Growth Stage Mapping

Map `manifestation_status` to garden stages with an emoji and label:

| manifestation_status | Garden Stage | Icon | Description |
|---|---|---|---|
| `idea` / `` / unknown | Seed | 🌱 | Just an idea, not yet planted |
| `specced` | Seedling | 🌿 | Spec written, ready to grow |
| `partial` / `in_progress` | Sapling | 🌳 | Growing — some tasks done |
| `validated` | Tree | 🌲 | Fully grown, proven value |
| `archived` / `closed` | Dormant | 🍂 | Resting or finished |

The mapping must handle any unknown status gracefully (default to Seed / 🌱).

### R2 — Growth Potential Visual (replace ROI bar)

Replace the bare `h-1.5` progress bar with a 5-cell stage strip:

```
[🌱]──[🌿]──[🌳]──[🌲]──[🌸]
  seed  seedling sapling tree flowering
```

- Cells before and including the current stage are filled (green/emerald tint)
- Cells after the current stage are empty (muted)
- The current stage cell pulses with a subtle CSS animation (`animate-pulse` or custom keyframe)
- An ROI multiplier badge appears above the strip: "×4.2 expected yield" in small muted text
- On hover/focus, the exact numbers appear in a tooltip: "Value gap: $42,000 · Est. cost: $8,000"

### R3 — Garden Language Relabeling

Replace all spreadsheet terms with garden terms in the visible UI:

| Old label | New label |
|---|---|
| Value gap | Growth potential |
| Est. cost | Water needed |
| ROI | Expected yield |
| Stake | Water (seedling/sapling) / Tend (tree) / Plant (seed) |
| Your CC Balance | Seeds available |

The `title` attribute and `aria-label` on numeric elements must include the original financial term
for screen reader context: e.g., `aria-label="Growth potential (value gap): $42,000"`.

### R4 — Secondary Number Layer

Financial numbers (`value_gap`, `estimated_cost`, ROI multiplier) must remain accessible but are
not displayed in the primary card layout:

- **Desktop**: numbers visible on card hover in a `<details>`-like expansion or tooltip
- **Mobile**: numbers accessible via a "See details" toggle that expands inline
- The **stage strip** (R2) is always visible; the numbers are always accessible but not dominant

### R5 — Garden Context Description

Each idea card shows a one-sentence garden-metaphor description below the title, derived from the
idea's `manifestation_status` and `free_energy_score`:

| Condition | Description |
|---|---|
| `free_energy_score` > 0.7 | "This plant has strong roots and is ready to grow fast." |
| `free_energy_score` 0.4–0.7 | "Steady growth — regular tending will help it thrive." |
| `free_energy_score` < 0.4 | "Needs attention — a little water could unlock real growth." |
| No score | "Young and untested — be the first to tend this idea." |

### R6 — CC Balance as "Seeds Available"

The `InvestBalanceSection` must:
- Replace heading "Your CC Balance" with "Seeds available"
- Replace "Enter your contributor name to see your balance" with "Enter your contributor name to see how many seeds you have"
- Show balance as: `42 seeds` (not `42.0 CC`) — still backed by the same API field
- Retain the ability to change contributor name

### R7 — Accessibility

- All emoji stage icons include `aria-hidden="true"` with adjacent visually-hidden text
- Stage strip cells have `role="img"` and `aria-label="Stage: Sapling (current)"`
- Color is not the sole differentiator — the current stage has a visible border outline
- Page passes WCAG AA contrast for all garden-colored elements

### R8 — No Backend Changes

No new API endpoints are required. All data comes from:
- `GET /api/ideas?limit=60` — existing endpoint
- `GET /api/contributions/ledger/{contributor_id}` — existing endpoint

Computed fields used:
- `manifestation_status` → stage mapping
- `free_energy_score` → growth description
- `value_gap`, `estimated_cost` → secondary detail layer
- derived ROI = `value_gap / estimated_cost` → "expected yield" badge

---

## Files to Change

| File | Change |
|---|---|
| `web/app/invest/page.tsx` | Replace spreadsheet layout with garden card layout |
| `web/app/invest/InvestBalanceSection.tsx` | Replace "CC Balance" language with "Seeds available" |

No new files required. No API changes. No database changes.

---

## Data Model

No data model changes. The garden metaphor is a pure presentation layer over existing fields.

Mapping reference for implementors:

```typescript
// Stage determination from manifestation_status
function gardenStage(status: string): GardenStage {
  const s = status.trim().toLowerCase();
  if (s === "validated") return "tree";
  if (s === "partial" || s === "in_progress") return "sapling";
  if (s === "specced") return "seedling";
  if (s === "archived" || s === "closed") return "dormant";
  return "seed"; // default for idea / empty / unknown
}

// Action verb for "Stake" button
function gardenVerb(stage: GardenStage): string {
  if (stage === "seed") return "Plant";
  if (stage === "tree" || stage === "flowering") return "Tend";
  return "Water";
}

// Growth description from free_energy_score
function growthDescription(score: number | null): string {
  if (score === null || score === undefined) return "Young and untested — be the first to tend this idea.";
  if (score > 0.7) return "This plant has strong roots and is ready to grow fast.";
  if (score >= 0.4) return "Steady growth — regular tending will help it thrive.";
  return "Needs attention — a little water could unlock real growth.";
}
```

---

## Visual Design Reference

### Card Layout (Garden Version)

```
┌─────────────────────────────────────────────────────┐
│  🌿 GraphQL caching layer          [Water →]        │
│  Steady growth — regular tending will help it        │
│  thrive.                                             │
│                                                      │
│  [🌱]──[🌿*]──[🌳]──[🌲]──[🌸]   ×4.2 expected    │
│  seed  seedling sapling tree flo.  yield             │
│                                                      │
│  ▼ Details  (collapsed by default)                   │
│    Growth potential: $42,000  Water needed: $8,000   │
└─────────────────────────────────────────────────────┘
* current stage, pulsing highlight
```

### Balance Section (Garden Version)

```
┌─────────────────────────────────────────────────────┐
│  Seeds available                                     │
│  42 seeds            contributor: alice  [change]    │
└─────────────────────────────────────────────────────┘
```

---

## Verification

Run these commands as the review baseline:

```bash
python3 scripts/validate_spec_quality.py --file specs/181-invest-page-garden-metaphor.md
curl -s https://coherencycoin.com/invest | grep -E "Growth potential|Water needed|Expected yield|Seeds available|Water|Tend|Plant"
```

This spec constitutes a contract. The following scenarios must pass in production.

### Scenario 1 — Garden language visible on page load

**Setup**: At least one idea exists in the system (any status).

**Action**:
```
curl -s https://coherencycoin.com/invest | grep -E "Growth potential|Water needed|Expected yield|Seeds available|Water|Tend|Plant"
```

**Expected**: Response HTML contains at least one of the garden-language strings. Does not contain
the strings "Value gap", "Est. cost" or "ROI" as visible labels (they may appear in `aria-label`
attributes for accessibility).

**Edge case**: If `curl` on production SSR is unavailable, navigate to `https://coherencycoin.com/invest`
in a browser and visually confirm no spreadsheet labels appear in the primary card layout.

---

### Scenario 2 — Stage strip renders for a known idea

**Setup**: An idea exists with `manifestation_status = "specced"` (maps to Seedling stage).

**Action**:
```
# Browser: navigate to https://coherencycoin.com/invest
# Inspect an idea card for the stage strip
```

**Expected**:
- The stage strip shows 5 cells: Seed, Seedling (highlighted/pulsing), Sapling (dim), Tree (dim), Flowering (dim)
- The Seedling cell has a visible indicator (border, fill, or pulse animation) marking it as current
- The `aria-label` on the strip includes "Seedling (current)"
- An "expected yield" badge appears next to or above the strip (e.g., "×3.1 expected yield")

**Edge case**: An idea with `manifestation_status = ""` (empty string) renders as Seed stage (🌱)
without throwing a JavaScript error.

---

### Scenario 3 — Financial numbers are secondary but accessible

**Setup**: Any idea card on `/invest`.

**Action** (desktop):
```
# Hover over the idea card or activate the "Details" toggle
```

**Expected**:
- Before hover/expand: the card does NOT show "Value gap: $X" or "Est. cost: $X" as standalone
  visible text in the primary layout
- After hover/expand: "Growth potential: $X" and "Water needed: $X" appear, showing the actual
  numeric values
- ROI multiplier badge (e.g., "×4.2 expected yield") is visible without hover (secondary but present)

**Edge case**: An idea with `value_gap = 0` and `estimated_cost = 0` shows "×0.0 expected yield"
(or "—") without a division-by-zero error or NaN display.

---

### Scenario 4 — Garden verb changes with idea stage

**Setup**: Ideas exist at multiple stages (seed, sapling, tree).

**Action**:
```
# Navigate to https://coherencycoin.com/invest and examine action buttons
```

**Expected**:
- Ideas at seed stage: button reads "Plant"
- Ideas at seedling/sapling stage: button reads "Water"
- Ideas at tree/flowering stage: button reads "Tend"
- Clicking any button navigates to `/ideas/{idea_id}` (same behavior as the current "Stake" button)
- The word "Stake" does not appear on the page as a button label

**Edge case**: An idea at dormant stage ("archived") still shows a navigable button (Tend or Water)
so that archived ideas are not dead ends on the invest page.

---

### Scenario 5 — CC Balance renders as "Seeds available"

**Setup**: A contributor with a known balance exists (contributor ID stored in localStorage).

**Action**:
```
# Navigate to https://coherencycoin.com/invest in a browser where
# localStorage["coherence_contributor_id"] = "<contributor_id>"
```

**Expected**:
- The balance section header reads "Seeds available" (not "Your CC Balance")
- The balance value displays as "42 seeds" or similar natural-language form (not "42.0 CC")
- The contributor name and "change" link remain functional

**Edge case**: No contributor ID in localStorage → prompt reads "Enter your contributor name to see
how many seeds you have" (not the old "see your balance" text).

---

## Risks

- `free_energy_score` may be missing on some ideas; fall back to "Young and untested" copy rather than leaving the card blank.
- `manifestation_status` may contain unexpected values; default to Seed stage for all unknown statuses.
- The garden metaphor could confuse users who expect direct financial language; keep numeric details accessible on expand/hover and retain the expected-yield cue.
- Emoji rendering can vary by platform; pair each emoji with visible stage text and accessibility labels.
- Motion can feel noisy on low-power or accessibility-sensitive devices; respect `prefers-reduced-motion`.
- Hover-only detail affordances can fail on touch devices; mobile must use an inline expand/toggle path.

---

## Known Gaps

- Follow-up task: apply the same metaphor shift to CLI `cc invest` and `cc portfolio` output.
- Follow-up task: align `/ideas`, `/contributors/{id}/portfolio`, and `/resonance` to the same garden-language system.
- Follow-up task: replace the initial stage strip with a richer animated SVG plant treatment if the simpler version lands well.
- Follow-up task: define an exact green/emerald palette token set if the current design-system colors prove too loose in review.

---

## Verification Checklist (for reviewer)

- [ ] `/invest` page loads without JavaScript errors in browser console
- [ ] No spreadsheet labels ("Value gap", "Est. cost", "ROI", "Stake") appear as primary visible text
- [ ] Stage strip renders for all idea cards with correct current-stage highlight
- [ ] Growth description sentence appears below each idea title
- [ ] Financial numbers visible via expand/hover, not in primary layout
- [ ] "Seeds available" replaces "Your CC Balance" in balance section
- [ ] Balance displays as "X seeds" (not "X.0 CC")
- [ ] Action button verb changes by stage (Plant / Water / Tend)
- [ ] All emoji have `aria-hidden="true"` with adjacent visually-hidden text
- [ ] Stage strip cells have appropriate `aria-label` attributes
- [ ] `prefers-reduced-motion` disables pulse animation
- [ ] Page passes Lighthouse accessibility score ≥ 90
