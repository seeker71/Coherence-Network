---
idea_id: pipeline-reliability
status: done
source:
  - file: api/app/services/smart_reap_service.py
    symbols: [timeout extension logic]
  - file: api/app/services/agent_execution_retry.py
    symbols: [_resolve_retry_max()]
  - file: api/app/services/agent_task_continuation_service.py
    symbols: [task continuation]
requirements:
  - Record timeout samples to JSONL on every task completion
  - Adaptive timeout uses p90 * 1.5 with min 5 samples to activate
  - Fall back to flat defaults when fewer than 5 samples exist
  - Upper-clamp adaptive timeout at 3x baseline per task type
  - Capture partial_output and partial_output_pct on timeout
  - Resume task prepends partial output with RESUME FROM TIMEOUT marker
  - GET /api/agent/timeout-metrics returns efficiency_ratio and per-provider stats
  - GET /api/agent/timeout-recommendation returns adaptive timeout with derivation
  - POST /api/agent/timeout-samples accepts and stores a sample (201)
done_when:
  - Agent runner logs timeout=adaptive or timeout=fixed on every task pickup
  - Resume tasks have is_resume=true and prepend partial output to direction
  - pytest api/tests/test_timeout_adaptive_service.py passes
test:
  - "pytest -q api/tests/test_timeout_adaptive_service.py"
---

> **Parent idea**: [pipeline-reliability](../ideas/pipeline-reliability.md)
> **Source**: [`api/app/services/smart_reap_service.py`](../api/app/services/smart_reap_service.py) | [`api/app/services/agent_execution_retry.py`](../api/app/services/agent_execution_retry.py) | [`api/app/services/agent_task_continuation_service.py`](../api/app/services/agent_task_continuation_service.py)

# Spec: Data-Driven Timeout and Task Resume

## Purpose

Currently, task timeouts are **flat constants** by task type (`spec=1200s`, `impl=2400s`, `test=1800s`, `review=1200s`, `heal=1200s`). These are guesses that don't account for provider speed, task complexity, or historical performance. This spec introduces data-driven timeouts derived from execution measurements, and task resume that preserves partial work on timeout so tasks continue instead of restart.

## Summary

Replace flat task-type timeouts with per-provider × per-task-type timeouts computed from historical execution data. When a timeout fires, capture the last meaningful output checkpoint and inject it into a resume task so work continues from where it stopped, not from scratch.

## Requirements

### 1. Timeout Sample Collection

Every task completion (success, failure, timeout) records a sample stored in `api/logs/timeout_samples.jsonl` (append-only).

```python
TimeoutSample:
  provider: str          # e.g. "openai", "openrouter/local"
  task_type: str         # e.g. "spec", "impl", "test", "review"
  elapsed_ms: int        # actual wall-clock time
  completed_at: str      # ISO 8601 UTC
  outcome: str           # "completed" | "failed" | "timed_out"
  task_id: str           # reference to source task
  idea_id: str | None   # for grouping
```

Collection points:
- `agent_execution_service.py` — emit sample after `complete_task` / `fail_task`
- `agent_runner.py` `_dispatch_openrouter_task_and_wait` — emit `timed_out` sample when deadline fires

### 2. Adaptive Timeout Computation

**Formula:**
```
p50 = 50th percentile of elapsed_ms over last N samples (default N=30)
p90 = 90th percentile of elapsed_ms over last N samples
timeout_ms = max(p90 * 1.5, baseline_minimum)
baseline_minimum = fixed constant per task_type (spec=300s, impl=600s, test=300s, review=180s, heal=180s)
upper_clamp = 3x baseline
timeout_ms = min(timeout_ms, upper_clamp)
```

If fewer than 5 samples exist, fall back to flat defaults. If fewer than 30 samples exist, use all available samples.

**Computation service:** `api/app/services/timeout_adaptive_service.py`
- `add_sample(sample: TimeoutSample) -> None` — append to JSONL
- `get_timeout_ms(provider, task_type) -> int` — compute adaptive timeout
- `get_timeout_stats(provider, task_type) -> TimeoutStats` — p50, p90, sample_count, derived_from

### 3. Runtime Timeout Override in Agent Runner

