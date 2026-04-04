# Spec 093 — Web Theme Auto-Detection

## Goal

Make the web UI automatically use light or dark theme based on the user’s OS/browser preference.

## Problem

- The UI defines both light and dark design tokens, but dark mode depended on a `.dark` class that is not set automatically.
- Users in dark-preference environments still saw the light theme by default.

## Scope

- Enable automatic dark-mode token selection via `prefers-color-scheme`.
- Keep explicit class-based overrides available for future manual controls:
  - `.dark` forces dark theme,
  - `.light` forces light theme.

## Out of Scope

- Adding a manual theme toggle control in the UI.
- Persisting user theme preference in storage.

## Acceptance Criteria

1. `web/app/globals.css` applies dark token values automatically when `prefers-color-scheme: dark` matches.
2. Existing token architecture remains intact for all components.
3. `.dark` and `.light` classes continue to act as explicit overrides.
4. Browser color-scheme metadata aligns with active theme tokens.
5. `cd web && npm run build` passes.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - `web/app/globals.css` applies dark token values automatically when `prefers-color-scheme: dark` matches.
  - Existing token architecture remains intact for all components.
  - `.dark` and `.light` classes continue to act as explicit overrides.
  - Browser color-scheme metadata aligns with active theme tokens.
  - `cd web && npm run build` passes.
commands:
  - - `cd web && npm run build`
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add end-to-end browser tests for critical paths.

## Acceptance Tests

See `api/tests/test_web_theme_auto_detection.py` for test cases covering this spec's requirements.


## Verification

- Local:
  - `cd web && npm run build`
- Manual:
  - Open web app with system light mode, verify light palette.
  - Switch system to dark mode, verify dark palette without reload logic changes.

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
