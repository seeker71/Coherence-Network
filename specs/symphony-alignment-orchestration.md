---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/services/agent_service.py
    symbols: [task state, task creation, task updates]
  - file: api/scripts/project_manager.py
    symbols: [spec/impl/test/review orchestration]
  - file: api/scripts/agent_runner.py
    symbols: [executor dispatch, task claim, task completion]
  - file: api/app/services/agent_service_pipeline_status.py
    symbols: [pipeline status]
  - file: api/app/models/agent.py
    symbols: [ControlPlaneTask, ControlPlaneProof]
  - file: api/tests/test_agent_control_plane.py
    symbols: [control-plane normalization, follow-through blockers, orchestration tissue]
requirements:
  - "Map OpenAI Symphony concepts to Coherence Network's existing orchestration surfaces without replacing the current delivery contract."
  - "Define one normalized control-plane task model that can represent internal API tasks, backlog items, GitHub issues, and future Linear issues."
  - "Specify a repo-owned workflow policy layer that preserves AGENTS.md while adding a machine-readable runtime contract."
  - "Define explicit dispatcher, workspace lifecycle, executor runner, evidence, reconciliation, and status-surface responsibilities."
  - "Preserve Coherence proof requirements: worktree-only execution, local gates, commit evidence, PR checks, and deploy validation where applicable."
done_when:
  - "A follow-up implementation can add tracker adapters without changing the executor contract."
  - "A follow-up implementation can expose active, blocked, retrying, review-ready, and deploy-ready work from one status surface."
  - "Existing AGENTS.md and task-card constraints remain the source of truth until a machine-readable workflow file is implemented."
test: "python3 scripts/validate_spec_quality.py --base origin/main --head HEAD"
constraints:
  - "Planning spec only; no runtime behavior changes in this task."
  - "Do not weaken mandatory worktree, evidence, PR, CI, or deploy contracts."
  - "Linear support must be an adapter behind the normalized task model, not a special-case control plane."
---

> **Parent idea**: [agent-pipeline](../ideas/agent-pipeline.md)
> **Related specs**: [project-manager-pipeline](project-manager-pipeline.md), [pipeline-observability-and-auto-review](pipeline-observability-and-auto-review.md), [unified-agent-cli-flow-patch-on-fail](unified-agent-cli-flow-patch-on-fail.md), [task-claim-tracking-and-roi-dedupe](task-claim-tracking-and-roi-dedupe.md)

# Spec: Symphony Alignment for Coherence Orchestration

## Purpose

OpenAI Symphony defines a tracker-driven orchestration pattern where issue trackers become control planes for isolated Codex implementation runs. Coherence Network already has a strong proof-oriented agent pipeline, but the orchestration concepts are spread across API tasks, backlog scans, runner scripts, worktree rules, evidence files, and status endpoints.

This spec digests Symphony into Coherence's architecture without replacing the existing delivery contract. The goal is to make the control plane explicit: one normalized task model, one policy layer, one dispatcher/reconciler shape, deterministic workspaces, and proof-first status reporting.

## Requirements

- [ ] **R1: Symphony mapping**: Document how Symphony's workflow loader, tracker client, orchestrator, workspace manager, agent runner, logging, and status surface map to existing Coherence components.
- [x] **R2: Normalized task model**: Define a task shape that can represent internal API tasks, backlog entries, GitHub issues, future Linear issues, and generated ROI tasks with common fields for state, source, priority, labels, blockers, workspace identity, proof requirements, and completion criteria. Initial implementation adds `ControlPlaneTask` and normalizes active internal API tasks.
- [ ] **R3: Policy layer**: Preserve `AGENTS.md` as the human and agent workflow authority while introducing a future machine-readable workflow contract, such as `WORKFLOW.md` or `config/orchestration_workflow.json`, for dispatch-safe runtime settings.
- [ ] **R4: Dispatcher contract**: Specify eligibility rules for active states, terminal states, priority order, blocker handling, task claims, max concurrency, stale detection, and retry backoff.
- [ ] **R5: Workspace lifecycle**: Require deterministic per-task branch and worktree naming, root containment, prompt-gate execution, lifecycle hooks, cleanup rules for terminal work, and refusal to run implementation commands in the primary workspace.
- [ ] **R6: Executor runner boundary**: Keep Codex, OpenClaw, Cursor, and other executors behind the existing task runner abstraction. Future `codex app-server` support may be added as one runner mode, not as a replacement for the current executor policy.
- [ ] **R7: Evidence and reconciliation**: Attach proof to task execution records, not only commits. Reconciliation must compare tracker state, task state, PR state, CI state, evidence validation, and deploy readiness before declaring work complete. Initial implementation adds follow-through proof fields and stale PR blockers to the status surface.
- [x] **R8: Status surface**: Expose one operator-readable and machine-readable status view for active, blocked, retrying, review-ready, merge-ready, deploy-ready, stale, and failed work. Initial implementation extends `/api/agent/pipeline-status` with `followthrough`, `orchestration_tissue`, and normalized active tasks.
- [ ] **R9: Adapter-first Linear support**: Add Linear only as a tracker adapter behind the normalized task model. GitHub Issues, internal API tasks, backlog specs, and ROI-generated tasks must continue to use the same dispatcher and evidence path.
- [x] **R10: Follow-through unblocker**: Treat stale open Codex PRs as active orchestration blockers. The reconciler must surface them with the exact PR URL, failing or pending gate, recommended action, and owner so new work does not accumulate behind abandoned follow-through.

