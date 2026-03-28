# Spec 170 — Resonance: Alive Empty State with Ambient Breathing

**Status:** draft
**Author:** worker-node
**Created:** 2026-03-28
**Idea:** Resonance: alive empty state with ambient breathing

---

## Summary

The `/resonance` page is the heartbeat of the Coherence Network. When the network has no recent activity, the current empty state renders a flat, static card with plain text: "The network is quiet right now." This feels dead — the opposite of the page's intent.

This spec replaces that empty state with an **organic breathing animation**: soft pulsing rings, ambient particle drift, a last-known pulse timestamp, and a warm invitation that conveys life even in silence. The heartbeat page must never feel dead.

---

## Goal

Transform the "no activity" fallback of the Resonance page from a static notice into a living, animated canvas that:

1. **Breathes** — a soft radial pulse animation (expanding, fading rings) that continuously cycles
2. **Drifts** — ambient floating particles that slowly orbit or drift across the canvas
3. **Remembers** — displays the last known pulse timestamp ("Last pulse: 3h ago")
4. **Invites** — shows a warm, human invitation to be the one who brings the network back to life
5. **Proves life** — is never ambiguous about whether the page is working or broken

The improvement to the idea over time is measured by the `last_pulse_at` timestamp becoming more recent and by tracking how many times users click the "Share an idea" CTA from this empty state.

---

## Background

Current empty state in `web/app/resonance/page.tsx` (line 266–283):

```tsx
// When ideas.length === 0 after FallbackIdeasSection loads fallback ideas:
<div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center">
  <p className="text-muted-foreground mb-3">
    The network is quiet right now. Be the first to share an idea.
  </p>
  <Link href="/" ...>Share an idea →</Link>
</div>
```

There are two empty-state layers:
1. `itemsWithActivity.length === 0` → renders `<FallbackIdeasSection />` which tries to load fallback ideas
2. Inside `FallbackIdeasSection`, `ideas.length === 0` → renders the truly dead empty card

Both layers need the breathing treatment, but the inner (fully empty) state needs it most.

---

## Requirements

### R1 — Breathing Animation (must-have)
- Display 3 concentric pulsing rings, each slightly offset in timing (0s, 0.6s, 1.2s delay)
- Rings expand from 40px → 120px diameter over 3s, fading from 0.4 opacity → 0
- Animation must be pure CSS (no JS canvas required for core loop) — accessible, no motion sickness
- Must respect `prefers-reduced-motion`: when set, show static rings instead of pulsing

### R2 — Ambient Particle Drift (must-have)
- 6–8 tiny dots (2–4px) that drift slowly across the background
- Implemented as CSS animations with randomized delays and directions
- Subtle, not distracting — opacity max 0.3
- Must respect `prefers-reduced-motion`: hide entirely when set

### R3 — Last Pulse Timestamp (must-have)
- Show "Last pulse: X ago" using the most recent `last_activity_at` from any idea in the system
- Source: `GET /api/ideas/resonance?window_hours=720&limit=1` (extending window to find historical pulse)
- If no pulse found in 720h, show "Last pulse: unknown"
- Format: relative time (same `timeAgo()` helper already in the file)
- Placement: centered beneath the pulsing rings, above the invitation text

### R4 — Warm Invitation (must-have)
- Replace "The network is quiet right now. Be the first to share an idea." with a warmer, poetic phrase
- Suggested copy (final copy can be adjusted by design): "The network is listening. Bring it an idea."
- CTA button: "Share the first idea →" linking to `/`
- Track CTA click via `data-track="empty-state-cta"` attribute for future analytics

### R5 — Working State Proof (must-have)
- The page must render a non-empty UI at all times — it is NEVER blank
- If the resonance API fails (`/api/ideas/resonance`), show the breathing animation (not an error or blank)
- If the fallback ideas API also fails, show the breathing animation + "Last pulse: unknown"
- Add a subtle "Network online ✓" badge (green dot + text) in the corner to show the API is reachable
- If API is unreachable, show "Network: checking…" with a spinner (no red error message)

