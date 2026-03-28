# Spec: CLI Full API Coverage (215 Endpoints)

## Purpose

Bring the Coherence Network terminal experience (`coherence-cli` / `cc`) to **parity with the public FastAPI surface**: every HTTP route that appears in the deployed OpenAPI catalog must be reachable through a documented, typed CLI path (dedicated subcommand, `cc api` passthrough, or explicit batch wrapper), with **machine-verifiable coverage** so contributors and operators can trust the CLI without manual spreadsheet audits.

Today the CLI meaningfully exposes roughly **39 of ~215** routes (~18%). The largest blind spots match operational needs: **agent pipeline**, **inventory**, **federation and messaging**, **runtime telemetry**, **ideas CRUD beyond list/view**, **value-lineage**, **treasury**, **governance**, and **service registry**. This spec orders work by product priority: **node messaging**, **task management**, **treasury**, **governance**, and **services**, then closes remaining gaps systematically.

**Related:** [Spec 148 — Coherence CLI comprehensive](148-coherence-cli-comprehensive.md) (foundational CLI); this spec extends 148 with **coverage completeness** and **proof mechanics**, not duplicate product vision.

## Summary

| Metric | Current (baseline) | Target |
|--------|---------------------|--------|
| API routes (OpenAPI) | ~215 | ~215 (moving target; version pinned in verification) |
| CLI-accessible routes | ~39 (~18%) | 100% of non-excluded routes |
| Proof | ad hoc | CI + `cc coverage` (or equivalent) + published artifact |

## Requirements

- [ ] **R1 — Coverage definition** — An “endpoint is covered” iff there exists a **documented** CLI invocation (in `cli/README.md` and inline `cc help`) that performs the same HTTP method and path template against `COHERENCE_API_URL`, OR the route is listed in an explicit **exclusion list** with rationale (e.g. binary streaming, websocket-only, deprecated).
- [ ] **R2 — Priority tranche (P0)** — Implement CLI for all routes under these API areas first: **federation/messaging** (node comms), **agent tasks + activity** (task management), **treasury**, **governance**, **service registry** — matching router modules `federation.py`, `agent_tasks_routes.py`, `task_activity_routes.py`, `treasury.py`, `governance.py`, `service_registry_router.py` and their nested paths.
- [ ] **R3 — Secondary tranche (P1)** — **Agent pipeline ops** (execute, run state, diagnostics, issues, grounded metrics, auto-heal, etc.), **inventory**, **runtime**, **ideas** (full CRUD and sub-resources), **value-lineage** — until gap counts from the baseline audit reach zero for those tags.
- [ ] **R4 — Universal escape hatch** — Provide `cc api <method> <path> [--json body]` (or equivalent) that signs requests with the same auth as other commands so **no** endpoint is unreachable while specialized subcommands are still rolling out.
- [ ] **R5 — Coverage manifest** — Add a **machine-readable** artifact (generated at build/CI) mapping `method+path` → `cli_command | api_passthrough | excluded` with line references to implementation files. Stored under `cli/` (e.g. `cli/coverage.manifest.json`) and referenced from README.
- [ ] **R6 — Regression gate** — CI fails if OpenAPI route count increases without a corresponding manifest update, or if covered fraction drops below **100% minus excluded**.
- [ ] **R7 — Operator UX** — Group commands by domain (`cc agent …`, `cc inventory …`, `cc runtime …`) consistent with OpenAPI tags; preserve **zero runtime dependencies** for the CLI package (Spec 148).

## Research Inputs (Required)

- `2026-03-28` — Internal baseline: task prompt `task_3111bb8447ba6cfb` (gap percentages by domain).
- `2026-03-24` — [Spec 148 — CLI comprehensive](148-coherence-cli-comprehensive.md) — architectural constraints (zero deps, `cc` entry).
- `2026-03-28` — `cli/bin/cc.mjs`, `cli/lib/commands/*.mjs` — current command surface.
- `2026-03-28` — `api/app/main.py` + `api/app/routers/*.py` — authoritative route registration.
- `2026-03-28` — `GET /api/meta/endpoints` — endpoint inventory for reconciliation (see `cli/lib/commands/meta.mjs`).

