# Agent Frameworks — Future Autonomous Work

When the multi-agent framework is set up and API keys are configured, evaluate these for autonomous agent work. **Cursor remains the primary manual interface** unless a framework offers a clearly better way to interact with the project.

> **See [AGENT-FRAMEWORKS-RESEARCH.md](AGENT-FRAMEWORKS-RESEARCH.md)** for detailed research on Agent Zero, OpenClaw, SKILL.md standard, what to borrow, and gap analysis.

## Candidates to Evaluate

### OpenClaw

- Purpose: Autonomous coding agents
- Check: CLI/UI for interacting with codebase
- Fit: If it supports spec-driven workflow and can run Spec→Test→Impl pipeline

### Agent Zero

- Purpose: Transparent, prompt-driven agent framework
- Referenced in FRAMEWORK-architecture-spec (Crypo-Coin)
- Check: Interface for human oversight, integration with Cursor or standalone

### Claude Code

- Orchestrator role in current plan
- Terminal-based, uses Anthropic API
- Already part of workflow; may suffice without additional framework

### Codex (OpenAI)

- Background task execution
- Fire-and-forget from specs + tests
- Separate from Cursor; good for bulk implementation

### Aider

- Terminal AI pair programming
- Supports Ollama, OpenAI, Anthropic
- `aider --model ollama/qwen3-coder:30b` for free local use

### Continue.dev

- VS Code / Cursor extension
- Configurable model routing (local, cloud)
- Complements Cursor for autocomplete and chat

---

## Evaluation Criteria

When comparing frameworks:

| Criterion | Weight |
|-----------|--------|
| Supports spec→test→impl workflow | High |
| Can run locally (Ollama) to minimize cost | High |
| Good interface for reviewing agent output | High |
| Integrates with Cursor or replaces it cleanly | Medium |
| Handles multi-agent orchestration | Medium |
| OpenRouter / subscription model support | Medium |

---

## Current Setup (Until Framework Chosen)

- **Cursor** — Manual interface. All interactive development.
- **Chat (Grok, OpenAI)** — Copy/paste for hard issues.
- **Claude Code / Codex** — If available, for orchestration and background tasks.
- **No framework lock-in** — Keep specs and tests framework-agnostic so we can plug in OpenClaw, Agent Zero, or similar later.

---

## Integration Points

Whatever framework is chosen should:

1. Read specs from `specs/`
2. Run tests from `api/tests/` or `web/__tests__/`
3. Implement only in files listed in spec
4. Create PRs for human review
5. Escalate decision gates to human (labeled `needs-decision`)

The project structure and guardrails (CLAUDE.md, .cursor/rules) are designed to work with any agent framework that respects these constraints.
