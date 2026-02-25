# Spec: Greenfield Autonomous Intelligence System (Guidance-First, Platform/Provider/Framework Agnostic)

## Purpose

Provide a greenfield blueprint for building an autonomous intelligence system with high learning velocity and low operational drag.

This version is intentionally guidance-first: it prioritizes outcomes, decision quality, and fast adaptation. It keeps only a minimal set of hard gates where failure impact is high.

## Requirements

- [ ] Use an outcomes-first operating model (throughput, reliability, visibility, and value delivery) instead of broad compliance checklists.
- [ ] Use playbooks and decision heuristics as defaults, with explicit deviation guidance when context demands it.
- [ ] Keep hard constraints minimal: only safety-critical, integrity-critical, and rollback-critical gates are mandatory.
- [ ] Convert external research (weekly cadence) into local experiments with measurable success/failure signals.
- [ ] Treat memory and self-improvement as iterative capabilities: adopt patterns progressively, keep rollback paths, and avoid irreversible complexity.
- [ ] Keep the bot feature inventory current so operators can see what exists, what is stable, and what is still exploratory.

## Guidance Model

### 1) Outcomes Over Compliance

Use these as primary optimization targets:

1. Faster cycle time with stable quality.
2. Lower incident recurrence and lower hidden failure cost.
3. Better operator and contributor visibility.
4. Clear linkage from idea -> execution -> observed impact.

### 2) Playbooks Over Rules

For each subsystem (memory, routing, self-improvement, monitoring), define:

1. Default approach.
2. When to deviate.
3. Failure signals.
4. Recovery moves.

### 3) Decision Heuristics

Use lightweight heuristics before adding policy complexity:

1. Start with the simplest path that preserves observability.
2. Escalate only when repeated failures share a cause signature.
3. Prefer reversible changes over tightly coupled architecture jumps.
4. If a change cannot be measured, treat it as exploratory, not foundational.

### 4) Experiment Cards (Default for New Capabilities)

Use this card shape for memory/self-improvement/routing changes:

```yaml
ExperimentCard:
  hypothesis: string
  intended_benefit: string
  risk: string
  scope: string
  success_signal: string
  failure_signal: string
  stop_or_rollback_condition: string
  owner: string
```

### 5) Open Problems Backlog

Keep an explicit list of unresolved problems, with no forced certainty:

1. Memory fidelity under long-horizon compression.
2. Self-improvement reliability under distribution shift.
3. Multi-tool security boundaries for autonomous execution.
4. Cost-aware adaptation without quality collapse.

## Minimal Hard Gates (Only 3)

### Gate 1: Safety-Critical Actions

High-risk/destructive actions require explicit approval control (human-in-the-loop or policy-equivalent).

### Gate 2: Data Integrity

No silent corruption or silent loss in core operational domains (tasks, evidence, telemetry, readiness state).

### Gate 3: Public Rollback Protection

Runtime-impacting deployments require public-path validation and rollback readiness when core user flows regress.

## Architecture Guidance

### Recommended Planes

1. Product plane: domain intelligence and user-visible capabilities.
2. Execution plane: tasks, routing, runners, retries.
3. Control plane: governance, quality gates, deployment checks.
4. Observability plane: metrics, events, traceability, incident artifacts.

Guidance:

1. Keep contracts explicit between planes.
2. Keep implementation choices swappable (framework/provider/runtime agnostic boundaries).
3. Avoid hidden coupling between execution and observability layers.

## API Capability Guidance (Implementation-Agnostic)

Use capability groups instead of prescriptive route semantics:

1. Health/readiness/version visibility.
2. Task orchestration lifecycle (create/list/get/update).
3. Metrics/monitor/effectiveness/status reporting.
4. Governance and deploy-contract visibility.
5. Provider usage/readiness validation surfaces.
6. Traceability and inventory surfaces (flow + endpoint coverage).

## Data Model Guidance (if applicable)