## Task Card (Required)

```yaml
goal: Achieve 100% CLI reachability for all non-excluded FastAPI routes with a coverage manifest and CI gate.
files_allowed:
  - cli/bin/cc.mjs
  - cli/lib/api.mjs
  - cli/lib/commands/**/*.mjs
  - cli/README.md
  - cli/README.template.md
  - cli/coverage.manifest.json
  - scripts/generate_cli_coverage.py
  - api/tests/test_cli_coverage_manifest.py
  - .github/workflows/*.yml
done_when:
  - coverage.manifest.json lists 100% of OpenAPI paths or explicit exclusions.
  - pytest test_cli_coverage_manifest passes in CI.
  - Documented verification commands in this spec succeed against staging/production.
commands:
  - python3 scripts/validate_spec_quality.py --file specs/task_3111bb8447ba6cfb.md
  - cd api && .venv/bin/pytest -q api/tests/test_cli_coverage_manifest.py
  - node cli/bin/cc.mjs meta endpoints | head -20
constraints:
  - Do not add npm dependencies to cli/package.json.
  - Exclusions must be reviewed in Known Gaps or removed within one release cycle.
```

## API Contract (if applicable)

**No new REST resources are required for MVP** if coverage is computed from **OpenAPI JSON** (`/openapi.json`) and the manifest is generated offline. Optional follow-up (nice-to-have):

### `GET /api/meta/cli-coverage` (optional)

**Response 200**

```json
{
  "openapi_path": "/openapi.json",
  "total_routes": 215,
  "covered": 215,
  "excluded": 0,
  "fraction": 1.0,
  "generated_at": "2026-03-28T12:00:00Z"
}
```

If not implemented, the spec is still satisfied by **repo-local** manifest + CI only.

## Data Model (if applicable)

**Coverage manifest** (JSON, committed):

```yaml
CliCoverageManifest:
  version: { type: integer, const: 1 }
  generated_at: { type: string, format: date-time }
  openapi_sha256: { type: string }
  routes:
    type: array
    items:
      type: object
      properties:
        method: { type: string, enum: [GET, POST, PUT, PATCH, DELETE] }
        path: { type: string }
        openapi_operation_id: { type: string }
        coverage_kind:
          type: string
          enum: [subcommand, passthrough, excluded]
        cli_entry: { type: [string, "null"] }
        implementation_ref: { type: [string, "null"] }
        exclusion_reason: { type: [string, "null"] }
```

## Files to Create/Modify

- `specs/task_3111bb8447ba6cfb.md` — this spec.
- `cli/bin/cc.mjs` — register new command groups and `api` passthrough.
- `cli/lib/api.mjs` — add `put`, `stream`, or other verbs if missing for parity.
- `cli/lib/commands/{agent,inventory,runtime,federation,ideas,treasury,governance,services,value_lineage}.mjs` — expand or split as needed.
- `cli/README.md` — coverage section + table linking tags to commands.
- `scripts/generate_cli_coverage.py` — diff OpenAPI vs manifest.
- `cli/coverage.manifest.json` — generated or hand-maintained until generator lands.
- `api/tests/test_cli_coverage_manifest.py` — contract test.

## Acceptance Tests

- `api/tests/test_cli_coverage_manifest.py::test_manifest_matches_openapi`
- `api/tests/test_cli_coverage_manifest.py::test_no_duplicate_route_keys`
- `api/tests/test_cli_coverage_manifest.py::test_exclusions_have_reasons`
- Manual: run P0 scenario commands in Verification Scenarios against `https://api.coherencycoin.com`.

## Verification

### Automated

```bash
python3 scripts/validate_spec_quality.py --file specs/task_3111bb8447ba6cfb.md
cd api && .venv/bin/pytest -q api/tests/test_cli_coverage_manifest.py
python3 scripts/generate_cli_coverage.py --check
```

### Verification Scenarios

#### Scenario 1 — Coverage manifest matches live OpenAPI

