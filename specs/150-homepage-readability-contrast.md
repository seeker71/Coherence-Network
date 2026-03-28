# Spec: Homepage readability — dark background body contrast

## Purpose

First-time visitors to `https://coherencycoin.com/` (route `/`) land on a warm, dark hero with amber accents. Body copy, stats labels, and form affordances were too faint against the layered gradients and fixed `body::before` bloom, so newcomers struggled to read the core question, summaries, and calls to action. This spec raises **minimum body-copy opacity to at least 0.85** (via Tailwind `text-foreground/85` or higher, or full `text-foreground`) while preserving the ambient look for headings and decorative glows. It does **not** add a light-mode toggle; that remains a follow-up (see Open questions).

## Requirements

- [x] **R1 — Body copy contrast**: All homepage (`/`) primary body text (hero description, stat labels, “How it works” descriptions, feed cards secondary lines, footer links, closing quote block, form helper text and placeholders except intentional error colors) uses foreground opacity **≥ 0.85** relative to `hsl(var(--foreground))` (e.g. `text-foreground/85`, `text-foreground/90`, or `text-foreground`).
- [x] **R2 — Design tokens**: Global CSS variables in `web/app/globals.css` are adjusted so default readable text is slightly brighter on the dark canvas (raise lightness of `--foreground` / `--muted-foreground` where used for prose) and the fixed full-screen bloom overlay is **slightly toned down** so it does not wash out text.
- [x] **R3 — Hero headline**: The main H1 remains visually prominent (full-opacity foreground); optional subtle text-shadow is allowed for separation from gradients without lowering opacity below 1.0 for the headline color.
- [x] **R4 — API-backed “proof” unchanged**: Homepage continues to consume existing public endpoints; no breaking changes to response shapes.

## Research Inputs (Required)

- `2024-2025` — [WCAG 2.2 Understanding Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) — informs contrast intent (implementation uses design tokens + opacity classes, not automated WCAG measurement in CI).
- `2025-03-25` — Project `web/app/page.tsx` + `web/app/globals.css` — baseline UI before this change.

## Task Card (Required)

```yaml
goal: Make homepage body text readable on dark background (opacity ≥ 0.85) without losing warm aesthetic.
files_allowed:
  - specs/150-homepage-readability-contrast.md
  - web/app/globals.css
  - web/app/page.tsx
  - web/components/idea_submit_form.tsx
  - api/tests/test_ui_readability.py
done_when:
  - pytest api/tests/test_ui_readability.py passes
  - Grep shows no homepage/footer body line below text-foreground/85 except decorative pings or error UI
commands:
  - cd /Users/ursmuff/source/Coherence-Network/api && .venv/bin/pytest -v tests/test_ui_readability.py
  - cd /Users/ursmuff/source/Coherence-Network/web && npm run build
constraints:
  - Modify only files_allowed; no light-mode toggle in this spec
```

## API Contract (if applicable)

No API contract changes. Homepage continues to use:

| Method | Path | Use on `/` |
|--------|------|------------|
| GET | `/api/ideas` | Summary + list fallback |
| GET | `/api/ideas/resonance?window_hours=72&limit=3` | Recent activity |
| GET | `/api/coherence/score` | Coherence stat |
| GET | `/api/federation/nodes` | Node count |

**Response shapes**: unchanged; must remain compatible with `web/app/page.tsx` types.

## Data Model (if applicable)

N/A — no model changes.

## Files to Create/Modify

- `specs/150-homepage-readability-contrast.md` — this spec
- `web/app/globals.css` — foreground/muted tokens; optional `body::before` strength
- `web/app/page.tsx` — hero, sections, footer classes for ≥ `/85` body copy; hero H1 clarity
- `web/components/idea_submit_form.tsx` — placeholder/input text classes for ≥ `/85`
- `api/tests/test_ui_readability.py` — contract tests (repo-root paths, CSS/token assertions)

## Evidence (measurable artifact)

- **Decision**: Dark-mode contrast fix only (no light-mode toggle in this delivery); toggle deferred — see Open Questions table.
- **Proof**: CI-style contract — `api/tests/test_ui_readability.py` asserts `globals.css` tokens (including softened `body::before` bloom), `page.tsx` opacity floor, and `idea_submit_form.tsx` placeholder/body classes.
- **Human review**: [WCAG 2.2 Understanding Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) (design uses token + opacity classes; automated WCAG measurement not in CI).

## ROI signals (idea `ux-homepage-readability` ↔ spec 150)

Tracked as value-vs-cost for portfolio / specs UI (`estimated_roi` = `potential_value / estimated_cost`, `actual_roi` = `actual_value / actual_cost` when costs are recorded):

| Signal | Value | Basis |
|--------|------:|--------|
| `potential_value` | 24 | Reduced bounce / faster comprehension on first-run `/` |
| `estimated_cost` | 3 | CSS + homepage class sweep + contract tests |
| `estimated_roi` | 8.0 | 24 / 3 |
| `actual_value` (post-ship) | TBD | e.g. engagement proxy or audit re-grade |
| `actual_cost` (post-ship) | TBD | engineer time or pipeline minutes |
| `actual_roi` | TBD | after actuals |

## Acceptance Tests

