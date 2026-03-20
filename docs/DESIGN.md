# Coherence Network -- Visual and Emotional Design Specification

**Status**: Draft
**Date**: 2026-03-20
**Author**: Product (spec-driven)

---

## Purpose

This document defines the visual and emotional direction for the Coherence Network website. The current site is a warm dark dashboard (dark browns, warm oranges, Space Grotesk font) that functions well but feels like a technical control panel. The goal is to evolve it into something that feels like a warm gathering place -- inviting, coherent, open, friendly, curious, joyful, connected, giving, and compassionate.

This is a design-level spec. It does not contain API contracts or data models. It describes the target experience, the color and typography systems, the landing page structure, the component tone, and the navigation simplification that implementation work should follow.

---

## 1. Emotional Design Principles

Seven principles guide every design decision. When in doubt, choose the option that better serves these.

### 1.1 Inviting

First impression should be "come in" not "log in." No jargon above the fold. Human language first. The site should feel like a door held open, not a turnstile.

### 1.2 Coherent

Every element should feel like it belongs. Consistent rhythm in spacing, color, and type weight. The visual language should mirror the product's core concept: everything connected, everything traceable. If a pattern appears once, it should appear everywhere it applies.

### 1.3 Open

Generous whitespace. Nothing cramped. Information breathes. The layout itself communicates "there is room for you here." Padding and margin should err on the side of too much, not too little.

### 1.4 Friendly

Warm colors, rounded shapes, gentle transitions. Nothing sharp or sudden. The UI should feel like a conversation, not a command line. Edges are soft. Language is plain.

### 1.5 Curious

Subtle motion that invites exploration. "What is down here?" Progressive disclosure. Do not overwhelm -- intrigue. Let people discover depth at their own pace.

### 1.6 Connected

Visual threads between elements. Show relationships, not just data points. Lines, flows, gradients that suggest continuity. Elements on the page should feel like they know about each other.

### 1.7 Giving

Lead with "here is what you can discover" not "here is what we need from you." The first screen should offer value, not ask for commitment. Generosity before transaction.

---

## 2. Color Palette Evolution

### Current State

The existing palette in `web/app/globals.css` is a dark warm foundation:

| Token | Current Value | Role |
|---|---|---|
| `--background` | `24 28% 10%` | Page background |
| `--foreground` | `34 36% 92%` | Primary text |
| `--card` | `24 22% 14%` | Card surface |
| `--primary` | `24 68% 62%` | Orange primary accent |
| `--muted-foreground` | `30 18% 72%` | Muted text |
| `--chart-2` | `165 34% 44%` | Teal chart accent |

**Assessment**: Good foundation. The warmth is right. But the palette lacks depth and joy. The orange primary feels urgent rather than generous.

### Proposed Evolution

Keep the warmth. Add depth and joy. The guiding metaphor shifts from "control panel glow" to "firelit gathering room."

| Token | Proposed Value | Rationale |
|---|---|---|
| `--background` | `24 22% 11%` | Soften slightly -- a touch more breathable |
| `--foreground` | `38 30% 90%` | Slightly warmer -- less clinical white |
| `--primary` | `36 72% 58%` | Shift from orange to amber-gold -- feels more generous, less urgent |
| `--primary-foreground` | `36 28% 11%` | Dark text on amber-gold buttons |
| `--muted-foreground` | `30 20% 65%` | Warmer muted text -- inviting, not faded |

New semantic accent tokens to add:

| New Token | Value | Usage |
|---|---|---|
| `--accent-warm` | `12 60% 65%` | Soft coral -- for human-focused elements (people, contributions) |
| `--accent-cool` | `158 30% 45%` | Sage green -- for growth, health, positive states |
| `--accent-glow` | `45 65% 72%` | Soft golden -- for highlights, achievements, joy moments |

Tokens to preserve unchanged:

- `--chart-2` (`165 34% 44%`): The teal provides beautiful contrast with the warm palette. Keep it.
- `--destructive`: No change needed.
- `--radius`: Keep `0.75rem` as global default; increase per-component where noted.

