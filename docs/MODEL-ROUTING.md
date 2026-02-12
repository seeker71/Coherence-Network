# Model Routing — Minimize Cost, Maximize Autonomy

## Available Resources

| Resource | Access | Cost |
|----------|--------|------|
| Ollama (local) | Mac/Windows | Free |
| Ollama Cloud Pro | Cloud API | ~$20/mo (included) |
| OpenRouter free models | API | $0 |
| Claude Pro | Chat + API | ~$20/mo |
| OpenAI Pro | Chat + API | ~$20/mo |
| Cursor Pro+ | IDE, background agents | ~$40/mo |
| Grok (SuperGrok) | Chat only (no API) | Subscription |
| Perplexity | Chat + API (limited credits) | $20 credits |

**No DeepSeek API.** Avoid additional per-token spend.

---

## Routing Tiers

### Tier 0: Local (FREE) — ~70% of work

| Model | Where | Use for |
|-------|-------|---------|
| Qwen3-Coder 30B | Ollama local | Spec draft, tests, simple impl, first-pass review |
| Qwen 2.5 Coder 7B | Ollama local | Fast autocomplete, boilerplate |

### Tier 1: OpenRouter Free — ~15% of work

| Model | Endpoint | Use for |
|-------|----------|---------|
| `openrouter/free` | OpenRouter | Backup when local struggles, second-opinion review |
| Free models (Qwen, etc.) | OpenRouter | Escalation without per-token cost |

### Tier 2: Subscriptions (Included) — ~12% of work

| Source | Use for |
|--------|---------|
| Claude (Haiku/Sonnet) | Orchestration, healing, complex integration |
| OpenAI (GPT-4o) | Codex-style tasks, integration |
| Cursor Pro+ | Interactive UI, graph viz, debugging |

### Tier 3: Chat Copy/Paste (No API) — Hard issues only

| Tool | Use for |
|------|---------|
| Grok (SuperGrok) | Complex framework questions, architecture dilemmas |
| OpenAI Chat | Same — paste code/error, get resolution guidance |

Use when stuck. Copy problem + context → paste in chat → apply solution manually.

### Tier 4: Optional Cloud

| Source | Use for |
|--------|---------|
| Ollama Cloud Pro | When local Ollama unavailable (travel, different machine) |
| Perplexity | Research, citations, summaries (use $20 credits sparingly) |

---

## Agent-to-Model Mapping

| Agent | Default | Escalation |
|-------|---------|------------|
| Spec Drafter | Local Qwen3 | OpenRouter free |
| Test Writer | Local Qwen3 | OpenRouter free |
| Impl Worker (backend) | Local Qwen3 | Cursor / Claude Code |
| Impl Worker (frontend) | Cursor | Claude Code |
| Review Panel | Local Qwen3 | Claude Haiku |
| Healer | Claude Haiku | Claude Sonnet |
| Orchestrator | Claude Haiku | Claude Sonnet |

---

## Escalation Rules

- Local fails tests 2× → OpenRouter free or Cursor
- OpenRouter/Cursor fails → Claude Code
- Security/auth code → Start at Claude (subscription)
- Architecture decision → Claude Sonnet/Opus; consider chat copy/paste for Grok/OpenAI
- Rate limited → Fall back to next tier

---

## Setup Order

1. **Ollama local** — Primary workhorse
2. **OpenRouter** — Free backup, no extra cost
3. **Claude / OpenAI** — From existing subscriptions
4. **Cursor** — Already primary IDE
5. **Ollama Cloud** — When needed for remote work

See [API-KEYS-SETUP.md](API-KEYS-SETUP.md) for configuration.
