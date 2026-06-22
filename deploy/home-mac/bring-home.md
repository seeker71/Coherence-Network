# Bring the body home — the Mac as the always-on node

The mind already came home: the real model runs usably on owned hardware (RTX, ~1 tok/s,
bit-exact; proven on the Adreno phone). This brings the **body** home too — stores + API + web
off the rented Hostinger VPS and onto the Mac, public reach via a Cloudflare tunnel the Mac owns.
The VPS is the gated/bootstrap shape the sovereignty north star retires; this retires it.

Staged so the **live site never drops** — Stages 1–3 touch nothing public; Stage 4 is the only
cutover, and it's reversible (point DNS back).

Run on the Mac (it has Docker + the VPS key `~/.ssh/hostinger-openclaw`). VPS = `root@187.77.152.42`,
compose root `/docker/coherence-network`, services: api · web · pulse · postgres · neo4j.

## Stage 1 — body runs on the Mac (local, zero live impact)
```
mkdir -p ~/coherence-home && cd ~/coherence-home
scp -i ~/.ssh/hostinger-openclaw root@187.77.152.42:/docker/coherence-network/docker-compose.yml .
# pull any referenced env/config too:
scp -i ~/.ssh/hostinger-openclaw root@187.77.152.42:/docker/coherence-network/.env . 2>/dev/null || true
git clone <repo> repo   # or symlink your existing checkout as ./repo (compose builds from it)
docker compose up -d --build   # Apple-Silicon arm64 images build from the repo Dockerfiles
curl -sf localhost:8000/api/health && echo OK   # adjust port to the compose
```
→ The body now runs on owned hardware. Reversible; no DNS touched.

## Stage 2 — bring the memory home (data)
Dump consistent on the VPS, restore on the Mac, verify counts match:
```
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network && docker compose exec -T postgres pg_dumpall -U postgres' > pg.sql
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network && docker compose exec -T neo4j neo4j-admin database dump neo4j --to-stdout' > neo4j.dump
# restore into the local containers, then verify: node count (neo4j) + row counts (postgres) == VPS.
```
(If neo4j is the silent organ right now, start it on the VPS first or dump from its last backup.)

## Stage 3 — public reach from the Mac (owned door, still no cutover)
```
brew install cloudflared
cloudflared tunnel login && cloudflared tunnel create coherence-home
# config.yml ingress: coherencycoin.com + api.coherencycoin.com + pulse.coherencycoin.com -> local ports
cloudflared tunnel run coherence-home
```
Test via the tunnel's `*.cfargotunnel.com` hostname BEFORE cutover — confirm the home body answers.

## Stage 4 — cutover (the only public move; reversible)
Point the Cloudflare DNS for the three hostnames at the Mac tunnel (CNAME → `<tunnel-id>.cfargotunnel.com`).
Watch the witness breathe from the Mac: `curl https://pulse.coherencycoin.com/pulse/now`.
Keep the VPS up ~24h as fallback; if the home node holds, retire it. To roll back: point DNS back.

## Discipline
- Never drop the live site: Stages 1–3 are invisible to the public; only Stage 4 switches DNS.
- The Mac must be genuinely always-on (sleep disabled: `sudo pmset -a sleep 0 disablesleep 1`, or `caffeinate`).
- Bit-exact isn't the gate here (it's infra, not compute) — the gate is: the home body answers
  `/api/health`, the witness breathes, and the graph/relational counts match the VPS before cutover.
