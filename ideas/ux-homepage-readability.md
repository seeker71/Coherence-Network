# Homepage Readability — text nearly invisible on dark background

**ID**: ux-homepage-readability
**Parent**: user-surfaces
**Status**: implemented

## Problem

Primary interactive elements (buttons, links, chart accents) used `hsl(36 72% 42%)` in light mode — a warm gold that renders at only ~3.3:1 contrast against the warm off-white background `hsl(42 40% 96%)`. WCAG AA requires ≥4.5:1 for normal text and interactive controls.

Dark mode was already compliant (primary at L=58% gives 7.7:1 on `hsl(24 22% 11%)`).

## Fix

Lowered light-mode `--primary`, `--ring`, and `--chart-1` from L=42% to L=34%, giving a measured contrast of **~4.78:1** on the warm off-white background — comfortably above the 4.5:1 threshold.

| Token | Before | After | Contrast (on bg) |
|-------|--------|-------|-----------------|
| `--primary` (light) | `36 72% 42%` | `36 72% 34%` | 3.33 → 4.78 |
| `--ring` (light) | `36 72% 42%` | `36 72% 34%` | 3.33 → 4.78 |
| `--chart-1` (light) | `36 72% 42%` | `36 72% 34%` | 3.33 → 4.78 |

## Evidence

`api/tests/test_homepage_contrast.py` — 14 WCAG AA assertions covering dark + light palettes. All pass.

## Files Modified

- `web/app/globals.css` — `:root.light` token values
- `api/tests/test_homepage_contrast.py` — regression tests
