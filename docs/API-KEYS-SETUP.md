# API Keys Setup

Configure once the multi-agent framework is decided. This doc lists what to set up and where.

## Priority Order

### 1. Ollama + Claude Code — Local first, cloud/claude fallback

**Model fallback chain:** local (glm-4.7-flash) → cloud (glm-5:cloud) → Claude. Default is local.

One-command setup:
```bash
cd api && ./scripts/setup_ollama_claude.sh
```
Pulls glm-4.7-flash:latest (proven for tool use), installs Claude Code, configures .env. Ollama 0.15.x+ works; no pre-release needed.

Manual:
```bash
brew install ollama
ollama serve
ollama pull glm-4.7-flash:latest
curl -fsSL https://claude.ai/install.sh | bash
# Configure: ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_BASE_URL=http://localhost:11434 ANTHROPIC_API_KEY=""
```

Cloud fallback: `ollama signin` and `ollama pull glm-5:cloud`. Use `model_override: "glm-5:cloud"` in task context.

Test: `python scripts/test_agent_run.py --run --model glm-4.7-flash:latest "Your direction"`

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

### 6. Telegram (Alerts + Webhook)

**Create the bot:**
1. In Telegram, search for @BotFather
2. Send `/newbot`, follow prompts (name + username ending in `bot`)
3. Copy the token (e.g. `123456789:ABCdef...`)

**Get your chat ID:**
1. Search for @userinfobot in Telegram
2. Send any message; it replies with your numeric user ID
3. For alerts, use this same ID as chat ID (for direct messages to you)

**Add to `api/.env`:**
```
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_IDS=123456789
TELEGRAM_ALLOWED_USER_IDS=123456789
```

**Setup checklist:**
1. Create bot: Telegram → @BotFather → `/newbot` → copy token
2. Get chat ID: Telegram → @userinfobot → send any message → copy your ID
3. Edit `api/.env` — add your values:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...
   TELEGRAM_CHAT_IDS=123456789
   TELEGRAM_ALLOWED_USER_IDS=123456789
   ```
4. Install deps: `cd api && pip install -e ".[dev]"` (or `pip install httpx python-dotenv`)
5. Test: `cd api && python scripts/test_telegram.py`
6. (Optional) Test API flow: start API (`uvicorn app.main:app --port 8000`), then `python scripts/test_telegram.py --api`

**Webhook (for /status, /tasks, /direction from Telegram):**

One-command start (recommended):
```bash
cd api && ./scripts/start_with_telegram.sh
```
Starts API + cloudflared + sets webhook. Ctrl+C stops all.

Manual steps:
1. `brew install cloudflared`
2. `cd api && ./scripts/start_with_telegram.sh` — or start API and tunnel separately, then `./scripts/setup_telegram_webhook.sh https://YOUR-URL.trycloudflare.com`
3. Message @Coherence_Network_bot: `/status`, `/tasks`, or type a direction

### 7. Perplexity (Optional, limited)

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

---

## Provider Readiness Automation

The provider readiness contract checks required provider configuration every 6 hours and raises an issue when blocking gaps exist.

- API: `GET /api/automation/usage/readiness`
- CI workflow: `.github/workflows/provider-readiness-contract.yml`
- Required providers variable: `AUTOMATION_REQUIRED_PROVIDERS` (comma-separated)

Recommended secrets/vars for full readiness:

```bash
# OpenAI usage/cost
OPENAI_ADMIN_API_KEY=

# GitHub billing usage
GITHUB_TOKEN=
GITHUB_BILLING_OWNER=
GITHUB_BILLING_SCOPE=org

# Railway deploy health automation
RAILWAY_TOKEN=
RAILWAY_PROJECT_ID=
RAILWAY_ENVIRONMENT=
RAILWAY_SERVICE=

# Vercel deploy health automation
VERCEL_TOKEN=
VERCEL_PROJECT_ID=
```
