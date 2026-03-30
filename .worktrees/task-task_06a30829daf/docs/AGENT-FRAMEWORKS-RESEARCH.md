# Agent Frameworks Research — Agent Zero, OpenClaw & Skills

Research summary for Coherence Network. Borrow patterns for agents, skills, and multi-agent setup.

---

## 1. Agent Zero (agent0ai/agent-zero)

### Architecture

- **Hierarchical agents**: Superior ↔ subordinate. Human is superior to Agent 0; Agent 0 can spawn sub-agents for subtasks.
- **Computer as tool**: Agents use OS directly — terminal, code execution, file system. No fixed tools; agents write their own scripts.
- **Default tools**: Search (SearXNG), memory, communication, code/terminal execution.
- **Projects**: Isolated workspaces with custom instructions, memory, secrets, Git clone. Prevents context bleed.
- **Tasks & Scheduling**: Cron, planned, ad-hoc. Can be project-scoped.
- **Prompts**: Everything in `prompts/` — editable, transparent. `prompts/default/agent.system.md` defines core behavior.

### Skills (SKILL.md Standard)

- Uses **AgentSkills** open standard (agentskills.io) — compatible with Claude Code, Codex, Goose, Cursor.
- Skills replace legacy "Instruments". Loaded dynamically when relevant.
- Located in `skills/`; UI for import/list.
- Format: YAML frontmatter + Markdown instructions.

### What to Borrow

- **Project isolation** — workspace + instructions + memory per "project" (e.g. per spec)
- **Hierarchy** — coordinator spawns worker agents for spec/test/impl/review
- **Prompt-driven** — all behavior from editable prompts, not hard-coded
- **Tasks** — scheduled, planned, ad-hoc with project association
- **SKILL.md** — portable skills usable across tools

---

## 2. OpenClaw

### Architecture

- **Gateway**: Model config, skills, channels (Telegram, WhatsApp, etc.). Port 18789.
- **Agents**: Per workspace. Memory via `MEMORY.md`, `IDENTITY.md`, daily logs.
- **Subagents**: Coordinator + workers. Use per-task sessions, not eternal sessions.
- **Auto-compaction**: Prevents context overflow (`agent.compaction.enabled`).

### Skills

- **AgentSkills-compatible** — `SKILL.md` with YAML frontmatter.
- **Locations** (precedence): workspace `skills/` > `~/.openclaw/skills` > bundled.
- **ClawHub**: Public registry — `clawhub install <skill>`, `clawhub update --all`.
- **Gating**: `metadata.openclaw.requires.bins`, `requires.env`, `requires.config` — skill loads only if conditions met.
- **Config override**: `~/.openclaw/openclaw.json` → `skills.entries.<name>.enabled`, `apiKey`, `env`.

### Multi-Agent Fleet

- **Per-agent workspace**: `~/agents/jarvis`, `~/agents/clu`, `~/agents/cortana`.
- **Memory**: `MEMORY.md`, `IDENTITY.md`, `memory/YYYY-MM-DD.md`.
- **Per-task sessions**: Workers spawned per gig; crons run isolated sessions.
- **Binding**: Gateway `host: 0.0.0.0` for exec sessions (fixes timeout in containers).

### What to Borrow

- **Skill locations** — workspace > managed > bundled
- **Skill gating** — require bins/env/config before load
- **ClawHub-style registry** — discover, install, update skills
- **Memory hierarchy** — MEMORY.md, IDENTITY.md, daily logs
- **Per-task sessions** — don’t run eternal sessions; spawn per task

---

## 3. AgentSkills / SKILL.md Standard (agentskills.io)

Portable across Agent Zero, OpenClaw, Claude Code, Codex, Cursor.

### Format

```yaml
---
name: skill-name          # 1-64 chars, lowercase, hyphens
description: What it does and when to use it.  # 1-1024 chars
license: MIT              # optional
compatibility: Requires git, docker  # optional
metadata:                 # optional
  author: org
  version: "1.0"
allowed-tools: Read Bash  # optional, experimental
---

Markdown instructions...
```

### Directory Structure

```
skill-name/
├── SKILL.md       # required
├── scripts/       # executable helpers
├── references/    # REFERENCE.md, FORMS.md
└── assets/        # templates, images
```