### Background Treatment

The current radial gradient backdrop in `globals.css` (lines 79-97) is a strong foundation. Evolution:

- Soften the orange bloom opacity slightly (from `0.2` to `0.16`).
- Shift the golden bloom hue from `44` to `40` to align with the new amber-gold primary.
- Keep the teal/green bottom bloom -- it anchors the page.
- The `body::before` screen-blended overlay should use the new accent-glow hue for the golden element.

---

## 3. Typography with Personality

### Current State

- **Sans**: Space Grotesk (loaded in `web/app/layout.tsx`, lines 9-13)
- **Mono**: IBM Plex Mono (lines 15-20)
- **Base size**: Browser default (16px implied)
- **Heading weight**: `font-semibold` used throughout `page.tsx`

**Assessment**: Space Grotesk has character but trends geometric and slightly cold at heavy weights. IBM Plex Mono is excellent -- no change needed.

### Proposed Changes

**Hero headings**: Use lighter weight. Replace `font-semibold` with `font-normal` or `font-light` on the main hero `h1`. Increase size to compensate (`text-4xl md:text-6xl`). Let the words breathe. Large size at light weight communicates confidence without shouting.

**Body text**: Keep Space Grotesk but increase the base size from 16px to 17px and line-height from the default to 1.65. Add these in `globals.css` on the `body` rule. Readability equals comfort.

- Alternative: If body text still reads too geometric after size adjustment, evaluate switching body to Inter. Keep Space Grotesk for headings only. This is a follow-up decision gate.

**Key phrase emphasis**: Use the primary amber-gold color for emphasis words instead of bold. Color draws the eye more gently than weight. Define a utility class or Tailwind color for this.

**Mono**: Keep IBM Plex Mono for code and data. No changes.

---

## 4. Landing Page Redesign

The current landing page (`web/app/page.tsx`) packs data, navigation, and onboarding into one dense scroll. The redesign separates concerns into five distinct sections, each with a clear emotional purpose.

### Section 1: THE INVITATION (full viewport height)

Replace the current hero section (lines 215-261 in `page.tsx`).

```
Section 1: THE INVITATION (full viewport height)
|-- Tagline (large, light weight): "Ideas deserve to become real."
|-- Subtitle (muted, warm): "Share what you see. Build what matters.
|   Every contribution traced from thought to impact."
|-- Soft illustration or abstract: flowing lines connecting dots (not a photo,
|   not an icon grid -- something organic that suggests connection)
|-- Single primary CTA: "Start Exploring" (amber-gold, rounded, generous padding)
|-- Secondary: "See how it works" (text link, underlined, no button)
|-- NO metrics here. No "19 ideas tracked." This is the invitation, not the report.
```

Key changes from current:
- Remove the three metric cards from hero. Move them to Section 3.
- Reduce CTAs from four buttons to one button plus one text link.
- Remove "Collaborative open source workspace" label. Replace with the tagline.
- Hero heading changes from `font-semibold text-3xl md:text-5xl` to `font-light text-4xl md:text-6xl`.

### Section 2: THREE PATHS (gentle scroll reveal)

Replace the current "Shared Journey" and "Getting Started" cards (lines 263-318).

```
Section 2: THREE PATHS (gentle scroll reveal)
|-- "Share an Insight" -- illustration + short paragraph about idea contribution
|-- "Build Something Real" -- illustration + paragraph about implementation
|-- "Back What Matters" -- illustration + paragraph about staking/investing
|-- Each card: large icon/illustration, 2-line description, subtle "Learn more ->"
```

These are not link dumps. Each path is a single concept with one illustration, two lines of description, and one "Learn more" text link. The current implementation has too many links per card.

### Section 3: THE PULSE (live but calm)

Relocate the metrics currently in the hero (lines 246-259) and the "Highest Estimated Collective Benefit" section (lines 320-369).

