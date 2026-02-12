# Overnight Backlog (8h+ unattended)

Work items ordered for overnight runs. Smaller, achievable tasks first.
Use: `./scripts/run_overnight_pipeline.sh --backlog specs/006-overnight-backlog.md`

**Progress:** Phase 1–3 largely done. Phase 4–5 and "Next Hours" below remain.

## Phase 1: Specs & Docs (items 1–15) — DONE
1. specs/001-health-check.md — Verify all health items complete; add any missing tests
2. specs/002-agent-orchestration-api.md — Verify all agent API items complete; add edge-case tests
3. specs/003-agent-telegram-decision-loop.md — Verify Telegram flow complete; add diagnostic test
4. specs/004-ci-pipeline.md — Verify CI complete; add badge to README if missing
5. specs/005-project-manager-pipeline.md — Verify PM complete; add E2E smoke test
6. specs/007-sprint-0-landing.md — Verify landing complete; add /docs reachability test
7. Write spec 009-api-error-handling: 422 validation, 404 consistency, error schema
8. Write spec 010-request-validation: task_type enum, direction length limits, Pydantic refinements
9. Write spec 011-pagination: GET /api/agent/tasks limit/offset with default page size
10. Update docs/SPEC-COVERAGE.md for specs 007, 008, and any new specs
11. Expand docs/AGENT-DEBUGGING.md: add "Pipeline stuck" section, "Task hangs" section
12. Expand docs/SETUP.md: add Troubleshooting section, venv path note for scripts
13. Fix README.md: remove or qualify "cd web" and "docker compose" (web/ and docker not yet present)
14. Add docs/RUNBOOK.md: ops runbook for API restart, log locations, pipeline recovery
15. Add docs/GLOSSARY.md: terms (coherence, task_type, pipeline, backlog, etc.)

## Phase 2: Tests (items 16–35) — DONE
16. Add test: GET /docs returns 200 (OpenAPI UI reachable)
17. Add test: POST /api/agent/tasks with invalid task_type returns 422
18. Add test: POST /api/agent/tasks with empty direction returns 422
19. Add test: pipeline-status returns 200 when no running task (empty state)
20. Add test: task log endpoint returns 404 when log file missing
21. Add test: project_manager load_backlog with malformed file (missing numbers)
22. Add test: project_manager --backlog flag uses alternate file
23. Add test: project_manager --state-file flag uses alternate state path
24. Add test: project_manager --reset clears state and starts from index 0
25. Add test: agent_service routes spec task_type to local model
26. Add test: agent_service routes test task_type to local model
27. Add test: agent_service routes review task_type to local model
28. Add test: PATCH task with invalid status returns 422
29. Add test: GET /api/health returns JSON with required fields under load (quick smoke)
30. Add test: CORS allows origins (OPTIONS preflight if applicable)
31. Add tests/holdout/ directory with README explaining holdout test pattern
32. Add integration test: create task, patch to completed, verify in list
33. Add test: build_direction for all phases with edge cases (empty item, long item)
34. Add test: refresh_backlog does not duplicate existing items
35. Add test: load_state/save_state handles corrupted JSON file gracefully

## Phase 3: API & Scripts (items 36–55) — DONE
36. Implement spec 009: consistent 404/422 error response schema
37. Implement spec 010: request validation (task_type enum, direction 1–5000 chars)
38. Implement spec 011: pagination for GET /api/agent/tasks (limit, offset)
39. Add GET /api/version returning app version (or use root; document)
40. Add OpenAPI summary/description for every endpoint in routers
41. Add --dry-run flag to project_manager (log what would be done, no HTTP)
42. Add script api/scripts/validate_backlog.py to check backlog format
43. Add script api/scripts/run_backlog_item.py --index N to run single backlog item
44. Improve check_pipeline.py: add --json output, table format option
45. Add retry logic to agent_runner for transient API connection errors (3 retries)
46. Add timeout to agent_runner HTTP calls (avoid indefinite hang)
47. Extract agent_service constants (MAX_OUTPUT_LEN, etc.) to config module
48. Add type hints to all public functions in agent_service.py
49. Add docstrings to agent_service module and main functions
50. Add py.typed marker to api/app for PEP 561 type package
51. Add request_id or correlation_id to task creation for traceability
52. Log task creation with task_id to structured log (for ops)
53. Add /api/agent/tasks/count endpoint (lightweight, for dashboards)
54. Add env validation at startup: warn if TELEGRAM_BOT_TOKEN missing but webhook enabled
55. Add readiness probe route /api/ready (or extend health) for k8s/deploy

## Phase 4: Specs for Future Work (items 56–70)
56. Write spec 012-web-skeleton: Next.js 16 app with / and /api-health check page
57. Write spec 013-logging-audit: structured logging, log levels, rotation
58. Write spec 014-deploy-readiness: env validation, health/ready, Dockerfile skeleton
59. Write spec 015-coherence-algorithm: algorithm sketch, inputs, outputs, weights stub
60. Expand specs/008-sprint-1-graph-foundation.md: add deps.dev API contract section
61. Add spec 016-holdout-tests: pattern, directory, CI exclusion, purpose
62. Add spec 017-agent-runner-resilience: retries, timeouts, backoff
63. Add spec 018-api-rate-limiting: placeholder/spec for future rate limits
64. Update docs/concepts/OSS-CONCEPT-MAPPING.md with concrete node/edge examples
65. Add docs/concepts/COHERENCE-ALGORITHM-SKETCH.md from PLAN.md formula
66. Review and cross-link all specs: add "See also" where relevant
67. Add acceptance criteria checklist to specs/TEMPLATE.md
68. Create specs/009-api-error-handling.md (if not created in item 7)
69. Create specs/010-request-validation.md (if not created in item 8)
70. Create specs/011-pagination.md (if not created in item 9)

## Phase 5: Polish & Cleanup (items 71–85)

## Next Hours (new items 86–100)
86. Implement spec 012: create web/ Next.js app with / and /api-health
87. Add api/scripts/run_backlog_item.py --index N to run single backlog item
88. Run ruff on api/ and fix auto-fixable issues
89. Add CHANGELOG.md with placeholder structure
90. Write spec 013-logging-audit: structured logging, levels, rotation
91. Write spec 014-deploy-readiness: Dockerfile skeleton, env validation
92. Add --max-items N to project_manager for testing
93. Expand docs/concepts/OSS-CONCEPT-MAPPING.md with concrete examples
94. Add "See also" cross-links to specs
95. Update AGENTS.md with conventions from recent work
71. Run ruff or black on api/ and fix any auto-fixable issues
72. Ensure all Python files have consistent docstring style (Google or NumPy)
73. Add .cursorignore or .gitignore entries for logs, __pycache__, .venv
74. Verify .env.example documents all required and optional env vars
75. Add Makefile or justfile with targets: test, run, lint, setup
76. Consolidate duplicate logic between project_manager and overnight_orchestrator if any
77. Add CHANGELOG.md with placeholder structure for future releases
78. Review agent runner log rotation: ensure logs don't grow unbounded
79. Add cleanup of old task logs (e.g. keep last 7 days) to cleanup_temp or new script
80. Document max backlog size and performance implications in project_manager
81. Add --max-items N to project_manager for testing (process only first N)
82. Verify all scripts in api/scripts/ have shebang and executable bit
83. Add smoke test script: curl health, pipeline-status, create minimal task
84. Update AGENTS.md with any new conventions from this session
85. Final pass: run full pytest, fix any flaky or failing tests
