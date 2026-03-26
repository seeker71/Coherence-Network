# Spec: Deploy Latest Main to VPS (`deploy-latest-to-vps`)

## Purpose

Production is behind `main` by 15+ PRs, so API and web behavior on `coherencycoin.com` does not reflect current merged capabilities. This spec defines a deterministic deploy-and-verify flow to rebuild and restart both services on the VPS, then prove that newly merged API and web behavior is live.

## Requirements

- [ ] Pull latest `origin/main` on VPS repo at `/docker/coherence-network/repo`.
- [ ] Rebuild both images with no cache: `api` and `web`.
- [ ] Restart both services using Docker Compose and confirm containers are healthy/running.
- [ ] Verify public API now exposes `/api/services` and returns `200`.
- [ ] Verify public health payload includes `schema_ok` and reports healthy status.
- [ ] Verify web serves updated behavior (fresh build) and can reach API without CORS/runtime failure.
- [ ] Capture deploy evidence (commands + outputs) in task/PR artifacts.

## Research Inputs (Required)

- `2026-03-26` - [Docker Compose CLI reference](https://docs.docker.com/reference/cli/docker/compose/) - source of truth for `build`, `up`, and service lifecycle behavior.
- `2026-03-26` - [FastAPI deployment concepts](https://fastapi.tiangolo.com/deployment/) - confirms API restart expectations and production process model.
- `2026-03-26` - [Project deploy runbook in CLAUDE.md](https://github.com/seeker71/Coherence-Network/blob/main/CLAUDE.md) - project-specific VPS paths, service names, and deploy sequence.

## Task Card (Required)

```yaml
goal: Deploy latest main to VPS so public API/web match merged main behavior.
files_allowed:
  - specs/156-deploy-latest-to-vps.md
done_when:
  - VPS is updated to latest origin/main and api+web containers are rebuilt and restarted.
  - Public /api/services returns HTTP 200 with JSON body.
  - Public health endpoint response includes schema_ok and healthy status after deploy.
commands:
  - ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 'cd /docker/coherence-network/repo && git pull origin main'
  - ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 'cd /docker/coherence-network && docker compose build --no-cache api web'
  - ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 'cd /docker/coherence-network && docker compose up -d api web'
  - curl -fsS https://api.coherencycoin.com/api/services
  - curl -fsS https://api.coherencycoin.com/api/health
constraints:
  - Do not modify application code as part of this task; deploy-only.
  - Do not run destructive docker cleanup commands (no volume/db prune).
  - If verification fails, collect evidence and stop before risky rollback actions.
```

## API Contract (if applicable)

### `GET /api/services`

**Response 200 (expected after deploy)**
```json
{
  "services": [
    {
      "id": "service_id",
      "name": "Service Name"
    }
  ]
}
```

Notes:
- Response may contain additional fields; minimum contract is HTTP `200` with JSON payload representing service registry data.

### `GET /api/health`

**Response 200 (expected after deploy)**
```json
{
  "status": "ok",
  "schema_ok": true
}
```

Notes:
- Health payload may include additional metadata (version/timestamp/components). `schema_ok` presence is required.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `specs/156-deploy-latest-to-vps.md` - deployment verification spec for VPS refresh.

## Acceptance Tests

Test scenarios that prove the deployment worked:

1. **Deploy execution succeeds**
   - Run SSH deploy sequence (`git pull`, `docker compose build --no-cache api web`, `docker compose up -d api web`).
   - Expect exit code `0` for each command.
   - Expect `docker compose ps` to show `api` and `web` as running/healthy.

2. **API feature parity check**
   - `curl -i https://api.coherencycoin.com/api/services`
   - Expect HTTP `200`.
   - Expect `Content-Type: application/json` and JSON body with service list structure.

3. **Health schema contract check**
   - `curl -i https://api.coherencycoin.com/api/health`
   - Expect HTTP `200`.
   - Expect JSON containing `"status":"ok"` and `"schema_ok":true`.

4. **Web freshness and API wiring check**
   - Open `https://coherencycoin.com/` and exercise at least one API-backed page/flow.
   - Expect no stale "endpoint missing" behavior and no visible runtime/API/CORS errors in browser console/network.

## Concurrency Behavior

- **Deploy operations**: Single-operator execution preferred; concurrent deploy sessions are out of contract and may cause race conditions.
- **Runtime traffic during deploy**: Brief transient 5xx/timeouts are acceptable during container restart window.
- **Post-deploy consistency**: API and web must both serve from newly built images before verification passes.

## Verification

```bash
# Local spec quality gate
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD

# Public deploy verification
curl -fsS https://api.coherencycoin.com/api/services
curl -fsS https://api.coherencycoin.com/api/health
curl -sI https://coherencycoin.com/
```

Acceptance criteria:
- Validator exits `0` with no blocking quality violations.
- `/api/services` and `/api/health` return `200`.
- Health JSON includes `schema_ok: true`.
- Web root responds successfully (HTTP `200` or expected redirect to canonical host with successful final response).

## Edge Cases and Error Handling Expectations

- If `git pull origin main` reports conflicts or detached state, stop deploy and resolve repository state before build.
- If `docker compose build` fails, do not restart partially built services; fix build error and rerun build.
- If `docker compose up -d` starts only one service, treat deploy as failed and restore both services to running state before exit.
- If `/api/services` returns `404` after deploy, mark as blocking regression and collect container logs (`api`, `web`) for triage.
- If `/api/health` returns `200` but lacks `schema_ok`, treat as contract failure (old image or schema regression).
- If web is up but API calls fail due to CORS/network, treat deploy as incomplete and capture browser/network evidence.

## Out of Scope

- Any feature implementation or bug fix in API/web code.
- Database schema migrations not already included in merged `main`.
- Infrastructure redesign (Traefik/Cloudflare/topology changes).

## Risks and Assumptions

- Assumes VPS host `187.77.152.42` and SSH key `~/.ssh/hostinger-openclaw` are valid and accessible.
- Assumes `/docker/coherence-network/repo` tracks the same GitHub `main` branch intended for release.
- Risk: no-cache rebuild increases deploy time and temporary service interruption; mitigate by running during low-traffic window.
- Risk: hidden env/config drift on VPS can cause post-deploy behavior to differ from local/CI despite correct code.

## Known Gaps and Follow-up Tasks

- Add automated post-deploy smoke check job that validates `/api/services` and `/api/health.schema_ok` after each main deploy.
- Add explicit deploy evidence artifact template for command output, image IDs, and endpoint snapshots.
- Add release lag monitor that alerts when production commit SHA drifts beyond a threshold from `origin/main`.

## Failure/Retry Reflection

- Failure mode: SSH or host connectivity failure.
- Blind spot: deploy readiness not verified before maintenance window.
- Next action: verify host reachability and credentials, then rerun deploy sequence from `git pull`.

- Failure mode: endpoint still stale after "successful" restart.
- Blind spot: old images reused or wrong compose project path.
- Next action: confirm compose path, image digests, and running container creation timestamps; rebuild+restart once.

## Decision Gates (if any)

- None for this deploy spec. Escalate only if production verification fails after one clean redeploy attempt.
