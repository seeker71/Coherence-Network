#!/usr/bin/env bash
# Coherence Network — Deploy to Hostinger VPS
# Usage: ./deploy/hostinger/deploy.sh [VPS_HOST] [DOMAIN]
# Example: ./deploy/hostinger/deploy.sh root@123.45.67.89 coherence.example.com
set -euo pipefail

VPS_HOST="${1:?Usage: deploy.sh VPS_HOST [DOMAIN]}"
DOMAIN="${2:-localhost}"
API_PORT=8000
WEB_PORT=3000
REMOTE_DIR="/opt/coherence"

echo "==> Deploying Coherence Network to ${VPS_HOST}"
echo "    Domain: ${DOMAIN}"
echo ""

# ── 1. Build web locally (standalone) ──────────────────────────────────────
echo "==> Building Next.js standalone..."
cd "$(git rev-parse --show-toplevel)/web"

# Set API URL for the build
export NEXT_PUBLIC_API_URL="https://${DOMAIN}/api"
npm ci --prefer-offline 2>/dev/null || npm install
npm run build

echo "==> Next.js build complete (standalone output)"

# ── 2. Package artifacts ───────────────────────────────────────────────────
cd "$(git rev-parse --show-toplevel)"
echo "==> Packaging deployment artifacts..."

TMPDIR=$(mktemp -d)

# API: copy source + requirements
mkdir -p "${TMPDIR}/api"
cp -r api/app api/scripts api/alembic* "${TMPDIR}/api/" 2>/dev/null || true
cp api/requirements*.txt "${TMPDIR}/api/" 2>/dev/null || true
cp api/Procfile "${TMPDIR}/api/" 2>/dev/null || true
# Include pyproject.toml if it exists
cp api/pyproject.toml "${TMPDIR}/api/" 2>/dev/null || true

# Web: copy standalone build
mkdir -p "${TMPDIR}/web"
cp -r web/.next/standalone/* "${TMPDIR}/web/" 2>/dev/null || true
# Copy static assets and public into standalone
cp -r web/.next/static "${TMPDIR}/web/.next/static" 2>/dev/null || true
cp -r web/public "${TMPDIR}/web/public" 2>/dev/null || true

# PM2 ecosystem file
cp deploy/hostinger/ecosystem.config.js "${TMPDIR}/" 2>/dev/null || true

# Nginx config
cp deploy/hostinger/nginx.conf "${TMPDIR}/nginx-coherence.conf" 2>/dev/null || true

# Create env templates
cat > "${TMPDIR}/api/.env" << ENVEOF
# Coherence API — Production Environment
# ⚠️  Fill in your actual values before starting

# Database
DATABASE_URL=postgresql://coherence:CHANGE_ME@localhost:5432/coherence
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USERNAME=neo4j
# NEO4J_PASSWORD=

# CORS — allow the web domain
ALLOWED_ORIGINS=https://${DOMAIN},http://localhost:3000

# API keys (optional — only needed for agent features)
# OPENROUTER_API_KEY=
# ANTHROPIC_API_KEY=

# Port
PORT=${API_PORT}
ENVEOF

cat > "${TMPDIR}/web/.env.production" << ENVEOF
NEXT_PUBLIC_API_URL=https://${DOMAIN}
PORT=${WEB_PORT}
ENVEOF

echo "==> Uploading to ${VPS_HOST}..."
rsync -azP --delete \
  "${TMPDIR}/api/" "${VPS_HOST}:${REMOTE_DIR}/api/"
rsync -azP --delete \
  "${TMPDIR}/web/" "${VPS_HOST}:${REMOTE_DIR}/web/"
scp "${TMPDIR}/ecosystem.config.js" "${VPS_HOST}:${REMOTE_DIR}/" 2>/dev/null || true
scp "${TMPDIR}/nginx-coherence.conf" "${VPS_HOST}:/etc/nginx/sites-available/coherence" 2>/dev/null || true

rm -rf "${TMPDIR}"

# ── 3. Remote setup: install deps + start services ────────────────────────
echo "==> Running remote setup..."
ssh "${VPS_HOST}" bash << 'REMOTE'
set -euo pipefail

echo "--- Installing API dependencies ---"
cd /opt/coherence/api
python3 -m venv .venv 2>/dev/null || true
.venv/bin/pip install -q --upgrade pip
if [ -f requirements.txt ]; then
  .venv/bin/pip install -q -r requirements.txt
elif [ -f pyproject.toml ]; then
  .venv/bin/pip install -q -e .
fi

echo "--- Setting permissions ---"
chown -R coherence:coherence /opt/coherence

echo "--- Configuring nginx ---"
if [ -f /etc/nginx/sites-available/coherence ]; then
  ln -sf /etc/nginx/sites-available/coherence /etc/nginx/sites-enabled/coherence
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
  echo "✅ Nginx configured"
else
  echo "⚠️  No nginx config found — set up manually"
fi

echo "--- Starting services with PM2 ---"
cd /opt/coherence
if [ -f ecosystem.config.js ]; then
  sudo -u coherence pm2 delete all 2>/dev/null || true
  sudo -u coherence pm2 start ecosystem.config.js
  sudo -u coherence pm2 save
  # Enable PM2 startup on boot
  pm2 startup systemd -u coherence --hp /home/coherence 2>/dev/null || true
  echo "✅ PM2 services started"
else
  echo "⚠️  No ecosystem.config.js — start services manually"
fi

echo ""
echo "✅ Deployment complete!"
REMOTE

echo ""
echo "==> ✅ Deployment finished!"
echo ""
echo "Verify:"
echo "  curl -fsS https://${DOMAIN}/api/health | jq ."
echo "  curl -fsS https://${DOMAIN}/"
echo ""
echo "If HTTPS is not yet configured, run:"
echo "  ssh ${VPS_HOST} 'certbot --nginx -d ${DOMAIN}'"
