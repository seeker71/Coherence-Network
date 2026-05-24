---
idea_id: user-surfaces
status: done
source:
  - file: web/app/page.tsx
    symbols: [Home]
  - file: web/app/globals.css
    symbols: []
done_when:
  - "Light mode activates on toggle click; persists across page reloads."
  - "System `prefers-color-scheme: light` is respected on first visit."
  - "Hero headline and body text pass WCAG AA (≥4.5:1) in both modes."
  - "`ThemeToggle` is keyboard-accessible and has a descriptive `aria-label`."
  - "No hydration mismatch (SSR-safe: initial HTML class set via inline script)."
  - "Light mode background is warm, not stark white — consistent with brand tone."
  - 'file_exists("web/app/page.tsx")'
  - 'symbol_in_file("web/app/page.tsx", "Home")'
  - 'file_exists("web/app/globals.css")'
test: "cd web && npm run test -- tests/theme-toggle.test.ts"
---

> **Parent idea**: [user-surfaces](../ideas/user-surfaces.md)
> **Source**: [`web/app/page.tsx`](../web/app/page.tsx) | [`web/app/globals.css`](../web/app/globals.css)

# UX Homepage Readability — Dark Mode Contrast Fixes & Light Mode Toggle

**ID**: ux-homepage-readability
**Status**: approved
**Created**: 2026-03-28
**Decision**: Both — fix dark mode contrast AND add a light mode toggle

## Purpose

Bring the homepage to WCAG AA contrast in both colour modes and give visitors a real light-mode option alongside the existing dark mode. Before this work, secondary text in dark mode fell below the 4.5:1 contrast threshold, and the `:root.light` CSS block was a broken stub that assigned `color-scheme: dark`. Adding a real light-mode palette and a user-controlled `ThemeToggle` solves both problems in one breath — the audit required to define light-mode values surfaces dark-mode contrast gaps as a side effect, and visitors who need or prefer light backgrounds gain agency.

## Requirements

- [x] **R1**: Fix `globals.css` `:root.light` CSS block with a genuine warm-light palette (WCAG AA compliant).
- [x] **R2**: Improve dark mode `--muted-foreground` and `--foreground` contrast ratios above 4.5:1.
- [x] **R3**: Create `ThemeProvider` client component (React context + `localStorage` persistence).
- [x] **R4**: Create `ThemeToggle` button component (sun/moon icon, accessible).
- [x] **R5**: Integrate `ThemeProvider` into root `layout.tsx` and add `ThemeToggle` to `SiteHeader` (desktop + mobile).
- [x] **R6**: Update `html` and `body::before` gradient rules to adapt to light mode.

## Files to Create/Modify

- `web/app/page.tsx` — homepage Server Component (rendered through `Home` default export)
- `web/app/globals.css` — `:root` and `:root.light` CSS variable blocks
- `web/app/layout.tsx` — wraps the tree with `ThemeProvider`
- `web/components/theme/ThemeProvider.tsx` — context + localStorage persistence
- `web/components/theme/ThemeToggle.tsx` — sun/moon toggle button
- `web/components/SiteHeader.tsx` — integration point for `ThemeToggle`
- `api/tests/test_homepage_contrast.py` — WCAG AA contrast regression suite

## Out of Scope

- Per-page `meta name="color-scheme"` declarations beyond the root scheme.
- A full site-wide dark-mode contrast audit beyond the homepage; tracked separately.
- `prefers-contrast: more` media-query support.

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

Verified by `api/tests/test_homepage_contrast.py` (14 WCAG AA contrast assertions).

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

## Acceptance Tests

See `api/tests/test_homepage_contrast.py` for the 14 WCAG AA contrast assertions covering both dark and light palettes.

## Verification

```bash
python3 -m pytest api/tests/test_homepage_contrast.py -x -v
```

- Toggle from dark → light → dark, reload — mode persists.
- Open with `prefers-color-scheme: light` browser setting — auto-selects light.
- Run axe-core or Lighthouse accessibility audit — no contrast failures.
- Visual: both modes render warm, branded, legible at 100% zoom.

## Risks and Assumptions

- No `next-themes` dependency available (no `node_modules` in worktree). Implementation uses a minimal React context + localStorage approach with an inline `<script>` to avoid flash.
- Warm gradient on `html` uses HSL variables; light mode overrides will shift gradient hue accordingly.

## Known Gaps and Follow-up Tasks

- [ ] **Per-page meta follow-up**: Update per-page `color-scheme` meta declarations once a sibling spec calls for them.
- [ ] **Site-wide contrast audit follow-up**: Run the full-site dark-mode contrast scan tracked in Spec 166.
- [ ] **High-contrast follow-up**: Add `prefers-contrast: more` media-query support when accessibility feedback names it.

## ROI Signals

| Signal | Before | Target |
|--------|--------|--------|
| Lighthouse accessibility score | ~85 | ≥92 |
| WCAG AA failures (axe-core, homepage) | 3 | 0 |
| Bounce rate (anecdotal) | high for day/bright-env users | –15% est. |
| Theme preference pct (localStorage) | N/A | tracked after launch |

## Outcome

Lowered light-mode `--primary`, `--ring`, and `--chart-1` from L=42% to L=34%, giving a measured contrast of **~4.78:1** on the warm off-white background — above the 4.5:1 threshold. Dark mode was already compliant (primary at L=58% gives 7.7:1 on `hsl(24 22% 11%)`).

| Token | Before | After | Contrast (on bg) |
|-------|--------|-------|-----------------|
| `--primary` (light) | `36 72% 42%` | `36 72% 34%` | 3.33 → 4.78 |
| `--ring` (light) | `36 72% 42%` | `36 72% 34%` | 3.33 → 4.78 |
| `--chart-1` (light) | `36 72% 42%` | `36 72% 34%` | 3.33 → 4.78 |

Regression coverage: `api/tests/test_homepage_contrast.py` — 14 WCAG AA assertions covering dark + light palettes. All pass.
