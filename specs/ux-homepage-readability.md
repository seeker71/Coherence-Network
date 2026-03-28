# Spec: UX Homepage Readability (ux-homepage-readability)

**Spec ID**: ux-homepage-readability
**Status**: Active
**Author**: product-manager agent
**Date**: 2026-03-28
**Priority**: High
**Supersedes**: specs/150-homepage-readability-contrast.md (that spec was ambiguous — this one is definitive)

---

## Summary

First-time visitors landing on `https://coherencycoin.com/` (route `/`) experience a warm, dark hero
with amber accents. The previous implementation attempt failed because the spec was vague about:

1. Which exact CSS token values to set in `globals.css`.
2. Which exact Tailwind opacity classes are required vs. forbidden in each file.
3. What the test assertions must check.
4. The boundary between "decorative" elements (allowed below `/85`) and "body copy" (must be `/85` or above).

This spec fixes those gaps with concrete values, exact file paths, line-by-line change instructions,
and test assertions that match implementation exactly.

### What Done Looks Like

- `web/app/globals.css` contains `--foreground: 38 32% 93%` and `--muted-foreground: 34 22% 90%`.
- `web/app/globals.css` contains a `.hero-headline` class with `color: hsl(var(--foreground))`.
- `web/app/globals.css` contains `hsl(28 92% 74% / 0.05)` in the `body::before` bloom rule.
- `web/app/page.tsx` uses class `hero-headline` on the `<h1>` element.
- `web/app/page.tsx` uses only `text-foreground`, `text-foreground/90`, or `text-foreground/85`
  for all body copy — **no** `text-foreground/70` or lower on prose text.
- `web/components/idea_submit_form.tsx` uses `placeholder:text-foreground/85` and no `text-foreground/70`.
- All four tests in `api/tests/test_ui_readability.py` pass.

---

## Problem Statement

The homepage hero sits atop layered gradients and a fixed `body::before` bloom overlay. The original
design used `text-foreground/70` or unstyled inherited text for body copy, which rendered too faint
against the warm backdrop. Newcomers could not read the core value proposition, stat labels, and
calls to action.

The fix is minimal: raise prose opacity to ≥ `/85`, tighten the CSS design tokens for foreground/
muted-foreground, and soften the bloom overlay. These are cosmetic-only changes — no API contract
changes, no new endpoints, no database migrations.

---

## Requirements

### R1 — CSS Token Values (globals.css)

`web/app/globals.css` `:root` block MUST contain exactly these token values (already in place from
prior work — do not regress them):

```css
--foreground: 38 32% 93%;
--muted-foreground: 34 22% 90%;
```

The `.hero-headline` class MUST exist in `globals.css`:

```css
.hero-headline {
  color: hsl(var(--foreground));
  text-shadow: 0 2px 28px hsl(20 40% 6% / 0.55);
}
```

The `body::before` bloom overlay MUST use softened opacities — the first gradient stop MUST be
`hsl(28 92% 74% / 0.05)` (not higher, which would wash out text):

```css
body::before {
  background:
    radial-gradient(520px 340px at 14% 24%, hsl(28 92% 74% / 0.05), transparent 72%),
    ...;
}
```

### R2 — Hero Headline Class (page.tsx)

The `<h1>` in the hero section MUST have class `hero-headline`. Example:

```tsx
<h1 className="hero-headline text-3xl md:text-5xl lg:text-6xl font-normal ...">
```

### R3 — Body Copy Opacity Floor (page.tsx)

All prose text in `web/app/page.tsx` MUST use one of:
- `text-foreground` (full opacity, for headings and emphasis)
- `text-foreground/90` (90% opacity, for secondary body copy and labels)
- `text-foreground/85` (85% opacity, for tertiary links and footer secondary copy)

**Forbidden in page.tsx body copy**: `text-foreground/70`, `text-foreground/60`, or lower.

Decorative elements (animated ping dots, skeleton shimmer, error color text) are exempt from this rule.

### R4 — Form Component Opacity (idea_submit_form.tsx)

`web/components/idea_submit_form.tsx` MUST:
- Use `placeholder:text-foreground/85` on `<textarea>` and `<input>` elements.
- Use `text-foreground/90` on form body text.
- NOT use `text-foreground/70` anywhere in the file.

### R5 — API Contract Unchanged

The homepage continues to consume these endpoints without modification:

| Method | Path | Use |
|--------|------|-----|
| GET | `/api/ideas` | Idea count and summary stats |
| GET | `/api/ideas/resonance?window_hours=72&limit=3` | Recent activity feed |
| GET | `/api/coherence/score` | Coherence score stat |
| GET | `/api/federation/nodes` | Node count stat |

Response shapes are **frozen** — any change to these shapes requires a separate spec.

---

## Files to Create or Modify