```yaml
Idea:
  id: string
  value_hypothesis: string
  status: enum[none, partial, validated]

Task:
  id: string
  task_type: enum[spec, impl, test, review, heal]
  status: enum[pending, running, completed, failed, needs_decision]
  route_decision: object

TaskRun:
  task_id: string
  duration_seconds: number
  outcome: enum[completed, failed]
  failure_class: string|null

EvidenceRecord:
  id: string
  change_intent: enum[runtime_feature, runtime_fix, process_only, docs_only, test_only]
  linked_ideas: list[string]
  linked_specs: list[string]
  linked_tasks: list[string]
  changed_files: list[string]
  validation_summary: object

ProviderReadiness:
  provider: string
  configured: boolean
  auth_probe_passed: boolean
  execution_probe_passed: boolean
  last_failure_class: string|null

ExperimentCard:
  hypothesis: string
  success_signal: string
  failure_signal: string
  stop_or_rollback_condition: string
```

## Landscape-Informed Guidance (Week Of Feb 17-24, 2026)

### Notable External Signals

1. Anthropic released Sonnet 4.6 with stronger coding/computer-use behavior and larger-context beta positioning.
2. Google announced Gemini 3.1 Pro in preview for more complex agentic usage.
3. GitHub introduced Gemini 3.1 Pro in Copilot public preview with strong early coding-loop results.
4. Enterprise agent messaging is moving toward specialized agent behavior with stronger tool and memory integration.

### Practical Takeaway

The market is converging on tool-using assistants with stronger context handling, but many capabilities remain preview-stage. Treat headline capability gains as directional signals, then validate locally through experiments before broad adoption.

## Memory Guidance: What Works and What Still Needs Work

### What Is Working

1. Two-layer memory (short-term task state + long-term durable memory).
2. Explicit memory write policies (hot-path vs background).
3. Adaptive memory structure selection by workload.
4. Memory isolation boundaries around tool execution.

### What Is Still Unsolved

1. Universal memory representation remains unsolved.
2. Compression fidelity and long-horizon causality remain fragile.
3. Condensed memory is frequently under-leveraged in execution.
4. Multi-agent memory boundary security remains high-risk.

### Recommended Local Posture

1. Start with simple scoped memory and durable audit trails.
2. Introduce compression only with measured fidelity checks.
3. Add memory isolation before adding memory complexity.
4. Keep memory policy changes behind experiment cards.

## Self-Improvement Guidance: What Works and What Still Needs Work

### What Is Working

1. Reflection loops and prompt adaptation.
2. Skill-evolution loops (controller + executor + designer roles).
3. Policy learning around memory usage without model retraining.

### What Is Still Unsolved

1. Faithful use of condensed experience is inconsistent.
2. Safety and integrity guarantees for self-evolving behavior are immature.
3. Robustness under distribution shift is still weak.
4. Standardized evaluation for self-improvement quality is fragmented.

### Recommended Local Posture

1. Keep self-improvement scoped, logged, and reversible.
2. Require explicit success/failure signals before promoting changes.
3. Separate exploration loops from production-critical loops.
4. Prefer targeted improvements over full autonomous self-rewrite patterns.

## Pitfalls, Lessons, and Successes (Guidance Form)

### Common Pitfalls

1. Process-heavy control layers that reduce flow more than they reduce risk.
2. Provider assumptions without readiness proof.
3. Retry loops that hide root causes.
4. Passing internal checks while public user journeys break.

### Lessons Learned

1. Small, visible controls outperform large hidden policy systems.
2. Evidence quality matters more than evidence volume.
3. Non-blocking diagnostics keep velocity while preserving visibility.
4. Reliability improvements should be prioritized by measured failure concentration.

### Success Patterns to Preserve

1. Isolated execution contexts for safer parallel work.
2. High-signal preflight checks aligned with CI reality.
3. Durable traceability across idea/spec/task/validation surfaces.
4. Hierarchical status reporting for operators.
5. Cheap-first routing with bounded escalation.

## Current Bot Feature Inventory (As Built So Far)

