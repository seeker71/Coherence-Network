# Spec 169: Resonance — Alive Empty State with Ambient Breathing

**Status**: Draft
**Author**: product-manager agent
**Date**: 2026-03-28
**Task ID**: task_0d3fb87a8855dbda

---

## Summary

The Resonance page (`/resonance`) is the heartbeat of the network. When no recent activity exists, the page currently shows a flat, lifeless paragraph: *"The network is quiet right now. Be the first to share an idea."* This is a missed opportunity — it makes the product feel broken or abandoned, and actively discourages engagement.

This spec replaces the flat empty state with an **organic breathing animation** — a living, ambient visual that communicates the network is awake and waiting, not dead. It also exposes the **last known pulse timestamp** (the most recent activity at any time in the past) so the page always has something meaningful to say. The empty state should feel like silence before speech, not an error.

---

## Purpose

Replace the dead, static empty state on the Resonance page with an organic breathing animation — soft pulsing rings, ambient particle drift, and a central heartbeat dot — combined with the last known pulse timestamp and a warm invitation to act. The heartbeat page must never feel broken, abandoned, or lifeless, even when no recent activity exists in the current 72-hour window.

---

## Requirements

- [ ] A `ResonanceBreathingOrb` component renders pulsing SVG rings + ambient particle drift on the empty state
- [ ] The breathing animation runs continuously without user interaction and respects `prefers-reduced-motion`
- [ ] `GET /api/ideas/resonance` response is wrapped in `{ ideas: [], meta: { last_pulse_at, total_ever, active_in_window, window_hours } }` shape
- [ ] `GET /api/ideas/resonance/meta` endpoint returns liveness metadata directly (HTTP 200, JSON)
- [ ] Empty state displays "Last pulse: Xh ago" using `last_pulse_at` from meta; falls back to "Waiting for first pulse…" when null
- [ ] Empty state displays "The network is listening." headline and a "Share an idea →" CTA link to `/`
- [ ] No React hydration mismatch — particle positions are deterministic (not random), timestamp formatted server-side
- [ ] Accessibility: breathing SVG is `aria-hidden`; reduced-motion CSS disables all animation keyframes
- [ ] API response change is backwards-compatible — existing consumers reading `data.ideas` are unaffected

---

## Research Inputs

- `2026-03-28` — Existing resonance page code in `web/app/resonance/page.tsx` (`FallbackIdeasSection`) — current flat empty state
- `2026-03-28` — Existing `api/app/routers/ideas.py` — current `/api/ideas/resonance` implementation returns raw array
- `2026-03-28` — Existing `web/app/globals.css` — current `animate-warm-pulse` keyframe definition

---

## Task Card

```yaml
goal: Replace the flat resonance empty state with a breathing animation and last-pulse timestamp
files_allowed:
  - web/app/resonance/page.tsx
  - web/components/resonance-breathing-orb.tsx
  - web/app/globals.css
  - api/app/routers/ideas.py
  - api/app/schemas/ideas.py
done_when:
  - GET /api/ideas/resonance/meta returns HTTP 200 with last_pulse_at, total_ever, active_in_window
  - GET /api/ideas/resonance returns { ideas: [...], meta: {...} } shape
  - /resonance page shows breathing orb + "The network is listening." + "Last pulse:" when empty
  - prefers-reduced-motion disables all animation
commands:
  - curl -s https://api.coherencycoin.com/api/ideas/resonance/meta | python3 -m json.tool
  - curl -s "https://api.coherencycoin.com/api/ideas/resonance?window_hours=72" | python3 -c "import json,sys; d=json.load(sys.stdin); print('has_meta:', 'meta' in d)"
constraints:
  - Do not modify the active resonance list (when items are present)
  - Keep particle positions deterministic (no Math.random()) to prevent SSR/CSR mismatch
```

---

## Files to Create or Modify

- `web/app/resonance/page.tsx` — update `FallbackIdeasSection` to read `meta.last_pulse_at` from API response; pass to `ResonanceBreathingOrb`
- `web/components/resonance-breathing-orb.tsx` — **new** — `ResonanceBreathingOrb` SVG + CSS component with pulsing rings and particle drift
- `web/app/globals.css` — add `@keyframes breatheRing`, `@keyframes particleDrift`, `.animate-breathe-ring`, `.animate-particle-drift-{1..6}`, `prefers-reduced-motion` block
- `api/app/routers/ideas.py` — update `/api/ideas/resonance` to return `{ideas, meta}` shape; add `GET /api/ideas/resonance/meta` route
- `api/app/schemas/ideas.py` — add `ResonanceMeta` and `ResonanceResponse` Pydantic models

