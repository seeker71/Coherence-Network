# API Keys Setup

Configure once the multi-agent framework is decided. This doc lists what to set up and where.

## Priority Order

### 1. Ollama (Local) — No key needed

```bash
# Mac
brew install ollama
ollama serve
ollama pull qwen3-coder:30b
ollama pull qwen2.5-coder:7b

# Windows: install from ollama.com
```

Runs at `http://localhost:11434`. OpenAI-compatible API.

### 2. OpenRouter — Free tier

1. Sign up: https://openrouter.ai
2. Keys → Create API Key
3. Add to `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-...
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   ```

Free models: `openrouter/free` or specific free model IDs. No per-token cost.

### 3. Claude (Anthropic)

1. console.anthropic.com
2. API Keys → Create Key
3. `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

### 4. OpenAI

1. platform.openai.com → API Keys
2. `.env`:
   ```
   OPENAI_API_KEY=sk-...
   ```

### 5. Ollama Cloud Pro

If you have Pro, API is at `https://ollama.com/api`. Check Ollama docs for auth (likely API key in account settings).

### 6. Perplexity (Optional, limited)

1. perplexity.ai → Settings → API
2. Add credits if needed
3. `.env`:
   ```
   PERPLEXITY_API_KEY=pplx-...
   ```

Use sparingly; $20 credits deplete quickly.

---

## Grok / OpenAI Chat (No API)

- **Grok (SuperGrok):** Chat only. Use for copy/paste when stuck on hard framework/architecture questions.
- **OpenAI Chat:** Same — paste code, error, or design question; apply solution manually.

No keys needed for chat; they use your existing subscription login.

---

## .env.example

```bash
# Coherence Network — API Keys
# Copy to .env and fill in

# OpenRouter (free models)
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Claude
ANTHROPIC_API_KEY=

# OpenAI
OPENAI_API_KEY=

# Ollama local (no key)
OLLAMA_BASE_URL=http://localhost:11434

# Ollama Cloud (Pro)
# OLLAMA_CLOUD_API_KEY=

# Perplexity (optional)
# PERPLEXITY_API_KEY=

# Database (when needed)
# NEO4J_URI=
# NEO4J_USER=
# NEO4J_PASSWORD=
# DATABASE_URL=
```

---

## Multi-Agent Framework

When OpenClaw, Agent Zero, or another framework is chosen:

1. Add framework-specific env vars
2. Configure model routing in framework config
3. Point framework at this project's specs and API
4. Use Cursor as manual override unless framework has a superior interface

See [AGENT-FRAMEWORKS.md](AGENT-FRAMEWORKS.md) for options.
