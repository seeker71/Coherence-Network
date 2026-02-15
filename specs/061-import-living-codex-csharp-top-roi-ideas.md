# Spec 061: Import Living-Codex-CSharp Top ROI Ideas and Specs

## Purpose

Import the highest-ROI idea/spec opportunities from the reference repository `seeker71/Living-Codex-CSharp` into the Coherence Network idea portfolio so they are ranked, tracked, and answerable through the existing API/UI governance loop.

## Grounding Sources

- `references/living-codex/IMPLEMENTATION_STATUS.md` (priority queue, effort bands, missing UI coverage)
- `references/living-codex/LIVING_CODEX_SPECIFICATION.md` (implemented vs missing capability ledger)
- `references/living-codex/specs/LIVING_UI_SPEC.md` (route and endpoint capability map)

## Requirements

1. Add 10 imported ideas into default portfolio with IDs prefixed `living-codex-csharp-`.
2. Each imported idea must include:
   - estimated cost
   - potential value
   - open question with estimated value/cost
   - machine and/or human interaction interfaces
   - source-grounded description pointing to reference files
3. Imported ideas must auto-appear for both new and existing portfolio files through default-idea migration behavior.
4. Tests must verify imported idea IDs are present in seeded portfolio responses.

## Validation

- `cd api && pytest -v tests/test_ideas.py`
- `GET /api/ideas` returns imported IDs in portfolio output.