### R6 — Progress Over Time (must-have)
- The `last_pulse_at` timestamp must be fetched dynamically on every page load (no caching)
- Future proof: the spec records that the "working proof" metric is: the timestamp grows more recent as the network becomes more active. A reviewer can prove the feature works by checking that `last_pulse_at` returns a valid ISO timestamp from the API.

---

## API Changes

### New endpoint (optional enhancement): `GET /api/ideas/resonance/last-pulse`

Returns the timestamp of the most recent activity across all ideas — used to power the "Last pulse: X ago" display.

**Response:**
```json
{
  "last_pulse_at": "2026-03-27T09:14:22Z",
  "idea_id": "001-some-idea",
  "idea_name": "Some idea name",
  "hours_since": 27.3
}
```

If no activity exists: `{ "last_pulse_at": null, "idea_id": null, "idea_name": null, "hours_since": null }`

**Alternative (no new endpoint needed):** Query `/api/ideas/resonance?window_hours=720&limit=1` and use the `last_activity_at` from the first result. This is the preferred approach to avoid backend changes.

**Existing endpoints used:**
- `GET /api/ideas/resonance?window_hours=72&limit=30` — primary resonance feed
- `GET /api/ideas?limit=60` — fallback idea list
- `GET /api/health` — used to show "Network online ✓" badge

---

## Data Model

No database changes required. All data is derived from existing fields.

The animation state is entirely client-side CSS. No new tables or columns.

---

## Files to Create / Modify

### Modified files

| File | Change |
|------|--------|
| `web/app/resonance/page.tsx` | Replace `FallbackIdeasSection` static empty card with `<AliveEmptyState>` component |

### New files

| File | Purpose |
|------|---------|
| `web/app/resonance/AliveEmptyState.tsx` | New client component — breathing animation, particles, timestamp, invitation |
| `web/app/resonance/alive-empty-state.css` | CSS animation keyframes for pulse rings and particle drift |

### Alternative (all-in-one)
If the project prefers minimal files, all CSS can be inline via Tailwind `@keyframes` in `globals.css` + a single `AliveEmptyState.tsx` component. The spec permits either approach.

---

## Component Specification: `AliveEmptyState`

```tsx
// web/app/resonance/AliveEmptyState.tsx
// Props:
interface AliveEmptyStateProps {
  lastPulseAt: string | null;  // ISO 8601 UTC or null
  networkOnline: boolean;      // true = API responded, false = API unreachable
}
```

### Visual structure (top to bottom)

```
┌─────────────────────────────────────────────────────────┐
│                    [network badge]                       │  ← top-right corner
│                                                          │
│              ◎  (pulsing rings, 3 concentric)            │  ← center, animated
│              ○                                           │
│              ○                                           │
│                                                          │
│         Last pulse: 3h ago                              │  ← below rings
│                                                          │
│    The network is listening. Bring it an idea.           │  ← invitation
│                                                          │
│         [ Share the first idea → ]                       │  ← CTA button
│                                                          │
│  ·    ·      ·         ·    ·       ·    ·               │  ← drifting particles
└─────────────────────────────────────────────────────────┘
```

### CSS animations required

```css
@keyframes pulse-ring {
  0%   { transform: scale(0.5); opacity: 0.4; }
  100% { transform: scale(2.5); opacity: 0; }
}

@keyframes particle-drift {
  0%   { transform: translate(0, 0); opacity: 0; }
  20%  { opacity: 0.3; }
  80%  { opacity: 0.2; }
  100% { transform: translate(var(--dx), var(--dy)); opacity: 0; }
}
```

### Accessibility
- All animation wrapped in `@media (prefers-reduced-motion: reduce)` override: static only
- `aria-label="Network is alive — last pulse was X ago"` on the animation container
- `role="status"` on the last-pulse text so screen readers announce it

