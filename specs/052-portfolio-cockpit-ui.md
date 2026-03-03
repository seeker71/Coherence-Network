# Spec: Portfolio Cockpit UI

## Purpose

Provide a human interface to prioritize unanswered questions by ROI, submit answers directly, and view runtime cost by idea.

## Requirements

- [ ] Web page `/portfolio` exists and is linked from home.
- [ ] Page fetches `GET /api/inventory/system-lineage` and displays question + runtime sections.
- [ ] Page allows answering unanswered questions via `POST /api/ideas/{idea_id}/questions/answer`.

## Validation Contract

- `web` build succeeds with the new route.
- Manual check: `/portfolio` renders and answer action posts successfully.

## Files

- `web/app/portfolio/page.tsx`
- `web/app/page.tsx`

