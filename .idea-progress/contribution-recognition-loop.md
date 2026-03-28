# Progress — contribution-recognition-loop

## Completed phases

- **Spec (task_7ef09f7229c375fa)**: Added `specs/contribution-recognition-loop.md` defining minimal visible recognition + weekly growth via `GET /api/contributors/{id}/recognition` and a web surface; no new persisted tables for MVP.

## Current task

- Complete (commit pending in same session).

## Key decisions

- **MVP scope**: Single read endpoint for summary + 8 weekly buckets; UI consumes API only (no client-side aggregation from full contribution lists).
- **Data**: Derive metrics from existing contribution records at request time; cache/materialize only as follow-up if needed.

## Blockers

- None.
