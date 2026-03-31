# Model Routing — Minimize Cost, Maximize Autonomy

## Fallback Chain (local → cloud → claude)

Tasks use **local first**, then cloud, then Claude:

| Priority | Tier | Model | Env / Override |
|----------|------|-------|----------------|
| 1 | local | glm-4.7-flash:latest | `OLLAMA_MODEL` (default) |
| 2 | cloud | glm-5:cloud | `model_override: "glm-5:cloud"` or `OLLAMA_CLOUD_MODEL` |
| 3 | claude | claude-3-5-haiku | HEAL tasks, or `model_override: "claude-3-5-haiku"` |

Use `context.model_override` when creating a task to force cloud or Claude (e.g. when local fails or is unavailable).

---

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

### Tier 0: Local (FREE) — Default, ~70% of work

**Proven for Claude Code tool use (Edit/Bash):** Ollama 0.15.x+, glm-4.7-flash (verified Feb 2026)

| Model | Where | Use for |
|-------|-------|---------|
| **GLM-4.7-Flash** | Ollama local | **Default** — native tool calling, 79.5% tool-use benchmarks, ~6.5GB VRAM |
| Qwen3-Coder 30B | Ollama local | Coding; works with Ollama 0.15.x+ (verified Feb 2026) |
| Granite 3.3 | Ollama local | General purpose (IBM), ~5GB |

**Ollama version:** 0.15.x stable works; GLM-4.7-Flash tool fixes in 0.15.1+.

**Recommended:** `OLLAMA_MODEL=glm-4.7-flash:latest` in `api/.env`. Pull: `ollama pull glm-4.7-flash:latest`

**Override:** Set `OLLAMA_MODEL=qwen3-coder:30b` in `api/.env` to use Qwen3-Coder for coding tasks.

### Tier 1: Ollama Cloud — Fallback when local unavailable

| Model | Where | Use for |
|-------|-------|---------|
| glm-5:cloud | Ollama Cloud | Strong coding/agentic; requires `ollama signin` |

Set `model_override: "glm-5:cloud"` in task context. Requires `ollama pull glm-5:cloud` and signed-in Ollama.

### Tier 2: Claude (Anthropic) — Complex tasks, HEAL

| Source | Use for |
|--------|---------|
| Claude (Haiku/Sonnet) | Orchestration, healing, complex integration |

HEAL tasks route to Claude by default. Set `ANTHROPIC_API_KEY` for Claude models.

### Tier 3: OpenRouter Free — ~15% backup

| Model | Endpoint | Use for |
|-------|----------|---------|
| `openrouter/free` | OpenRouter | Backup when local struggles |

### Tier 4: Chat Copy/Paste (No API) — Hard issues only

| Tool | Use for |
|------|---------|
| Grok (SuperGrok) | Complex framework questions |
| OpenAI Chat | Same — paste code/error, apply solution manually |

---

## Agent-to-Model Mapping

| Agent | Default | Fallback |
|-------|---------|----------|
| Spec Drafter | glm-4.7-flash (local) | glm-5:cloud → Claude |
| Test Writer | glm-4.7-flash (local) | glm-5:cloud → Claude |
| Impl Worker | glm-4.7-flash (local) | glm-5:cloud → Claude |
| Review Panel | glm-4.7-flash (local) | glm-5:cloud → Claude |
| Healer | claude-3-5-haiku | — |

---

## Escalation Rules

- Local fails → use `model_override: "glm-5:cloud"` for next task
- Cloud unavailable → use `model_override: "claude-3-5-haiku"` (requires ANTHROPIC_API_KEY)
- Security/auth code → Start at Claude
- Architecture decision → Claude Sonnet/Opus

### Automatic Executor Cost Policy

The agent API now supports an automatic executor policy:

- Use the cheap executor by default.
- Escalate to a stronger executor only when retry/failure thresholds are reached.

Environment variables:

