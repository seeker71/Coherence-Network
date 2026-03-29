# Idea Progress: My Portfolio (ux-my-portfolio)

Personal view of everything a contributor invested in and contributed to.

## Status
- **Phase:** Specification
- **Current task:** Done writing specification.

## Completed phases
- Research: Explored existing `api/app/routers/me_portfolio.py` and `web/app/contributors/[id]/portfolio/page.tsx`.
- Specification: Created `specs/ux-my-portfolio.md` with Garden/Ledger view requirements and authentication strategy.

## Key decisions
- **Authentication:** Use existing API key mechanism via `X-API-Key` header. Frontend stores key in local storage.
- **Visual Metaphor:** Dual-view (Garden/Ledger) toggle.
- **Data Model:** Reuse existing `PortfolioSummary`, `CCHistory`, `IdeaContributionsList`, `StakesList`, `TasksList` models.
- **Garden Visualization:** Adopt SVG/Orb style from Automation Garden.

## Blockers
- None.
