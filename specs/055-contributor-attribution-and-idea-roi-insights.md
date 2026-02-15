# Spec 055: Contributor Attribution and Idea ROI Insights

## Goal

Make it directly answerable which contributors drove idea/spec/implementation work (human vs machine), and which ideas have the highest/lowest ROI or highest potential where ROI is still missing.

## Requirements

1. `GET /api/inventory/system-lineage` must include contributor attribution rows from value-lineage links.
2. Each attribution row must include:
   - lineage id, idea id, spec id, role, contributor
   - perspective classification (`human`, `machine`, `unknown`)
   - valuation context (estimated cost, measured value, ROI ratio)
3. `GET /api/inventory/system-lineage` must include idea ROI insights:
   - most estimated ROI ideas
   - least estimated ROI ideas
   - most actual ROI ideas (when actual cost exists)
   - least actual ROI ideas (when actual cost exists)
   - ideas missing actual ROI with highest potential (by estimated ROI/potential)
4. `/portfolio` must render:
   - human vs machine attribution counts and sample rows
   - most/least ROI + missing highest-potential ROI signals

## Test Plan

1. Validate inventory response includes `contributors` and `roi_insights`.
2. Validate human and machine attribution are both detected from contributor identifiers.
3. Validate ROI ranking collections are present and structured.
4. Validate web build succeeds with new portfolio sections.

## Acceptance

- API tests pass with attribution + ROI sections.
- Web build passes with added portfolio UI.
