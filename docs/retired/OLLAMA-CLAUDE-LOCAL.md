# Claude Code + Local Ollama: Research & Working Setup

How to get a local Ollama model working with Claude Code and actual tool use (Edit, Bash). Based on official docs, GitHub issues, and real reports.

## Summary

| Setup | Edit/Bash works? | Source |
|-------|------------------|--------|
| **glm-4.7-flash local** | ✅ Yes | Verified Feb 2026; Ollama 0.15.x+ |
| **glm-5:cloud** | ✅ Yes | Verified in this project; requires `ollama signin` |
| **qwen3-coder local** | ✅ Yes | Verified Feb 2026; Ollama 0.15.x+ (was Ollama version, not model) |

**Fallback chain:** local (glm-4.7-flash) → cloud (glm-5:cloud) → Claude (claude-3-5-haiku). Use `model_override` in task context to force cloud or Claude.

---

## 1. Official Ollama Anthropic Compatibility

**Source:** [docs.ollama.com/api/anthropic-compatibility](https://docs.ollama.com/api/anthropic-compatibility)

Ollama exposes `/v1/messages` (Anthropic Messages API). Supports: Messages, Streaming, Tools, Tool results, Thinking.

### Environment variables

```bash
export ANTHROPIC_AUTH_TOKEN=ollama   # Bearer token (required)
export ANTHROPIC_API_KEY=""          # Required but ignored
export ANTHROPIC_BASE_URL=http://localhost:11434
```

**Important:** Use `ANTHROPIC_AUTH_TOKEN` (Bearer), NOT `ANTHROPIC_API_KEY` (X-Api-Key).

### Quick setup (Ollama 0.15+)

```bash
ollama launch claude
# Prompts for model selection, configures Claude Code
```

### Manual run

```bash
ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_BASE_URL=http://localhost:11434 ANTHROPIC_API_KEY="" \
  claude --model qwen3-coder
```

### Python tool-calling example (from docs)

```python
import anthropic

client = anthropic.Anthropic(
    base_url='http://localhost:11434',
    api_key='ollama',  # required but ignored
)

message = client.messages.create(
    model='qwen3-coder',
    max_tokens=1024,
    tools=[{
        'name': 'get_weather',
        'description': 'Get the current weather in a location',
        'input_schema': {
            'type': 'object',
            'properties': {'location': {'type': 'string'}},
            'required': ['location']
        }
    }],
    messages=[{'role': 'user', 'content': "What's the weather in San Francisco?"}]
)
for block in message.content:
    if block.type == 'tool_use':
        print(f'Tool: {block.name}', f'Input: {block.input}')
```

---

## 2. Ollama Version for Local Tool Use

**Update (Feb 2026):** Ollama 0.15.x stable works with glm-4.7-flash tool use. Pre-release no longer required. GLM-4.7-Flash fixes landed in 0.15.1.

```bash
brew upgrade ollama   # or brew install ollama
ollama -v            # expect 0.15.x or 0.16.x
```

### Context length

Ollama maintainer (GitHub #13820): *"This model needs more context length and shifting does not work well with tools."*

```bash
OLLAMA_CONTEXT_LENGTH=64000 ollama serve
# Or 128K for better results
```

User report: *"Tools worked for me with opencode (with 64K and 128K context)"*

---

## 3. Claude Code Telemetry Workaround

**Source:** [GitHub ollama/ollama#13949](https://github.com/ollama/ollama/issues/13949)

Claude Code sends requests to unsupported endpoints (`/v1/messages/count_tokens?beta=true`). Ollama returns 404; in some setups this can cause timeouts. Set:

```bash
export DISABLE_TELEMETRY=1
export DISABLE_ERROR_REPORTING=1
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
```

---

## 4. GLM-4.7-Flash Local Setup

**Source:** paddo.dev, [ollama/ollama#13820](https://github.com/ollama/ollama/issues/13820), verified Feb 2026

### Requirements

- Ollama 0.15.x+ (stable)
- Model from Ollama library (not raw HuggingFace GGUF — HF models lack capability template)
- 64K–128K context recommended

```bash
# Install/upgrade Ollama
brew install ollama   # or brew upgrade ollama

# Pull from library
ollama pull glm-4.7-flash:latest

# Run with context (optional, can improve tool use)
OLLAMA_CONTEXT_LENGTH=64000 ollama serve
```

### Known issues

- **XML parsing:** `glm-4.6 tool call parsing failed` — can occur with malformed tool output; try higher context
- **"does not support tools":** Use model from `ollama pull`, not HuggingFace import

### claude-launcher (role-model remapping)

Claude Code routes to different models (Haiku/Sonnet/Opus). Without remapping, role-model requests can leak to Anthropic. [claude-launcher](https://github.com/paddo/claude-launcher) keeps everything local:

```bash
npm install -g claude-launcher
claude-launcher -l   # Launch fully local
```

---

## 5. Proxy Alternative: LiteLLM

**Source:** [mattlqx/claude-code-ollama-proxy](https://github.com/mattlqx/claude-code-ollama-proxy)

Proxy translates Anthropic API → LiteLLM → Ollama. Useful if direct Ollama Anthropic compatibility has issues.

```bash
# .env
PREFERRED_PROVIDER="ollama"
OLLAMA_API_BASE="http://localhost:11434"
BIG_MODEL="llama3"
SMALL_MODEL="llama3:8b"

# Run proxy
uv run uvicorn server:app --host 0.0.0.0 --port 8082

# Connect Claude Code
ANTHROPIC_BASE_URL=http://localhost:8082 claude
```

---

## 6. Config Isolation (wal.sh)

**Source:** [wal.sh/research/claude-code-ollama](https://wal.sh/research/claude-code-ollama.html)

Avoid auth conflicts with claude.ai by using a separate config dir:

```bash
export CLAUDE_CONFIG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/claude-ollama"
mkdir -p "$CLAUDE_CONFIG_DIR"

ANTHROPIC_AUTH_TOKEN=ollama \
ANTHROPIC_BASE_URL=http://localhost:11434 \
CLAUDE_CONFIG_DIR="$CLAUDE_CONFIG_DIR" \
  claude --model qwen3-coder
```

---

## 7. Headless Mode: Edit Permission

Claude Code prompts for Edit approval by default. In headless (`-p`) mode there is no user to approve. Add:

```bash
--allowedTools Read,Edit,Grep,Glob,Bash --dangerously-skip-permissions
```

Or project `.claude/settings.json`:

```json
{
  "permissions": {
    "defaultMode": "acceptEdits"
  }
}
```

---

## 8. Recommended Models (from sources)

| Model | Type | Tool use | Notes |
|-------|------|----------|-------|
| glm-5:cloud | Cloud | ✅ | 744B MoE, 40B active; requires `ollama signin` |
| glm-4.7-flash | Local | ✅ | Ollama 0.15.x+; default for this project |
| qwen3-coder | Local | ✅ | Works with Ollama 0.15.x+ |
| qwen3 | Local | ✅ | Official streaming tool support (Ollama blog) |
| gpt-oss:20b | Local | ✅ | Ollama docs |
| Devstral, Llama 3.1/4 | Local | ✅ | Ollama streaming tool blog |

---

## 9. Checklist for Local Tool Use

1. [ ] Ollama 0.15.x+ (stable)
2. [ ] `OLLAMA_CONTEXT_LENGTH=64000` or `128000`
3. [ ] Model from `ollama pull` (not HuggingFace)
4. [ ] `ANTHROPIC_AUTH_TOKEN=ollama` (Bearer)
5. [ ] `--dangerously-skip-permissions` or `acceptEdits` for headless Edit
6. [ ] Telemetry env vars if timeouts occur
7. [ ] Test with simple Edit: `claude -p "Create test.txt with content hi" --model <model> --allowedTools Read,Edit,Bash --dangerously-skip-permissions`

---

## 10. References

- [Ollama Anthropic Compatibility](https://docs.ollama.com/api/anthropic-compatibility)
- [Ollama Streaming Tool Calls](https://ollama.com/blog/streaming-tool)
- [paddo.dev: Claude Code Local Ollama](https://paddo.dev/blog/claude-code-local-ollama/)
- [wal.sh: Claude Code + Ollama](https://wal.sh/research/claude-code-ollama.html)
- [GitHub #13820: glm-4.7-flash tools](https://github.com/ollama/ollama/issues/13820)
- [GitHub #13949: Claude Code compatibility](https://github.com/ollama/ollama/issues/13949)
- [claude-code-ollama-proxy](https://github.com/mattlqx/claude-code-ollama-proxy)
