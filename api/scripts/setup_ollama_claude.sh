#!/bin/bash
# Setup Ollama + Claude Code for agent orchestration.
# Run from api/: ./scripts/setup_ollama_claude.sh
#
# Prereqs: brew (macOS)
# Env: OLLAMA_MODEL (default qwen3-coder:30b), OLLAMA_BASE_URL (default http://localhost:11434)

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
cd "$API_DIR"

OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3-coder:30b}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo "=== Ollama + Claude Code Setup ==="
echo ""

# 1. Ollama
echo "[1/4] Ollama"
if ! command -v ollama >/dev/null 2>&1; then
  echo "      Installing via brew..."
  brew install ollama
fi

# Start Ollama if not running
if ! curl -s "$OLLAMA_BASE_URL/api/tags" >/dev/null 2>&1; then
  echo "      Starting Ollama (background)..."
  ollama serve &
  sleep 3
fi

if curl -s "$OLLAMA_BASE_URL/api/tags" >/dev/null 2>&1; then
  echo "      Ollama running at $OLLAMA_BASE_URL"
else
  echo "      ERROR: Ollama not reachable. Run: ollama serve"
  exit 1
fi

# Pull model if not present
MODEL_BASE="${OLLAMA_MODEL%%:*}"
if curl -s "$OLLAMA_BASE_URL/api/tags" 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
names=[m.get('name','') for m in d.get('models',[])]
target=sys.argv[1]
found=any(target in n or n.startswith(target) for n in names)
sys.exit(0 if found else 1)
" "$MODEL_BASE" 2>/dev/null; then
  echo "      Model $OLLAMA_MODEL already present."
else
  echo "      Pulling $OLLAMA_MODEL (may take a while)..."
  ollama pull "$OLLAMA_MODEL"
fi
echo ""

# 2. Claude Code
echo "[2/4] Claude Code"
if ! command -v claude >/dev/null 2>&1; then
  if [ -f "$HOME/.local/bin/claude" ]; then
    echo "      Found at ~/.local/bin/claude — ensure it's in PATH"
    export PATH="$HOME/.local/bin:$PATH"
  else
    echo "      Installing Claude Code..."
    curl -fsSL https://claude.ai/install.sh | bash
    export PATH="$HOME/.local/bin:$PATH"
  fi
fi

if command -v claude >/dev/null 2>&1; then
  echo "      Claude Code: $(claude -v 2>/dev/null || echo 'installed')"
else
  echo "      ERROR: Claude Code not found. Install: curl -fsSL https://claude.ai/install.sh | bash"
  exit 1
fi
echo ""

# 3. Config for Ollama
echo "[3/4] Config for Ollama"
ENV_ADD="
# Claude Code + Ollama (for agent tasks)
OLLAMA_MODEL=$OLLAMA_MODEL
ANTHROPIC_AUTH_TOKEN=ollama
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=$OLLAMA_BASE_URL
"
if [ -f .env ]; then
  if grep -q "ANTHROPIC_AUTH_TOKEN=ollama" .env 2>/dev/null; then
    echo "      .env already has Ollama config."
  else
    echo "$ENV_ADD" >> .env
    echo "      Appended Ollama config to .env"
  fi
else
  echo "$ENV_ADD" >> .env
  echo "      Created .env with Ollama config."
fi
echo ""

# 4. Test
echo "[4/4] Quick test"
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL="$OLLAMA_BASE_URL"

# Use model name without ollama/ prefix for claude --model
MODEL_NAME="${OLLAMA_MODEL#ollama/}"
if claude -p "Reply with exactly: OK" --model "$MODEL_NAME" --no-session-persistence 2>/dev/null | grep -q "OK"; then
  echo "      Claude Code + Ollama: OK"
else
  echo "      Test inconclusive. Try manually:"
  echo "        ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_BASE_URL=$OLLAMA_BASE_URL ANTHROPIC_API_KEY=\"\" claude -p 'echo hello' --model $MODEL_NAME"
fi
echo ""
echo "Done. Run test: python scripts/test_agent_run.py"
