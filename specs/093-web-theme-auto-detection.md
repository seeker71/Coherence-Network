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

## Verification

- Local:
  - `cd web && npm run build`
- Manual:
  - Open web app with system light mode, verify light palette.
  - Switch system to dark mode, verify dark palette without reload logic changes.
