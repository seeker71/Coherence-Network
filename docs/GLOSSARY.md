# Glossary — Coherence Network

| Term | Definition |
|------|------------|
| **Backlog** | Ordered list of work items (in `specs/005-backlog.md` or `specs/006-overnight-backlog.md`). Parsed as numbered lines. |
| **Coherence** | Project health score 0.0–1.0. Measures contributor diversity, dependency health, activity, etc. |
| **Direction** | Human-written instruction for an agent task (e.g. "Add GET /api/projects endpoint"). |
| **Pipeline** | The flow: project manager picks backlog item → creates spec/impl/test/review tasks → agent runner executes them. |
| **Task type** | `spec`, `test`, `impl`, `review`, or `heal`. Determines model routing and command template. |
| **needs_decision** | Task status when human input is required (e.g. after tests fail, or scope question). Pipeline pauses until `/reply`. |
| **Agent runner** | Script that polls for pending tasks, runs the command (Claude Code), PATCHes progress. |
| **Project manager** | Orchestrator: loads backlog, creates tasks in phase order (spec→impl→test→review), validates before advancing. |
| **Holdout tests** | Tests excluded from agent context; CI runs them to prevent "return true" hacks. |
| **Spec-driven** | Workflow: spec defines requirements → tests written → implementation makes tests pass. |
