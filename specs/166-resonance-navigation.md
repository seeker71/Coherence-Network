# Spec 166 — Resonance-Based Navigation (Tunable Discovery)

**ID:** `task_84f5a4d0a17b2d24`  
**Status:** Implemented  
**Priority:** High  
**Created:** 2026-03-28

## Purpose

Replace keyword-centric retrieval with tunable, state-aware discovery via a resonance vector over named axes.

## API Contract

- **POST** `/api/discovery/resonance`
- **Request body:** `axes` (five floats 0–1: `curiosity`, `serendipity`, `depth`, `coherence_affinity`, `recency`), optional `axis_weights`, optional `contributor_id`, `limit`, `include_internal`, `include_graph`.
- **Response:** Ranked `ideas` with `resonance_score` and per-idea `axis_profile`; optional `nodes` and `connections` from the graph around top hits.

## Files to Create/Modify

- `specs/166-resonance-navigation.md` (this file)
- `api/app/models/resonance_navigation.py`
- `api/app/services/resonance_navigation_service.py`
- `api/app/routers/discovery.py`
- `api/app/main.py`
- `web/app/discover/page.tsx`
- `web/components/site_header.tsx`
- `scripts/dif_verify_file.sh` (optional helper for Merly DIF checks on Python files)

## Verification

- `POST /api/discovery/resonance` with default body returns 200 and a non-empty `ideas` list when the portfolio has ideas.
- Discover page loads and fetches results when sliders change.

## Risks and Assumptions

- Axis signals are heuristics over portfolio and graph data; empty graph still returns scored ideas.
- Serendipity uses contributor ledger + keyword overlap when `contributor_id` is set.

## Known Gaps and Follow-up Tasks

- Learned embeddings for semantic resonance.
- Persist user preference profiles across sessions.