---

## Integration in `page.tsx`

The `FallbackIdeasSection` function currently renders both a fallback list (when ideas exist) and the empty card (when they don't). After this change:

```tsx
// Existing: shows static empty card when ideas.length === 0
// After: shows AliveEmptyState with last pulse timestamp

async function FallbackIdeasSection() {
  const [ideas, lastPulse, healthOk] = await Promise.all([
    loadFallbackIdeas(),
    loadLastPulse(),      // new helper — GET /api/ideas/resonance?window_hours=720&limit=1
    checkNetworkOnline(), // new helper — GET /api/health
  ]);

  if (ideas.length === 0) {
    return (
      <AliveEmptyState
        lastPulseAt={lastPulse}
        networkOnline={healthOk}
      />
    );
  }
  // ... existing fallback ideas list
}
```

---

## Verification Scenarios

### Scenario 1 — Empty state renders animation (not blank)

**Setup:** The API returns zero resonance items and zero fallback ideas (simulate by visiting when network is quiet, or mock)

**Action:**
```bash
curl -s "https://coherencycoin.com/resonance" -L | grep -i "last pulse\|listening\|Share the first"
```

**Expected:** The page HTML contains "Last pulse" text AND "listening" OR "Share the first idea" — proving the animation container rendered.

**Edge:** If curl fails with network error, retry once. If still failing, the page itself has an error — not the empty state.

---

### Scenario 2 — Last pulse timestamp is shown and non-stale

**Setup:** At least one idea exists in the system with a recent `last_activity_at`

**Action:**
```bash
# Get the raw timestamp from API
curl -s "https://api.coherencycoin.com/api/ideas/resonance?window_hours=720&limit=1" | grep last_activity_at

# Verify page displays a relative time
curl -s "https://coherencycoin.com/resonance" -L | grep -i "last pulse"
```

**Expected:**
- API returns a JSON object with `last_activity_at` set to a valid ISO 8601 timestamp
- Page HTML contains "Last pulse: Xh ago" or "Last pulse: Xd ago" (not "Last pulse: unknown")

**Edge:** If `window_hours=720` returns empty, page shows "Last pulse: unknown" — not an error, not a crash.

---

### Scenario 3 — Network badge reflects live API status

**Setup:** Network is online

**Action:**
```bash
# Confirm /api/health returns 200
curl -s -o /dev/null -w "%{http_code}" "https://api.coherencycoin.com/api/health"

# Confirm page shows "online" indicator
curl -s "https://coherencycoin.com/resonance" -L | grep -i "online\|checking"
```

**Expected:**
- Health check returns `200`
- Page HTML contains "online" or "Network online" text
- Does NOT contain "checking…" when API is healthy

**Edge:** Simulate unreachable API: page shows "Network: checking…" spinner rather than error message or crash. Page does NOT show a red error banner.

---

### Scenario 4 — Accessibility: prefers-reduced-motion

**Setup:** Browser has `prefers-reduced-motion: reduce` set

**Action:** Load `/resonance` in a browser with `--force-prefers-reduced-motion` flag OR inspect CSS

```bash
# Verify the CSS includes the reduced-motion override
curl -s "https://coherencycoin.com/resonance" -L | grep -i "prefers-reduced-motion\|animation: none"
# OR check the component source
grep -r "prefers-reduced-motion" web/app/resonance/
```

**Expected:** CSS or inline style contains `prefers-reduced-motion: reduce` override that disables pulse animation. Page still shows static rings and invitation text.

**Edge:** If user has no preference, animations run at full speed. No JS error occurs in either case.

---

### Scenario 5 — Proof of "working over time" (regression check)

**Setup:** Run at two different times with at least one idea created between runs

**Action:**
```bash
# Run 1 (before new idea):
TIME1=$(curl -s "https://api.coherencycoin.com/api/ideas/resonance?window_hours=720&limit=1" | grep -o '"last_activity_at":"[^"]*"')
echo "Time 1: $TIME1"

# Create a new idea or wait for network activity

# Run 2 (after new idea):
TIME2=$(curl -s "https://api.coherencycoin.com/api/ideas/resonance?window_hours=720&limit=1" | grep -o '"last_activity_at":"[^"]*"')
echo "Time 2: $TIME2"

# TIME2 should be more recent than TIME1
```

**Expected:** `TIME2` timestamp is equal to or more recent than `TIME1`. This proves the "last pulse" display grows more current over time as the network becomes active — the core proof of the feature being "alive."

**Edge:** If both timestamps are equal (no new activity), that is acceptable. If `TIME2` is older than `TIME1`, that indicates a caching bug.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| CSS animation performance on low-end devices | Low | Keep ring count to 3, particle count to 6, no canvas |
| `window_hours=720` query is slow on large datasets | Low | Add DB index on `last_activity_at` if needed; response time target < 200ms |
| Tailwind CSS purge strips unused animation classes | Medium | Use safelist in `tailwind.config.js` OR use `style` attribute for keyframe names |
| Empty state never shows (network always has data) | Low | The breathing animation is still valuable when resonance feed is empty but fallback ideas exist — the "quiet" message in the fallback list should also use breathing context |
| Copy ("The network is listening") feels too precious | Medium | Copy is configurable; the animation spec is technology-agnostic |

---

## Known Gaps and Follow-up Tasks

1. **Click tracking on CTA** — `data-track="empty-state-cta"` attribute placed but analytics pipeline to count clicks not specified here. Follow-up: spec for analytics event capture.
2. **Sound design** — A very subtle, optional heartbeat sound (Web Audio API, user-opt-in) could enhance the living feeling. Descoped for now.
3. **Dark/light mode** — Pulse ring colors should adapt. Use `hsl(var(--primary))` to inherit theme color. Ensure contrast in both modes.
4. **Mobile performance** — Particles should be hidden on devices with `(prefers-reduced-motion: reduce)` AND on small screens if performance is poor. Follow-up: add media query for small viewports.
5. **Fallback list + breathing** — When `ideas.length > 0` but resonance feed is empty, the page shows fallback ideas without any breathing. The heading area could still include a subtle pulse indicator. Descoped for now.

---

## Open Questions Answered

> *How can we improve this idea, show whether it is working yet, and make that proof clearer over time?*

**Improvement:** The breathing animation itself is evidence of life — but the `last_pulse_at` timestamp is the measurable proof. Each time a new idea, spec, or contribution is created, the timestamp moves forward. A reviewer can compare `last_pulse_at` values across two runs to prove the network is alive and the feature is tracking activity correctly.

**Working proof:** The `GET /api/ideas/resonance?window_hours=720&limit=1` endpoint is the single source of truth. If it returns a `last_activity_at` within a reasonable window (< 30 days), the network is alive and the timestamp renders correctly. Verification Scenario 5 (above) automates this check.

**Clarity over time:** As the network grows, the timestamp naturally becomes more recent. The empty state itself becomes less common (the resonance feed fills up), which is the ultimate proof that the feature is working — by making the empty state less necessary while still making it beautiful when it appears.

---

## Acceptance Criteria

- [ ] `/resonance` page never renders a blank or static empty card
- [ ] When resonance feed is empty AND fallback ideas are empty, `AliveEmptyState` component renders
- [ ] `AliveEmptyState` shows at minimum: 3 pulsing rings, "Last pulse: X" text, warm invitation, CTA link
- [ ] `last_pulse_at` is fetched fresh on each page load with no caching
- [ ] CSS animation respects `prefers-reduced-motion: reduce`
- [ ] Network online badge is visible and reflects real API status
- [ ] All 5 Verification Scenarios pass against production `coherencycoin.com`
- [ ] No console errors in browser when empty state renders
- [ ] CTA link navigates to `/` (idea submission page)
