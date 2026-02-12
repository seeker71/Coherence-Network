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
LOG_DIR="${API_DIR}/logs"
mkdir -p "$LOG_DIR"
API_LOG="$LOG_DIR/start_api.log"
TUNNEL_LOG="$LOG_DIR/start_tunnel.log"
PIDFILE="$LOG_DIR/start.pid"

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
PYTHON="${API_DIR}/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"
$PYTHON -m uvicorn app.main:app --port "$PORT" --host 127.0.0.1 >> "$API_LOG" 2>&1 &
API_PID=$!
echo "$API_PID" > "$PIDFILE"

# Wait for API
for i in $(seq 1 15); do
  if curl -s "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    echo "      API ready."
    break
  fi
  [ $i -eq 15 ] && { echo "API failed to start. Check $API_LOG"; exit 1; }
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