---

## Problem Statement

Current empty state (file: `web/app/resonance/page.tsx`, function: `FallbackIdeasSection`, innermost branch when `ideas.length === 0`):

```tsx
<div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center">
  <p className="text-muted-foreground mb-3">
    The network is quiet right now. Be the first to share an idea.
  </p>
  <Link href="/" ...>Share an idea →</Link>
</div>
```

Problems:
- No visual differentiation between "quiet" and "broken"
- No temporal anchor — visitor cannot tell if activity was 1 hour ago or 1 year ago
- No ambient life — contradicts the "heartbeat of the network" framing in the page header
- No motivation gradient — invites a cold-start action without warmth

---

## Solution: Alive Empty State Component

### Visual Design

A **three-layer breathing composition**:

1. **Pulsing rings** — 3–4 concentric SVG circles that expand outward and fade, staggered by 0.8s each. The innermost circle is `~24px` diameter; rings expand to `~120px`. Colors use the existing `warmPulse` amber palette.

2. **Ambient particle drift** — 6–8 tiny dots (2–3px) floating upward slowly with slight horizontal drift, using CSS `@keyframes`. Positions are deterministic (not random) so they render identically on SSR and CSR with no hydration mismatch.

3. **Central heartbeat dot** — a single 8px circle with the existing `animate-warm-pulse` class at the center.

The composition is contained in a `ResonanceBreathingOrb` component (~160×160px SVG + CSS overlay).

### Text Content

Below the animation:
- **Timestamp line**: "Last pulse: {timeAgo(last_pulse_at)}" — always shown. If no activity ever, "Waiting for first pulse…"
- **Invitation headline**: "The network is listening."
- **CTA**: "Share an idea →" link to `/`

### Fallback State Hierarchy

The empty state has three tiers (graceful degradation):

| Tier | Condition | Shown |
|------|-----------|-------|
| A — Active | `resonance.length > 0` | Normal resonance list (existing behavior) |
| B — Quiet with history | `resonance.length === 0` but `last_pulse_at` known | Breathing orb + last pulse timestamp + invitation |
| C — First-run | `resonance.length === 0` and no history | Breathing orb + "Waiting for first pulse…" + invitation |

---

## API Changes

### New field on existing endpoint

**`GET /api/ideas/resonance`** — add `meta` object to response when result is empty:

```json
{
  "ideas": [],
  "meta": {
    "last_pulse_at": "2026-03-27T14:22:10Z",
    "window_hours": 72,
    "total_ever": 147
  }
}
```

The `meta` field is always returned (even when ideas list is non-empty) so clients can always display temporal context. When no ideas have ever existed, `last_pulse_at` is `null` and `total_ever` is `0`.

**Backwards-compatible**: existing clients that only read the array will continue to work because `data.ideas` path is unchanged. If the API returns a raw array (legacy), the frontend treats `last_pulse_at` as unknown.

### New endpoint

**`GET /api/ideas/resonance/meta`**

Returns the metadata object directly:

```json
{
  "last_pulse_at": "2026-03-27T14:22:10Z",
  "window_hours": 72,
  "total_ever": 147,
  "active_in_window": 0
}
```

This allows dashboard widgets, health checks, and future agents to query network liveness without loading full resonance data.

---

## Acceptance Criteria

### AC-1: Animation renders on empty state
- **Given** the `/resonance` page loads with no items in the 72-hour window
- **Then** the page shows a breathing animation (pulsing rings visible, not static)
- **And** the animation runs continuously without user interaction
- **And** no JS errors appear in the browser console
- Manual validation: load `/resonance` with devtools open, confirm Animations panel shows active animations

### AC-2: Last pulse timestamp is displayed
- **Given** the API has `last_pulse_at` in the resonance meta
- **Then** the empty state shows "Last pulse: Xh ago" (or "just now") beneath the animation
- **And** the timestamp uses the same `timeAgo()` format as the rest of the page

