# Spec 060: High-ROI Auto-Answer and Derived Idea Generation

## Goal

Continuously answer high-ROI questions using available evidence and convert high-value answers into new tracked ideas when appropriate.

## Requirements

1. Add endpoint:
   - `POST /api/inventory/questions/auto-answer`
   - params: `limit` (1..25), `create_derived_ideas` (bool)
2. Endpoint behavior:
   - select top unanswered questions by ROI
   - answer questions when an evidence-backed template is available
   - attach measured delta when evidence quality supports it
   - report skipped questions when evidence template is unavailable
3. Derived idea generation:
   - when enabled, generate specific new ideas from answered high-ROI governance questions
   - avoid duplicates by idea id
4. Add service capability to add idea if missing, with standing-question guarantees.
5. Keep process testable and deterministic in API tests.

## Validation

- API tests verify:
  - auto-answer endpoint returns completed report
  - at least one question gets answered in default portfolio
  - derived idea(s) are created when requested
