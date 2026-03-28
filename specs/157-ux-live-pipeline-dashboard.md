# 157 — UX: Live pipeline dashboard

## Purpose

Provide a single place that answers: **What is the system doing right now?** New contributors see nodes, executing tasks, and recent completions. Expert contributors see queue depth, provider success rates, Thompson Sampling (prompt A/B) stats, and idea activity with lifecycle hints.

## Requirements

1. **API**: `GET /api/agent/live-pipeline` returns one JSON document aggregating:
   - Online runners (nodes) with lease-aware online status
   - Running and pending tasks, recent completions (from pipeline status)
   - Queue depth and diagnostics where available
   - Provider / model metrics (rolling window)
   - Effectiveness snapshot (throughput, success, issues summary)
   - Prompt A/B (Thompson) variant stats
   - Top ideas by runtime activity in the window, enriched with idea name and `manifestation_status` when resolvable

2. **Web**: Route `/live` renders a dashboard that consumes the aggregate endpoint, auto-refreshes on an interval, and links to `/tasks`, `/today`, and individual ideas.

3. **Navigation**: Primary nav includes “Live”; live-updates controller treats `/live` as an active polling route.

## API Contract

- **Path**: `GET /api/agent/live-pipeline`
- **Response**: JSON with at least `generated_at`, `summary`, `runners`, `execution`, `providers`, `effectiveness`, `prompt_ab`, `ideas_in_motion`, `partial_errors` (optional list of strings if a sub-source failed)

## Files to Create/Modify

- `specs/157-ux-live-pipeline-dashboard.md` (this file)
- `api/app/services/live_pipeline_service.py`
- `api/app/routers/live_pipeline_routes.py`
- `api/app/routers/agent.py` (include router)
- `web/app/live/page.tsx`
- `web/components/live/LivePipelineDashboard.tsx`
- `web/components/site_header.tsx`
- `web/components/page_context_links.tsx`
- `web/components/live_updates_controller.tsx`
- `.gitignore` (append patterns per deploy task)

## Verification

- `curl -s http://localhost:8000/api/agent/live-pipeline | jq .summary` returns JSON with numeric counts
- `/live` loads without build errors; dashboard shows sections for runners, execution, providers, expert blocks

## Risks and Assumptions

- Aggregates depend on existing services; partial failure should not 500 the whole endpoint.
- Runner and task data require the API store/DB as in other agent routes.

## Known Gaps and Follow-up Tasks

- WebSocket push for sub-second updates (optional).
- Historical sparklines for queue depth.