```
Section 3: THE PULSE (live but calm)
|-- "What's Happening Now" (not "System Status")
|-- Warm metric cards with human labels:
|   |-- "Ideas being explored" (not "Ideas tracked")
|   |-- "Value created together" (not "Total potential value")
|   |-- "People contributing" (not "Contributors")
|-- Recent activity feed (who did what, when -- human names, not IDs)
|-- Animated subtly: numbers that count up, dots that pulse, not dashboards that blink
```

Label rewrites:

| Current Label | New Label |
|---|---|
| "Ideas tracked" | "Ideas being explored" |
| "Estimated total potential value" | "Value created together" |
| "Remaining value gap" | "Room to grow" |
| "Highest Estimated Collective Benefit" | "Where help matters most" |
| "Recent Achievements" | "What people built" |

### Section 4: THE FLOW (visual, not text)

Replace the current "Shared Journey" pill list (lines 270-283).

```
Section 4: THE FLOW (visual, not text)
|-- Animated horizontal flow: Idea -> Review -> Spec -> Build -> Ship -> Impact
|-- Each step: small icon + one word + subtle connecting line
|-- When you hover a step, a tooltip shows a real example
|-- This replaces the current "Shared Journey" text-heavy card
```

The current implementation uses inline `span` elements with rounded-full borders. The redesign replaces these with a connected visual flow -- a horizontal pipeline where each node links to the next with a line or gradient, suggesting continuous movement.

### Section 5: FIRST STEPS (warm, not instructional)

Replace the current "Getting Started" ordered list and the three LANDING_PATHS cards (lines 286-416).

```
Section 5: FIRST STEPS (warm, not instructional)
|-- "You don't need to know everything. Start here."
|-- Three simple options:
|   |-- "Browse ideas" (curious? start here)
|   |-- "See the demo" (want to understand? watch this)
|   |-- "Publish your first idea" (ready? let's go)
|-- Tone: welcoming, no pressure, no "sign up now"
```

### Elements to Remove or Relocate

- **Search Projects section** (lines 372-400): Move to the Ideas page, not the landing page. Search is a task, not a welcome.
- **Advanced surfaces collapsible** (lines 418-431): Move to a site footer or settings menu. The landing page should not expose operational tooling.
- **LANDING_PATHS cards** (lines 402-416): Replace with the simpler Section 5 above.

---

## 5. Component Tone Guide

### Buttons

| Variant | Current | Proposed |
|---|---|---|
| Primary | Default shadcn/ui styling with `--primary` | Amber-gold background, dark text, `px-8 py-3`, `rounded-full`, subtle shadow. Should feel like a warm invitation, not a corporate CTA. |
| Secondary | Default shadcn/ui `variant="secondary"` | Transparent with warm border (`border-primary/40`), soft hover glow (`hover:bg-primary/10`). Feels like "there is more here if you want." |
| Ghost | Default shadcn/ui `variant="outline"` | Just text with underline on hover. Minimal. "No pressure." Remove the border. |

### Cards

Current cards use `rounded-xl border p-5`. Proposed changes:

- Increase rounding: `rounded-2xl` (16px) for all card-level containers.
- Softer borders: `border-border/40` instead of the default solid border.
- More internal padding: `p-6 md:p-8` instead of `p-5`.
- Subtle gradient backgrounds: `bg-gradient-to-b from-card/80 to-card` gives depth without weight.
- A card should feel like a comfortable space, not a data container.

### Transitions

- All hover/focus transitions: `duration-300 ease-out` (not the default 150ms). Slower equals calmer.
- Scale on hover: `hover:scale-[1.01]` (barely perceptible, but feels alive).
- Color transitions on hover: gentle warm shift, not abrupt state change.
- Add `transition-all` to interactive elements globally in `globals.css`.

### Icons

- Continue using Lucide icons. Prefer rounded variants and thinner stroke weight where available.
- Accent icons should use the amber-gold primary color, not white. They should feel highlighted, not clinical.
- Size: prefer `w-5 h-5` for inline, `w-8 h-8` for card headers. Generous but not heavy.

