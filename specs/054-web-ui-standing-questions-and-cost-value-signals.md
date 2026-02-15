# Spec 054: Web UI Standing Questions and Cost/Value Signals

## Goal

Ensure the web UI is continuously improved with explicit standing questions and measurable cost/value signals so unknown gaps close over time.

## Requirements

1. Portfolio ideas must include a dedicated `web-ui-governance` idea.
2. `web-ui-governance` must include these standing questions:
   - How can we improve the UI?
   - What is missing from the UI for machine and human contributors?
   - Which UI element has the highest actual value and least cost?
   - Which UI element has the highest cost and least value?
3. Existing persisted idea portfolios must be auto-migrated to include missing default ideas.
4. `/portfolio` must surface web UI standing questions and allow answering them.
5. `/portfolio` must show UI element cost/value rankings derived from runtime telemetry:
   - highest actual value / least cost
   - highest cost / least value
6. Rankings must be based on currently measurable data and clearly indicate proxy-based value when direct value is unavailable.

## API/Model Notes

- Reuse existing endpoints:
  - `GET /api/inventory/system-lineage`
  - `GET /api/runtime/events`
  - `POST /api/ideas/{idea_id}/questions/answer`
- No new endpoint required for initial delivery.

## Test Plan

1. Verify `web-ui-governance` appears in `GET /api/ideas`.
2. Verify all four required web UI questions are present.
3. Verify legacy portfolio files are migrated with missing default ideas.
4. Verify `/portfolio` builds and type-checks.

## Acceptance

- API tests pass with web UI governance defaults and migration behavior.
- Web build succeeds.
- Human operators can inspect and answer web UI standing questions directly in `/portfolio`.
