# Spec 091: Web Live Refresh and Link Parity

## Goal

Make the web UI behave like a modern operational interface:

1. pages auto-refresh when new runtime data arrives;
2. UI reloads after web deployment version changes;
3. key entity pages are cross-linked for contributor navigation (contributors, contributions, assets, tasks, ideas, flow, gates).

## Requirements

1. Add a shared live-update controller in layout with poll-driven refresh.
2. Add a reusable live-refresh hook for client pages with API-driven data.
3. Wire live-refresh into portfolio, contributors, contributions, assets, tasks, friction, project detail, and gates pages.
4. Add filterable links across contributor/contribution/asset/task pages via query parameters.
5. Ensure all changed pages still pass production build checks.

## Validation

- `cd web && npm run build`
- Manual: verify live-update indicator toggles ON/OFF and pages update without manual reload.
