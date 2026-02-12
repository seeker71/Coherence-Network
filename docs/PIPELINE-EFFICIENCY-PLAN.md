# Pipeline Efficiency & Self-Improvement Plan

> How we measure, debug, and improve the agent pipeline — time, cost, accuracy, prompt effectiveness — with hierarchical visibility and automatic improvement toward the overall goal.

## 1. Overall Goal (North Star)

**Coherence Network delivers open source contribution intelligence**: map the ecosystem, compute project health scores, enable funding flows. The agent pipeline accelerates this by autonomously executing backlog items (spec → impl → test → review) with minimal human time.

**Success criteria for the pipeline:**
- Backlog items complete with high success rate
- Low wall-clock time per item
- Predictable, low cost per task
- Spec compliance and test pass rate
- Human attention only when needed (needs_decision, failures)

---

## 2. Hierarchical System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 0: GOAL                                                                │
│   Product: OSS intelligence graph, coherence scores, funding flows           │
│   Pipeline goal: Maximize backlog throughput while maintaining quality       │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: ORCHESTRATION                                                       │
│   project_manager     backlog → phases (spec/impl/test/review)               │
│   agent_runner        poll pending → execute → PATCH status                  │
│   overnight_pipeline  run_overnight_pipeline.sh (PM + runner)                │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: TASK EXECUTION                                                      │
│   API (create_task, PATCH)  agent_service (routing, templates)               │
│   Cursor CLI / Claude Code  agent "direction" --model X                      │
│   Subagents                product-manager, qa-engineer, dev-engineer, etc.  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: ARTIFACTS & OUTCOMES                                                │
│   specs/  implementation files  tests  task logs  pipeline state             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**What needs attention at each layer:**

| Layer | Attention Signals |
|-------|-------------------|
| 0 Goal | Goal progress stalled; backlog misaligned with product roadmap |
| 1 Orchestration | PM stuck; runner not picking tasks; needs_decision backlog |
| 2 Execution | High failure rate; long durations; wrong model/prompt chosen |
| 3 Artifacts | Spec drift; tests failing; flaky builds; duplicate work |

---

## 3. Efficiency Dimensions

### 3.1 Time Spent

| Metric | How to measure | Target |
|--------|----------------|--------|
| **Per-task duration** | `duration_seconds` in task log; PATCH timestamp diff | P50 < 60s for spec/test; < 120s for impl |
| **Wall-clock per backlog item** | First task created → last task (review) completed | < 15 min end-to-end |
| **Queue wait time** | Pending task `created_at` until `started_at` | < 2 min |
| **Human time per item** | Count of needs_decision, manual fixes, reviews | < 5 min |

**Implementation:** Persist `started_at`, `updated_at`; compute duration on completion; aggregate by task_type and model. Add `GET /api/agent/metrics?metric=time`.

### 3.2 Cost Incurred

| Metric | How to measure | Target |
|--------|----------------|--------|
| **Per-task cost** | Cursor/Claude usage; token count when available | Track; alert on > $0.50/task |
| **Daily/weekly spend** | Sum by model, executor | Budget threshold; auto-throttle |
| **Cost per backlog item** | Sum of spec+impl+test+review tasks | Compare cursor/auto vs composer-1 |

**Implementation:** Cursor CLI may expose usage in output or logs; Claude API returns usage in response. Parse and store. Fallback: proxy by task count × model tier (e.g. auto=0.1, composer=0.3 units).

### 3.3 Accuracy

| Metric | How to measure | Target |
|--------|----------------|--------|
| **Task success rate** | completed / (completed + failed) | > 85% |
| **Spec compliance** | Spec Guard pass; files in spec list | 100% on pass |
| **Test pass rate** | pytest exit 0 after impl | > 90% |
| **Review pass rate** | review task output contains "pass" | Track; improve prompts |

**Implementation:** Already have status; add post-impl pytest run in pipeline; parse review output for pass/fail; persist in metrics.

### 3.4 Prompt Selection & Effectiveness

| Metric | How to measure | Target |
|--------|----------------|--------|
| **Prompt variant outcome** | A/B: variant A vs B → success rate, duration | Best variant wins |
| **build_direction clarity** | Correlation: direction length/clarity → success | Shorter, clearer = better |
| **Subagent effectiveness** | By task_type: spec vs impl vs test vs review success | Identify weak subagent |
| **Template fit** | Specs match TEMPLATE.md sections | Auto-check on spec completion |

**Implementation:** Tag tasks with `prompt_variant`, `direction_template`; aggregate by variant. Add direction quality heuristics (length, structure).

---

## 4. Automatic Measurement

### 4.1 Instrumentation Points

