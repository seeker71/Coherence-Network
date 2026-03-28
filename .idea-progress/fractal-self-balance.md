# Progress — fractal-self-balance

## Completed phases

- **2026-03-28 — Spec task (`task_d8987182d242e208`)**: Added `specs/fractal-self-balance.md` defining minimal read-only graph balance metrics (entropy, collapse proxy, top-degree nodes), single GET endpoint contract, empty-graph behavior, files to touch for implementation, verification commands, risks, and out-of-scope items (no auto-rewiring, no ML).

## Current task

(none — spec task complete)

## Key decisions

- **MVP is read-only**: One GET endpoint computing metrics from existing `graph_nodes` / `graph_edges` (no new tables required for MVP).
- **Collapse** operationalized as a documented concentration score (e.g. Gini or max/mean degree); **entropy** as Shannon entropy on a documented distribution (degree or edge-type counts).

## Blockers

- None.
