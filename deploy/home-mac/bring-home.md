# Add the Mac as a peer node — a body with no center

The mind already came home: the real model runs usably on owned hardware (RTX, ~1 tok/s,
bit-exact; proven on the Adreno phone). This adds the **Mac as a peer node** of the body — stores
+ API + web on owned, always-on hardware, with its own public door (a Cloudflare tunnel the Mac
owns). **The VPS is NOT retired** — it stays a *valuable node* (public reach, always-on). The
sovereignty move is **no center**, not no-VPS: the body lives across peers (Windows/RTX, Mac,
Android, VPS), content-addressed so every copy is the same body, and any node can serve — or fail —
without the body going dark. Today the VPS is the single point; this makes it one peer among several.

Staged so the **live site never drops** — Stages 1–3 touch nothing public; Stage 4 only *adds* the
Mac as a second door (no cutover-or-die), reversible.

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

## Stage 4 — the Mac becomes a SECOND door (no center, no cutover-or-die)
Add the Mac tunnel as a second origin for the hostnames — a Cloudflare load-balance / failover pool
(or a weighted CNAME) — so **both** the Mac and the VPS serve. Neither is the center: if either node
dies, the other answers; the content-addressed memory means both hold the same body. Watch both
breathe: `curl https://pulse.coherencycoin.com/pulse/now`. The VPS keeps doing what it's good at
(public reach); the Mac adds owned, always-on capacity. To undo: drop the Mac from the pool.

## The shape this is heading toward (named, not built here)
A center-less, content-addressed body: each node (Windows/RTX, Mac, Android, VPS) holds the memory
keyed by NodeID, peers sync (same NodeID = same cell anywhere), any node can be a door, any node can
fall without the body going dark. This runbook is rung one — the Mac as a real peer holding a live
copy and serving. Full peer-to-peer memory sync is the next rung.

## Discipline
- Never drop the live site: Stages 1–3 are invisible to the public; Stage 4 only *adds* an origin.
- The Mac must be genuinely always-on (sleep disabled: `sudo pmset -a sleep 0 disablesleep 1`, or `caffeinate`).
- Bit-exact isn't the gate here (infra, not compute) — the gate is: the Mac node answers `/api/health`,
  the witness breathes, and its graph/relational counts match the VPS before it joins the door pool.
