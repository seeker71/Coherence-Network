# Progress — fractal-accessible-ontology

## Completed phases

- **test (task_6bf198faeb651094)** — Added `api/tests/test_fractal_accessible_ontology.py`: contract tests for accessible ontology (plain-language ideas, tags/domains, concept-resonance, cards feed, progress dashboard) with embedded Verification Scenarios for reviewers.

- **test (task_89d4a841704f2312)** — Added/confirmed `api/tests/test_fractal_accessible_ontology.py` with four pytest cases: portfolio progress dashboard (`GET /api/ideas/progress`), per-idea progress after `POST /api/ideas`, cards feed inventory shape (`idea_id`, `title`, `subtitle`), and multi-scale session (cards + `GET /api/concepts/stats` + `GET /api/concepts/search`). Module docstring encodes acceptance criteria for reviewers.

- **code-review (task_31b984b115e01e38)** — Reviewed implementation vs acceptance criteria (static analysis). **CODE_REVIEW_FAILED**: router calls service methods that are not implemented on `accessible_ontology_service`; `GET /api/ontology/garden` and `GET /api/ontology/stats` expected by `web/app/ontology/page.tsx` are not registered on the router despite service helpers; tests use an isolated `test_app` and do not assert against the production FastAPI app. Mandatory DIF `curl` could not be executed in this session (shell rejected) — use `.task-checkpoint.md` commands locally.

## Current task

(none — review delivered; follow-up implementation needed to align router, service, web, and tests)

## Key decisions

- Tests use isolated `IDEA_PORTFOLIO_PATH` (`tmp_path`) to avoid polluting shared portfolio data (historical note; current test file focuses on embedded ontology CRUD app).
- Card feed assertions use `idea_id`, `title`, and `subtitle` (inventory card shape), not `id`/`name` (may be superseded by ontology garden types).
- **Review**: Single source of truth should be chosen — either suggestion/endorse flow **or** concepts CRUD + garden/stats — and router + tests + web must match.

## Blockers

- **Integration gap**: Production router and service implementations diverge; web calls routes that are not mounted.
- **DIF**: Not run in agent session; run commands in `.task-checkpoint.md` before merge.