### AC-3: API meta field is populated
- **Given** at least one idea activity exists in the database (any time)
- **When** `GET /api/ideas/resonance` is called with a narrow window that returns 0 ideas
- **Then** the response body includes `meta.last_pulse_at` as a non-null ISO 8601 UTC string
- **And** `meta.total_ever` is a positive integer

### AC-4: No hydration mismatch
- **Given** the page is server-side rendered
- **When** React hydrates on the client
- **Then** no "Hydration failed" errors appear in the browser console
- **Specifically**: particle positions are deterministic, not random

### AC-5: Warm invitation is visible
- **Given** the empty state is shown (Tier B or C)
- **Then** the text "The network is listening." is visible on the page
- **And** a "Share an idea" link is visible pointing to `/`

### AC-6: Animation is accessible
- **Given** a user has `prefers-reduced-motion: reduce` set in their OS
- **Then** the breathing rings do NOT animate (animation pauses or is removed)
- **Then** the static orb (non-animated version) is still shown

### AC-7: Meta endpoint works independently
- **Given** the API is running
- **When** `GET /api/ideas/resonance/meta` is called
- **Then** HTTP 200 with JSON body containing `last_pulse_at`, `total_ever`, `active_in_window`

---

## Verification

These scenarios are designed to be run against the production API and browser. A reviewer MUST be able to execute them exactly as written.

Quick smoke test (run first):
```bash
curl -s https://api.coherencycoin.com/api/ideas/resonance/meta | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'last_pulse_at' in d and 'total_ever' in d, 'FAIL: meta shape missing'; print('PASS: meta endpoint OK, total_ever=', d['total_ever'])"
```

### Scenario 1: Meta endpoint returns liveness data
**Setup**: Production API is running; at least one idea or activity exists
**Action**:
```bash
curl -s https://api.coherencycoin.com/api/ideas/resonance/meta | python3 -m json.tool
```
**Expected**: HTTP 200, JSON with keys `last_pulse_at` (non-null ISO string), `total_ever` (integer ≥ 1), `active_in_window` (integer ≥ 0)
**Edge**: If no activity ever exists: `last_pulse_at` is `null`, `total_ever` is `0`, response is still HTTP 200 (not 404/500)

### Scenario 2: Resonance endpoint wraps ideas in meta shape
**Setup**: Any state of the database
**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/ideas/resonance?window_hours=72&limit=30" | python3 -c "import json,sys; d=json.load(sys.stdin); print('has_meta:', 'meta' in d); print('meta:', d.get('meta'))"
```
**Expected**: Output includes `has_meta: True` and `meta:` with a dict containing at minimum `last_pulse_at` and `total_ever`
**Edge**: If the API still returns a raw array (not yet updated), the script prints `has_meta: False` — this is the failure condition indicating the API migration is not complete

### Scenario 3: Narrow window forces empty state, meta still present
**Setup**: Any production state
**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/ideas/resonance?window_hours=1&limit=30" | python3 -c "import json,sys; d=json.load(sys.stdin); print('ideas:', len(d.get('ideas',[]))); print('last_pulse_at:', d.get('meta',{}).get('last_pulse_at'))"
```
**Expected**: `ideas: 0` (very likely with 1-hour window), `last_pulse_at: <ISO string>` (not None)
**Edge**: If `ideas` is non-zero for the 1-hour window, reduce to `window_hours=0` — meta must still be present

### Scenario 4: Browser — empty state breathing animation is visible
**Setup**: Navigate to `https://coherencycoin.com/resonance` in a browser; confirm the resonance list is empty (or use DevTools to override `window_hours=0`)
**Action**: Load the page; open DevTools → Elements
**Expected**:
- An element with class `resonance-breathing-orb` is present in the DOM
- The element has CSS animation running (Animations panel shows non-zero active animations)
- The text "The network is listening." is visible in the page
- The text "Last pulse:" followed by a time string is visible
**Edge**: With `prefers-reduced-motion: reduce` in DevTools → Rendering, no animation should run (static orb only)

### Scenario 5: Error handling — meta endpoint with bad params
**Setup**: API is running
**Action**:
```bash
curl -s -w "\nHTTP:%{http_code}" "https://api.coherencycoin.com/api/ideas/resonance/meta?window_hours=notanumber"
```
**Expected**: HTTP 422 with JSON validation error, not HTTP 500
**And**:
```bash
curl -s -w "\nHTTP:%{http_code}" "https://api.coherencycoin.com/api/ideas/resonance/meta?window_hours=-1"
```
**Expected**: HTTP 422 or HTTP 200 with `active_in_window: 0` (negative window treated as 0), not HTTP 500

