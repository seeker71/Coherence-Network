# Progress — 036-check-pipeline-hierarchical-view

## Completed phases

- **2026-03-28 — Review + spec contract (task task_4058a62e9b5ae373):** Confirmed hierarchical pipeline view is implemented in `api/scripts/check_pipeline.py` (Goal → PM → Tasks → Artifacts; `--json` hierarchical; `--flat` legacy). Spec updated with runnable Verification Scenarios targeting `GET /api/agent/status-report`, `/api/agent/pipeline-status`, `/api/agent/effectiveness`. JSON merge logic tightened with `_layer0_goal_usable_from_report`. `.gitignore` corruption fixed.

## Current task

(none — hand off to runner for pytest, validate_commit_evidence, DIF, git push)

## Key decisions

- Treat status-report `layer_0_goal` as unusable when `summary` is empty or contains `not yet generated` (case-insensitive), so JSON and stdout both fall back to effectiveness or built layers consistently.

## Blockers

- Agent session could not execute shell (pytest, DIF curl, git). Runner should run verification commands locally.