- `api/tests/test_ui_readability.py::test_get_coherence_score_endpoint`
- `api/tests/test_ui_readability.py::test_homepage_readability_contract_files`
- `api/tests/test_ui_readability.py::test_homepage_readability_page_classes`
- `api/tests/test_ui_readability.py::test_homepage_readability_css_tokens`

## Verification

```bash
cd api && .venv/bin/pytest -v tests/test_ui_readability.py
cd web && npm run build
```

## Verification Scenarios

Reviewers may run these against **production** (`https://coherencycoin.com`) or **local** (`http://localhost:3000` with API up).

### Scenario 1 — Full read path for homepage data (create → read → update → list)

- **Setup**: API reachable; public **POST** `/api/ideas` (same as landing form) creates ideas; **PATCH** `/api/ideas/{id}` requires `X-API-Key` (use deploy key or `dev-key` in local tests).
- **Action**:
  1. `curl -sS -X POST "https://api.coherencycoin.com/api/ideas" -H "Content-Type: application/json" -d '{"id":"verify-read-150","name":"Readability check","description":"Spec 150 verification","potential_value":10,"estimated_cost":1,"confidence":0.5,"manifestation_status":"none"}'`
  2. `curl -sS "https://api.coherencycoin.com/api/ideas/verify-read-150"`
  3. `curl -sS -X PATCH "https://api.coherencycoin.com/api/ideas/verify-read-150" -H "Content-Type: application/json" -H "X-API-Key: $COHERENCE_API_KEY" -d '{"manifestation_status":"partial"}'`
  4. `curl -sS "https://api.coherencycoin.com/api/ideas" | head -c 2000`
- **Expected**:
  1. HTTP **201** with JSON containing `"id":"verify-read-150"` (or 409 if id already exists — then GET must still work).
  2. HTTP **200** with same `id` and `name` matching POST.
  3. HTTP **200** and JSON shows `"manifestation_status":"partial"` (or other accepted enum value).
  4. HTTP **200** and response body includes `verify-read-150` in the ideas list or embedded summary.
- **Edge**: POST same `id` again → **409** conflict (not 500). PATCH without `X-API-Key` → **401**. GET `/api/ideas/nonexistent-uuid-xyz` → **404** (not 500).

### Scenario 2 — Coherence score used on homepage

- **Setup**: None.
- **Action**: `curl -sS "https://api.coherencycoin.com/api/coherence/score"`
- **Expected**: HTTP **200**, JSON with numeric `score` where `0.0 <= score <= 1.0`, plus `signals_with_data`, `total_signals`, `computed_at`.
- **Edge**: If API maintenance returns **503**, note deploy health; homepage should still render without crashing (client already tolerates null).

### Scenario 3 — Static contract: homepage source uses minimum body opacity

- **Setup**: Repository at known revision.
- **Action**: `cd api && .venv/bin/pytest -v tests/test_ui_readability.py`
- **Expected**: All tests **passed**; asserts `web/app/page.tsx` and `globals.css` meet token/class rules documented in tests.
- **Edge**: If a developer lowers opacity below threshold, tests **fail** until implementation is fixed (tests are not weakened to pass).

### Scenario 4 — Resonance feed error handling

- **Setup**: None.
- **Action**: `curl -sS -o /dev/null -w "%{http_code}" "https://api.coherencycoin.com/api/ideas/resonance?window_hours=72&limit=3"`
- **Expected**: HTTP **200** with JSON array (possibly empty) — homepage treats empty as fallback to top ideas.
- **Edge**: `window_hours=-1` or invalid → **422** or documented validation error (not 500).

### Scenario 5 — Browser spot-check (homepage only)

- **Setup**: Open `/` in Chromium/Safari.
- **Action**: Visually confirm hero subtext, stats row, “How it works” descriptions, feed secondary text, footer tagline, and idea form placeholders are readable against background; headings remain warm/ambient.
- **Expected**: Body copy readable without straining; no new light-mode toggle required for this spec.

## Out of Scope

- Light/dark theme toggle (decision: **fix dark-mode contrast first**; toggle is a separate spec).
- Changing non-home routes (`/ideas`, `/resonance`, etc.) except shared tokens in `globals.css` that affect all pages.
- Automated visual regression / Percy screenshots (optional follow-up).

## Open Questions (from task)

| Question | Decision |
|----------|----------|
| Light mode toggle vs dark-only fix? | **Dark contrast fix only** in this spec; toggle deferred. |
| How to show proof it’s working over time? | **Existing**: coherence score + live stats on hero; **extend later**: analytics on bounce rate, or scheduled contrast audit in CI — document in Known Gaps. |

## Risks and Assumptions

- **Assumption**: Slightly brighter `--foreground` and weaker `body::before` do not break other pages; if a page looked too bright, follow-up can scope tokens to `main` wrappers only.
- **Risk**: Over-brightening mutes brand warmth — mitigate by small L% steps and keeping amber accents unchanged.

## Known Gaps and Follow-up Tasks

- Add optional **readability lint** (grep or stylelint) in CI for `text-foreground/70` on marketing pages.
- Consider **prefers-contrast: more** media query for system high-contrast users.
- Light mode toggle spec (cross-link when filed).

## Failure/Retry Reflection

- **Failure mode**: Production CSS cached by CDN — users may need hard refresh after deploy.
- **Next action**: Invalidate Cloudflare cache or wait for TTL if contrast fix not visible immediately.

## See also

- `specs/093-web-theme-auto-detection.md` — related theme work (out of scope here).
