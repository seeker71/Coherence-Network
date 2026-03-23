# Join the Coherence Network

Run this on any machine to become a contributing node.

## Prerequisites

Install at least one AI provider CLI. The runner auto-detects all available providers.

### Claude (Anthropic)

```bash
npm install -g @anthropic-ai/claude-code
claude auth login          # browser-based OAuth
```

### Codex (OpenAI)

```bash
npm install -g @openai/codex
codex login                # browser-based OAuth via ChatGPT
```

### Gemini (Google)

```bash
npm install -g @google/gemini-cli
```

On first run, Gemini authenticates via Google. Set the env var so it uses browser OAuth:

```bash
export GOOGLE_GENAI_USE_GCA=true    # Linux/macOS — add to ~/.bashrc or ~/.zshrc
set GOOGLE_GENAI_USE_GCA=true       # Windows CMD
```

### Cursor Agent

**Linux/macOS:**

```bash
curl https://cursor.com/install -fsSL | bash
agent login                # browser-based OAuth
```

**Windows (via npm):**

```bash
npm install -g @nothumanwork/cursor-agents-sdk
```

The npm package installs `cursor-agent`. Create an `agent` shim so the runner finds it:

```bash
# PowerShell
$npmDir = (npm config get prefix)
$vendorDir = "$(npm root -g)\@nothumanwork\cursor-agents-sdk\vendor"
$version = (Get-Content "$vendorDir\manifest.json" | ConvertFrom-Json).version
Copy-Item "$vendorDir\$version\windows-x64\cursor-agent.cmd" "$npmDir\agent.cmd"
```

Then authenticate:

```bash
agent login                # opens browser
agent status               # verify: should show your email
```

Cursor Agent requires [ripgrep](https://github.com/BurntSushi/ripgrep). Install via:

```bash
winget install BurntSushi.ripgrep.MSVC   # Windows
brew install ripgrep                      # macOS
sudo apt install ripgrep                  # Ubuntu/Debian
```

### Ollama (local models)

Install from https://ollama.com and pull a model:

```bash
ollama pull mistral-nemo:12b       # or any model you prefer
```

### Ollama (cloud models)

Cloud models run on Ollama's servers — no GPU required:

```bash
ollama pull qwen3-coder:480b-cloud
```

Requires an Ollama account. See https://ollama.com/search?c=cloud for available models.

### OpenRouter (API, free tier available)

Get an API key from https://openrouter.ai/keys and set it:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."   # add to ~/.bashrc or ~/.zshrc
```

No CLI install needed — the runner calls the API directly.

## Setup

```bash
git clone https://github.com/seeker71/Coherence-Network.git
cd Coherence-Network/api
pip install -e .
```

## Run

```bash
cd ..   # back to repo root
python scripts/local_runner.py --timeout 300
```

The runner auto-detects your providers, registers with the hub, picks tasks, executes them, and pushes measurements.

## Verify

```bash
python scripts/local_runner.py --dry-run
```

Check that your providers are listed. Then verify your node on the hub:

```bash
curl https://api.coherencycoin.com/api/federation/nodes
```

Your machine should appear with its hostname, OS, and detected providers.

## What it does

- Picks highest-ROI tasks from the idea portfolio
- Routes to the best provider for each task type (data-driven, not hardcoded)
- File tasks (spec/impl/test) go to tool-capable providers only (claude, codex, gemini, cursor)
- Review tasks go to any provider (including ollama, openrouter)
- Outcomes feed Thompson Sampling — the network learns what works
- Measurements visible at https://coherencycoin.com/automation

## Supported providers

| Provider | Type | Tool-capable | Install |
|----------|------|-------------|---------|
| claude | CLI | Yes | `npm i -g @anthropic-ai/claude-code` |
| codex | CLI | Yes | `npm i -g @openai/codex` |
| gemini | CLI | Yes | `npm i -g @google/gemini-cli` |
| cursor | CLI | Yes | `curl https://cursor.com/install -fsSL \| bash` |
| ollama-local | CLI | No | https://ollama.com |
| ollama-cloud | CLI | No | `ollama pull <model>-cloud` |
| openrouter | API | No | Set `OPENROUTER_API_KEY` env var |

## Continuous mode

```bash
python scripts/local_runner.py --timeout 300 --loop --interval 120
```

## CLI reference

```
python scripts/local_runner.py [OPTIONS]

  --timeout N        Task timeout in seconds (default: 300)
  --loop             Poll continuously for new tasks
  --interval N       Poll interval in seconds (default: 120)
  --task TASK_ID     Run one specific task
  --dry-run          Show what would run without executing
  --stats            Show provider selection stats and exit
  --no-register      Skip federation node registration
  --resume           Enable timeout resume flow (save patch + re-enqueue)
```
