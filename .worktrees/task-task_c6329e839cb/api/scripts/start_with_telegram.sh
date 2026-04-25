#!/bin/bash
# Start API + cloudflared tunnel + set Telegram webhook. One command.
# Ctrl+C stops everything.
#
# Prereqs: brew install cloudflared; api/.env with TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
cd "$API_DIR"

# Load env
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

PORT="${PORT:-8000}"
API_START_TIMEOUT_SEC="${API_START_TIMEOUT_SEC:-90}"
LOG_DIR="${API_DIR}/logs"
mkdir -p "$LOG_DIR"
API_LOG="$LOG_DIR/start_api.log"
TUNNEL_LOG="$LOG_DIR/start_tunnel.log"
PIDFILE="$LOG_DIR/start.pid"

select_api_launcher() {
  local candidates=("${API_DIR}/.venv/bin/python" "python3" "python")
  local candidate
  for candidate in "${candidates[@]}"; do
    if [ "$candidate" = "python3" ] || [ "$candidate" = "python" ]; then
      command -v "$candidate" >/dev/null 2>&1 || continue
    else
      [ -x "$candidate" ] || continue
    fi

    if "$candidate" -c "import uvicorn" >/dev/null 2>&1; then
      echo "python::$candidate"
      return 0
    fi
  done
  if command -v uvicorn >/dev/null 2>&1; then
    echo "uvicorn::$(command -v uvicorn)"
    return 0
  fi
  return 1
}

cleanup() {
  echo ""
  echo "Shutting down..."
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null || true
  rm -f "$PIDFILE"
  exit 0
}
trap cleanup SIGINT SIGTERM

# 0. Stop any existing API/tunnel
pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
pkill -f "localtunnel" 2>/dev/null || true
sleep 2

# 1. Start API
echo "[1/4] Starting API on port $PORT..."
: > "$API_LOG"
: > "$TUNNEL_LOG"
if ! API_LAUNCHER="$(select_api_launcher)"; then
  echo "No usable Uvicorn launcher is available."
  echo "Checked Python runtimes: ${API_DIR}/.venv/bin/python, python3, python"
  echo "Checked executable: uvicorn"
  echo "Install uvicorn (or add it to one of these runtimes) and retry."
  exit 1
fi
LAUNCHER_KIND="${API_LAUNCHER%%::*}"
LAUNCHER_PATH="${API_LAUNCHER#*::}"
if [ "$LAUNCHER_KIND" = "python" ]; then
  if [ "$LAUNCHER_PATH" != "${API_DIR}/.venv/bin/python" ]; then
    echo "      Using fallback runtime: $LAUNCHER_PATH"
  fi
  "$LAUNCHER_PATH" -m uvicorn app.main:app --port "$PORT" --host 127.0.0.1 >> "$API_LOG" 2>&1 &
else
  echo "      Using uvicorn executable: $LAUNCHER_PATH"
  "$LAUNCHER_PATH" app.main:app --port "$PORT" --host 127.0.0.1 >> "$API_LOG" 2>&1 &
fi
API_PID=$!
echo "$API_PID" > "$PIDFILE"

# Wait for API
for i in $(seq 1 "$API_START_TIMEOUT_SEC"); do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "API process exited before health check. Check $API_LOG"
    exit 1
  fi
  if curl -s "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    echo "      API ready."
    break
  fi
  [ "$i" -eq "$API_START_TIMEOUT_SEC" ] && {
    echo "API failed to start within ${API_START_TIMEOUT_SEC}s. Check $API_LOG"
    exit 1
  }
  sleep 1
done

# 2. Start cloudflared
echo "[2/4] Starting cloudflared tunnel..."
cloudflared tunnel --url "http://127.0.0.1:$PORT" > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

# Wait for tunnel URL (subdomain like "foo-bar-baz", not "api")
PUBLIC_URL=""
for i in $(seq 1 20); do
  PUBLIC_URL=$(grep -oE 'https://[a-zA-Z0-9]+(-[a-zA-Z0-9]+)+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
  [ -n "$PUBLIC_URL" ] && break
  sleep 1
done

if [ -z "$PUBLIC_URL" ]; then
  echo "      Cloudflared failed. Trying localtunnel fallback..."
  kill "$TUNNEL_PID" 2>/dev/null || true
  TUNNEL_PID=""
  npx -y localtunnel --port "$PORT" > "$TUNNEL_LOG" 2>&1 &
  TUNNEL_PID=$!
  for i in $(seq 1 15); do
    PUBLIC_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.loca\.lt' "$TUNNEL_LOG" 2>/dev/null | head -1)
    [ -n "$PUBLIC_URL" ] && break
    sleep 1
  done
fi

if [ -z "$PUBLIC_URL" ]; then
  echo "      Tunnel failed. Last log lines:"
  tail -5 "$TUNNEL_LOG" | sed 's/^/        /'
  echo ""
  echo "      API still running on http://127.0.0.1:$PORT (no webhook)"
  echo ""
  echo "Press Ctrl+C to stop API."
  wait $API_PID 2>/dev/null || true
  exit 1
fi
echo "      Tunnel: $PUBLIC_URL"

# 3. Set webhook (tunnel needs a few seconds to propagate)
echo "[3/4] Setting Telegram webhook..."
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
  sleep 5
  WEBHOOK_URL="${PUBLIC_URL%/}/api/agent/telegram/webhook"
  RESULT=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")
  if echo "$RESULT" | grep -q '"ok":true'; then
    echo "      Webhook set."
  else
    echo "      Webhook failed: $RESULT"
  fi
else
  echo "      TELEGRAM_BOT_TOKEN not set, skipping webhook."
fi

echo "[4/4] Ready. Message @Coherence_Network_bot with /status"
echo ""
echo "  API:     http://127.0.0.1:$PORT"
echo "  Tunnel:  $PUBLIC_URL"
echo "  Logs:    tail -f $API_LOG $LOG_DIR/telegram.log"
echo ""
echo "Press Ctrl+C to stop."
wait $API_PID 2>/dev/null || wait $TUNNEL_PID 2>/dev/null || true
