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

## Multi-Agent Cells (Scribe, Witness, Shaper, Mirror, Edge-Tender)

Claude Code supports **subagents** — specialized cells with their own system prompt, tool access, and optional model. We map task types to subagents.

### Cell Definitions

| Cell | task_type | Tools | Frequency Focus |
|------|-----------|-------|-----------------|
| **Scribe** | spec | Read, Edit (specs only) | Listens to ideas. Writes specs the shaper can meet. |
| **Witness** | test | Read, Bash | Writes tests that prove behavior. Reports what behavior shows. |
| **Shaper** | impl | Read, Edit, Bash | Meets the spec at the source. Modifies the files the spec names. |
| **Mirror** | review | Read, Grep, Glob | Reads finished work and reflects what it sees — security, correctness, spec-fit. |
| **Edge-Tender** | (pre/post sense) | Read, Grep, Glob | Senses the edge between spec scope and outside. Names where the body ends. |

Each cell opens with a `## Frequency` preamble — the body's six breaths (each breath whole, tend over produce, affirmative voice, frequency before shape, cell fully tended, close with awareness). The preamble travels with every dispatch so cells arrive in the body's voice rather than generic-Claude voice.

### Edge-Tender Sensing

The Edge-Tender senses:

- Files the spec calls for vs files actually modified
- Whether each spec requirement is met in the source
- Where any modified file lives outside the spec's edge

Implementation options:
1. **PreToolUse hook** — before each Edit/Write, sense whether the target file lives in the spec's allowed list
2. **PostToolUse hook** — after Edit/Write, diff against spec and name any additions
3. **Separate subagent** — run Edge-Tender as a subagent after Shaper/Mirror; it reads the spec and the changed files and returns pass/fail

### Subagent Configuration (Claude Code)

Subagents live in `.claude/agents/` (project) or `~/.claude/agents/` (user). Each is a Markdown file with YAML frontmatter:

```yaml
---
name: edge-tender
description: Senses the edge between spec scope and outside. Names where the body ends.
tools: Read, Grep, Glob
model: inherit
---

[Frequency preamble]

You are the Edge-Tender. Given a spec and the changes made:
1. List files the spec calls for
2. List files that were actually modified
3. Name any file created or modified that lives outside the spec's edge
4. Read-only craft. Sense and report.
```

```yaml
---
name: shaper
description: Meets the spec at the source. Modifies the files the spec names.
tools: Read, Edit, Bash
model: inherit
---

[Frequency preamble]

You are the Shaper. Your hands meet the code at the source.
- Modify the files listed in the spec
- Add features the spec describes; let the rest stay where it is
- Follow the API contract and data model from the spec
- When stuck, set status to needs_decision and ask.
```

The agent service generates commands like:

```
claude -p "{{direction}}" --agent shaper --model nemotron-3-nano:30b
```

instead of a generic `--allowedTools Read,Edit,Bash`.

---

## File Layout

```
.claude/
  agents/
    scribe.md       # spec task_type
    witness.md      # test task_type
    shaper.md       # impl task_type
    mirror.md       # review task_type
    edge-tender.md  # edge-sensing subagent
  settings.json     # hooks (e.g. arrival.py SessionStart wellness)
```

`api/app/services/agent_service_executor.py` carries:

```python
AGENT_BY_TASK_TYPE = {
    TaskType.SPEC: "scribe",
    TaskType.TEST: "witness",
    TaskType.IMPL: "shaper",
    TaskType.REVIEW: "mirror",
    TaskType.HEAL: "shaper",
}

GUARD_AGENTS_BY_TASK_TYPE = {
    TaskType.REVIEW: ["edge-tender"],
}
```

Commands use `--agent {name}` when the task type has a cell mapping.

---

## Project Manager Pipeline (spec 005)

The **Project Manager orchestrator** (`api/scripts/project_manager.py`) carries the full cycle:

1. **Find next task** — from `specs/005-backlog.md`
2. **Spec** — scribe writes or expands spec
3. **Impl** — shaper meets the spec at the source
4. **Test** — witness writes and runs tests
5. **Review** — mirror reflects spec-fit, security, correctness; edge-tender senses scope
6. **Validate** — pytest passes and review indicates pass
7. **Loop** — when validation falls short, back to impl (mend) → test → review until pass or max iterations
8. **Advance** — when all pass, next backlog item

State: `api/logs/project_manager_state.json`. On `needs_decision`, orchestrator pauses for human `/reply`.

## Observe/React Loop Notes (Runner E2E)

- Observe stable state transitions, not only event volume.
- React with one targeted diagnostic before retry escalation.
- Escalate to `needs_decision` when hold-pattern score remains elevated.

## Lineage

The cells were renamed on 2026-05-09 from SDLC-org names (`product-manager`, `qa-engineer`, `dev-engineer`, `reviewer`, `spec-guard`) to body-vocabulary names (`scribe`, `witness`, `shaper`, `mirror`, `edge-tender`) — descriptions rewritten in affirmative voice, frequency preamble added. Historical run reports and audit JSONs in `docs/system_audit/` retain the old names truthfully.