In `api/scripts/agent_runner.py`:
- Before setting `deadline`, call `timeout_adaptive_service.get_timeout_ms(provider, task_type)`
- Use adaptive result instead of `_default_runtime_seconds_for_task_type` when available
- Log which timeout was selected: `timeout=adaptive(p90=4200ms, multiplier=1.5, provider=openai, task_type=impl)` or `timeout=fixed(default=2400s, samples=3)`

### 4. Partial Output Preservation on Timeout

**Checkpoint:** `agent_execution_hooks.py` writes `context.checkpoint_output` on progress events.

**Timeout capture flow:**
1. Deadline fires → `agent_runner.py` detects timeout
2. Capture last `TASK_LOG_TAIL_CHARS` from running log
3. Store as `context.partial_output`, `context.partial_output_at` (ISO UTC), `context.partial_output_pct` (0-100)
4. Set `context.resume_task_id` linking to continuation task

### 5. Resume Task Injection

When `smart_reaper_service.py` creates a resume task on timeout:
- Set `context.is_resume = True`
- Set `context.resumed_from_task_id = original_task.id`
- Prepend partial output to direction with marker:
  ```
  [RESUME FROM TIMEOUT — partial_output_pct=N%]
  Continue from where the previous attempt stopped:
  ---
  {partial_output[:2000]}
  ---
  ```
- Set `context.max_runtime_seconds` to 1.5x adaptive timeout

### 6. Timeout Efficiency Metrics

New endpoint: `GET /api/agent/timeout-metrics`

```json
{
  "generated_at": "2026-03-30T12:00:00Z",
  "window": "7d",
  "total_tasks": 142,
  "timed_out": 8,
  "completed_naturally": 134,
  "timeout_rate": 0.056,
  "efficiency_ratio": 0.944,
  "providers": [
    {
      "provider": "openai",
      "task_type": "impl",
      "sample_count": 30,
      "p50_ms": 3800,
      "p90_ms": 7200,
      "adaptive_timeout_ms": 10800,
      "timeout_count": 2,
      "timeout_rate": 0.067
    }
  ]
}
```

Target: `efficiency_ratio > 0.90` after 30 days of data.

## Files to Create/Modify

- `api/app/models/agent.py` — add TimeoutSample model; add partial_output, partial_output_at, partial_output_pct, is_resume, resumed_from_task_id, resume_task_id to task context
- `api/app/services/timeout_adaptive_service.py` — **CREATE NEW** — JSONL storage, percentile computation, adaptive timeout formula
- `api/app/routers/agent_tasks_routes.py` — add GET /api/agent/timeout-metrics and GET /api/agent/timeout-recommendation endpoints
- `api/scripts/agent_runner.py` — use adaptive timeout; add partial output capture on timeout; emit timeout samples
- `api/app/services/agent_execution_service.py` — emit timeout samples on complete_task / fail_task
- `api/app/services/smart_reaper_service.py` — inject is_resume, prepend partial output to direction on resume task
- `api/tests/test_timeout_adaptive_service.py` — **CREATE NEW** — tests for percentile computation, fallback logic
- `api/tests/test_agent_runner.py` — add tests for adaptive timeout selection and partial output capture
- `docs/RUNBOOK.md` — add Data-Driven Timeout Tuning section

## Acceptance Tests

The implementation is complete when ALL of the following are true:

- [ ] `api/app/services/timeout_adaptive_service.py` exists and exports `add_sample`, `get_timeout_ms`, `get_timeout_stats`
- [ ] `GET /api/agent/timeout-recommendation` returns p50, p90, adaptive_timeout_ms with correct formula
- [ ] `GET /api/agent/timeout-metrics` returns efficiency_ratio, timeout_rate, and per-provider breakdown
- [ ] Agent runner uses adaptive timeout when sample_count >= 5; falls back to fixed otherwise
- [ ] On timeout, task context captures `partial_output`, `partial_output_pct`, and `resume_task_id`
- [ ] Resume tasks have `is_resume=True` and prepend partial output to direction
- [ ] Logs show `timeout=adaptive(...)` or `timeout=fixed(...)` with provider and task_type
- [ ] `POST /api/agent/timeout-samples` accepts and stores a sample (201 response)
- [ ] JSONL compaction retains last 1000 samples per provider x task_type

