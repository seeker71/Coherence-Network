# Spec: docs/GLOSSARY.md — Project Terms

## Purpose

Provide a single reference for Coherence Network terminology so agents and humans share consistent definitions for pipeline, backlog, coherence, task types, and related concepts. Reduces ambiguity in specs, AGENTS.md, and runbooks. Addresses backlog item 15 in spec 006.

## Requirements

- [ ] `docs/GLOSSARY.md` exists and is the canonical glossary.
- [ ] **Format**: Table or equivalent (Term | Definition) so terms are scannable; optional short intro line (e.g. "Glossary — Coherence Network").
- [ ] **Required terms** (each has a clear, one- or two-sentence definition):
  - **Backlog** — ordered list of work items; where stored (e.g. specs/005-backlog.md, specs/006-overnight-backlog.md) and how parsed.
  - **Coherence** — project health score (0.0–1.0); what it measures (e.g. contributor diversity, dependency health, activity).
  - **Pipeline** — the flow from backlog → tasks → execution (e.g. project manager picks item, creates spec/impl/test/review tasks, agent runner runs them).
  - **Task type** — allowed values (e.g. `spec`, `test`, `impl`, `review`, `heal`) and how they affect routing/commands.
  - **Direction** — human-written instruction for an agent task.
  - **needs_decision** — task status when human input is required; pipeline behavior until resolved.
  - **Agent runner** — script/process that polls for tasks, runs the command, reports progress.
  - **Project manager** — orchestrator that loads backlog, creates tasks in phase order, validates before advancing.
  - **Holdout tests** — tests excluded from agent context; purpose (e.g. prevent "return true" hacks); where (e.g. api/tests/holdout/).
  - **Spec-driven** — workflow: spec defines requirements → tests written → implementation makes tests pass.
- [ ] Definitions stay consistent with AGENTS.md, CLAUDE.md, and agent API (e.g. task_type values match API).

## API Contract (if applicable)

N/A — documentation only.

## Data Model (if applicable)

N/A.

## Files to Create/Modify

- `docs/GLOSSARY.md` — create or expand to include all required terms with definitions. Only this file is in scope for this spec.

## Acceptance Tests

- Manual or automated check that `docs/GLOSSARY.md` exists.
- Check that the file defines at least: Backlog, Coherence, Pipeline, Task type (or task_type), Direction, needs_decision, Agent runner, Project manager, Holdout tests, Spec-driven. Exact headings may vary (e.g. "Task type" vs "task_type"); intent is that each concept is findable and defined.

## Out of Scope

- Changing API, scripts, or code; only documenting terms.
- Adding every possible term; focus on terms used in pipeline, backlog, agent orchestration, and spec-driven workflow.

## See also

- [006 Overnight Backlog](006-overnight-backlog.md) — item 15: Add docs/GLOSSARY.md (coherence, task_type, pipeline, backlog, etc.)
- [002 Agent Orchestration API](002-agent-orchestration-api.md) — task_type, direction, status values
- [005 Project Manager Pipeline](005-project-manager-pipeline.md) — pipeline, backlog, project manager