| File | Action | Scope of Change |
|------|--------|----------------|
| `web/app/globals.css` | Modify | CSS tokens `:root`, `.hero-headline` rule, `body::before` bloom |
| `web/app/page.tsx` | Modify | Apply `hero-headline` class; replace any `text-foreground/<85` on prose |
| `web/components/idea_submit_form.tsx` | Modify | Apply `placeholder:text-foreground/85`; remove `text-foreground/70` if present |
| `api/tests/test_ui_readability.py` | Modify / Create | Tests matching the exact assertions below |

**Do not create new files.** All changes fit in the four files above.

---

## Exact Test Assertions

The file `api/tests/test_ui_readability.py` MUST contain tests with these exact assertions.
Do not weaken these assertions to make tests pass — fix the implementation instead.

### Test 1 — `test_get_coherence_score_endpoint`

```python
response = client.get("/api/coherence/score")
assert response.status_code == 200
data = response.json()
assert "score" in data
assert "signals_with_data" in data
assert "total_signals" in data
assert "computed_at" in data
assert 0.0 <= data["score"] <= 1.0
```

Purpose: Proves the homepage stat source is healthy.

### Test 2 — `test_homepage_readability_css_tokens`

```python
css_path = REPO_ROOT / "web" / "app" / "globals.css"
assert css_path.is_file()
css = css_path.read_text(encoding="utf-8")
assert "--foreground: 38 32% 93%" in css
assert "--muted-foreground: 34 22% 90%" in css
assert ".hero-headline" in css
assert "hsl(28 92% 74% / 0.05)" in css
```

Purpose: Proves CSS tokens and hero headline class are correctly set. Fails if a developer
accidentally reverts the lightness values or removes the hero-headline rule.

### Test 3 — `test_homepage_readability_page_classes`

```python
import re
page_path = REPO_ROOT / "web" / "app" / "page.tsx"
assert page_path.is_file()
content = page_path.read_text(encoding="utf-8")
assert "hero-headline" in content
assert "text-foreground/90" in content
for match in re.findall(r"text-foreground/(\d+)", content):
    assert int(match) >= 85, f"Found text-foreground/{match} — minimum allowed is 85"
```

Purpose: Ensures no prose element falls below the 85% opacity floor. Fails if any
`text-foreground/70` (or lower) is added to page.tsx.

### Test 4 — `test_idea_submit_form_readability`

```python
form_path = REPO_ROOT / "web" / "components" / "idea_submit_form.tsx"
assert form_path.is_file()
content = form_path.read_text(encoding="utf-8")
assert "placeholder:text-foreground/85" in content
assert "text-foreground/90" in content
assert "text-foreground/70" not in content
```

Purpose: Proves the idea submission form meets the opacity floor.

---

## Verification

### Primary command

Run from the repository root:

```bash
cd api && .venv/bin/pytest -v tests/test_ui_readability.py
```

Expected output (all four tests must pass):

```
tests/test_ui_readability.py::test_get_coherence_score_endpoint PASSED
tests/test_ui_readability.py::test_homepage_readability_css_tokens PASSED
tests/test_ui_readability.py::test_homepage_readability_page_classes PASSED
tests/test_ui_readability.py::test_idea_submit_form_readability PASSED

4 passed in X.XXs
```

### Secondary command (build check)

```bash
cd web && npm run build
```

Expected: Zero TypeScript errors. Zero build failures.

---

## Verification Scenarios

### Scenario 1 — CSS token regression guard

**Setup**: Repo checked out, `web/app/globals.css` present.

**Action**:
```bash
grep -n "foreground" web/app/globals.css | grep "\-\-foreground:\|muted-foreground:"
```

**Expected output** (exact strings):
```
5:    --foreground: 38 32% 93%;
14:    --muted-foreground: 34 22% 90%;
```

**Why it matters**: If `--foreground` lightness is lowered (e.g., back to `38 32% 78%`), body copy
becomes unreadable on the dark canvas. This grep is the fastest sanity check before running tests.

---

### Scenario 2 — Opacity floor scan (no prose below /85)

**Setup**: Repo checked out, `web/app/page.tsx` present.

**Action**:
```bash
grep -n "text-foreground/" web/app/page.tsx | grep -v "text-foreground/8[5-9]\|text-foreground/9[0-9]\|hover:text-foreground\|text-foreground "
```

**Expected output**: Empty (no lines printed). Any printed line represents a violation.

**Edge case**: `hover:text-foreground` transition classes are allowed (they raise opacity on hover,
not lower it). The grep above correctly excludes them.

---

### Scenario 3 — Form opacity check

**Setup**: Repo checked out.

**Action**:
```bash
grep -n "text-foreground/7" web/components/idea_submit_form.tsx
```

**Expected output**: Empty (no matches). Any match is a violation.

---

### Scenario 4 — API health (homepage data contract)

