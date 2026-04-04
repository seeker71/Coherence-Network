# Spec 186: My Portfolio — Garden vs Ledger

**Spec ID**: 186-portfolio-garden-metaphor
**Status**: Draft
**Depends on**: Spec 181 (Invest Page — Garden Metaphor), Spec 174 (Portfolio API), Spec 188 (My Portfolio — Personal Contributor View)
**Depended on by**: —

---

## Summary

The portfolio pages (`/my-portfolio`, `/contributors/{id}/portfolio`) currently present a contributor's
activity as a **financial ledger**: CC balances, ROI percentages, stakes, tasks completed. While
spec 181 reframed the `/invest` page with a garden metaphor, the portfolio pages remain in spreadsheet
language. This creates a jarring transition: contributors go from "watering seedlings" on `/invest`
to reading "ROI: +24%" on their portfolio.

This spec extends the garden metaphor to the portfolio pages. A contributor's portfolio becomes a
**personal garden**: ideas they contributed to are "plants they tend", stakes are "seeds planted",
CC earned is "harvest", and task completions are "work done in the garden". Financial numbers remain
accessible but secondary — the primary experience is: *look at what I've grown*.

The change is **presentation-only**: no API changes, no data model changes.

---

## Problem Statement

The current portfolio page:

1. Leads with financial metrics: "CC Balance: 4820", "+24% ROI", "200 CC staked"
2. Uses transactional language: "Ideas I Staked On", "Tasks I Completed"
3. Health signals are color-coded dots with labels like "active/slow/dormant" — functional but cold
4. CC history chart is a bare bar chart with no garden context
5. No connection between the garden metaphor on `/invest` and the ledger view on `/my-portfolio`

A contributor who just "watered" an idea on `/invest` should see their portfolio as a living garden,
not a brokerage statement.

---

## Goal

Reframe the portfolio pages from ledger to garden:

