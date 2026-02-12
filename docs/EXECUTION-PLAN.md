# Integrated Execution Plan

> One execution goal, one loop: product delivery + pipeline self-improvement + auto-update + monitor. Integrates [PLAN](PLAN.md), [PIPELINE-EFFICIENCY-PLAN](PIPELINE-EFFICIENCY-PLAN.md), [COMMUNITY-RESEARCH-PRIORITIES](COMMUNITY-RESEARCH-PRIORITIES.md), and [spec 026](../specs/026-pipeline-observability-and-auto-review.md).

---

## 1. Overall Execution Goal

**Deliver Coherence Network product outcomes while continuously improving the pipeline that delivers them.**

| Dimension | Goal |
|-----------|------|
| **Product** | OSS intelligence graph, coherence scores, funding flows (see [PLAN](PLAN.md)) |
| **Pipeline** | High success rate, low time/cost, spec compliance, minimal human time |
| **Self-improvement** | Research, measure, prioritize, fix; community traction and forum |
| **System coherence** | Framework auto-updates when features pass; monitor detects and fixes issues |

---

## 2. The Execution Loop

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         INTEGRATED EXECUTION LOOP                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   Backlog ──► project_manager ──► agent_runner ──► Tasks (spec/impl/test/review)  │
│       │              │                    │                      │                │
│       │              │                    │                      ▼                │
│       │              │                    │              ┌──────────────┐         │
│       │              │                    │              │   Monitor    │         │
│       │              │                    │              │  - Progress  │         │
│       │              │                    │              │  - Metrics   │         │
│       │              │                    │              │  - Attention │         │
│       │              │                    │              └──────┬───────┘         │
│       │              │                    │                     │                 │
│       │              │                    │                     ▼                 │
│       │              │                    │              ┌──────────────┐         │
│       │              │                    │              │ Auto-Update  │         │
│       │              │                    │              │ (on pass)    │         │
│       │              │                    │              └──────┬───────┘         │
│       │              │                    │                     │                 │
│       │              │                    ▼                     ▼                 │
│       │              │            ┌──────────────┐      ┌──────────────┐         │
│       │              └───────────►│ Meta-Pipeline│◄─────│ Auto-Detect  │         │
│       │                           │ (improve     │      │ & Auto-Fix   │         │
│       │                           │  pipeline)   │      │              │         │
│       │                           └──────────────┘      └──────────────┘         │
│       │                                    │                     ▲                │
│       └────────────────────────────────────┴─────────────────────┘                │
│                          Research & Prioritization                                │
│                          (COMMUNITY-RESEARCH-PRIORITIES)                          │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Meta-Pipeline: Working on the Pipeline Itself

The **meta-pipeline** is the backlog of work that improves the pipeline. It runs through the same spec→impl→test→review flow as product work.

### Meta-Pipeline Backlog Sources

| Source | Items |
|--------|-------|
| **spec 026** | Metrics, A/B testing, goal tracking, auto-review, auto-scheduling |
| **PIPELINE-EFFICIENCY-PLAN** | Core metrics, attention signals, hierarchical view, cost tracking |
| **COMMUNITY-RESEARCH-PRIORITIES** | Forum setup, docs, integration, publishing |
| **Gaps from monitor** | Auto-generated when monitor detects recurring issues |

### Meta-Pipeline Execution

- Add meta-pipeline items to `specs/006-overnight-backlog.md` or a dedicated `specs/007-meta-pipeline-backlog.md`
- Run project_manager + agent_runner on that backlog (same tools, same flow)
- Example items: "Implement GET /api/agent/metrics", "Add attention heuristics to pipeline-status", "Set up GitHub Discussions"
- Prioritize by Impact × Effort; align with efficiency plan phases 1–7

### Ensuring the Pipeline Continues

- **Cadence:** Reserve ~20% of backlog capacity for meta-pipeline items
- **Triggers:** When monitor flags "repeated failures" or "no metrics", add a meta-item
- **Ownership:** Human approves meta-backlog; agent implements per spec

---

## 4. Auto-Update: Framework Updates When Features Pass

When a feature is **implemented and passes spec tests**, the system auto-updates framework artifacts so the system stays coherent.

### Trigger

- **Event:** All tests for a spec pass (pytest exit 0; or CI green for the spec’s test module)
- **Scope:** Per-spec or per-PR; can run in CI or as post-merge hook

### What Gets Updated

| Artifact | Update Rule | Example |
|----------|-------------|---------|
| **SPEC-COVERAGE.md** | Mark spec as "Tested ✓" when tests pass | `| 027 New Feature | ✓ | ✓ | ✓ | Complete |` |
| **STATUS.md** | Update sprint/area status when related specs complete | `Sprint 2: coherence API done` |
| **docs/PLAN.md (5b)** | Update "Current Status" table when milestone reached | Add row when new capability ships |
| **Backlog** | Optionally mark backlog item done; advance index | PM state already does this |
| **Framework manifest** | If we add a `specs/manifest.json` or similar: append spec id, status | `{"027": "complete"}` |

### Implementation

1. **CI job:** After `pytest` passes, run `scripts/update_spec_coverage.py` (to be created)
2. **Script reads:** Test results, spec list from `specs/`
3. **Script writes:** Updates SPEC-COVERAGE.md, STATUS.md (and optionally manifest)
4. **Rule:** Only update when tests pass; never overwrite human edits without explicit opt-in
5. **Audit:** Changes are in git; human reviews in PR

