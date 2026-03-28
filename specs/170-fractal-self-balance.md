# Spec 170: Fractal Self-Balance (Anti-Collapse, Entropy Management)

**Spec ID**: 170-fractal-self-balance  
**Idea ID**: fractal-self-balance  
**Status**: implemented  
**Date**: 2026-03-28  
**Depends on**: Spec 169 (typed graph), `/api/graph/*`  

## Purpose

The system observes its own graph shape and surfaces **dynamic equilibrium** signals: split when a concept accumulates too many children, merge when orphan nodes cluster, and measure **energy concentration** across ideas so neglected high-potential branches are visible when attention collapses onto a few nodes.

## Requirements

- [x] `GET /api/graph/balance` returns a JSON report with:
  - `split_signals` — nodes with outgoing `parent-of` child count ≥ configurable `max_children` (default 10)
  - `merge_suggestions` — clusters of orphan `idea`/`concept` nodes (no incoming `parent-of`) that are connected to each other via any edge; components of size ≥ 2
  - `entropy` — per-idea energy from `free_energy_score` (fallback 1.0), `top3_energy_share`, `concentration_alert` when top-3 share ≥ 0.8, and `neglected_branches` (ideas not in top-3 by energy but with `value_gap` or `roi_cc` above dataset median among non-top-3)
- [x] Query params: `max_children` (5–100, default 10), `concentration_threshold` (0.5–1.0, default 0.8)
- [x] Service: `api/app/services/graph_balance_service.py` — pure analysis over `graph_nodes` / `graph_edges`
- [x] Models: `api/app/models/graph_balance.py` — Pydantic response types
- [x] Router: `api/app/routers/graph_balance.py`
- [x] `pytest api/tests/test_graph_balance.py` passes

## Verification

- `cd api && pytest api/tests/test_graph_balance.py -v` — 0 failures
- `curl -s http://localhost:8000/api/graph/balance` — 200 with keys `split_signals`, `merge_suggestions`, `entropy`, `parameters`

## Risks and Assumptions

- Energy uses graph node `free_energy_score` when present; empty graphs return zeros without error.
- Merge suggestions are advisory; automation of merge/split is out of scope.

## Known Gaps and Follow-up Tasks

- Wire optional UI dashboard (`web/app/graph/balance/page.tsx`) to consume the report.
- Persist balance snapshots for time-series charts.
