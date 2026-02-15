# Spec 057: Inventory Issue Detection and Auto-Tasking

## Goal

Automatically detect inventory integrity issues (starting with duplicate idea questions) and create remediation tasks without manual triage.

## Requirements

1. `GET /api/inventory/system-lineage` must include quality issue output for duplicate questions:
   - `quality_issues.duplicate_idea_questions.count`
   - `quality_issues.duplicate_idea_questions.groups[]`
2. Add scan endpoint:
   - `POST /api/inventory/issues/scan`
   - `create_tasks=true` creates a heal task for detected issues.
3. Task creation from scan must be deduplicated (reuse existing open task with same issue signature).
4. Pipeline monitor (`api/scripts/monitor_pipeline.py`) must call scan endpoint each cycle and surface issue condition in monitor output.

## Validation

- API tests verify duplicate detection and task-creation dedupe behavior.
- Monitor script compiles and scan route is callable.
