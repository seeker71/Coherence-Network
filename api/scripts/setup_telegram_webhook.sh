#!/bin/bash
# Setup Telegram webhook. Requires: API running + public URL.
#
# Option A - cloudflared (recommended, no signup):
#   brew install cloudflared
#   cloudflared tunnel --url http://localhost:8000
#   Use the https://xxx.trycloudflare.com URL
#
# Option B - ngrok (needs account):
#   npx ngrok http 8000
#
# Then run:
#   export PUBLIC_URL=https://your-tunnel.trycloudflare.com
#   ./scripts/setup_telegram_webhook.sh
#
# Or pass URL: ./scripts/setup_telegram_webhook.sh https://xxx.trycloudflare.com

set -e
cd "$(dirname "$0")/.."
source .env 2>/dev/null || true

PUBLIC_URL="${1:-$PUBLIC_URL}"
if [ -z "$PUBLIC_URL" ]; then
  echo "Usage: PUBLIC_URL=https://xxx.trycloudflare.com $0"
  echo "   or: $0 https://xxx.trycloudflare.com"
  echo ""
  echo "Start tunnel first: cloudflared tunnel --url http://localhost:8000"
  exit 1
fi

WEBHOOK_URL="${PUBLIC_URL%/}/api/agent/telegram/webhook"
echo "Setting webhook: $WEBHOOK_URL"
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}" | python3 -m json.tool
echo ""
echo "Done. Message @Coherence_Network_bot with /status to test."
