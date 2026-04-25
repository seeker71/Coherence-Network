# Pipeline Run Report — 2026-03-06

## Summary

- **tracking-mechanism-efficiency**: Accepted (manifestation_status=validated)
- **api-docs-completion**: Implemented, validated, accepted
- **tracking-infrastructure-upgrade**: Implemented, validated (window_days param)
- **Validated ideas**: 6
- **Unvalidated ideas**: 46
- **Commit**: `d071489` tracking-infrastructure-upgrade + pipeline report with Cursor CLI prompts

---

## Cursor CLI calls — per step, actual prompts, models, generated steps

Each step is a **separate Cursor CLI call** with its own model, prompt, and output contract. Run via `POST /api/agent/tasks` → API returns `command` → agent_runner (or manual) executes it.

### Spec (Cursor CLI)

| Field | Value |
|-------|-------|
| **Model** | `auto` (strong tier per `model_routing.json`) |
| **Role agent** | `product-manager` |
| **CLI** | `agent --trust --print --output-format json "{{direction}}" --model auto --sandbox disabled` |
| **Prompt (direction)** | `Spec: {item}\n\nGoal: produce one valid spec file accepted by the judge.\nJudge: python3 scripts/validate_spec_quality.py --file <spec_path>\n\n1. Read specs/TEMPLATE.md and use the same section names.\n2. Create one file: specs/<name>.md.\n3. Include at minimum: Purpose, Requirements (>=3), Research Inputs, Task Card, Files to Create/Modify, Acceptance Tests, Verification, Out of Scope, Risks, Known Gaps.\n4. Run judge until PASS.` |
| **Generated steps** | 1. Create spec file 2. Run validate_spec_quality 3. Fix until PASS |
| **Required output** | `SPEC_PATH`, `JUDGE`, `VALIDATION` |

### Impl (Cursor CLI)

| Field | Value |
|-------|-------|
| **Model** | `auto` (fast tier) |
| **Role agent** | `dev-engineer` |
| **CLI** | Same template, direction = impl scope |
| **Prompt (direction)** | `Implement: {item}\n\nGoal: satisfy spec assertions with minimum cost and scope.\n\n1. Read spec: Files to Create/Modify, Acceptance Tests.\n2. Edit only listed files. Smallest patch only.\n3. Run acceptance commands; stop at first FAIL, fix, rerun.\n4. Repeat until all PASS.` |
| **Generated steps** | 1. Edit spec-listed files 2. Run acceptance commands 3. Fix and rerun until PASS |
| **Required output** | `FILES_CHANGED`, `TESTS`, `JUDGE`, `RESULT` |
| **On failure** | Next impl uses `impl_iteration` template with `{last_output}` (test failures or PATCH_GUIDANCE) |

### Test (Cursor CLI)

| Field | Value |
|-------|-------|
| **Model** | `auto` (fast tier) |
| **Role agent** | `qa-engineer` |
| **CLI** | Same template |
| **Prompt (direction)** | `Tests: {item}\n\nGoal: encode spec assertions as deterministic tests.\n\n1. Read spec requirements and acceptance criteria.\n2. Create/update one test file mapping assertions to requirements.\n3. Run: cd api && pytest <test-file> -q` |
| **Generated steps** | 1. Create/update test file 2. Run pytest |
| **Required output** | `TEST_FILE`, `TESTS`, `JUDGE`, `RESULT` |

### Review (Cursor CLI)

| Field | Value |
|-------|-------|
| **Model** | `auto` (strong tier) |
| **Role agent** | `reviewer` |
| **Guard agents** | `spec-guard` |
| **CLI** | Same template |
| **Prompt (direction)** | `Review: {item}\n\nGoal: decide PASS/FAIL using the agreed judge only.\n\n1. Read spec Acceptance Tests and Files to Create/Modify.\n2. Run each acceptance command; record pass/fail.\n3. Check changed files in allowed scope.\n4. PASS only when all pass and scope clean.` |
| **Generated steps** | 1. Run acceptance commands 2. Scope check 3. Emit PASS_FAIL and PATCH_GUIDANCE |
| **Required output** | `PASS_FAIL`, `VERIFIED`, `JUDGE`, `FINDINGS`, `PATCH_GUIDANCE` |
| **On FAIL** | `PATCH_GUIDANCE` = `file:line:minimal fix` — fed into next impl iteration |

### Feedback loop

| Condition | Action |
|-----------|--------|
| Test fails | Next impl uses `impl_iteration` with `{last_output}` = test failure output |
| Review FAIL | Next impl uses `impl_iteration` with `{last_output}` = PATCH_GUIDANCE + findings |
| Loop until | All acceptance commands PASS and review says PASS_FAIL: PASS |

**impl_iteration prompt** (from `prompt_templates.json`):
```
Fix (iteration {iteration}): {item}
Previous failure: {last_output}
Goal: resolve the current failure with the smallest safe delta.
ROOT_CAUSE: [one line]
FIX: [one line]
FILES_CHANGED: [paths]
VERIFICATION: [command -> PASS|FAIL]
```

