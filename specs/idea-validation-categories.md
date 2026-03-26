# Idea validation categories

## Purpose

Classify each idea by how it should be verified in the pipeline. Network-facing work is checked against live Coherence APIs and UI; external or research ideas use different evidence. This spec adds `validation_category` to the idea model and API, inference for the spec phase, category-specific verification hooks for the runner, and review-task prompt text that matches the category.

## Goal

- Persist `validation_category` on every idea (`network_internal` | `external_project` | `research` | `community` | `infrastructure`).
- Expose the field on `POST /api/ideas` and `PATCH /api/ideas/{id}` (authenticated patch).
- Provide `infer_validation_category(interfaces, description)` for spec authoring and default-on-create when the client omits the field.
- Provide one verification entrypoint per category (runner calls these; they return structured pass/fail and check lists without requiring production network access in unit tests).
- Adapt automated review task directions in `scripts/idea_to_task_bridge.py` by category.

## API contract

| Field | Type | Notes |
|-------|------|--------|
| `validation_category` | string enum | Required on `Idea` responses; optional on create (default inferred); optional on PATCH |

Enum values: `network_internal`, `external_project`, `research`, `community`, `infrastructure`.

## Files to create/modify

- `specs/idea-validation-categories.md` — this document
- `api/app/models/idea.py` — enum + `Idea`, `IdeaCreate`, `IdeaUpdate`
- `api/app/services/idea_graph_adapter.py` — load/save `validation_category` in graph properties
- `api/app/services/idea_registry_service.py` — parity load/save when SQL legacy path is used
- `api/app/services/idea_service.py` — create/update + derived ideas metadata
- `api/app/services/idea_validation_category.py` — **new** — inference + verification functions + review addendum helper
- `api/app/routers/ideas.py` — wire create/patch
- `scripts/idea_to_task_bridge.py` — spec + review directions
- `api/tests/test_validation_category.py` — **new** — API + inference + verification smoke

## Acceptance criteria

1. Creating an idea with explicit `validation_category` returns the same value from `GET /api/ideas/{id}`.
2. Creating an idea without `validation_category` sets a value via `infer_validation_category` (deterministic for fixed interfaces/description).
3. `PATCH /api/ideas/{id}` with API key updates `validation_category`.
4. Invalid enum on create/patch yields HTTP 422.
5. Verification dispatcher returns a dict with `passed`, `category`, `checks`, and `summary` for each category.
6. Review task direction text includes category-specific verification instructions for `network_internal` vs `external_project`.

## Verification scenarios

### Scenario 1 — Create–read–update cycle (network_internal)

- **Setup:** Clean test DB / isolated env; API key `dev-key` available.
- **Action:** `curl -s -X POST "$API/api/ideas" -H "Content-Type: application/json" -H "X-API-Key: dev-key" -d '{"id":"vc-net-1","name":"N","description":"Uses GET /api/health","potential_value":1,"estimated_cost":1,"validation_category":"network_internal"}'`
- **Expected:** HTTP 201; JSON contains `"validation_category":"network_internal"`.
- **Then:** `curl -s "$API/api/ideas/vc-net-1"` → 200; same field present.
- **Then:** `curl -s -X PATCH "$API/api/ideas/vc-net-1" -H "X-API-Key: dev-key" -H "Content-Type: application/json" -d '{"validation_category":"research"}'` → 200; GET shows `research`.
- **Edge:** PATCH with `"validation_category":"not_a_category"` → 422.

### Scenario 2 — Inferred category on create

- **Setup:** No existing idea `vc-inf-1`.
- **Action:** POST body omits `validation_category` but includes `"description":"monitoring uptime SLA for the deployment pipeline"` (and minimal required numeric fields).
- **Expected:** HTTP 201; `validation_category` is `infrastructure` (inference from description).
- **Edge:** Empty description and empty interfaces → stable default (`network_internal` per implementation).

### Scenario 3 — List and scores unchanged

- **Setup:** At least one idea with `validation_category` set.
- **Action:** `GET /api/ideas?limit=50`
- **Expected:** HTTP 200; each idea in `ideas[]` includes `validation_category`; `summary` fields unchanged in meaning.

### Scenario 4 — Verification hook (runner contract)

- **Setup:** In-process call with an `Idea` model instance.
- **Action:** `from app.services.idea_validation_category import verify_for_category; verify_for_category(idea)`
- **Expected:** Returns a dict with keys `category`, `passed`, `summary`, `checks` (list); no exception for any valid `ValidationCategory`.

### Scenario 5 — Review bridge prompt (CLI / script)

- **Setup:** Python env with repo on `PYTHONPATH`.
- **Action:** Import `review_prompt_addendum_for_category` (or equivalent) with `network_internal` and `external_project`.
- **Expected:** Non-empty strings; `network_internal` text mentions endpoints/API; `external_project` mentions evidence URL or screenshot.

## Risks and assumptions

- Graph node properties may omit legacy fields; missing `validation_category` defaults to `network_internal` when loading.
- Verification functions are advisory/heuristic until wired to live HTTP against production; they must remain testable offline.

## Known gaps and follow-up tasks

- Wire `verify_network_internal` to real `curl`/`httpx` checks against `PUBLIC_API_BASE` in deployment runner only.
- UI: display badge for `validation_category` on idea cards.

## Verification (automated)

- `cd api && pytest api/tests/test_validation_category.py -v`
- `cd api && pytest api/tests/test_ideas.py -v --ignore=tests/holdout` (regression)