- **Setup:** Clean worktree; `OPENAPI_URL` defaults to production API or fixture file with known SHA.
- **Action:** `python3 scripts/generate_cli_coverage.py --check`
- **Expected:** Exit code 0; stdout includes `fraction: 1.000` (or 100% minus documented exclusions); `openapi_sha256` matches fetched schema.
- **Edge:** If OpenAPI fetch fails, script exits non-zero with stderr containing `openapi_fetch_failed` (no silent pass).

#### Scenario 2 — Passthrough reaches an uncovered route

- **Setup:** API key in env for authenticated route; pick any path listed as `passthrough` in manifest.
- **Action:** `node cli/bin/cc.mjs api GET /api/health`
- **Expected:** HTTP 200; body includes `"status"` or standard health JSON (same as `curl -s -H "X-API-Key: …" "$API/api/health"`).
- **Edge:** `cc api GET /api/nonexistent` returns non-zero or prints 404 detail without stack trace.

#### Scenario 3 — P0: Treasury from CLI

- **Setup:** Valid API key with treasury read permission (or public read if applicable).
- **Action:** `node cli/bin/cc.mjs treasury` then `node cli/bin/cc.mjs treasury deposits`
- **Expected:** Structured output; first command shows treasury summary fields consistent with `GET /api/treasury` (or documented sub-paths).
- **Edge:** Without API key, command fails with clear “set COHERENCE_API_KEY” message (not silent null).

#### Scenario 4 — P0: Task activity heartbeat parity

- **Setup:** Existing task id `T` with permission to post activity.
- **Action:** `node cli/bin/cc.mjs progress --task T --event agent_heartbeat --data '{"step":"verify"}'` (or exact CLI after implementation; must map to `POST /api/agent/tasks/{id}/activity`).
- **Expected:** HTTP 2xx; response JSON echoing accepted activity.
- **Edge:** Duplicate post with same idempotency key (if supported) returns 409; without key, server-defined behavior documented.

#### Scenario 5 — Meta alignment

- **Setup:** API reachable.
- **Action:** `node cli/bin/cc.mjs meta` then `node cli/bin/cc.mjs meta endpoints agent`
- **Expected:** `meta` prints endpoint count consistent with OpenAPI (~215); filtered list non-empty for agent-tagged routes.
- **Edge:** Filter with gibberish string returns 0 rows and exit 0 (not error).

## Out of Scope

- Changing FastAPI routes solely to ease CLI (prefer CLI adaptation).
- Web UI parity.
- Adding non–zero-dependency packages to `cli/` (violates Spec 148).
- Full interactive TUI for inventory (terminal listing suffices for this spec).

## Risks and Assumptions

- **OpenAPI drift:** Route count changes weekly; CI must pin or hash OpenAPI to avoid flaky mainline.
- **Auth variance:** Some routes need headers beyond `X-API-Key`; passthrough must support optional headers file.
- **Volume:** 215 endpoints is large; **passthrough (R4)** de-risks phased subcommand polish.
- **Assumption:** Baseline “39 of 215” is approximate; implementation must re-measure from `/openapi.json`.

## Known Gaps and Follow-up Tasks

- Optional `GET /api/meta/cli-coverage` for live dashboards.
- WebSocket endpoints may remain `excluded` until a `cc listen` extension defines semantics.
- Review exclusions each release in CHANGELOG.

## Evidence: Is This Idea Working, and Clearer Over Time?

| Evidence type | What it proves | Where |
|---------------|----------------|--------|
| **Coverage fraction** | Objective % of routes reachable | CI badge / `generate_cli_coverage.py --check` output |
| **Manifest diff** | What changed between releases | Git history of `cli/coverage.manifest.json` |
| **Live meta** | Human spot-check | `cc meta` / `cc meta endpoints` against production |
| **Independent verification** | Third parties can rerun the same commands | This spec’s Verification Scenarios + public API URL |

**Progressive clarity:** Each merge that touches CLI must update the manifest; the **diff** is the proof line. Optional publish to `docs/STATUS.md` table “CLI coverage: 100% (excl. N)”.

## See also

- [Spec 148 — Coherence CLI comprehensive](148-coherence-cli-comprehensive.md)
- `cli/README.md`
- `GET /api/meta/endpoints`