### Guardrails

- Updates are **additive or status-only** (e.g. ✓) — no removal of specs or tests
- Human can override by editing the doc; script should not conflict
- If script fails, CI still passes (script is best-effort; not blocking)

---

## 5. Monitor: Track Progress, Detect, Fix

The **monitor** ensures the system has enough information to automatically detect and fix issues.

### What the Monitor Tracks

| Category | Data | Source |
|----------|------|--------|
| **Progress** | Backlog index, phase, tasks completed/failed | project_manager state, API tasks |
| **Metrics** | Duration, success rate, by task_type/model | agent_runner logs, future GET /metrics |
| **Pipeline health** | Running task, pending count, stuck detection | pipeline-status, heuristics |
| **Artifact health** | Spec compliance, test pass, CI status | pytest, spec Guard, CI API |
| **Goal alignment** | Backlog items vs sprint goals | Backlog tags, PLAN roadmap |

### Information Needed for Auto-Detect

The system must persist and expose:

- **Task lifecycle:** created_at, started_at, updated_at, status, output (or log path)
- **Duration:** duration_seconds per task (already in task log)
- **Aggregates:** success rate by task_type, model; P50/P95 duration
- **Pipeline state:** current_task_id, phase, backlog_index, blocked
- **CI/test results:** pass/fail per run; which spec’s tests ran
- **Attention flags:** Stuck, repeated failures, needs_decision count

### Detection Rules (from PIPELINE-EFFICIENCY-PLAN)

| Condition | Severity | Auto-Detect | Auto-Fix (when enabled) |
|-----------|----------|-------------|-------------------------|
| Pending task > 30 min | Medium | ✓ | Suggest restart runner |
| 3+ consecutive failures same phase | High | ✓ | Create needs_decision; optionally heal task |
| Pipeline stuck 10+ min | High | ✓ | Alert; suggest restart |
| Success rate < 80% (7d) | Medium | ✓ | Suggest model/prompt review |
| Spec task output missing "Spec path:" | Low | ✓ | Flag; no auto-fix |
| Review says fail but tests pass | Medium | ✓ | Flag inconsistency |
| CI red | High | ✓ | Block merge; notify |

### Auto-Fix Framework

- **Phase 1 (current):** Detect + log + suggest (human acts)
- **Phase 2:** Auto-create heal task or needs_decision; human approves
- **Phase 3:** Full auto-fix for low-risk conditions (e.g. retry with different model)

**Decision gate:** Enable auto-fix only after 1 month of stable metrics and human review of suggestions.

### Monitor Implementation

- **Existing:** `check_pipeline.py`, `GET /api/agent/pipeline-status`
- **To add:** `GET /api/agent/metrics`, attention flags in pipeline-status, persistence of TaskMetric
- **Scheduler:** Cron or pipeline job runs monitor every N minutes; on anomaly, log + (optionally) create task

---

## 6. Integration with Other Docs

| Document | Role |
|----------|------|
| **[PLAN](PLAN.md)** | Product vision, roadmap, sprints — the *what* we build |
| **[PIPELINE-EFFICIENCY-PLAN](PIPELINE-EFFICIENCY-PLAN.md)** | Metrics, efficiency, auto-debug, auto-improve — the *how well* we run |
| **[COMMUNITY-RESEARCH-PRIORITIES](COMMUNITY-RESEARCH-PRIORITIES.md)** | Questions, research, prioritization, forum — the *learning and sharing* |
| **[spec 026](../specs/026-pipeline-observability-and-auto-review.md)** | Detailed requirements for observability and auto-review |
| **EXECUTION-PLAN** (this doc) | Integrates all into one loop: meta-pipeline, auto-update, monitor |
| **[SPEC-COVERAGE](SPEC-COVERAGE.md)** | Spec→impl→test map; *auto-updated* when tests pass |
| **[STATUS](STATUS.md)** | Current status; *auto-updated* when milestones complete |

---

## 7. Pipeline-in-Place Checklist

Use this to confirm the full pipeline is in place:

### Core Pipeline
- [ ] project_manager creates tasks from backlog
- [ ] agent_runner executes tasks (Cursor/Claude)
- [ ] spec → impl → test → review flow works
- [ ] Overnight pipeline runs unattended

### Meta-Pipeline
- [ ] Meta-backlog exists (efficiency, monitoring, community items)
- [ ] Meta-items run through same flow as product items
- [ ] Prioritization uses Impact × Effort; goal-aligned

### Auto-Update
- [ ] Script or CI job updates SPEC-COVERAGE when tests pass
- [ ] STATUS.md updated when milestones complete
- [ ] No overwrite of human-authored content without opt-in

### Monitor
- [ ] Progress tracked (backlog, phase, tasks)
- [ ] Metrics persisted (duration, status)
- [ ] Attention rules implemented (stuck, failures, etc.)
- [ ] Enough info for auto-detect; auto-fix gated by decision

---

## 8. See Also

- [AGENT-DEBUGGING](AGENT-DEBUGGING.md) — Manual debugging
- [RUNBOOK](RUNBOOK.md) — Ops procedures
- [specs/TEMPLATE](specs/TEMPLATE.md) — Spec format for new work