- `AGENT_EXECUTOR_POLICY_ENABLED` (default `1`)
- `AGENT_EXECUTOR_CHEAP_DEFAULT` (default `cursor`, falls back to `AGENT_EXECUTOR_DEFAULT`)
- `AGENT_EXECUTOR_ESCALATE_TO` (default `claude`; if equal to cheap, falls back to `openclaw`)
- `AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD` (default `2`)
- `AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD` (default `1`)
- `CURSOR_CLI_MODEL` / `CURSOR_CLI_REVIEW_MODEL` (recommended `auto`)
- Cursor/Codex subscription windows come from host-runner telemetry and CLI auth context.

Notes:

- `POST /api/agent/tasks` applies this automatically when `context.executor` is not explicitly set.
- `GET /api/agent/route` supports `executor=auto` (policy default).
- Each task stores policy decision metadata under `context.executor_policy` for auditability.

### External configuration (config over env)

Configuration lives in **config files**; env is only for override paths.

- **Executors (no aliasing):** `api/config/executor_routing.json` (or `EXECUTOR_ROUTING_CONFIG_PATH`). Defines canonical `executors` list, `runner_auth_context_key_by_executor`, and `model_prefix_by_executor`. One name per executor; no executor_aliases. Every executor has a model prefix (e.g. `claude`, `openrouter`) so stored models are uniformly `executor/model_id`. Only canonical executor names are accepted; no aliasing.
- **Models:** `api/config/model_routing.json` (or `MODEL_ROUTING_CONFIG_PATH`). Defines:
  - **Strong / fast tiers:** `tiers_by_executor` (e.g. `strong`, `fast` model id per executor) and `task_type_tier` (e.g. `spec`/`review`/`heal` → strong, `impl`/`test` → fast). Routing uses `get_model_for_executor_and_task_type(executor, task_type)` so spec and review use the strong model, impl and test use the fast model.
  - `default_models_by_executor`: optional legacy model id per executor (default/review); used only when `tiers_by_executor` is not set for that executor.
  - `openrouter_models_by_task_type`: **only used when executor is openrouter**. Model per task type (spec/test/impl/review/heal); typically `openrouter/free` for free-tier.
  - `openrouter_free_model`: default for openrouter when not per-task.
  - **Fallback when a model is out of usage:** `fallback_chains` is an object keyed by executor; each value is an ordered list of model ids. On rate-limit or quota errors, the runner/retry path calls `get_fallback_model(executor, current_model)` and retries with the next model in the chain if non-null. Execution retry (`agent_execution_retry.record_failure_hits_and_retry`) applies this when the failure category is `rate_limit` or `paid_provider_blocked`.
  No aliasing: model ids are used as-is.
See `api/config/model_routing.json` and `api/app/services/agent_routing/model_routing_loader.py`.

---

## Setup Order

1. **Ollama local** — Primary (glm-4.7-flash)
2. **Ollama Cloud** — `ollama signin`, `ollama pull glm-5:cloud` for fallback
3. **Claude** — ANTHROPIC_API_KEY for HEAL and escalation
4. **OpenRouter** — Free backup
5. **Cursor** — Already primary IDE

See [API-KEYS-SETUP.md](API-KEYS-SETUP.md) for configuration.

---

## Cursor CLI (Alternative Executor)

Use **Cursor CLI** (`agent` command) instead of Claude Code for headless, scriptable runs. Pass `context: {"executor": "cursor"}` when creating tasks, or run project manager with `--cursor`.

| Task Type | Cursor Model |
|-----------|--------------|
| spec, impl, test | auto |
| review, heal | auto |

Use `auto` as default so Cursor can balance availability/quality against subscription limits.  
Track and back off via:
- `GET /api/automation/usage`
- `GET /api/automation/usage/alerts`
- provider telemetry limits (reported in usage snapshots/readiness)

See [CURSOR-CLI.md](CURSOR-CLI.md) for setup and usage.