### Progressive Disclosure

1. **Metadata** (~100 tokens): name + description loaded at startup
2. **Instructions** (<5k tokens): full SKILL.md when skill is activated
3. **Resources**: scripts/references loaded on demand

### Claude Code Extensions

- `disable-model-invocation: true` — user-only (e.g. deploy)
- `user-invocable: false` — model-only (background knowledge)
- `allowed-tools: Read, Grep` — restrict tools
- `context: fork` + `agent: Explore` — run in subagent
- `$ARGUMENTS`, `$0`, `$1` — argument substitution
- `!`command` — inject command output before sending to model

---

## 4. What to Borrow for Coherence Network

| Pattern | Source | Use |
|---------|--------|-----|
| SKILL.md format | AgentSkills | `.claude/skills/` or `skills/` — spec-guard, spec-writer, test-writer, impl, reviewer |
| Skill gating | OpenClaw | `metadata.requires.bins`, `requires.env` — only load when deps present |
| Project/workspace isolation | Agent Zero | Per-spec or per-task workspace to avoid context bleed |
| Per-task sessions | OpenClaw, Agent Zero | Spawn agent per task; don’t keep one long-lived session |
| Memory hierarchy | OpenClaw | MEMORY.md, IDENTITY.md, `memory/YYYY-MM-DD.md` for agent state |
| Subagent roles | Claude Code | product-manager, qa-engineer, dev-engineer, reviewer, spec-guard |
| Skill locations | OpenClaw | `skills/` (workspace) > `~/.coherence/skills` > bundled |
| Human-in-the-loop | Agent Zero | Superior = human; agents ask permission, report back |
| Telegram integration | OpenClaw (we have) | Alerts, /status, /tasks, /reply, /attention |

---

## 5. Gap Analysis — What’s Missing to Make It Work

### Current State

- API: tasks, routing, usage, Telegram webhook, /status, /tasks, /usage, /direction
- Claude Code + Ollama for execution
- No SKILL.md skills, no subagent configs, no Spec Guard
- No agent runner (poll → run → PATCH)
- No /reply, /attention (spec 003)
- No project/workspace isolation

### Gaps

| Gap | Needed |
|-----|--------|
| **Skills** | Add `skills/` with SKILL.md for spec-guard, spec-writer, test-writer, impl, reviewer. AgentSkills format. |
| **Subagents** | `.claude/agents/*.md` for product-manager, qa-engineer, dev-engineer, reviewer, spec-guard. Map task_type → agent. |
| **Spec Guard** | PreToolUse hook or separate spec-guard subagent to validate Edit/Write against spec. |
| **Agent runner** | Script that polls pending tasks, runs command with correct --agent, PATCHes status/progress. |
| **Decision loop** | /reply, /attention (spec 003). Store decision, resume or record. |
| **Project/workspace** | Per-spec or per-task working directory to avoid cross-task context bleed. |
| **Memory** | MEMORY.md, IDENTITY.md for agent learning (optional; Agent Zero/OpenClaw style). |
| **Skill gating** | `metadata.requires` so skills load only when deps (bins, env) exist. |
| **Compaction** | If we add long sessions, enable summarization to avoid context overflow. |

### Implementation Order

1. **Subagent files** — `.claude/agents/{product-manager,qa,dev,reviewer,spec-guard}.md` with prompts + tools
2. **Skills** — `skills/spec-guard/SKILL.md`, `skills/spec-driven/SKILL.md` (spec compliance)
3. **Agent service** — map task_type → `--agent {name}`
4. **Spec 003** — /reply, /attention, progress, agent runner
5. **Spec Guard** — PreToolUse or post-impl spec-guard run
6. **Project isolation** — optional; per-spec `workdir` when running agent

---

## 6. References

- [Agent Zero](https://github.com/agent0ai/agent-zero) — README, docs/guides/usage.md, docs/guides/projects.md
- [OpenClaw](https://docs.clawd.bot/) — Skills, Multi-Agent Architecture
- [AgentSkills spec](https://agentskills.io/specification)
- [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills)
- [Claude Code subagents](https://docs.claude.com/en/docs/claude-code/sub-agents)
