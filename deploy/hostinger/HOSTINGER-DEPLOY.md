# Coherence Network — Hostinger VPS Deployment

Deploy the API (FastAPI) and website (Next.js) to a Hostinger VPS.

## Prerequisites

- Hostinger VPS (Ubuntu 22.04+ recommended, KVM plan)
- SSH access to the VPS (`ssh root@YOUR_VPS_IP`)
- A domain pointed to the VPS IP (via Hostinger DNS or your registrar)
- Local machine: Node.js 20+, Git, rsync

## Quick Deploy (3 steps)

### 1. Initial VPS setup (one time)

```bash
ssh root@YOUR_VPS_IP 'bash -s' < deploy/hostinger/setup-vps.sh
```

This installs Node.js 20, Python 3, Nginx, PM2, and creates the app user.

### 2. Deploy application

```bash
./deploy/hostinger/deploy.sh root@YOUR_VPS_IP your-domain.com
```

This:
- Builds Next.js locally (standalone mode)
- Packages API + web artifacts
- Uploads via rsync
- Installs Python dependencies on the VPS
- Configures nginx reverse proxy
- Starts both services via PM2

### 3. Enable HTTPS

```bash
ssh root@YOUR_VPS_IP 'bash -s your-domain.com' < deploy/hostinger/setup-ssl.sh
```

## Architecture

```
Internet → Nginx (port 80/443)
              ├── /api/*  → FastAPI (uvicorn, port 8000)
              └── /*      → Next.js (port 3000)
```

Both services run as the `coherence` user, managed by PM2 for auto-restart and log management.

## Configuration

### API environment (`/opt/coherence/api/.env`)

After first deploy, SSH in and edit:

```bash
ssh root@YOUR_VPS_IP
sudo -u coherence nano /opt/coherence/api/.env
```

Key variables:
- `DATABASE_URL` — PostgreSQL connection string
- `ALLOWED_ORIGINS` — Your domain (set automatically by deploy script)
- `OPENROUTER_API_KEY` — For agent features (optional)

### Web environment (`/opt/coherence/web/.env.production`)

Set automatically by deploy script. The key variable is:
- `NEXT_PUBLIC_API_URL` — Points to your domain

## Management

```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# View running services
sudo -u coherence pm2 list

# View logs
sudo -u coherence pm2 logs coherence-api
sudo -u coherence pm2 logs coherence-web

# Restart services
sudo -u coherence pm2 restart all

# Nginx status
systemctl status nginx
```

## Re-deploy (after code changes)

Just run the deploy script again:

```bash
./deploy/hostinger/deploy.sh root@YOUR_VPS_IP your-domain.com
```

It rebuilds, uploads, and restarts services automatically.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 502 Bad Gateway | Check PM2: `sudo -u coherence pm2 list` — services may have crashed |
| API not responding | Check logs: `sudo -u coherence pm2 logs coherence-api` |
| Web shows blank page | Ensure `NEXT_PUBLIC_API_URL` is correct in `/opt/coherence/web/.env.production` |
| SSL certificate error | Re-run: `certbot --nginx -d your-domain.com` |
| Permission denied | `chown -R coherence:coherence /opt/coherence` |

## Files

| File | Purpose |
|------|---------|
| `setup-vps.sh` | One-time VPS setup (installs deps) |
| `deploy.sh` | Full build + upload + restart |
| `ecosystem.config.js` | PM2 process config (API + Web) |
| `nginx.conf` | Reverse proxy template |
| `setup-ssl.sh` | Let's Encrypt HTTPS setup |
