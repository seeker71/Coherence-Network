# Glossary — Coherence Network

Canonical definitions for pipeline, backlog, agent orchestration, and spec-driven workflow. See AGENTS.md, CLAUDE.md, and MODEL-ROUTING.md for usage.

| Term | Definition |
|------|------------|
| **Backlog** | Ordered list of work items (in `specs/005-backlog.md` or `specs/006-overnight-backlog.md`). Parsed as numbered lines. |
| **Coherence** | Project health score from 0.0 to 1.0. Measures contributor diversity, dependency health, activity, etc. |
| **Direction** | Human-written instruction for an agent task (e.g. "Add GET /api/projects endpoint"). |
| **Pipeline** | The flow: project manager picks backlog item → creates spec/impl/test/review tasks → agent runner executes them. |
| **Task type** (task_type) | `spec`, `test`, `impl`, `review`, or `heal`. Determines model routing and command template. |
| **needs_decision** | Task status when human input is required (e.g. after tests fail, or scope question). Pipeline pauses until `/reply`. |
| **Agent runner** | Script that polls for pending tasks, runs the command (Claude Code), PATCHes progress. |
| **Project manager** | Orchestrator: loads backlog, creates tasks in phase order (spec→impl→test→review), validates before advancing. |
| **Holdout tests** | Tests excluded from agent context (e.g. `api/tests/holdout/`); CI runs them to prevent "return true" hacks. |
| **Spec-driven** | Workflow: spec defines requirements → tests written → implementation makes tests pass. |
| **Heal** | Task type for fixing failures (e.g. after tests fail); may create follow-up spec/impl tasks. |
| **Status** | Task lifecycle state: pending, running, completed, failed, needs_decision (see agent API). |
| **Resource exhausted** | API or LLM quota/rate limit exceeded (e.g. gRPC RESOURCE_EXHAUSTED). Retry with backoff or switch model/tier (see MODEL-ROUTING.md). |
| **Connection stalled** | HTTP connection established but no (or incomplete) response — often ReadTimeout/ConnectTimeout. Fix: ensure API is running (`uvicorn app.main:app --port 8000`), check firewall/proxy; use shorter timeouts in scripts (see RUNBOOK.md, AGENT-DEBUGGING.md). |