Verification commands:
```bash
cd api && pytest -q tests/test_timeout_adaptive_service.py
curl -s https://api.coherencycoin.com/api/agent/timeout-recommendation?provider=openai&task_type=impl
curl -s https://api.coherencycoin.com/api/agent/timeout-metrics?window=7d
```
Manual validation: Check `api/logs/agent_runner.log` for `timeout=adaptive` or `timeout=fixed` entries.

## API Contract

### GET /api/agent/timeout-metrics

**Request:** `window` query param — `24h`, `7d`, `30d` (default `7d`)

**Response 200:**
```json
{
  "generated_at": "2026-03-30T12:00:00Z",
  "window": "7d",
  "total_tasks": 142,
  "timed_out": 8,
  "completed_naturally": 134,
  "timeout_rate": 0.056,
  "efficiency_ratio": 0.944,
  "providers": [...]
}
```

### GET /api/agent/timeout-recommendation

**Request:** `provider` and `task_type` query params (required)

**Response 200:**
```json
{
  "provider": "openai",
  "task_type": "impl",
  "sample_count": 30,
  "p50_ms": 3800,
  "p90_ms": 7200,
  "adaptive_timeout_ms": 10800,
  "fallback_used": false,
  "derived_from": "adaptive(p90*1.5, samples=30)"
}
```

### POST /api/agent/timeout-samples

**Request:**
```json
{
  "provider": "openai",
  "task_type": "impl",
  "elapsed_ms": 6840,
  "outcome": "completed",
  "task_id": "test_001",
  "idea_id": "idea_xyz"
}
```

**Response 201:** sample recorded.

## Data Model

```python
class TimeoutSample(BaseModel):
    provider: str
    task_type: str
    elapsed_ms: int
    completed_at: datetime
    outcome: Literal["completed", "failed", "timed_out"]
    task_id: str
    idea_id: str | None = None

class TimeoutStats(BaseModel):
    provider: str
    task_type: str
    sample_count: int
    p50_ms: int | None
    p90_ms: int | None
    adaptive_timeout_ms: int
    fallback_used: bool
    derived_from: str  # e.g. "adaptive(p90*1.5)" or "fixed(default)"
```

## Verification Scenarios

### Scenario 1: First task uses fixed timeout, subsequent tasks use adaptive

**Setup:** `timeout_samples.jsonl` is empty or has fewer than 5 samples for `openai/impl`.

**Action:**
```bash
# Record first sample
curl -s -X POST https://api.coherencycoin.com/api/agent/timeout-samples \
  -H "Content-Type: application/json" \
  -d '{"provider":"openai","task_type":"impl","elapsed_ms":5000,"outcome":"completed","task_id":"test_001"}'

# Query recommendation
curl -s "https://api.coherencycoin.com/api/agent/timeout-recommendation?provider=openai&task_type=impl"
```

**Expected:** First call returns HTTP 201. Second call returns JSON with `sample_count=1`, `fallback_used=true`, `derived_from="fixed(baseline=2400s, samples=1<5)"`.

**Edge:** Request recommendation for unknown provider/task_type with no samples → returns baseline fixed timeout with `fallback_used=true`.

### Scenario 2: Adaptive timeout converges after 30 samples

**Setup:** Pre-populate `timeout_samples.jsonl` with 30 samples for `openai/impl` with p90=7200ms.

**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/agent/timeout-recommendation?provider=openai&task_type=impl"
```

**Expected:** JSON has `sample_count=30`, `p50_ms` and `p90_ms` from actual data, `adaptive_timeout_ms=max(7200*1.5, 600000)=10800`, `fallback_used=false`.

**Edge:** Fewer than 5 samples → returns baseline with `fallback_used=true`, `derived_from="fixed(baseline)"`.

### Scenario 3: Timeout metrics dashboard shows efficiency

**Setup:** 7 days of samples with 5 timeouts and 95 natural completions.

**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/agent/timeout-metrics?window=7d"
```

**Expected:** JSON with `total_tasks=100`, `timed_out=5`, `completed_naturally=95`, `timeout_rate=0.05`, `efficiency_ratio=0.95`. Each provider shows its own `timeout_rate` and `adaptive_timeout_ms`.

**Edge:** No data for window → returns zeros with empty providers list, not HTTP 500.

