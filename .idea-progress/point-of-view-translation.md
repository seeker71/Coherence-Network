# Progress — point-of-view-translation

## Completed phases

- **2026-03-29 — Spec task (task_bb7f0fb0298)**: Added `specs/point-of-view-translation.md` — full product spec aligned with spec 181, existing `translate_service`, `/api/news/feed?pov=`, and ideas translation routes. Includes Verification Scenarios for production curl checks, evidence section, ROI/proof requirements, Risks, Known Gaps.

## Current task

(none — spec task complete pending git commit)

## Key decisions

- **Canonical REST shape**: Spec 181 remains the implementation reference; `point-of-view-translation.md` is the idea-level contract and links to 181.
- **News POV**: Confirmed as rank/filter only; no rewrite of article bodies in scope.

## Blockers

- Git commit must be performed outside agent if shell remains blocked.