### Validation CLI (post Cursor pipeline)

| Step | CLI | Output |
|------|-----|--------|
| Acceptance | `python3 scripts/run_pinned_idea_acceptance.py` | Runs: no_placeholder, spec_quality, pytest, live_api |

---

## tracking-mechanism-efficiency (accepted)

| Task | CLI | Output |
|------|-----|--------|
| 1. Verify idea status | `curl -s http://127.0.0.1:8000/api/ideas/tracking-mechanism-efficiency \| python3 -c "import sys,json; d=json.load(sys.stdin); print('manifestation_status:', d['manifestation_status'])"` | `manifestation_status: validated` |
| 2. Full metrics | `curl -s 'http://127.0.0.1:8000/api/agent/metrics'` | `keys: ['by_model', 'by_task_type', 'execution_time', 'success_rate']` |
| 3. metric=time filter | `curl -s 'http://127.0.0.1:8000/api/agent/metrics?metric=time'` | `keys: ['execution_time']` |
| 4. pytest | `cd api && pytest -q tests/test_agent_integration_api.py::test_agent_metrics_returns_200_and_supports_metric_filter` | `1 passed, 2 warnings in 0.70s` |
| 5. Idea counts | `curl -s http://127.0.0.1:8000/api/ideas \| python3 -c "..."` | `validated: 4 unvalidated: 48` |

---

## api-docs-completion (next idea — implemented & validated)

| Task | CLI | Output |
|------|-----|--------|
| 1. OpenAPI summary | `curl -s http://127.0.0.1:8000/openapi.json \| python3 -c "import sys,json; d=json.load(sys.stdin); op=d['paths']['/api/agent/metrics']['get']; print('summary:', op.get('summary'))"` | `summary: Task metrics (success rate, duration, by task_type/model)` |
| 2. pytest | `cd api && pytest -q tests/test_agent_integration_api.py -k 'metrics or openapi'` | `2 passed, 7 deselected, 2 warnings in 0.78s` |
| 3. Idea status | `curl -s http://127.0.0.1:8000/api/ideas/api-docs-completion \| ...` | `manifestation_status: validated` |
| 4. Idea counts | `curl -s http://127.0.0.1:8000/api/ideas \| ...` | `validated: 5 unvalidated: 47` |

### Files changed

- `api/app/routers/agent_issues_routes.py` — Added `summary="Task metrics (...)"` to `GET /api/agent/metrics`
- `api/tests/test_agent_integration_api.py` — Added `test_openapi_metrics_has_summary`

---

## Proof-of-idea-to-acceptance pipeline (run_pinned_idea_acceptance.py)

| Step | Performed by | CLI | Output (proof) |
|------|--------------|-----|----------------|
| step_1_no_placeholder | Validation | `scripts/run_pinned_idea_acceptance.py` (in-process file check) | `[PROOF] step_1_no_placeholder: {"files_checked": [...], "result": "no_forbidden_tokens"}` |
| step_2_spec_quality | Validation | `python3 scripts/validate_spec_quality.py --file specs/053-ideas-prioritization.md` | `[PROOF] step_2_spec_quality: {"validator_exit": 0, "sections_present": {...}}` |
| step_3_pytest | Validation | `python -m pytest -q tests/test_ideas.py` | `[PROOF] step_3_pytest: {"exit_code": 0, "tests_passed": 14}` |
| step_4_live_api | Validation | `curl -sS http://localhost:8000/api/ideas?only_unvalidated=true` | `[PROOF] step_4_live_api: {"status": 200, "ideas_returned": 47}` |
| acceptance_complete | — | — | `[PROOF] acceptance_complete: all steps passed` |

**Cursor CLI** (agent does spec→impl→test→review before this): API returns `command` when task created; agent_runner runs it. Example: `agent --trust --print --output-format json "{{direction}}" --model {{model}}`.

---

---

## Next idea (highest ROI, unvalidated): tracking-infrastructure-upgrade — implemented & validated

| Field | Value |
|-------|-------|
| **id** | tracking-infrastructure-upgrade |
| **score** | 6.18 |
| **status** | validated |
| **Files changed** | `api/app/services/metrics_service.py`, `api/app/routers/agent_issues_routes.py`, `api/tests/test_agent_integration_api.py` |

**Implementation:** Added `window_days` query param (1–90) to `GET /api/agent/metrics`. Configurable rolling window; response includes `window_days` when provided.

**Verification CLI:**
```
curl -s 'http://127.0.0.1:8000/api/agent/metrics?window_days=1' | python3 -c "import sys,json; d=json.load(sys.stdin); print('window_days:', d.get('window_days'))"
# Expected: window_days: 1

cd api && pytest -q tests/test_agent_integration_api.py::test_agent_metrics_window_days_parameter
# Expected: 1 passed
```

---

## Verification

All tasks passed. Pipeline works as expected:
- Ideas marked accepted (validated)
- Live API returns expected responses after restart
- pytest passes for changed code
- Unvalidated count declined: 48 → 47
- run_pinned_idea_acceptance.py: all 4 steps passed
