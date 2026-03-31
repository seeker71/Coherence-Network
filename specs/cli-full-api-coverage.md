# CLI full API coverage (universal REST + agent wiring)

## Goal

Operators and agents must reach **every** documented Coherence Network HTTP API from the terminal without waiting for a bespoke `cc <noun>` subcommand. Today many endpoints are exposed only through the canonical route registry (~215 API routes) while the CLI covered a small fraction. This spec adds:

1. **`cc rest`** — authenticated raw HTTP to any path under the configured hub (GET/POST/PATCH/PUT/DELETE), so **100% of API routes are reachable** from the terminal when combined with `GET /api/inventory/routes/canonical`.
2. **`cc rest coverage`** — fetches the canonical route manifest and prints **route count + version + proof** that “full access” is available via `cc rest`.
3. **`cc agent`** — wire the existing `cli/lib/commands/agent.mjs` (previously orphaned) plus **execute**, **route**, **pickup**, and **smart-reap** subcommands for pipeline operations.
4. **`cc task count`** and **`cc task events`** — lightweight task observability aligned with `/api/agent/tasks/count` and `/api/agent/tasks/{id}/events`.
5. **Fix** — export `getApiBase()` from `cli/lib/api.mjs` for `watchTask` and other callers.

### Open question: how we show the idea is working

- **Quantitative:** `cc rest coverage` prints `canonical_api_route_count` from the server manifest; that number should match the repo’s `api/config/canonical_routes.json` (or deployment mirror) within the same release.
- **Qualitative:** `cc rest GET /api/health` must return 200; `cc rest GET /api/inventory/routes/canonical` must return JSON with `api_routes` array.
- **Over time:** CI and the spec tests assert (a) `rest` and `agent` commands are registered, (b) `getApiBase` exists, (c) canonical routes endpoint responds. Optional dashboard: track `len(api_routes)` in release notes.

## Files to modify / create

| File | Action |
|------|--------|
| `cli/lib/api.mjs` | Add `getApiBase`, `request()` for arbitrary methods and response body handling |
| `cli/lib/commands/rest.mjs` | **New** — `handleRest` for `cc rest` and `cc rest coverage` |
| `cli/lib/commands/agent.mjs` | Add `execute`, `route`, `pickup`, `smart-reap` subcommands |
| `cli/lib/commands/tasks.mjs` | Add `count`, `events` branches |
| `cli/bin/cc.mjs` | Register `rest`, `agent`; extend help |
| `api/tests/test_cli_full_coverage.py` | Tests for new commands and `getApiBase` export |
| `specs/cli-full-api-coverage.md` | This spec |

## Acceptance criteria

- [ ] `cc rest GET /api/health` prints JSON body (or raw text) and exits 0 when the server returns 2xx.
- [ ] `cc rest POST /api/runtime/events` accepts `--body '{"event_type":"cli_smoke",...}'` (may 401/422 without full payload — CLI must not crash; prints status).
- [ ] `cc rest coverage` calls `GET /api/inventory/routes/canonical` and prints `canonical_api_route_count` and registry `version`.
- [ ] `cc agent` (no subcommand) shows status report; `cc agent route impl` calls GET `/api/agent/route?task_type=impl`.
- [ ] `cc agent execute <task_id>` sends POST `/api/agent/tasks/{id}/execute` with optional `X-Agent-Execute-Token` from env `AGENT_EXECUTE_TOKEN`.
- [ ] `cc task count` prints task counts from `/api/agent/tasks/count`.
- [ ] `node cli/bin/cc.mjs` loads without `getApiBase` undefined error when using `watch`.
- [ ] Pytest class `TestCliUniversalRest` passes.

## Verification scenarios

### Scenario 1 — Universal GET health

- **Setup:** API running (local TestClient or production `https://api.coherencycoin.com`).
- **Action:** `COHERENCE_HUB_URL=<base> node cli/bin/cc.mjs rest GET /api/health`
- **Expected:** HTTP status 200 echoed or implied; response body includes a `status` field (e.g. `ok` / `healthy`).
- **Edge:** `cc rest GET /api/no-such-path-ever-xyz` → non-2xx; CLI exits with non-zero and prints status line (not a stack trace).

### Scenario 2 — Coverage manifest proof

- **Setup:** Same API base as above.
- **Action:** `node cli/bin/cc.mjs rest coverage`
- **Expected:** Output includes `canonical_api_route_count` ≥ 1 and `registry_version` string; human-readable line states that any path can be called via `cc rest`.
- **Edge:** If the server returns non-JSON, CLI prints error message and exits non-zero.

### Scenario 3 — Agent route (no auth)

- **Setup:** API up.
- **Action:** `node cli/bin/cc.mjs agent route impl`
- **Expected:** JSON printed with routing fields (executor/model or documented `RouteResponse` shape); HTTP 200.
- **Edge:** `cc agent route __invalid_type__` → 422 or safe error body; CLI prints failure without crashing.

### Scenario 4 — Task count

- **Setup:** API up.
- **Action:** `node cli/bin/cc.mjs task count`
- **Expected:** Prints numeric counts or JSON from `/api/agent/tasks/count` (HTTP 200).
- **Edge:** Without API key, if server returns 401/403, CLI shows error from `request`/fetch path.

### Scenario 5 — Execute token gate

- **Setup:** `AGENT_EXECUTE_TOKEN` unset; task id `task_fake` (nonexistent).
- **Action:** `node cli/bin/cc.mjs agent execute task_fake`
- **Expected:** HTTP 403 or 404 from API; stderr or stdout explains failure (not uncaught exception).
- **Edge:** With wrong token, 403.

## Risks and assumptions

- **Assumption:** CLI users set `COHERENCE_HUB_URL` / `COHERENCE_API_URL` for non-production targets; `cc rest` does not second-guess path prefixes (paths must include `/api/...` where applicable).
- **Risk:** Raw POST can destroy data; operators must use confirmations in runbooks. Mitigation: documented in `cc help`; no `DELETE` without explicit method token.

## Known gaps and follow-up tasks

- [ ] OpenAPI-driven shell completion for `cc rest` paths.
- [ ] Optional `--dry-run` that only prints the resolved URL.
- [ ] Map high-traffic routes to first-class `cc` subcommands over time (reduce need for memorizing paths).

## Evidence (independently verifiable)

- Run `node cli/bin/cc.mjs rest coverage` against production and capture stdout (route count + version).
- Run `pytest api/tests/test_cli_full_coverage.py::TestCliUniversalRest -q` in CI.
- Live API: `https://api.coherencycoin.com/api/inventory/routes/canonical` returns the same manifest the CLI consumes.

## See also

- `specs/148-coherence-cli-comprehensive.md` — core CLI contract
- `api/config/canonical_routes.json` — source of route cardinality
