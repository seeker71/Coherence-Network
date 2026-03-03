# System Question Ledger (Cost/Value Ordered)

Date: 2026-02-28  
Author/Agent: OpenAI Codex

This ledger orders open questions by **lowest answer cost** and **highest system value**, then records factual answers and learning actions.

Scoring:
- **Effort**: estimated engineering time to answer (lower is better).
- **Value**: expected impact on correctness, throughput, and roadmap alignment (higher is better).
- **ROI score**: `value / effort`.

## Priority Order

| Rank | Question | Effort (hrs) | Value (1-10) | ROI |
|---|---|---:|---:|---:|
| 1 | What API surface is actually mounted vs what docs/web/pipeline expect? | 0.5 | 10 | 20.0 |
| 2 | Is local build/test health currently green for API and web? | 0.5 | 9 | 18.0 |
| 3 | What failure categories dominate pipeline throughput loss? | 1.0 | 9 | 9.0 |
| 4 | Which docs/contracts are currently drifted from runtime truth? | 2.0 | 8 | 4.0 |
| 5 | What production endpoints are actually live and matching local code? | 2.0 | 8 | 4.0 |
| 6 | What measurable economic value has been generated end-to-end? | 4.0 | 8 | 2.0 |
| 7 | Which model/prompt/executor combinations improve success rate fastest? | 6.0 | 9 | 1.5 |

## Answers Completed This Cycle

### 1) Mounted API surface vs expectations (answered, refreshed 2026-02-28)

Evidence:
- Script: `/Users/ursmuff/source/Coherence-Network/api/scripts/audit_runtime_surface.py`
- Command run: `cd api && .venv/bin/python scripts/audit_runtime_surface.py`

Findings:
- Mounted routes: 144 total.
- Agent router declares 29 routes and all 29 are mounted under `/api/agent/*`.
- Web/API drift now concentrates in unresolved endpoints (`/api/import/stack`, `/api/projects/*`, `/api/search`) plus query-parameter path comparisons that should be normalized in drift checks.

Value:
- Prevents false assumptions in planning and monitoring.
- Immediate high-value alignment point for next implementation cycle.

### 2) Local test/build health (answered)

Evidence:
- API: `cd api && .venv/bin/pytest -q` -> `46 passed in 0.38s`
- Web: `cd web && npm run build` -> successful production build

Status:
- Local API and web are currently build-test healthy for their present mounted/tested scope.

Value:
- Confirms safe baseline before structural changes.

### 3) Pipeline failure concentration (partially answered with facts)

Evidence:
- Analysis artifact: `/Users/ursmuff/source/Coherence-Network/docs/system_audit/pipeline_failure_analysis_2026-02-14.json`
- Script: `/Users/ursmuff/source/Coherence-Network/api/scripts/analyze_pipeline_failures.py`

Findings:
- Records: 689; Completed: 279; Failed: 410; Success rate: 0.405.
- Highest failure pressure is `impl` tasks (121 completed, 309 failed).
- Top failure signals include: `other_failure`, `log_missing`, `validation_error`, `runtime_error`, `timeout`, `command_not_found`.

Value:
- Identifies where to focus next improvement budget (impl phase first, then logging quality).

### 4) How to enforce phase-gate process automatically in CI (answered)

Evidence:
- Validator script: `/Users/ursmuff/source/Coherence-Network/scripts/validate_commit_evidence.py`
- Tests: `/Users/ursmuff/source/Coherence-Network/api/tests/test_commit_evidence_validation.py`
- Workflow gate: `/Users/ursmuff/source/Coherence-Network/.github/workflows/thread-gates.yml`

Findings:
- Commit-evidence schema and gate logic are now machine-validated.
- CI now has a branch-level workflow that runs evidence validation + API tests + web build.
- This closes the gap where branch pushes previously had no CI signal.

### 5) How to detect new docs/runtime drift before it spreads (answered)

Evidence:
- Drift checker: `/Users/ursmuff/source/Coherence-Network/scripts/check_runtime_drift.py`
- Drift baseline: `/Users/ursmuff/source/Coherence-Network/docs/system_audit/runtime_drift_allowlist.json`
- Tests: `/Users/ursmuff/source/Coherence-Network/api/tests/test_runtime_drift_check.py`

Findings:
- Known current drift is baselined explicitly.
- New drift now fails CI in `Thread Gates` via `check_runtime_drift.py`.

### 6) Docs/runtime drift list with exact file-by-file corrections (answered)

Evidence:
- Runtime audit command output from `scripts/audit_runtime_surface.py` on 2026-02-28.
- Source references inspected in `web/app/**/*` for API calls and `api/app/main.py` mounted routers.

Corrections queued:
1. `web/app/**` references to `/api/import/stack` are currently unmatched by mounted API routes.
2. `web/app/**` references to `/api/projects/*` are currently unmatched by mounted API routes.
3. `web/app/**` references to `/api/search` are currently unmatched by mounted API routes.
4. Drift comparison should normalize query strings for route-presence checks so endpoints like `/api/friction/events?limit=20` compare against `/api/friction/events`.

### 7) Production parity verification (Railway live runtime vs local) (answered)

Evidence:
- Command run: `./scripts/verify_web_api_deploy.sh` on 2026-02-28.

Findings:
- Web endpoints are reachable (`/`, `/gates`, `/api-health` returned HTTP 200).
- Production API checks timed out (`/api/health`, `/api/gates/main-head`, `/api/health/persistence`).
- Web API proxy returned degraded/unreachable (`/api/health-proxy` returned HTTP 502 with upstream unreachable message).
- Result: production parity is currently blocked by live API reachability, not by local route registration.

### 8) Economic value realized (actual contribution/distribution totals over time) (answered baseline)

Evidence:
- Command run:
  - `cd api && .venv/bin/python - <<'PY' ... idea_service.list_ideas(); value_lineage_service.list_links(); value_lineage_service.list_usage_events() ... PY`

Findings:
- Portfolio totals: `potential_value=378.0`, `actual_value=30.0`, `value_gap=348.0`.
- Value-lineage records: `lineage_links=0`, `usage_events=0`, `usage_value_total=0`.
- Interpretation: realized value is still estimate-driven; end-to-end economic realization is not yet captured in lineage/usage events.

## Still Open (next answer queue)

1. **Optimization experiments (route/model/prompt changes vs measurable success delta)**  
   Why open: baseline exists, controlled intervention and re-measurement not yet done.

## Codex Learning Loop (repeat each cycle)

1. Measure current truth
   - `cd api && .venv/bin/python scripts/audit_runtime_surface.py`
   - `cd api && .venv/bin/python scripts/analyze_pipeline_failures.py`
   - `cd api && .venv/bin/pytest -q`
   - `cd web && npm run build`
2. Compare against docs/spec assumptions.
3. Apply smallest high-ROI correction.
4. Re-measure and record deltas:
   - mounted-route mismatch count
   - success rate (`metrics.jsonl`)
   - impl failure count
   - log_missing count
5. Keep only changes that improve measurable outcomes.

## This Contribution: Cost / Value Attribution

Attribution record:
- `/Users/ursmuff/source/Coherence-Network/docs/system_audit/contribution_codex_2026-02-14.json`

Estimated effort used in this contribution:
- ~1.5 engineer-hours (analysis, scripting, validation, documentation).

Estimated build value generated:
- High immediate decision value (clarified real runtime scope, established repeatable audits).
- Medium-to-high operational value (failure concentration signal and measurable improvement loop).