---

## 6. Navigation Simplification

### Current State

The site header (`web/components/site_header.tsx`) defines three navigation groups:

- `PRIMARY_NAV`: 5 items (Today, Demo, Ideas, Work, Progress)
- `EXPLORE_NAV`: 5 items (Search, Portfolio, Plans, Contribute, People)
- `TOOL_NAV`: 10 items (Usage, Automation, Remote Ops, Agent, Friction, Checks, Contributions, Assets, Import, API Health)

Total: 20 items in the header, plus 10 more in the landing page "Advanced surfaces" collapsible. This is overwhelming for new visitors.

### Proposed Structure

**Primary nav (always visible in header)**: 4 items.

| Label | Route | Contains |
|---|---|---|
| Home | `/` | The welcoming landing page |
| Ideas | `/ideas` | Browse, publish, fork (the marketplace) |
| Build | `/tasks` | Tasks, specs, progress (the workshop) |
| Community | `/contributors` | People, contributions, governance (the gathering) |

**Everything else**: Accessible through contextual links within pages, not the top nav. Pages like Usage, Automation, Remote Ops, Agent, Friction, Checks, Assets, Import, and API Health are operational tools. They belong in a secondary nav or footer, not in the primary header.

**Mobile**: Bottom tab bar with these 4 items plus a search icon. The current responsive behavior (hidden on small screens) should be replaced with a persistent bottom bar.

**Search**: Move from the landing page to a persistent search icon in the header (magnifying glass icon, opens a command palette or search overlay).

---

## 7. Core Values in Visual Language

Each core value should have a consistent visual signature used across the site.

| Value | Visual Expression | Usage Example |
|---|---|---|
| Coherence | Connected flowing lines, consistent spacing rhythm | The Flow section (Section 4), connecting lines between pipeline stages |
| Resonance | Ripple effects, concentric circles, wave patterns | Notification animations, impact indicators |
| Transparency | Glass-like card effects, visible layers, open layouts | Card `backdrop-blur`, layered z-index compositions |
| Trust | Warm glow, stable foundations, grounded elements | Footer, authentication states, verified badges |
| Giving | Outward-flowing gradients, generous whitespace, open hands metaphor | Hero section, contribution prompts, CTA areas |
| Connection | Dotted lines between elements, overlapping circles, shared borders | Graph visualizations, contributor networks |
| Joy | Accent gold highlights, subtle sparkle effects, celebration moments | Achievement cards, milestone notifications, the accent-glow token |

---

## 8. Micro-Interactions

These small moments add life without creating noise.

| Trigger | Animation | Duration |
|---|---|---|
| Idea receives a new fork | Subtle golden pulse on the idea card border | 600ms ease-out |
| Contribution is recorded | Brief warm glow on the contributor's avatar | 400ms ease-out |
| Coherence score is healthy | Gentle breathing animation (scale 1.0 to 1.02) on the score indicator | 3s infinite ease-in-out |
| Page scroll | Content fades in from below with a gentle rise (`translateY(12px)` to `0`, `opacity 0` to `1`) | 500ms ease-out, triggered at 80% viewport intersection |
| Loading states | Warm pulsing gradient (`animate-pulse` with amber-gold gradient), not a spinner | Continuous until loaded |
| Hover on flow step | Tooltip fades in with example data | 200ms ease-out |
| Number display | Count-up animation from 0 to final value | 800ms ease-out |

---

## Files to Create or Modify

This section lists the files that implementation of this design spec will touch.

### Files to Modify

