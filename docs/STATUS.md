# Coherence Network — Status

> Implementation status for the active execution scope.

## Current State

### Phase Visibility

- Milestone Tag: **A** (Core Stability)
- Progress source: [`docs/SPEC-TRACKING.md`](SPEC-TRACKING.md)

| Area | Status |
|------|--------|
| API baseline and health endpoints | ✅ Complete |
| Graph indexing + project retrieval | ✅ Complete |
| Coherence endpoint support | ✅ Complete |
| Import stack support (lockfile + requirements) | ✅ Complete |
| Agent orchestration endpoints | ✅ Complete |
| Production deployment | ✅ Active (Hostinger public API + web contract passing) |
| Form-native front-door promotion | 🚧 In progress (BML route catalog + Go native probes; compatibility API remains bridge/upstream for tail routes) |
| Pipeline monitoring + attention workflow | 🚧 In progress |
| Full unattended effectiveness loop | 🚧 In progress |

## Public Deployments

| Service | Platform | URL | Status |
|---------|----------|-----|--------|
| API/front door | Hostinger VPS | https://api.coherencycoin.com | ✅ Active (`/api/health` 200; deployed SHA verified by public contract; public carrier still includes bridge routes while native front-door promotion proceeds) |
| Web | Hostinger VPS | https://coherencycoin.com | ✅ Active |
| Database | Hostinger Docker Compose | internal Postgres service | ✅ Active (config-file credentials; see [PRODUCTION-SUBSTRATE.md](PRODUCTION-SUBSTRATE.md)) |

### Deployment Health
- API health endpoint: ✅ Reachable at https://api.coherencycoin.com/api/health
- Web root: ✅ Reachable on current public domain
- Web API health page: ✅ Reachable
- CORS configuration: ✅ Allows https://coherencycoin.com
- Production DB: ✅ Hostinger internal Postgres is the live DB. Railway Postgres/Supabase pooler paths are historical or stale.

## Specs Implemented (Selected)

- 001–005 core API/pipeline foundations
- 007–014 platform baseline and safeguards
- 016–025 holdout/web/coherence/import capabilities
- 027–028 pipeline automation structure
- 030, 032, 034, 035, 037–044 hardening and status features

See [SPEC-COVERAGE.md](SPEC-COVERAGE.md) and [SPEC-TRACKING.md](SPEC-TRACKING.md) for full mapping.

## Active Priorities

1. Grow Form-native/BML handler coverage for observed web-used `/api` traffic.
2. Improve pipeline effectiveness and issue resolution loop.
3. Keep status/coverage artifacts in sync with shipped behavior.
4. Continue graph + coherence quality improvements through scoped specs.
5. Standardize estimate-to-measurement execution for new ideas (see [IDEA-MEASUREMENT-FLOW.md](IDEA-MEASUREMENT-FLOW.md)).
6. Execute non-software MVP marketplace track with ROI ordering (see [MVP-MARKETPLACE-STATUS.md](MVP-MARKETPLACE-STATUS.md)).

## Non-Software MVP Track

- Current highest-ROI item: 30-day OKRs and dashboard metrics (Objective 1).
- Status + continuation plan: [MVP-MARKETPLACE-STATUS.md](MVP-MARKETPLACE-STATUS.md).
- OKRs + operations docs:
  - [MVP-MARKETPLACE-STATUS.md](MVP-MARKETPLACE-STATUS.md) (`30-Day OKRs (v1)`)
  - [MVP-PARTNER-OUTREACH.md](MVP-PARTNER-OUTREACH.md)
  - [MVP-DASHBOARD-METRICS.md](MVP-DASHBOARD-METRICS.md)
- Next execution step: run first 10-contact outreach sprint and log week-1 dashboard baseline.

## Validation Snapshot

- API endpoint set is implemented, locally testable, and publicly verified on the current API/web domains; native route promotion is tracked separately so bridge traffic is not counted as high-grammar native.
- Test suite remains the release gate.
- Overnight pipeline remains the main autonomous execution path.

## Config Refactoring (ENV → Config Files)

**Goal:** Move all configuration from ENV var fallbacks to config files (`api/config/api.json`).

### Progress

| File | Status | Notes |
|------|--------|-------|
| `agent_service_store.py` | ✅ Done | persist, path, db_reload_ttl, output_max_chars |
| `agent_execution_codex_service.py` | ✅ Done | runtime_cost_per_second, external costs |
| `telegram_adapter.py` | ✅ Done | alert_window, max_per_window, bot_token, chat_ids |
| `metrics_service.py` | ✅ Done | file_path, use_db, max_rows |
| `runtime_event_store.py` | ✅ Done | database URL |
| `agent_execution_retry.py` | ✅ Done | disable_codex, auto_retry, model_override |
| `automation_usage_service.py` | 🚧 Partial | snapshots_path, use_db, max_snapshots, cache TTL |
| `openrouter_client.py` | ✅ Done | chat_url, headers, temperature |
| `inventory_service.py` | ✅ Done | cache_ttl, timing, tracking_repository |
| `idea_service.py` | ✅ Done | internal prefixes, sync settings |
| `agent_service_executor.py` | ✅ Done | policy_enabled, defaults |
| `runtime_service.py` | ✅ Done | database_url import, tool_success_streak |
| `release_gate_service.py` | ✅ Done | verification jobs, retry settings |
| `telegram_railway_service.py` | ✅ Done | API/Web base URLs, GitHub token |
| 9 router files | ✅ Done | Various config readings |
| `config_service.py` | ✅ Done | Core refactor |

### Test Impact

| Test File | Status | Notes |
|-----------|--------|-------|
| `test_agent_executor_policy.py` | ❌ 4 failing | Tests set ENV vars that code no longer reads |
| `test_agent_telegram_webhook.py` | ❌ 7 failing | Tests expect legacy hosted URLs, not config |
| `test_execute_endpoint_auto_retries_*` | ❌ 1 failing | Tests set ENV vars not in config |
| `test_026_pipeline_observability.py` | ❌ 1 error | JSONB/SQLite incompatibility (pre-existing) |

### Remaining ENV Usages (~230)

High priority:
- `automation_usage_service.py` (87+) - Provider API keys, OAuth tokens, provider URLs
- `agent_routing/executor_config.py` (13)
- `idea_service.py` (11)
- `friction_service.py` (5)
- `runtime/cache.py`, `runtime/paths.py` (8)

### Config Sections Added

- `inventory.*` - cache_ttl, timing, tracking_repository
- `runtime.*` - events_path, idea_map_path  
- `commit_evidence.*` - directory
- `route_evidence.*` - probe_directory
- `storage.value_lineage_path`
- `github.*` - token, api_token
- `agent_providers.openrouter_*` - chat_url, http_referer, temperature
