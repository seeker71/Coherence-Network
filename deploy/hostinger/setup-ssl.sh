#!/usr/bin/env bash
# Coherence Network — Enable HTTPS via Let's Encrypt
# Usage: ssh root@VPS_HOST 'bash -s DOMAIN' < deploy/hostinger/setup-ssl.sh
set -euo pipefail

DOMAIN="${1:?Usage: setup-ssl.sh DOMAIN}"

echo "==> Setting up SSL for ${DOMAIN}..."

# Update nginx config with actual domain
sed -i "s/YOUR_DOMAIN/${DOMAIN}/g" /etc/nginx/sites-available/coherence
nginx -t && systemctl reload nginx

# Get certificate
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email "admin@${DOMAIN}" --redirect

echo "==> ✅ HTTPS enabled for ${DOMAIN}"
echo "    Certificate auto-renews via certbot timer"