### Product Intelligence

1. Health/readiness/version surfaces.
2. Graph/index/search/coherence capabilities.
3. Import-stack analysis.
4. Idea prioritization and value-gap style tracking.
5. Contributor/contribution/asset/value-lineage visibility.

### Autonomous Delivery

1. Task lifecycle across spec/impl/test/review/heal.
2. Pipeline orchestration with persisted state.
3. Decision pause/resume handling.
4. Optional operator messaging loop integration.

### Governance and Reliability

1. Start/preflight/deploy checks.
2. Commit evidence and traceability surfaces.
3. Monitoring, issue signaling, and self-healing hooks.
4. Provider readiness and usage-readiness visibility.

## Files to Create/Modify

- `specs/111-greenfield-autonomous-intelligence-system.md` - rewrite to a guidance-first blueprint with minimal hard gates.

## Acceptance Tests

- [ ] Manual validation: spec is guidance-first and not framed as broad mandatory-rule enforcement.
- [ ] Manual validation: only 3 hard gates are present (safety-critical, data-integrity, rollback-protection).
- [ ] Manual validation: memory and self-improvement sections include both working patterns and unresolved gaps.
- [ ] Manual validation: spec includes an explicit feature inventory and external reference list.
- [ ] `python3 scripts/validate_spec_quality.py --file specs/111-greenfield-autonomous-intelligence-system.md` exits 0.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/111-greenfield-autonomous-intelligence-system.md
rg -n "Guidance Model|Minimal Hard Gates|Memory Guidance|Self-Improvement Guidance|Current Bot Feature Inventory|External Sources" specs/111-greenfield-autonomous-intelligence-system.md
```

## External Sources (Landscape + Memory/Self-Improvement References)

- Anthropic Sonnet 4.6 (Feb 17, 2026): https://www.anthropic.com/news/claude-sonnet-4-6
- Anthropic Enterprise Agents Briefing (Feb 24, 2026): https://www.anthropic.com/events/the-briefing-enterprise-agents
- Google Gemini 3.1 Pro (Feb 19, 2026): https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/
- GitHub Copilot Gemini 3.1 Pro preview (Feb 19, 2026): https://github.blog/changelog/2026-02-19-gemini-3-1-pro-is-now-in-public-preview-in-github-copilot/
- LangGraph Memory Overview: https://docs.langchain.com/oss/python/langgraph/memory
- LangMem API Reference: https://langchain-ai.github.io/langmem/reference/
- MemSkill (arXiv:2602.02474): https://arxiv.org/abs/2602.02474
- FluxMem (arXiv:2602.14038): https://arxiv.org/abs/2602.14038
- AgentSys (arXiv:2602.07398): https://arxiv.org/abs/2602.07398
- Authenticated Workflows (arXiv:2602.10465): https://arxiv.org/abs/2602.10465
- LLM Agents Are Not Always Faithful Self-Evolvers (arXiv:2601.22436): https://arxiv.org/abs/2601.22436

## Out of Scope

- Enforcing organization-wide policy templates from this document alone.
- Full migration plan from current implementation to the greenfield target.
- Prescriptive vendor, cloud, framework, or model-provider commitments.

## Risks and Assumptions

- Risk: guidance without strong ownership can become ambiguous; mitigation is explicit owner assignment per experiment/playbook.
- Risk: too much freedom can hide regressions; mitigation is preserving the 3 hard gates and measurable signals.
- Assumption: teams maintain enough observability to evaluate guidance outcomes.

## Known Gaps and Follow-up Tasks

- Follow-up task: publish a compact playbook library per subsystem (memory, routing, self-improvement, monitor operations).
- Follow-up task: define target SLO/SLI ranges for each maturity phase.
- Follow-up task: create a conformance checklist that tests outcomes and signals rather than rigid rule compliance.

## Decision Gates (if any)

- Confirm final definition boundaries for the 3 hard gates.
- Confirm escalation posture for failed experiments (retry vs rollback vs park).
