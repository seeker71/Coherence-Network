# Spec 056: Operating Console Estimated ROI Queue

## Goal

Track the operating console estimated ROI and ensure work can be pulled automatically when it is next in the ROI queue.

## Requirements

1. `GET /api/inventory/system-lineage` must include:
   - `next_roi_work` selected by highest idea estimated ROI, then highest question ROI.
   - `operating_console` status with estimated ROI, estimated ROI rank, and whether it is next.
2. Each question row in inventory must include `idea_estimated_roi`.
3. API must expose task generation for next estimated ROI work:
   - `POST /api/inventory/roi/next-task`
   - optional `create_task=true` to enqueue agent task.
4. Web `/portfolio` must display:
   - operating console estimated ROI and rank
   - whether operating console is next
   - current next ROI work item details.

## Validation

- API tests for `next_roi_work`, `operating_console`, and ROI task endpoint.
- Web build passes with updated portfolio UI.
