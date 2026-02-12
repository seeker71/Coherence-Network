# Agent Architecture — How Local Models Do Read/Edit/Execute & Multi-Agent Roles

## How Read, Edit, Execute Works (Ollama + Claude Code)

The **Ollama model does not perform Read/Edit/Bash directly**. Claude Code does.

**Flow:**
1. You run `claude -p "Add a test" --model nemotron-3-nano:30b --allowedTools Read,Edit,Bash`
2. **Claude Code** sends the prompt to the model (Ollama via `ANTHROPIC_BASE_URL=http://localhost:11434`)
3. The model (Ollama) uses **tool-calling** (Anthropic-compatible API): it returns structured "I want to read file X" or "I want to run bash command Y"
4. **Claude Code** executes those tools in your workspace (Read, Edit, Bash)
5. Tool results go back to the model
6. Loop until the model signals done

Ollama supports the Anthropic tool-use schema, so when Claude Code talks to `localhost:11434`, the model generates tool calls and Claude Code runs them. The model *decides what to do*; Claude Code *does it*.

---

## Multi-Agent Roles (Product Manager, QA, Dev, Reviewer, Spec Guard)

Claude Code supports **subagents** — specialized agents with their own system prompt, tool access, and optional model. We map task types to subagents.

### Role Definitions

| Role | task_type | Tools | System Prompt Focus |
|------|-----------|-------|---------------------|
| **Product Manager** | spec | Read, Edit (specs only) | Write clear specs. Requirements, acceptance criteria, files to modify. No implementation. |
| **QA Engineer** | test | Read, Bash | Write tests. Run tests. Report failures. Do not change production code. |
| **Dev Engineer** | impl | Read, Edit, Bash | Implement only what the spec says. Modify only files listed in spec. No scope creep. |
| **Reviewer** | review | Read, Grep, Glob | Review for correctness, security, spec compliance. Suggest changes; do not apply. |
| **Spec Guard** | (pre/post hook) | Read, Grep, Glob | Verify work against spec. Flag anything outside scope. Block creation of files not in spec. |

### Spec Guard Behavior

The Spec Guard enforces:

- Implement ONLY what the spec says
- Modify ONLY files listed in the spec
- Do NOT create new docs/files unless the spec requires them
- Flag scope creep and escalate to `needs_decision`

Implementation options:
1. **PreToolUse hook** — before each Edit/Write, validate that the target file is in the spec’s allowed list
2. **PostToolUse hook** — after Edit/Write, diff against spec and flag additions
3. **Separate subagent** — run Spec Guard as a subagent after Dev/Review; it reads the spec and the changed files and returns pass/fail

### Subagent Configuration (Claude Code)

Subagents live in `.claude/agents/` (project) or `~/.claude/agents/` (user). Each is a Markdown file with YAML frontmatter:

```yaml
---
name: spec-guard
description: Validates work against spec. Use when checking that implementation matches spec.
tools: Read, Grep, Glob
model: inherit
---

You are the Spec Guard. Given a spec and the changes made:
1. List files the spec says to modify
2. List files that were actually modified
3. Flag any file created or modified that is NOT in the spec
4. Do NOT use Edit or Write. Report only.
```

```yaml
---
name: dev-engineer
description: Implements features per spec. Modifies only files listed in spec.
tools: Read, Edit, Bash
model: inherit
---

You are the Dev Engineer. Implement ONLY what the spec says.
- Modify ONLY files listed in the spec
- Do NOT create new files unless the spec explicitly requires them
- Do NOT add features not in the spec
- If unsure, set status to needs_decision and ask.
```

Our agent service would generate commands like:

```
claude -p "{{direction}}" --agent dev-engineer --model nemotron-3-nano:30b
```

instead of a generic `--allowedTools Read,Edit,Bash`.

---

## What We Need to Add

1. **Subagent files** — `.claude/agents/product-manager.md`, `qa-engineer.md`, `dev-engineer.md`, `reviewer.md`, `spec-guard.md`
2. **Agent service** — map `task_type` → `--agent {name}` and subagent-specific tools
3. **Spec Guard integration** — either:
   - Hooks that validate Edit/Write against spec, or
   - A Spec Guard subagent run after impl/review
4. **Spec reference in context** — pass `context.spec_ref` into the prompt so the agent knows which spec to follow

---

## File Layout (Proposed)

```
.claude/
  agents/
    product-manager.md   # spec task_type
    qa-engineer.md       # test task_type
    dev-engineer.md      # impl task_type
    reviewer.md          # review task_type
    spec-guard.md        # validation subagent
  settings.json          # optional hooks for Spec Guard
```

`api/app/services/agent_service.py` would have:

```python
AGENT_BY_TASK_TYPE = {
    TaskType.SPEC: "product-manager",
    TaskType.TEST: "qa-engineer",
    TaskType.IMPL: "dev-engineer",
    TaskType.REVIEW: "reviewer",
    TaskType.HEAL: None,  # use default, no subagent
}
```

Commands would use `--agent {name}` when the task type has an agent mapping.
