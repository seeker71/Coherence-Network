# Spec: New Contributor Orientation

**Idea ID:** `ux-new-contributor-orientation`
**Parent:** UX & Contributor Experience (`ux-contributor-experience`)
**Status:** Draft
**Date:** 2026-03-30

## Purpose

Give first-time visitors enough context to understand what the Coherence Network is and why their ideas matter, before asking them to contribute — without adding friction for returning visitors.

## Summary

A first-time visitor to coherencycoin.com sees an idea submission form and "What idea are you holding?" but has **zero context** about what the Coherence Network is, what ideas are for, what CC (coherence credits) means, or why they should participate. The "How it works" section (Share → Grow → Value) exists but is too brief and sits below the fold on most viewports.

This spec adds three orientation elements to the homepage:

1. **Above-the-fold explainer** — a 2-sentence description immediately below the headline and above the idea form that explains what this is and why it matters.
2. **"What is this?" expandable section** — a collapsible detail block (between the explainer and the form) that answers the most common newcomer questions: What is Coherence Network? What are ideas? What is CC? How does value flow?
3. **Live proof indicators** — enhanced pulse-stat labels that contextualize the numbers with validation status (e.g., "324 ideas alive · 5 validated · 2 nodes running") so newcomers see a living, active system.

### Design decision: permanent section, not dismissible overlay

The orientation should be a **permanent, inline section** of the homepage, not a dismissible onboarding overlay. Rationale:

- Overlays create friction — they block the primary action and feel like cookie banners.
- The explainer text is only ~30 words; it adds context without stealing space.
- The expandable "What is this?" section is collapsed by default — zero visual cost for returning visitors.
- Search engines index inline content; overlays are invisible to crawlers.
- No localStorage/cookie state to manage or break.

### Measuring whether it works

The spec includes a tracking mechanism so we can tell over time if orientation is improving conversion:

- The API already tracks idea submissions. Compare the submission rate (ideas created per unique visitor session) before vs. after this change.
- Add a `data-orientation-expanded` event attribute to the "What is this?" toggle so analytics tools (if added later) can measure how often newcomers expand it.
- The `/api/ideas/count` endpoint already provides `total` and `by_status` — the live proof indicators will surface these numbers directly, making the system's health self-evident.

## Out of Scope

- User authentication or session tracking — no login required.
- Persistent dismissal state (localStorage/cookies) — the orientation is always available.
- Full redesign of the homepage layout or "How it works" section.
- Analytics/event-tracking integration (follow-up task).
- Localization / i18n.
- Changes to the idea submission form itself.
- Backend API changes — all required data already exists.

## Acceptance Criteria

1. A 2-sentence explainer paragraph is visible above the fold on a 375×667 viewport, between the `<h1>` headline and the pulse stats.
2. A "What is this?" collapsible section exists below the explainer, collapsed by default, with 4 Q&A pairs explaining the network, ideas, CC, and value flow.
3. The collapsible toggle uses `aria-expanded` for accessibility and animates smoothly.
4. The pulse stats row shows total ideas, validated ideas, and "nodes running" using data from `GET /api/ideas/count`.
5. The page renders without errors when all APIs are unreachable (graceful fallback).
6. `cd web && npm run build` succeeds with no TypeScript or lint errors.
7. The idea submission form remains unchanged in position and behavior.

## Requirements

### R1: Above-the-fold explainer text

Add a short paragraph between the `<h1>` headline and the pulse stats, visible on all viewport sizes.

**Copy (final wording may be tuned in implementation):**
> The Coherence Network turns ideas into reality through open collaboration.
> Share a thought, and the network's contributors — human and AI — will refine it, build it, and track the value created.

**Acceptance criteria:**
- Text is visible without scrolling on a 375×667 viewport (iPhone SE).
- Text renders below the `<h1>` and above the pulse stats row.
- Text uses `text-foreground/80` styling, `text-sm md:text-base`, max-width `max-w-lg`.
- No new API calls required — this is static copy.

### R2: "What is this?" expandable section

Add a collapsible disclosure element between the explainer text and the idea form. Collapsed by default.