---

## Data Model

### `ResonanceMeta` (new Pydantic schema)

```python
class ResonanceMeta(BaseModel):
    last_pulse_at: Optional[datetime] = None    # Most recent idea activity, ever
    window_hours: int                            # The query window used
    total_ever: int = 0                          # All idea activity records ever
    active_in_window: int = 0                   # Items in current window
```

### `ResonanceResponse` (wrapping schema)

```python
class ResonanceResponse(BaseModel):
    ideas: List[ResonanceItem]
    meta: ResonanceMeta
```

The existing `ResonanceItem` schema is unchanged.

---

## CSS Animations (new keyframes)

```css
/* Breathing ring — expands outward and fades */
@keyframes breatheRing {
  0%   { r: 12; opacity: 0.8; }
  100% { r: 60; opacity: 0; }
}

/* Particle drift — floats upward with sway */
@keyframes particleDrift1 {
  0%   { transform: translate(0px, 0px); opacity: 0; }
  20%  { opacity: 0.6; }
  80%  { opacity: 0.4; }
  100% { transform: translate(8px, -60px); opacity: 0; }
}
/* ... particleDrift2 through particleDrift6 with varied x offsets */

/* Accessibility — disable all breathing animations */
@media (prefers-reduced-motion: reduce) {
  .animate-breathe-ring,
  .animate-particle-drift-1,
  .animate-particle-drift-2,
  .animate-particle-drift-3,
  .animate-particle-drift-4,
  .animate-particle-drift-5,
  .animate-particle-drift-6 {
    animation: none !important;
  }
}
```

---

## Component API

### `ResonanceBreathingOrb`

```tsx
interface ResonanceBreathingOrbProps {
  lastPulseAt?: string | null;   // ISO 8601 UTC string
  totalEver?: number;            // Total activity count ever
}

export function ResonanceBreathingOrb({ lastPulseAt, totalEver }: ResonanceBreathingOrbProps)
```

The component renders:
1. An SVG `<svg viewBox="0 0 160 160" aria-hidden="true">` with breathing rings
2. An absolutely-positioned particle layer (CSS-only, 6 dots)
3. A text block below: "The network is listening." + last pulse + CTA

The component avoids `Math.random()` — all positions use deterministic offsets to prevent SSR/CSR hydration mismatch. Prefer rendering timestamp server-side and passing as a string prop.

Suggested DOM contract for automated testing:
```html
<div
  class="resonance-breathing-orb"
  data-last-pulse="2026-03-27T14:22:10Z"
  data-total-ever="147"
  aria-label="Network breathing — last pulse 14 hours ago"
>
```

---

## Risks and Assumptions

- **API shape change breaks consumers** (Medium): Wrapping the response in `{ ideas, meta }` is a breaking change for clients reading a raw array. Mitigation: consumers using `data.ideas` path are unaffected; document migration path for raw-array consumers.
- **SVG animation performance on low-end devices** (Low): CSS `animation` is GPU-composited; particle count capped at 6 to keep budget negligible.
- **Hydration mismatch from client-only timestamps** (Medium): Format timestamp server-side as a pre-rendered string; pass as prop to avoid client bundle overhead.
- **`prefers-reduced-motion` not respected** (Low): Explicit `@media (prefers-reduced-motion: reduce)` block disables all animation keyframes.
- **`last_pulse_at` query cost on large datasets** (Low): Uses `MAX(created_at)` — a single fast aggregate on an indexed column.
- **Assumption**: The existing `animate-warm-pulse` Tailwind utility is already defined in `globals.css`; the new keyframes extend it, not replace it.

---

## Known Gaps and Follow-up Tasks

- **Pulse frequency counter**: Future spec (follow-up idea) could show "X pulses in the last 24h" as a network health indicator.
- **Sonification**: A very subtle audio tone on pulse (opt-in). Out of scope for this spec; log as separate idea.
- **Live refresh**: The empty state could poll `/api/ideas/resonance` every 30s and transition to active list when activity appears. Deferred to separate follow-up task to avoid complexity.
- **Network health score**: Expose `health_score` from resonance meta combining recency + frequency + diversity. Requires separate aggregation spec.
- **Storybook**: Add visual story for `ResonanceBreathingOrb` in all three tiers. Deferred to front-end quality follow-up.
- **Playwright screenshot test**: Automated visual regression for the breathing orb. Track as follow-up test task once component is implemented.

