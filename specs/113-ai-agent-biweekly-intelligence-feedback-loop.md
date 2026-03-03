# Spec: AI Agent Biweekly Intelligence Feedback Loop

## Purpose

Integrate external AI-agent developments into Coherence Network execution quality so the system continuously adapts to new framework patterns, coding-agent practices, and security risks. This reduces stale execution behavior, lowers retry waste, and improves the quality of spec-driven implementation tasks.

## Requirements

- [ ] Add a reproducible intelligence artifact format that captures source URL, source type, publication date, and project-relevance score.
- [ ] Extend task contracts so task-card completeness is measurable at task creation time.
- [ ] Record structured retry blind-spot reflections in task context on each failure/retry path.
- [ ] Classify retry failures into normalized categories and persist category metadata for downstream analysis.
- [ ] Emit retry-category metadata into lifecycle telemetry rows.
- [ ] Add monitor checks that flag stale intelligence artifacts (older than configured freshness window).
- [ ] Add monitor checks that flag unresolved high-severity AI-agent security advisories.
- [ ] Add an executable script that builds a biweekly intelligence digest using real web-source fetches.
- [ ] Add an executable script that produces a 10-point implementation plan JSON with measurable checks.
- [ ] Produce system-audit evidence artifacts and pass targeted tests for all changed behaviors.

## API Contract (if applicable)

### `GET /api/agent/tasks/{task_id}`

**Behavior updates**
- Response `context` should include:
  - `task_card_validation`: structured completeness report when task-card context is present.
  - `retry_reflections`: ordered reflection rows when retries happen.

**Response 200 additions (context excerpt)**
```json
{
  "context": {
    "task_card_validation": {
      "present": true,
      "score": 1.0,
      "missing": []
    },
    "retry_reflections": [
      {
        "retry_number": 1,
        "failure_category": "timeout",
        "blind_spot": "Scope too broad for timeout budget"
      }
    ]
  }
}
```

## Data Model (if applicable)

```yaml
TaskContextExtensions:
  task_card_validation:
    type: object
    properties:
      present: { type: boolean }
      score: { type: number }
      missing: { type: array, items: { type: string } }
  retry_reflections:
    type: array
    items:
      type: object
      properties:
        retry_number: { type: integer }
        failure_category: { type: string }
        blind_spot: { type: string }
        next_action: { type: string }

IntelligenceDigest:
  type: object
  properties:
    generated_at: { type: string }
    window_days: { type: integer }
    sources:
      type: array
      items:
        type: object
        properties:
          url: { type: string }
          published_at: { type: string }
          source_type: { type: string }
          relevance_score: { type: number }
```

## Files to Create/Modify

- `specs/113-ai-agent-biweekly-intelligence-feedback-loop.md` - this spec
- `api/app/services/agent_service.py` - task-card validation metadata at task creation
- `api/app/services/agent_execution_retry.py` - structured retry reflections and failure category metadata
- `api/app/services/agent_execution_hooks.py` - lifecycle metadata support for retry category fields
- `api/scripts/monitor_pipeline.py` - stale-intelligence and security-advisory checks
- `api/scripts/collect_ai_agent_intel.py` - biweekly intelligence digest generator
- `api/scripts/build_ai_agent_improvement_plan.py` - 10-point plan generator from digest + repo data
- `api/tests/test_agent_execute_endpoint.py` - retry reflection assertions
- `api/tests/test_agent_task_persistence.py` - task-card validation assertions
- `api/tests/test_monitor_pipeline_github_actions.py` - new monitor condition tests
- `docs/system_audit/ai_agent_biweekly_sources_2026-02-28.json` - source evidence artifact
- `docs/system_audit/ai_agent_biweekly_summary_2026-02-28.md` - 3-page summary
- `docs/system_audit/ai_agent_10_point_plan_2026-02-28.json` - generated implementation plan

## Acceptance Tests

- `cd api && pytest -q tests/test_agent_execute_endpoint.py -k "retry"`
- `cd api && pytest -q tests/test_agent_task_persistence.py -k "task_card"`
- `cd api && pytest -q tests/test_monitor_pipeline_github_actions.py -k "intelligence or advisory"`
- `cd api && python3 scripts/collect_ai_agent_intel.py --window-days 14 --output ../docs/system_audit/ai_agent_biweekly_sources_2026-02-28.json`
- `cd api && python3 scripts/build_ai_agent_improvement_plan.py --intel ../docs/system_audit/ai_agent_biweekly_sources_2026-02-28.json --output ../docs/system_audit/ai_agent_10_point_plan_2026-02-28.json`

## Verification

```bash
cd api && pytest -q tests/test_agent_execute_endpoint.py -k "retry"
cd api && pytest -q tests/test_agent_task_persistence.py -k "task_card"
cd api && pytest -q tests/test_monitor_pipeline_github_actions.py -k "intelligence or advisory"
cd api && python3 scripts/collect_ai_agent_intel.py --window-days 14 --output ../docs/system_audit/ai_agent_biweekly_sources_2026-02-28.json
cd api && python3 scripts/build_ai_agent_improvement_plan.py --intel ../docs/system_audit/ai_agent_biweekly_sources_2026-02-28.json --output ../docs/system_audit/ai_agent_10_point_plan_2026-02-28.json
```

## Out of Scope

- Full autonomous deployment of every proposed plan item to production.
- Non-agent product redesign in `web/`.
- Replacing existing provider quota/readiness architecture.

## Risks and Assumptions

- Source pages may vary in machine-readable date metadata; script must tolerate missing fields.
- Retry-reflection metadata increases context size; bounded history is required.
- Monitor checks must avoid false positives when artifacts are intentionally absent in local-only runs.

## Known Gaps and Follow-up Tasks

- Follow-up task: wire generated intelligence digest into automated nightly pipeline trigger.
- Follow-up task: add dashboard panels for retry category trendlines.

## Decision Gates (if any)

- If task-card enforcement is switched to hard-fail mode in the future, require explicit owner approval.