**Trigger:** A subtle link-style toggle: "What is this? ▸" (collapsed) / "What is this? ▾" (expanded).

**Expanded content (4 short Q&A pairs):**

| Question | Answer |
|----------|--------|
| What is the Coherence Network? | An open platform where ideas are submitted, refined through questions and specs, and built by a mix of human and AI contributors. Every contribution is tracked. |
| What are ideas? | Anything you think should exist — a tool, a process, a fix, a concept. Ideas start as a sentence and grow through community attention. |
| What is CC? | Coherence Credits — a unit of value attributed to contributions. When an idea creates value, CC flows back to everyone who helped build it. |
| How does value flow? | You share an idea → contributors ask questions, write specs, implement code → the system tracks who did what → when value is realized, credit is distributed proportionally. |

**Acceptance criteria:**
- Toggle is a `<button>` with `aria-expanded` for accessibility.
- Content is hidden by default (`display: none` or height-collapse).
- Animation: smooth height transition (200ms ease-out) or CSS `details/summary`.
- Uses existing design tokens — no new colors, fonts, or spacing scales.
- Client component (requires `"use client"` or extracted to a sub-component).

### R3: Enhanced live proof indicators

Update the pulse-stat row to include the validated idea count, making the system feel more alive and credible to newcomers.

**Current stats:** `{N} ideas alive` · `{N} value created` · `{N} nodes` · `{score} coherence`

**New stats:** `{total} ideas` · `{validated} validated` · `{N} nodes running` · `{score} coherence`

The validated count comes from `GET /api/ideas/count` → `by_status.validated`.

**Acceptance criteria:**
- A new server-side fetch calls `/api/ideas/count` and extracts `total` and `by_status.validated`.
- The "ideas alive" stat becomes `{total} ideas` and a new stat `{validated} validated` is added.
- Fallback: if the count endpoint fails, fall back to `summary.total_ideas` from the existing `/api/ideas` response (current behavior).
- The word "running" is appended to nodes: `{N} nodes running`.

### R4: Preserve existing UX for returning visitors

- The explainer text is always visible but short enough (~30 words) to not impede returning visitors.
- The "What is this?" section is collapsed by default — returning visitors never see it unless they choose to.
- No localStorage, cookies, or dismissal state is needed.
- The idea submission form remains the primary call-to-action, unchanged in position or behavior.

## API Changes

### New endpoint: none

No new API endpoints are required. All data is already available:

| Data needed | Existing endpoint | Field |
|-------------|-------------------|-------|
| Total ideas | `GET /api/ideas/count` | `total` |
| Validated ideas | `GET /api/ideas/count` | `by_status.validated` |
| Node count | `GET /api/federation/nodes` | `length` of array |
| Coherence score | `GET /api/coherence/score` | `score` |

### Modified fetch: `loadIdeasCount()`

Add a new server-side fetch function in `web/app/page.tsx` that calls `/api/ideas/count` and returns `{ total, validated }`. This supplements (does not replace) the existing `loadIdeas()` call.

## Data Model

No data model changes. All data already exists in the API.

## Files to Create/Modify

- `web/app/page.tsx` — add explainer paragraph after `<h1>`, add `loadIdeasCount()` fetch, update pulse-stats to show validated count and "nodes running" label, import the new orientation component
- `web/components/orientation-disclosure.tsx` — **new file** — client component for the "What is this?" collapsible section with toggle button and Q&A content

### Files NOT modified

- `api/` — no backend changes
- `web/components/idea_submit_form.tsx` — form is unchanged
- `web/app/globals.css` — no new styles needed (uses existing Tailwind utilities)

## Verification Scenarios

### Scenario 1: Explainer text visible above the fold

**Setup:** Production deployment with orientation changes live.
**Action:** Open `https://coherencycoin.com/` in a browser at 375×667 viewport (mobile).
**Expected:**
- The headline "What idea are you holding?" is visible.
- Immediately below: "The Coherence Network turns ideas into reality through open collaboration. Share a thought, and the network's contributors — human and AI — will refine it, build it, and track the value created."
- Below the explainer: the pulse stats row.
- Below the stats: the idea submission form.
- All elements visible without scrolling.
**Edge case:** If viewport is extremely small (320×480), the explainer may push the form below the fold — acceptable, since the explainer IS the priority content for orientation.

