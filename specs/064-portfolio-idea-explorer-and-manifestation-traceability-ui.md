# Spec 064: Portfolio Idea Explorer and Manifestation Traceability UI

## Purpose

Make `/portfolio` fully browseable so operators can inspect all ideas, their questions/answers, implementation/manifestation process evidence, and cost-benefit signals without being constrained to summary slices.

## Requirements

1. Add an Idea Explorer section to `/portfolio` with:
   - idea search by id/name/description
   - manifestation-status filter
   - pagination through full idea list
   - selectable idea details panel
2. Selected idea details must include:
   - value/cost and ROI (estimated and actual)
   - unanswered and answered questions with answer ROI/measured delta
   - manifestation snapshot and runtime cost row
   - implementation/manifestation process evidence from lineage links (`spec_id`, `implementation_refs`, valuation ROI)
3. UI must compile and render via web build.

## Validation

- `cd web && npm run build`
- Manual check on `/portfolio`: can browse all ideas and inspect selected idea detail sections.