**Setup**: API running locally or production reachable.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/coherence/score | python3 -c \
  "import json,sys; d=json.load(sys.stdin); assert 0.0<=d['score']<=1.0; print('OK', d['score'])"
```

**Expected output**:
```
OK 0.XX
```

**Edge case**: If API is unreachable, the homepage falls back gracefully (null score renders as
`—` in the UI). This is acceptable for the frontend — the test above verifies API health separately.

---

### Scenario 5 — Browser smoke check

**Setup**: `http://localhost:3000` running with API.

**Actions**:
1. Open `/` in a browser.
2. Inspect hero body text (`text-foreground/90`): should be clearly legible against warm background.
3. Inspect idea form textarea placeholder: visible grey-amber text at 85% opacity.
4. Inspect footer secondary links: `text-foreground/85` — readable.
5. Inspect the `<h1>` hero headline: should be full-brightness with faint text-shadow for depth.

**Expected**: All prose text readable without straining. Warm amber bloom still visible in hero
as ambient decoration — but not washing out text.

---

## Boundary Definitions (Allowed vs. Forbidden)

This table removes the ambiguity from the prior spec:

| Element type | Min opacity | Example class |
|--------------|-------------|---------------|
| Hero H1 headline | 100% (full) | `hero-headline` (CSS class) |
| Hero body copy | 90% | `text-foreground/90` |
| Stat labels and values | 90% | `text-foreground/90` |
| Feed card primary line | 100% | `text-foreground` |
| Feed card secondary line | 90% | `text-foreground/90` |
| Footer primary links | 90% | `text-foreground/90` |
| Footer secondary links | 85% | `text-foreground/85` |
| Form textarea text | 90% | `text-foreground/90` |
| Form placeholder text | 85% | `placeholder:text-foreground/85` |
| Decorative pings / pulses | Any | Exempt |
| Error/destructive text | Any | Exempt |
| Hover state transitions (`hover:text-foreground`) | Any | Exempt (raises opacity) |

---

## Out of Scope

- Light/dark mode toggle — separate spec (see `specs/093-web-theme-auto-detection.md`).
- Other routes (`/ideas`, `/resonance`, `/contribute`) — only `/` and its form component.
- Automated visual regression / Percy screenshots.
- WCAG AA automated scoring in CI — contrast is enforced via opacity floor in tests, not external tooling.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Developer adds a `text-foreground/70` class in future (opacity regression) | Medium | Test 3 (`test_homepage_readability_page_classes`) blocks it in CI |
| `--foreground` token reverted by a global CSS refactor | Low | Test 2 (`test_homepage_readability_css_tokens`) blocks it |
| Build fails due to TypeScript error in page.tsx | Low | `npm run build` in CI catches it |
| `idea_submit_form.tsx` opacity lowered for "softer" look | Medium | Test 4 (`test_idea_submit_form_readability`) blocks it |

**Assumption**: The four test files (`page.tsx`, `globals.css`, `idea_submit_form.tsx`,
`test_ui_readability.py`) are the only files that need changes. If another component on the homepage
also has low-opacity prose text, it must be addressed in a follow-up spec scoped to that component.

---

## Known Gaps and Follow-up Tasks

- **Gap**: The opacity floor check in `test_homepage_readability_page_classes` scans only `page.tsx`.
  If low-opacity text is added in a shared component imported by `page.tsx`, it won't be caught.
  Follow-up: extend grep scan to cover all components imported by the homepage.

- **Gap**: No automated browser contrast measurement (e.g., axe-core). The opacity-floor approach
  is a proxy for contrast, not a direct WCAG measurement. Acceptable for this spec.

- **Gap**: The `--muted-foreground` token affects all pages, not just `/`. If a different page relies
  on a lower value, raising it here may change that page's appearance. Monitor after deploy.

---

## Failure / Retry Reflection

The previous implementation attempt failed because the spec said "raise opacity to ≥ 0.85" without
specifying:
- Which exact CSS token values to use (implementer guessed wrong values for `--foreground`).
- Which file paths contain the `idea_submit_form.tsx` component (it is in `web/components/`, not
  `web/app/`).
- What the tests must assert (tests were written to match a wrong implementation).
- How to distinguish "decorative" elements (exempt) from "body copy" (must meet floor).

This spec resolves all four ambiguities. **Do not modify tests to make them pass. Fix the
implementation.**

---

## Decision Gates

- **Token values**: The exact HSL values (`38 32% 93%`, `34 22% 90%`) were chosen to maintain the
  warm amber palette while ensuring ≥ 90% visual brightness on the dark canvas. If the design
  direction changes (e.g., cooler palette), new token values require a new spec — do not edit these
  in place without spec coverage.

- **Opacity floor at 85%**: The 85% minimum was chosen because `/80` and below became unreadable
  in user testing on the layered gradient backdrop. If the backdrop gradient is significantly
  lightened in the future, this floor can be lowered — but requires a new spec with justification.