---

## Observability

### API-level signals

- **`/api/ideas/resonance/meta`** — poll-able endpoint for network health dashboards
- **`total_ever`** — monotonically increasing; if it stops growing, the network is stagnant
- **`active_in_window`** — shows real-time activity intensity; can be used for animated breath speed
- **Response time** — the `MAX(created_at)` query should complete in <5ms on indexed tables

### Frontend signals

- **`resonance-breathing-orb` DOM element** — presence confirms the empty state is rendered
- **`data-last-pulse` attribute** on the orb container — allows automated scraping of the displayed timestamp
- **Animation active** — DevTools Animations panel shows at least 1 active animation

---

## How to Prove This Is Working Over Time

1. **API signal**: `GET /api/ideas/resonance/meta` returns `last_pulse_at` within the last 48 hours consistently. If `last_pulse_at` is older than 7 days, the network itself may be stagnant — worth alerting.

2. **Visual signal**: Screenshot comparison test (via Playwright or manual) showing the breathing orb is rendered when no resonance items exist.

3. **Engagement signal**: Track click-through rate on the "Share an idea" CTA in the empty state vs. the previous flat state. If the breathing empty state is warmer, click-through should increase.

4. **Regression signal**: If `meta` disappears from the API response (e.g., after a refactor), the timestamp line silently vanishes. A dedicated API contract test checking for `meta.last_pulse_at` catches this early.

5. **Accessibility signal**: Run `axe` scan on `/resonance` — the breathing SVG must be `aria-hidden` and not trigger a motion-related accessibility violation.

The **three-layer proof stack** that gets stronger as usage grows:

| Layer | Mechanism | Automated? |
|-------|-----------|------------|
| **Contract** | `GET /api/ideas/resonance/meta` returns the required JSON shape | CI test (asserts 200 + shape) |
| **Visual** | Playwright screenshot of `/resonance?window_hours=0` shows `.resonance-breathing-orb` | CI screenshot diff |
| **Behavioral** | `last_pulse_at` returned is within 7 days of today in production | Nightly health check |
| **Engagement** | Click-through rate on "Share an idea →" CTA | Weekly manual review |
| **Regression** | If `meta` field disappears from API response, CI contract test fails | CI (fast) |

---

## Open Questions Addressed

> *"How can we improve this idea, show whether it is working yet, and make that proof clearer over time?"*

### 1 — How to improve the idea

| Improvement Area | Concrete action |
|-----------------|----------------|
| **Emotional resonance** | Vary the animation speed based on network activity: faster breath when `active_in_window > 5`, slower when 0. The orb becomes a live health indicator. |
| **Temporal context** | Show relative quietude: "Quieter than usual" vs "Most active time" based on historical average. |
| **First-time visitor** | If `total_ever === 0`, render "You could be the first heartbeat." with a distinct pulsing dot color. |
| **Progressive loading** | The orb skeleton should render immediately on SSR so the page never shows blank space during hydration. |

### 2 — How to show it is working (right now)

```bash
# Step 1: Check the meta endpoint exists
curl -s -w "\nHTTP:%{http_code}" https://api.coherencycoin.com/api/ideas/resonance/meta

# Step 2: Confirm response shape
curl -s https://api.coherencycoin.com/api/ideas/resonance/meta | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(list(d.keys()))"

# Step 3: Confirm resonance endpoint wraps ideas in meta shape
curl -s "https://api.coherencycoin.com/api/ideas/resonance?window_hours=72&limit=1" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print('has_meta:', 'meta' in d)"

# Step 4: Visually confirm — navigate to /resonance in browser
# Look for: element with class "resonance-breathing-orb" in the DOM
```

If all 4 steps pass, the feature is implemented and live.

---

## Out of Scope

- Modifying the active resonance list (when items are present) — this spec only touches the empty state.
- Changes to the News Feed section.
- Backend scheduler changes.
- Mobile-specific layout adjustments (the orb uses `max-width: 200px; margin: auto` and is naturally responsive).
- Removing or altering the `/api/ideas/resonance` path — only the response shape changes.
