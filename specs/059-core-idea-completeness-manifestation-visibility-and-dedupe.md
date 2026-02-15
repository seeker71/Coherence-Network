# Spec 059: Core Idea Completeness, Manifestation Visibility, and Question Dedupe

## Goal

Close blind spots where core system ideas/components are missing from portfolio, manifestation status is not easily inspectable, and duplicate questions persist.

## Requirements

1. Portfolio defaults must include core ideas:
   - overall system
   - API/runtime component
   - web interface component
   - agent pipeline component
   - value attribution component
2. Existing persisted portfolio files must auto-migrate to include missing core ideas.
3. Idea open questions must be deduplicated automatically on load (normalized text match).
4. `GET /api/inventory/system-lineage` must include `manifestations`:
   - counts by status
   - full items list
   - missing manifestation list
5. Inventory issue scanning must detect:
   - missing core ideas
   - missing core manifestations
6. Monitor integration must surface those issues automatically.
7. `/portfolio` must let humans browse all ideas and manifestation status.

## Validation

- API tests validate core idea presence/migration and dedupe behavior.
- API tests validate manifestation output and issue/evidence checks.
- Web build validates manifestation browsing UI.
