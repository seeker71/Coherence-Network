# Meta-Pipeline Backlog

Work that improves the pipeline itself. Runs through the same spec→impl→test→review flow. See [docs/EXECUTION-PLAN.md](../docs/EXECUTION-PLAN.md).

**Full automation priority (Feb 2026):** Items 1–5 close meta-level gaps; items 6+ are general pipeline improvement.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 027, 045, 047, 114

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - All requirements implemented and tests pass
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Items

### Full Automation (Prioritized)

1. **Progress toward PLAN metric:** Add to GET /api/agent/effectiveness: `plan_progress` with Phase 6/7 completion (from PM state or backlog) so we measure progress toward PLAN.md goals → spec [045-effectiveness-plan-progress-phase-6-7.md](045-effectiveness-plan-progress-phase-6-7.md)
2. **Heal completion → issue resolution:** When a heal task completes and its related monitor condition clears on next check, ensure monitor records resolution; optionally auto-resolve the issue in monitor_issues.json → spec [047-heal-completion-issue-resolution.md](047-heal-completion-issue-resolution.md)
3. **Meta-questions periodic check:** Add script or monitor extension that runs META-QUESTIONS checklist periodically; log answers to api/logs/meta_questions.json; surface "unanswered" or "failed" in status-report
4. **Backlog alignment check:** Add monitor rule or effectiveness field: verify backlog items (from 006) map to PLAN phases; flag if Phase 6/7 items not being worked
5. **Heal task effectiveness tracking:** Record which heal task addressed which issue; when condition clears, attribute to heal; add to metrics "heal_resolved_count"

### Pipeline Improvement (General)

6. Write spec 027-auto-update-framework: script to update SPEC-COVERAGE and STATUS when tests pass; CI integration
7. Implement spec 027: update_spec_coverage.py; wire in CI
8. Implement spec 026 Phase 1: persist task metrics; GET /api/agent/metrics
9. Add attention heuristics to pipeline-status (stuck, repeated failures)
10. Add hierarchical view to check_pipeline (goal → PM → tasks → artifacts)
11. Set up GitHub Discussions as public forum; add "Join the conversation" to README
12. Add meta-pipeline items to overnight backlog rotation (20% capacity)

### Measured Improvement Queue (2026-02-19 Production Snapshot)

13. **Stale running task reaper + auto-heal trigger:** Detect tasks with `status=running` and `updated_at` older than 30 minutes, mark orphan, and trigger heal/restart actions. Baseline test (2026-02-19): 5/5 running tasks were older than 120 minutes (oldest update age: ~11,836s). Target: `stale_over_30m <= 1` in steady state.
14. **Failed-task diagnostics completeness contract:** Require failed tasks to persist a non-empty `error` summary and output excerpt/classification. Baseline: 16/16 failed tasks had null `error` and null `output`. Target: <5% failed tasks missing diagnostics.
15. **Monitor liveness/freshness guard:** Alert when `/api/agent/status-report` remains unknown or `/api/agent/monitor-issues.last_check` is null/stale; auto-create heal tasks if monitor is not writing reports. Baseline: `generated_at=null`, `overall.status=unknown`, `last_check=null`.
16. **Paid-provider block mitigation policy:** Add cooldown plus low-cost fallback routing when `paid_provider_blocked` friction spikes. Baseline: 184 open `paid_provider_blocked` events out of 238 open friction events. Target: reduce open paid-provider blocks by >=50% week-over-week.
17. **Runtime 502 hotspot suppression + retry hygiene:** Add endpoint-specific circuit breaker/backoff for `/api/health-proxy` and `/api/runtime-beacon`; avoid repeated expensive failing probes. Baseline (1h): `/api/health-proxy` had 8/61 responses with 502, `/api/runtime-beacon` had 3/4 responses with 502. Target: <2% 502 rate over rolling 24h.
18. **Provider readiness signal hardening:** Distinguish billing/usage-permission failures from true provider outage in readiness checks. Baseline: readiness is blocked by `openai: status=degraded` while other required execution providers are healthy. Target: `all_required_ready` reflects execution-critical health only.

Evidence snapshot and hypothesis tests: [docs/system_audit/pipeline_improvement_snapshot_2026-02-19.json](../docs/system_audit/pipeline_improvement_snapshot_2026-02-19.json)

### Flow & A/B Optimization Queue (2026-03-18 Orchestration Cycles)

19. **Auto-heal from diagnostics:** When `classify_error` returns a known category, auto-generate a heal task with a targeted fix prompt. Wire into existing heal task system. Baseline: 0% of failures auto-healed. Target: >40% of failures auto-healed without human intervention. → spec [114-auto-heal-from-diagnostics.md](114-auto-heal-from-diagnostics.md)
20. **Pre-review spec scan:** Before impl, have reviewer read spec+tests and flag likely pitfalls (ambiguous requirements, missing edge cases). Measure: `pitfalls_found_pre_impl / total_review_issues`. Target: catch >50% of review issues before impl starts.
21. **Prompt cost budgeting:** Set token budget per phase (spec: 2K, test: 3K, impl: 5K, review: 3K). Track actual vs budget. Penalize over-budget variants in Thompson Sampling. Measure: `actual_tokens / budget_tokens` ratio. Target: <1.2x for all phases.
22. **Cycle time compression:** Track wall-clock time from idea selection to PASS review. A/B test prompt sequencing. Baseline: ~15 min (cycle 2). Target: <10 min for straightforward specs.
23. **Spec reuse detection:** Before writing a new spec, check if existing specs cover >50% of requirements. Measure: `specs_with_reuse_detected / total_new_specs`. Target: detect overlap in >30% of cases.
24. **Error pattern library:** When `classify_error` sees a new pattern 3+ times, auto-add to pattern library and create root-cause spec. Measure: `unique_categories_resolved / total_unique`. Target: 80% of recurring errors have remediation within 1 week.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add distributed locking for multi-worker pipelines.

## Acceptance Tests

See `api/tests/test_meta_pipeline_backlog.py` for test cases covering this spec's requirements.

