# Task template — Coherence Network workspace

Tasks are created via `coh task seed {idea_id}` or the pipeline orchestrator.
They are not authored by hand. This file documents the fields the orchestrator
populates so humans understand what an agent sees.

## Required task fields

```yaml
task_type: {spec|test|impl|review|deploy|verify}
context:
  idea_id: {parent-idea-slug}
  spec_id: {spec-id}
  workspace_id: coherence-network
direction: |
  {One-paragraph instruction to the agent.
   Cites the spec source map and done_when checks.}
constraints:
  - {Hard rule from spec frontmatter}
```

## Agent entry points

Every provider (claude, codex, cursor, gemini, openrouter) routes through
`api/scripts/local_runner.py::build_prompt()`. That function injects:

1. Workspace agent persona (loaded from `.agents/{task_type}-{provider}.md`
   or falls back to `.claude/agents/` for the default workspace)
2. Workspace guardrails (from this workspace's `guides/contribution.md`)
3. Task direction + constraints
4. Source map from the spec

This guarantees that **every** task executed for this workspace follows the
same rules regardless of which provider runs it.
