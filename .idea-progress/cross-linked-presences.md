# Idea Progress: cross-linked-presences

## Current task
- Phase: impl (complete)
- Task ID: task_131deda2df344503
- Status: DONE

## Completed phases
- Spec (2026-03-30): Wrote specs/cross-linked-presences.md — 10 requirements, 5 verification scenarios, passed quality validation.
- Impl (2026-03-30): Implemented ecosystem cross-links across all 6 surfaces — 9 files changed, 396 insertions.

## Key decisions
- 6 core surfaces: GitHub, Web, API, CLI, MCP Server, OpenClaw Skill
- skills.sh/askill.sh removed from canonical table (secondary, not core)
- "Join the Network" row removed from README (replaced by GitHub row)
- Single canonical source at docs/shared/ecosystem-table.md
- Drift detection via scripts/check_ecosystem_links.py (implemented)
- Web gets /ecosystem page + site footer with ecosystem links
- Footer hidden on mobile (mobile-bottom-nav already handles navigation)
- API description updated to list GitHub first in ecosystem line

## Blockers
- None