| Point | What to capture | Where |
|-------|-----------------|-------|
| Task create | task_id, task_type, model, executor, direction_hash, prompt_variant | agent_service |
| Task start | started_at | agent_runner PATCH |
| Task complete | status, duration_seconds, output_len, exit_code | agent_runner |
| Pipeline phase | backlog_index, phase, iteration | project_manager |
| Review output | pass/fail, issues_count | Parse from output |

### 4.2 Metrics Store

- **Format:** SQLite or JSON append (MVP); PostgreSQL when available
- **Schema:** TaskMetric (task_id, task_type, model, executor, duration_seconds, status, created_at, prompt_variant)
- **Aggregation:** Rolling 7d window; by task_type, model, prompt_variant

### 4.3 Dashboards & APIs

- `GET /api/agent/metrics` — P50/P95 duration, success rate, by model/task_type
- `GET /api/agent/pipeline-status` — Already exists; extend with attention flags
- `check_pipeline.py --metrics` — Print efficiency summary
- **Hierarchical view:** Top = goal progress; then PM state; then task metrics; then artifact health

---

## 5. Automatic Debugging

### 5.1 Attention Detection

| Condition | Severity | Action |
|-----------|----------|--------|
| Pending task > 30 min | Medium | Log; suggest runner/PM check |
| 3+ consecutive failures same phase | High | Create needs_decision; suggest heal |
| Review says fail but impl passed tests | Medium | Flag inconsistency |
| Spec task output missing "Spec path:" | Low | Flag incomplete spec |
| Pipeline stuck (no task progress 10+ min) | High | Alert; suggest restart runner |

### 5.2 Root Cause Hints

- **Long duration:** Model slow; direction too large; subagent overloaded
- **High failure:** Wrong model for task; unclear direction; spec too vague
- **needs_decision pile-up:** Ambiguous directions; scope creep; human bottleneck

### 5.3 Debug Flow

1. **Detect** — Metrics + heuristics flag anomaly
2. **Context** — Fetch task log, direction, output, PM state
3. **Suggest** — "Try clearer direction" / "Switch model" / "Split backlog item"
4. **Optional auto-fix** — Create heal task; retry with variant B

---

## 6. Automatic Improvement

### 6.1 Prompt & Direction Improvement

- **A/B test prompts:** Two variants of build_direction; assign by hash(task_id) % 2; compare success rate
- **Learn from failures:** Extract common failure patterns; suggest direction templates
- **Auto-tune:** If variant B wins 10+ tasks, promote B to default

### 6.2 Model & Executor Tuning

- **Model routing:** Track success rate by (task_type, model); route to best
- **Executor choice:** Compare cursor/auto vs composer-1: success rate, duration, cost
- **Fallback:** On 2 failures with model A, retry with model B (e.g. auto → composer)

### 6.3 Pipeline & Backlog Improvement

- **Auto-split large items:** If impl fails 2× with "too broad", create task "Split backlog item N"
- **Priority reorder:** If goal X stalled, surface items that unblock X
- **Queue hygiene:** Detect duplicate directions; merge or skip

### 6.4 Feedback Loop

```
Measure → Detect anomaly → Suggest/auto-fix → Re-measure
```

- Weekly: Aggregate metrics; identify worst-performing (task_type, model, variant)
- On failure: Record; if pattern (same direction structure), suggest improvement
- On success: Reinforce (this variant works)

---

## 7. Implementation Roadmap

| Phase | Scope | Effort |
|-------|-------|--------|
| **1. Core metrics** | Persist duration, status; GET /api/agent/metrics | 1–2 days |
| **2. Attention signals** | Heuristics: stuck, failures, inconsistencies; extend pipeline-status | 1 day |
| **3. Hierarchical view** | Goal → PM → tasks → artifacts in check_pipeline / API | 1 day |
| **4. A/B prompts** | prompt_variant in context; aggregate by variant | 1–2 days |
| **5. Auto-debug** | Attention → create needs_decision or heal task | 1 day |
| **6. Cost tracking** | Parse usage from Cursor/Claude; store; alert | 2–3 days |
| **7. Auto-improvement** | Promote winning variant; retry with different model | 2–3 days |

---

## 8. Decision Gates

- **Metrics storage:** SQLite for MVP (single file, no extra deps); migrate to PostgreSQL when DB is standard
- **Auto-scheduling:** Start with "suggest" only; human approves. Enable full auto after 1 month of stable metrics
- **Prompt changes:** All prompt edits go through spec or explicit approval; no silent A/B promotion without review

---

## 9. See Also

- [specs/026-pipeline-observability-and-auto-review.md](../specs/026-pipeline-observability-and-auto-review.md) — Detailed requirements
- [docs/AGENT-DEBUGGING.md](AGENT-DEBUGGING.md) — Manual debugging
- [docs/PLAN.md](PLAN.md) — Product and tech roadmap