### Scenario 2: "What is this?" toggle works

**Setup:** Homepage loaded.
**Action:** Click the "What is this?" toggle text.
**Expected:**
- Section expands with smooth animation (≤300ms).
- Four Q&A pairs are visible: "What is the Coherence Network?", "What are ideas?", "What is CC?", "How does value flow?"
- The toggle text updates its arrow indicator (▸ → ▾).
- `aria-expanded` attribute on the button changes from `"false"` to `"true"`.
**Then:** Click the toggle again.
**Expected:** Section collapses. `aria-expanded` returns to `"false"`.
**Edge case:** Rapid toggling (click 5 times fast) does not break layout or leave the section in an intermediate state.

### Scenario 3: Live proof indicators show validated count

**Setup:** API is running with ideas in the database.
**Action:**
```bash
# Verify API returns count data
curl -s https://api.coherencycoin.com/api/ideas/count
```
**Expected:** Response like `{"total":324,"by_status":{"none":242,"partial":77,"validated":5}}`
**Then:** Load `https://coherencycoin.com/` and inspect the stats row.
**Expected:**
- Shows `324 ideas` (or current total).
- Shows `5 validated` (or current validated count).
- Shows `2 nodes running` (or current node count).
- Shows coherence score.
**Edge case:** If `/api/ideas/count` returns 500 or times out, the page still renders with fallback data from `/api/ideas` summary. No blank stats, no error messages visible to the user.

### Scenario 4: Page renders when all APIs are down

**Setup:** API server is unreachable (e.g., test with `NEXT_PUBLIC_API_BASE=http://localhost:1` in dev).
**Action:** Load the homepage.
**Expected:**
- Headline renders: "What idea are you holding?"
- Explainer text renders (static content, no API needed).
- "What is this?" toggle renders and works (static content).
- Pulse stats row is hidden (no data to show — matches current behavior).
- Idea form renders (submission will fail, but the form is visible).
**Edge case:** No JavaScript errors in the console related to orientation components.

### Scenario 5: Web build succeeds

**Setup:** Clean checkout of the branch with orientation changes.
**Action:**
```bash
cd web && npm run build
```
**Expected:** Build completes with exit code 0. No TypeScript errors, no lint errors related to changed files.
**Edge case:** `npm run build` with `NODE_ENV=production` also succeeds (no dev-only imports leaking).

## Risks and Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Explainer text pushes form below fold on small phones | Medium | Low | Keep text to ~30 words; test on 375×667 viewport |
| "What is this?" animation jank on low-end devices | Low | Low | Use CSS transitions, not JS animation; `prefers-reduced-motion` media query disables animation |
| `/api/ideas/count` endpoint not deployed on production | Low | Medium | Fallback to existing `/api/ideas` summary data |
| Copy is unclear or uses jargon newcomers don't understand | Medium | Medium | Copy is deliberately plain English; can be A/B tested later |

### Assumptions

- The existing `/api/ideas/count` endpoint is deployed and returns the documented shape.
- The homepage hero section has enough vertical space for ~30 words of explainer text without major layout disruption.
- shadcn/ui's design tokens and Tailwind utilities are sufficient — no new CSS primitives needed.
- The "What is this?" Q&A content is accurate as of spec writing and may need periodic updates as the system evolves.

## Known Gaps and Follow-up Tasks

- **Analytics integration** — The `data-orientation-expanded` attribute is a hook for future analytics. No analytics tool is wired up yet. Follow-up: integrate with an event tracker to measure expansion rate.
- **A/B testing the copy** — The explainer wording is a first draft. Follow-up: test 2-3 variants and measure idea submission rate changes.
- **Localization** — All copy is English-only. Follow-up: i18n support if the network expands internationally.
- **"What is CC?" deep link** — The Q&A mentions CC but doesn't link to a dedicated page explaining the credit system. Follow-up: create `/cc` or `/about/credits` page.
- **Dismissible for logged-in users** — If authentication is added later, returning authenticated users could have the explainer auto-hidden. Not needed now since there's no auth.
