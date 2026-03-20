#!/usr/bin/env bash
# Coherence Network — Hostinger VPS Initial Setup
# Run this ONCE on a fresh Hostinger VPS (Ubuntu 22.04+)
# Usage: ssh root@YOUR_VPS_IP 'bash -s' < deploy/hostinger/setup-vps.sh
set -euo pipefail

echo "==> Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx \
  python3-pip python3-venv git curl nodejs npm

# Install Node.js 20 LTS via NodeSource if old version
NODE_MAJOR=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1 || echo 0)
if [ "$NODE_MAJOR" -lt 20 ]; then
  echo "==> Upgrading Node.js to 20 LTS..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y -qq nodejs
fi

# Install PM2 for process management
echo "==> Installing PM2..."
npm install -g pm2

# Create app user
if ! id coherence &>/dev/null; then
  echo "==> Creating coherence user..."
  useradd -m -s /bin/bash coherence
fi

# Create app directories
echo "==> Creating app directories..."
mkdir -p /opt/coherence/{api,web}
chown -R coherence:coherence /opt/coherence

echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Copy deploy/hostinger/deploy.sh to your local machine"
echo "  2. Configure DNS to point your domain to this VPS IP"
echo "  3. Run deploy.sh to deploy the application"
echo "  4. Run deploy/hostinger/setup-ssl.sh to enable HTTPS"