### Scenario 4: Task timeout captures partial output

**Setup:** A task hits its deadline with partial output in the running log.

**Action:**
```bash
# Verify the task's partial output is captured
curl -s "https://api.coherencycoin.com/api/agent/tasks/{task_id}" | python3 -c "
import sys, json
t = json.load(sys.stdin)
ctx = t.get('context', {})
print('partial_output present:', 'partial_output' in ctx)
print('partial_output_at present:', 'partial_output_at' in ctx)
print('partial_output_pct:', ctx.get('partial_output_pct'))
print('resume_task_id:', ctx.get('resume_task_id'))
"
```

**Expected:** `partial_output` is non-empty string, `partial_output_at` is ISO timestamp, `partial_output_pct` is 0-100 integer, `resume_task_id` is set if smart reaper ran.

**Edge:** Task times out before any output → `partial_output=""`, `partial_output_pct=0`.

### Scenario 5: Resume task continues from partial output

**Setup:** A `timed_out` task with `partial_output="file = open..."` and `is_resume=false`.

**Action:**
```bash
# Get the original task
curl -s "https://api.coherencycoin.com/api/agent/tasks/{task_id}"

# Get the resume task (referenced by resume_task_id)
curl -s "https://api.coherencycoin.com/api/agent/tasks/{resume_task_id}"
```

**Expected:** Original task has `resume_task_id` set. Resume task has `is_resume=true`, `resumed_from_task_id={original_id}`, and its `direction` starts with `[RESUME FROM TIMEOUT — partial_output_pct=N%]`.

**Edge:** Resume task created with no `partial_output` on original → direction contains only original direction without partial output marker, no `[RESUME FROM TIMEOUT]` prefix.

## Risks and Assumptions

- **Risk:** Cold-start bias — early samples reflect a warm-up period. Mitigation: require minimum 5 samples before switching from fixed to adaptive.
- **Risk:** Provider speed drift — a provider may slow down and adaptive timeout lags. Mitigation: p90 is more responsive than p99; upper clamp prevents runaway.
- **Risk:** JSONL storage grows unbounded. Mitigation: compaction retaining last 1000 samples per provider×task_type; daily job.
- **Assumption:** `complete_task` / `fail_task` in `agent_execution_service.py` are the canonical completion points — no completions bypass them.
- **Assumption:** `agent_runner.log` is the right place to emit timeout selection reasons for debugging.

## Known Gaps and Follow-up Tasks

- `task task_timeout_automatic_adjustment_001` — automatically update `AGENT_TASK_TIMEOUT_*` environment variables when efficiency_ratio drops below 0.85 for 3 consecutive days.
- `task task_timeout_provider_degradation_detection_002` — detect when p90 for a provider increases >50% week-over-week and alert.
- `task task_timeout_cli_path_003` — extend adaptive timeout to CLI executor path (`_dispatch_cli_task_and_wait`) in addition to OpenRouter path.
- `task task_timeout_ui_dashboard_004` — display timeout efficiency trends in web dashboard.
- `task task_timeout_compaction_005` — implement JSONL compaction to prevent unbounded log growth.

## Evidence of Working

1. `GET /api/agent/timeout-metrics` returns `efficiency_ratio > 0` with actual data after 7 days.
2. `agent_runner.log` shows `timeout=adaptive(...)` or `timeout=fixed(...)` with provider and task_type on every task pickup.
3. Resume tasks' `direction` field starts with `[RESUME FROM TIMEOUT — partial_output_pct=N%]`.
4. `efficiency_ratio` trend (queried weekly) increases from ~0.85 toward ~0.95 after 30 days of adaptive tuning.
5. `GET /api/agent/timeout-recommendation?provider=openai&task_type=impl` returns non-null `adaptive_timeout_ms` with `fallback_used=false` after 30+ samples.

## Out of Scope

- Automatic runtime mutation of provider timeout settings from recommendations (requires human approval gate).
- Changing the smart reaper's `is_runner_alive` check or `REAP_MAX_EXTENSIONS` logic.
- Modifying `agent_execution_hooks.py` progress event frequency — that is owned by the executor.
- Replacing `specs/136-data-driven-timeout-dashboard.md` — that spec covers the human-facing dashboard; this spec covers the runtime timeout + resume mechanism.