| File | Changes |
|---|---|
| `web/app/globals.css` | Update CSS custom properties (color tokens), add new accent tokens, adjust body font-size and line-height, add global transition defaults, update background gradient values |
| `web/app/page.tsx` | Full restructure into 5 sections per Section 4 of this spec. Remove search, remove advanced surfaces, rewrite labels, restructure hero |
| `web/app/layout.tsx` | Potentially add Inter font import if body font decision gate approves the switch. Update metadata description to match new tone |
| `web/components/site_header.tsx` | Reduce to 4 primary nav items. Add search icon. Remove EXPLORE_NAV and TOOL_NAV from header |
| `web/components/ui/button.tsx` | Adjust default styles for primary variant (rounded-full, generous padding). Add amber-gold specific styling |
| `web/components/ui/card.tsx` | Increase default rounding, soften borders, add gradient background option |
| `web/tailwind.config.ts` | Add new color tokens (accent-warm, accent-cool, accent-glow) to the theme extension |

### Files to Create

| File | Purpose |
|---|---|
| `web/components/landing/invitation-hero.tsx` | Section 1: The Invitation hero component |
| `web/components/landing/three-paths.tsx` | Section 2: Three Paths scroll-reveal cards |
| `web/components/landing/the-pulse.tsx` | Section 3: Live metrics with human labels |
| `web/components/landing/the-flow.tsx` | Section 4: Animated horizontal value pipeline |
| `web/components/landing/first-steps.tsx` | Section 5: Welcome getting-started section |
| `web/components/mobile-tab-bar.tsx` | Mobile bottom navigation bar (4 tabs + search) |

---

## Verification

This is a design spec, not a feature spec. Verification is visual and qualitative.

- Build succeeds: `cd web && npm run build` passes with no errors after implementation.
- Lighthouse accessibility score remains above 90.
- All new color combinations pass WCAG AA contrast ratio (4.5:1 for body text, 3:1 for large text).
- The landing page loads with no layout shift (CLS < 0.1).
- Manual review: five-second test with a new visitor confirms the emotional principles (inviting, not overwhelming).

---

## Out of Scope

- Dark/light theme toggle (the site is dark-only for now; light mode is a separate effort).
- Illustration or icon creation (this spec describes what they should convey, not the assets themselves).
- Animation library selection (Framer Motion, CSS-only, or other -- left to implementation).
- Backend API changes (all data sources remain the same; only labels and presentation change).
- Mobile app (this covers responsive web only).
- Authentication flows (login/signup UX is a separate spec).

---

## Risks and Assumptions

- **Risk**: Lighter heading weights may reduce readability on low-contrast displays. Mitigation: test on multiple monitors and enforce WCAG AA minimums.
- **Risk**: Reducing nav items may frustrate power users who rely on direct header links. Mitigation: ensure all pages remain reachable via contextual links and browser URL. Add a site map in the footer.
- **Assumption**: The current warm dark palette direction is correct and should be evolved, not replaced. If user research later indicates a preference for light mode, this spec would need revision.
- **Assumption**: Space Grotesk at lighter weights still reads well at the proposed hero sizes. If not, a font swap to a humanist sans-serif (e.g., Plus Jakarta Sans) should be evaluated.

---

## Known Gaps and Follow-up Tasks

- **Decision gate**: Body font -- keep Space Grotesk or switch to Inter. Requires a side-by-side prototype comparison. Follow-up task: `task_body_font_evaluation`.
- **Asset gap**: Illustrations for the Three Paths section and the hero abstract visual are described but not created. Follow-up task: `task_landing_illustrations`.
- **Mobile tab bar**: Exact interaction patterns (haptic feedback, active state animation) need mobile device testing. Follow-up task: `task_mobile_nav_ux`.
- **Scroll animation performance**: Intersection Observer-based fade-ins need performance profiling on lower-end devices. Follow-up task: `task_scroll_animation_perf`.

---

## Decision Gates

1. **Body font**: Space Grotesk vs Inter for body text. Requires prototype. Owner: Design lead.
2. **Animation library**: CSS-only vs Framer Motion for micro-interactions. Depends on complexity of the Flow section animation. Owner: Frontend lead.
3. **Illustration style**: Abstract geometric vs organic hand-drawn for hero and Three Paths. Owner: Design lead.