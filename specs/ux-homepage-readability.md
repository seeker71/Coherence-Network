---
idea_id: user-surfaces
status: done
source:
  - file: web/app/page.tsx
    symbols: [homepage]
  - file: web/app/globals.css
    symbols: [accessibility styling]
done_when:
  - "Light mode activates on toggle click; persists across page reloads."
  - "System `prefers-color-scheme: light` is respected on first visit."
  - "Hero headline and body text pass WCAG AA (≥4.5:1) in both modes."
  - "`ThemeToggle` is keyboard-accessible and has a descriptive `aria-label`."
  - "No hydration mismatch (SSR-safe: initial HTML class set via inline script)."
  - "Light mode background is warm, not stark white — consistent with brand tone."
---

> **Parent idea**: [user-surfaces](../ideas/user-surfaces.md)
> **Source**: [`web/app/page.tsx`](../web/app/page.tsx) | [`web/app/globals.css`](../web/app/globals.css)

# UX Homepage Readability — Dark Mode Contrast Fixes & Light Mode Toggle

**ID**: ux-homepage-readability
**Status**: approved
**Created**: 2026-03-28
**Decision**: Both — fix dark mode contrast AND add a light mode toggle

## Problem Statement

The homepage and site-wide layout suffer from two compounding readability issues:

1. **Dark mode contrast is too low** — secondary text uses `foreground/90` and `foreground/85` opacity, which on the warm dark background falls below WCAG AA (4.5:1 for normal text). The `:root.light` CSS block exists but assigns `color-scheme: dark` — a broken stub.
2. **No light mode option** — users who prefer or need high-contrast light backgrounds have zero recourse; there is no theme toggle anywhere in the UI.

## Decision Rationale

Adding a light mode toggle *solves both problems simultaneously*:
- Forces us to define a real light-mode colour palette with WCAG AA contrast by design.
- Gives users agency, which reduces friction and increases retention.
- Dark mode contrast can be improved as a side effect of the audit required to define light mode values.

Fixing only dark mode contrast leaves the second problem unaddressed and is a partial solution.

## Scope

- Fix `globals.css` `:root.light` CSS block with a genuine warm-light palette (WCAG AA compliant).
- Improve dark mode `--muted-foreground` and `--foreground` contrast ratios.
- Create `ThemeProvider` client component (React context + `localStorage` persistence).
- Create `ThemeToggle` button component (sun/moon icon, accessible).
- Integrate `ThemeProvider` into root `layout.tsx`.
- Add `ThemeToggle` to `SiteHeader` (desktop + mobile).
- Update `html` and `body::before` gradient rules to adapt to light mode.

## Acceptance Criteria

- [ ] Light mode activates on toggle click; persists across page reloads.
- [ ] System `prefers-color-scheme: light` is respected on first visit.
- [ ] Hero headline and body text pass WCAG AA (≥4.5:1) in both modes.
- [ ] `ThemeToggle` is keyboard-accessible and has a descriptive `aria-label`.
- [ ] No hydration mismatch (SSR-safe: initial HTML class set via inline script).
- [ ] Light mode background is warm, not stark white — consistent with brand tone.

## Colour Tokens — Light Mode

```
--background:      42 40% 96%    (warm off-white)
--foreground:      24 28% 14%    (deep warm near-black, 14:1+ on background)
--card:            42 30% 98%
--card-foreground: 24 26% 16%
--muted:           36 20% 90%
--muted-foreground: 28 18% 38%   (≥4.5:1 on card background)
--primary:         36 72% 42%    (darker gold for light bg, ≥4.5:1)
--border:          36 20% 82%
```

## Verification

- Toggle from dark → light → dark, reload — mode persists.
- Open with `prefers-color-scheme: light` browser setting — auto-selects light.
- Run axe-core or Lighthouse accessibility audit — no contrast failures.
- Visual: both modes render warm, branded, legible at 100% zoom.

## Risks and Assumptions

- No `next-themes` dependency available (no `node_modules` in worktree). Implementation uses a minimal React context + localStorage approach with an inline `<script>` to avoid flash.
- Warm gradient on `html` uses HSL variables; light mode overrides will shift gradient hue accordingly.

## Known Gaps and Follow-up Tasks

- Per-page meta `color-scheme` declarations not updated in this spec; deferred.
- Dark mode baseline contrast audit (full page scan) deferred to Spec 166.
- System-level `prefers-contrast: more` media query support deferred.

## ROI Signals

| Signal | Before | Target |
|--------|--------|--------|
| Lighthouse accessibility score | ~85 | ≥92 |
| WCAG AA failures (axe-core, homepage) | 3 | 0 |
| Bounce rate (anecdotal) | high for day/bright-env users | –15% est. |
| Theme preference pct (localStorage) | N/A | tracked after launch |