- **"CC Balance"** → **"Harvest"** (what you've gathered)
- **"Ideas I Contributed To"** → **"Plants I Tend"**
- **"Ideas I Staked On"** → **"Seeds I Planted"**
- **"Tasks I Completed"** → **"Garden Work"**
- **ROI %** → secondary, shown as "yield" on hover/expand
- **Health signals** → garden health: "thriving", "growing", "needs water", "dormant"
- **CC history chart** → "Harvest over time" with garden context

The page must still be navigable, auditable, and fast. No backend changes.

---

## Requirements

### R1 — Garden Health Mapping

Map existing `activity_signal` values to garden health labels:

| activity_signal | Garden Health | Icon | Color |
|---|---|---|---|
| `active` | Thriving | 🌿 | emerald-500 |
| `slow` | Growing | 🌱 | yellow-500 |
| `dormant` | Dormant | 🍂 | muted |
| `unknown` | Untested | 🫘 | muted |

The mapping must handle unknown signals gracefully (default to Untested).

### R2 — Section Relabeling

Replace all ledger terms with garden terms:

| Old label | New label |
|---|---|
| CC Balance | Harvest |
| CC Earning History | Harvest Over Time |
| Ideas I Contributed To | Plants I Tend |
| Ideas I Staked On | Seeds I Planted |
| Tasks I Completed | Garden Work |
| CC attributed | CC earned |
| ROI | Yield |
| Staked | Planted |
| network % of supply | Share of garden |

### R3 — Secondary Financial Layer

Financial numbers (ROI%, exact CC amounts) remain accessible but are not the primary visual signal:

- **Desktop**: ROI% and detailed CC breakdown visible on card hover or in a `<details>` expansion
- **Mobile**: "See details" toggle expands inline
- The **garden health** (R1) is always visible; the numbers are always accessible but not dominant

### R4 — Garden Context for Each Plant

Each idea card in "Plants I Tend" shows a one-sentence garden description based on health and
contribution types:

| Condition | Description |
|---|---|
| `active` + multiple contribution types | "This plant is thriving — your diverse contributions are paying off." |
| `active` + single contribution type | "Growing well — focused care on this one area." |
| `slow` | "Steady growth — a little more attention could accelerate it." |
| `dormant` | "Resting — no recent activity, but the roots are still there." |
| No contributions | "Empty plot — nothing growing here yet." |

### R5 — Seeds Planted (Stakes) Garden Reframe

Stake cards reframe investment as planting:

- **"200 CC staked"** → **"200 seeds planted"**
- **"+24% ROI"** → **"×1.24 yield"** (secondary, on hover)
- **"Staked {date}"** → **"Planted {date}"**
- Negative ROI shown as "withered" with muted styling (not red alarm)

### R6 — Garden Work (Tasks) Reframe

Task cards reframe completion as garden work:

- **Provider name** → "Tool used" (e.g., "claude-sonnet" → "claude-sonnet")
- **Outcome badge** → "Result: passed/failed/partial" with garden context
- **"5 CC earned"** → **"5 seeds harvested"**

### R7 — CC Balance as "Harvest"

The CC balance section must:

- Replace "CC Balance" heading with "Harvest"
- Show balance as: `4 820 seeds harvested` (not `4 820 CC`)
- Network percentage as: `0.48% share of garden`
- Retain the toggle between absolute and percentage views

### R8 — Accessibility

- All emoji include `aria-hidden="true"` with adjacent visually-hidden text
- Health signal colors are not the sole differentiator — include text labels
- Page passes WCAG AA contrast for all garden-colored elements
- `prefers-reduced-motion` disables any pulse animations

### R9 — No Backend Changes

No new API endpoints required. All data comes from existing portfolio endpoints:

- `GET /api/contributors/{id}/portfolio`
- `GET /api/contributors/{id}/cc-history`
- `GET /api/contributors/{id}/idea-contributions`
- `GET /api/contributors/{id}/stakes`
- `GET /api/contributors/{id}/tasks`

---

## Files to Change

| File | Change |
|---|---|
| `web/app/contributors/[id]/portfolio/page.tsx` | Apply garden metaphor to all sections |
| `web/app/my-portfolio/page.tsx` | Update entry page language if it shows any labels |

No new files required. No API changes. No database changes.

---

## Data Model

No data model changes. The garden metaphor is a pure presentation layer over existing fields.

Mapping reference for implementors:

```typescript
// Garden health from activity_signal
function gardenHealth(signal: string): GardenHealth {
  const s = signal.trim().toLowerCase();
  if (s === "active") return { label: "Thriving", emoji: "🌿", color: "emerald" };
  if (s === "slow") return { label: "Growing", emoji: "🌱", color: "yellow" };
  if (s === "dormant") return { label: "Dormant", emoji: "🍂", color: "muted" };
  return { label: "Untested", emoji: "🫘", color: "muted" };
}

// Garden description for idea cards
function plantDescription(
  signal: string,
  contributionTypes: string[],
): string {
  const s = signal.trim().toLowerCase();
  if (s === "active" && contributionTypes.length > 1)
    return "This plant is thriving — your diverse contributions are paying off.";
  if (s === "active")
    return "Growing well — focused care on this one area.";
  if (s === "slow")
    return "Steady growth — a little more attention could accelerate it.";
  if (s === "dormant")
    return "Resting — no recent activity, but the roots are still there.";
  return "Empty plot — nothing growing here yet.";
}
```

---

## Visual Design Reference

### Portfolio Header (Garden Version)

```
┌─────────────────────────────────────────────────────────┐
│  My Garden                                  [Seeds / %] │
│  alice                                      [⚙️ Key]    │
│  🐙 github/alice ✓  |  📱 telegram/@alice ✓             │
│                                                         │
│  Harvest              Harvest Over Time (90d)            │
│  4 820 seeds          ███░░░▓▓▓▓████  ↑12% this season  │
└─────────────────────────────────────────────────────────┘
```

### Plants I Tend (Garden Version)

```
┌─────────────────────────────────────────────────────────┐
│  Plants I Tend                        [sort: harvest ▼] │
│  ┌ my-portfolio  🌿thriving  spec,test   120 seeds  ▶ │
│  │ Growing well — focused care on this one area.        │
│  └ ux-overhaul   🌱growing   code         48 seeds  ▶ │
│    │ Steady growth — a little more attention could...   │
└─────────────────────────────────────────────────────────┘
```

### Seeds I Planted (Garden Version)

```
┌─────────────────────────────────────────────────────────┐
│  Seeds I Planted                       [sort: yield ▼]  │
│  ┌ cc-launch     Planted Jan 15    200 seeds planted ▶ │
│  │               ×1.24 yield (show on hover)            │
│  └ ux-overhaul   Planted Feb 3      50 seeds planted ▶ │
│                  ×0.96 yield (show on hover)            │
└─────────────────────────────────────────────────────────┘
```

---

## Verification

This spec constitutes a contract. The following scenarios must pass in production.

### Scenario 1 — Garden language visible on portfolio page load

**Setup**: A contributor exists with at least one idea contribution.

**Action**:
```
# Navigate to https://coherencycoin.com/contributors/{id}/portfolio
```

**Expected**: Response HTML contains at least one of the garden-language strings:
"Harvest", "Plants I Tend", "Seeds I Planted", "Garden Work", "Thriving", "Growing".
Does not contain "CC Balance", "Ideas I Staked On", or "Tasks I Completed" as visible labels.

### Scenario 2 — Garden health renders for idea cards

**Setup**: An idea contribution exists with `activity_signal = "active"`.

**Action**:
```
# Inspect the idea card in the "Plants I Tend" section
```

**Expected**:
- The health indicator shows "Thriving" with 🌿 emoji and emerald color
- The `aria-label` on the health indicator includes "Thriving"
- A garden description sentence appears below the idea title

### Scenario 3 — Financial numbers are secondary but accessible

**Setup**: Any stake card on the portfolio page.

**Action** (desktop):
```
# Hover over the stake card or activate the "Details" toggle
```

**Expected**:
- Before hover/expand: the card shows "X seeds planted" and planting date
- After hover/expand: yield (ROI%) and valuation appear
- The word "ROI" does not appear as a primary label (may appear in `aria-label`)

### Scenario 4 — Harvest section renders as "Harvest" not "CC Balance"

**Setup**: A contributor with a known balance.

**Action**:
```
# Navigate to portfolio page
```

**Expected**:
- The balance section header reads "Harvest" (not "CC Balance")
- The balance value displays as "4 820 seeds harvested" or similar natural-language form
- The toggle between absolute and percentage views still works
- Percentage view shows "X% share of garden" (not "X% of network")

### Scenario 5 — Empty states use garden language

**Setup**: A contributor with no contributions, stakes, or tasks.

**Action**:
```
# Navigate to portfolio page
```

**Expected**:
- "Plants I Tend" section: "No plants yet — start by contributing to an idea."
- "Seeds I Planted" section: "No seeds planted yet — water an idea on the Invest page."
- "Garden Work" section: "No garden work yet — pick up a task to get started."

---

## Risks and Assumptions

| Risk | Mitigation |
|---|---|
| Garden metaphor may obscure financial clarity for power users | Numbers remain accessible via expand/hover; ROI still computable |
| Emoji rendering inconsistent across platforms | Supplement all emoji with text labels visible by default |
| Existing contributors may be confused by terminology change | Garden terms are intuitive; old terms preserved in `aria-label` for screen readers |
| Animation performance on low-power devices | Use `prefers-reduced-motion` media query to disable animations |

---

## Known Gaps and Follow-up Tasks

1. **CLI `cc portfolio` command**: This spec does not change CLI output. A follow-up spec should
   apply garden metaphor to CLI portfolio output.

2. **Garden metaphor on `/invest` page**: Already covered by spec 181. This spec ensures consistency
   between `/invest` and `/my-portfolio`.

3. **Garden growth over time**: The "Harvest Over Time" chart shows CC earned but does not yet show
   garden growth trajectory (how many plants are thriving vs dormant over time). Deferred.

4. **Garden-wide health summary**: A future enhancement could show an overall garden health score
   (e.g., "3 thriving, 2 growing, 1 dormant") at the top of the portfolio.

---

## Verification Checklist (for reviewer)

- [ ] Portfolio page loads without JavaScript errors in browser console
- [ ] No ledger labels ("CC Balance", "Ideas I Staked On", "Tasks I Completed") appear as primary visible text
- [ ] Garden health renders correctly for all activity_signal values
- [ ] Garden description sentence appears below each idea title in "Plants I Tend"
- [ ] Financial numbers (ROI%, valuation) visible via expand/hover, not in primary layout
- [ ] "Harvest" replaces "CC Balance" in balance section
- [ ] Balance displays as "X seeds harvested" (not "X CC")
- [ ] Stake cards use "seeds planted" language
- [ ] Task cards use "garden work" language
- [ ] All emoji have `aria-hidden="true"` with adjacent visually-hidden text
- [ ] `prefers-reduced-motion` disables animations
- [ ] Empty states use garden language
- [ ] Page passes Lighthouse accessibility score ≥ 90