## Research Inputs

- `2026-04-28` - [OpenAI Symphony repository](https://github.com/openai/symphony) - Symphony describes autonomous implementation runs driven by project work, with proof before landing changes.
- `2026-04-28` - [OpenAI Symphony service specification](https://github.com/openai/symphony/blob/main/SPEC.md) - Draft v1 defines Linear-compatible polling, per-issue workspaces, Codex app-server integration, retry/reconciliation, workflow policy, and observability responsibilities.
- Existing Coherence specs:
  - `specs/project-manager-pipeline.md`
  - `specs/pipeline-observability-and-auto-review.md`
  - `specs/unified-agent-cli-flow-patch-on-fail.md`
  - `specs/task-claim-tracking-and-roi-dedupe.md`

## Symphony to Coherence Mapping

| Symphony concept | Coherence surface today | Alignment target |
|---|---|---|
| Workflow loader | `AGENTS.md`, task-card contract, deploy contract | Add a machine-readable workflow policy while preserving `AGENTS.md` authority |
| Tracker client | `/api/agent/tasks`, backlog specs, ROI-generated tasks | Introduce tracker adapters that normalize all work into one task shape |
| Orchestrator | `project_manager.py`, pipeline advance/status services | Centralize eligibility, dispatch, retry, and reconciliation policy |
| Workspace manager | Mandatory `~/.claude-worktrees/...` flow | Make branch/worktree lifecycle explicit per task |
| Agent runner | `agent_runner.py`, local runner, executor policy | Keep executor-neutral runner boundary; add app-server mode later if useful |
| Logging | task logs, runtime events, evidence JSON | Attach execution proof and state transitions to each task |
| Status surface | status report, metrics, monitor issues | One status view for active, blocked, retrying, review, merge, deploy, and stale states |

## Proposed Control-Plane Model

```yaml
ControlPlaneTask:
  id: string
  source:
    kind: internal_api | backlog | github_issue | linear_issue | roi_generated
    external_id?: string
    url?: string
  title: string
  description?: string
  state: pending | running | blocked | needs_decision | review_ready | merge_ready | deploy_ready | completed | failed | terminal
  priority?: integer
  labels: [string]
  blocked_by: [string]
  task_type: spec | impl | test | review | heal | deploy | monitor
  files_allowed: [string]
  done_when: [string]
  commands: [string]
  constraints: [string]
  workspace:
    branch: string
    path: string
    key: string
  execution:
    executor: string
    model?: string
    claimed_by?: string
    claimed_at?: string
    attempts: integer
    max_attempts: integer
    next_retry_at?: string
  proof:
    local_validation: pending | pass | fail
    evidence_file?: string
    pr_url?: string
    ci_status: pending | pass | fail
    deploy_status: pending | pass | fail | not_required
    followthrough_status: clear | blocked
    followthrough_blockers:
      - kind: stale_pr | failing_check | stale_deploy | missing_evidence
        url?: string
        command?: string
        owner?: string
```

## Runtime Architecture Target

```text
Tracker adapters
  -> normalized ControlPlaneTask

Policy loader
  -> workflow config, task-card constraints, proof requirements

Dispatcher
  -> eligible tasks, priority, blockers, claims, concurrency

Workspace manager
  -> branch, worktree, prompt gate, lifecycle hooks

Executor runner
  -> Codex/OpenClaw/Cursor session, logs, artifacts

Evidence validator
  -> tests, local gates, commit evidence, PR checks, deploy proof

Reconciler
  -> task state, tracker state, PR state, CI state, stale runs, retries

Status surface
  -> active, blocked, retrying, review-ready, merge-ready, deploy-ready, failed
```

## Phased Implementation Plan

### Implemented Slice: Follow-through Vitality

- `ControlPlaneTask`, proof, execution, source, and workspace models exist in `api/app/models/agent.py`.
- `/api/agent/pipeline-status` now includes `followthrough` with stale Codex PR blockers, PR URLs, owners, reasons, and suggested commands.
- `/api/agent/pipeline-status` now includes `orchestration_tissue` with `vitality_score`, `circulation`, `stale_tissue_count`, and `hardened_tissue_count`.
- `/api/agent/pipeline-status` now includes `control_plane.normalized_active` for running and pending internal API tasks.
- `api/tests/test_agent_control_plane.py` validates internal task normalization, stale PR remediation guidance, and tissue signals.

### Phase 1: Contract and Inventory

- Create a Symphony alignment inventory that marks each concept as `covered`, `partial`, or `missing`.
- Identify the current task state enum and runner state transitions.
- Decide whether the machine-readable workflow contract should live in `WORKFLOW.md`, `config/orchestration_workflow.json`, or both.

### Phase 2: Normalized Task Model

- Add a normalized model or adapter layer without changing external task APIs.
- Map existing internal tasks and backlog items into the model.
- Preserve task-card fields: `goal`, `files_allowed`, `done_when`, `commands`, and `constraints`.

### Phase 3: Dispatcher and Reconciler

- Make eligibility, active states, terminal states, stale timeout, retry backoff, max concurrency, and blocker handling explicit.
- Reconcile task status against PR checks, evidence validation, and deploy status.
- Reconcile stale open Codex PRs before allowing new branches to advance; if checks are green and merge state is clean, the operator path is merge-or-close, otherwise the status surface must show the exact failing check and remediation command.
- Ensure duplicate work prevention uses existing claim and fingerprint behavior.

### Phase 4: Status Surface

- Add or extend a status endpoint/report that groups work by active, blocked, retrying, review-ready, merge-ready, deploy-ready, stale, failed, and completed.
- Include evidence file paths, PR URLs, check states, deploy states, follow-through blockers, attempts, executor, model, and latest failure reason.

### Phase 5: Tracker Adapters

- Add Linear as an adapter after the normalized model is stable.
- Add GitHub Issues as an adapter if it is more immediately useful for the current repo workflow.
- Keep ticket writes, comments, and state transitions workflow-defined and auditable.

## Files to Create/Modify for Follow-up Implementation

- `api/app/models/agent.py` - normalized control-plane task model or compatibility wrapper.
- `api/app/services/agent_service.py` - task normalization and state transitions.
- `api/app/services/agent_service_pipeline_status.py` - grouped orchestration status.
- `api/scripts/project_manager.py` - dispatcher/reconciler policy.
- `api/scripts/agent_runner.py` - proof attachment and workspace metadata.
- `api/tests/test_agent_control_plane.py` - model, eligibility, and reconciliation tests.
- `docs/system_audit/commit_evidence_<date>_symphony_alignment.json` - proof for implementation commits.

## Acceptance Tests

- `api/tests/test_agent_control_plane.py` validates that existing internal tasks normalize into `ControlPlaneTask` without losing task-card fields.
- `api/tests/test_agent_control_plane.py` validates that backlog/spec-derived work normalizes into the same shape as API-created work.
- `api/tests/test_agent_control_plane.py` validates that the dispatcher refuses blocked tasks, duplicate claimed tasks, and tasks outside active states.
- `api/tests/test_agent_control_plane.py` validates that the reconciler marks stale or failed tasks with a machine-readable reason.
- `api/tests/test_agent_control_plane.py` validates that the status surface groups active, blocked, retrying, review-ready, merge-ready, deploy-ready, failed, and completed tasks.
- `api/tests/test_agent_control_plane.py` validates that a stale Codex PR blocks new work with the exact PR URL and recommended remediation action.
- `api/tests/test_linear_tracker_adapter.py` uses fixtures and does not require live Linear credentials.

## Verification

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
cd api && python3 -m pytest -q tests/test_agent_control_plane.py tests/test_agent_task_claims.py tests/test_flow_cli.py tests/test_agent_monitor_helpers.py tests/test_stale_task_reaper.py
```

## Out of Scope

- Replacing the current executor policy with Symphony's Elixir reference implementation.
- Requiring Linear as the only control plane.
- Weakening prompt-gate, local gate, evidence, PR, CI, or deploy requirements.
- Adding runtime behavior in this planning-only task.

## Risks and Assumptions

- Assumption: Coherence should absorb Symphony as an orchestration pattern, not as a wholesale runtime replacement.
- Assumption: Internal API tasks and backlog tasks remain first-class even after external tracker adapters are added.
- Risk: A machine-readable workflow file could drift from `AGENTS.md`; mitigate by adding validation that reports conflicts rather than silently choosing one.
- Risk: Expanding status and reconciliation can create noisy blockers; mitigate by making blocker reasons structured and actionable.

## Known Gaps

- Follow-up task: add a normalized `ControlPlaneTask` model; current task state is still distributed across API services, scripts, logs, and evidence records.
- Follow-up task: add a Linear tracker adapter after the normalized model is stable.
- Follow-up task: add one status surface that proves tracker state, worktree state, PR state, CI state, deploy state, and evidence state together.
- Follow-up task: add a machine-readable workflow policy; `AGENTS.md` remains the authoritative contract until then.
- Follow-up task: extend stale PR follow-through reconciliation beyond live GitHub CLI collection into persisted monitor reports so deployed environments without `gh` still show the latest known blocker state.

## Decision Gates

- Choose workflow contract location and syntax.
- Choose first external tracker adapter: GitHub Issues or Linear.
- Decide whether Codex app-server support is needed before the normalized model and status surface are complete.
