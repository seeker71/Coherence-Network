# Code Health And Memory Audit - 2026-04-25

Goal: increase flexibility, understanding, flow, and alignment by finding code tissue that should be refactored, composted, moved into config/DB, or linked into bidirectional memory.

## Current Sensing

Machine evidence:

- `cd api && python3 scripts/run_maintainability_audit.py --output /tmp/code_audit_maintainability.json`
- Severity: `high`
- Risk score: `790`
- Layer violations: `1`
- Large modules: `23`
- Very large modules: `9`
- Long functions: `88`
- Placeholders: `27`
- App env reads: `135` under `api/app`, with `83` in `api/app/services/automation_usage_service.py`
- Default local API pytest body after consolidation: `320` tests

## Highest Leverage Findings

### 1. Strong Spine: One Model Still Imports A Service

Finding: `api/app/models/evidence.py` imports `GpsCoordinate` from `app.services.story_protocol_bridge`.

Why it matters: models are supposed to shape data. Services should depend on models, not the other way around. This is the remaining reported layer inversion.

Tending path:

- Move `GpsCoordinate` into `api/app/models/evidence.py` or a small shared model module.
- Update `story_protocol_bridge` to import the model.
- Done when maintainability audit reports `layer_violation_count=0`.

### 2. Root: Config Is Still Leaking Through Env Reads

Finding: app code still has `135` direct env reads. The biggest cluster is automation usage (`83`). Other app env reads live in provider routing, database adapters, push keys, health, release gates, and runner registry.

Why it matters: configuration has multiple nervous systems. Some reads are legitimate secret edges, but many are app behavior, URLs, limits, provider models, cache policy, and fallback defaults that belong in `api/config/api.json` or a dedicated config pack.

Tending path:

- Create a provider/config access layer for automation usage so the service reads typed config, not env.
- Keep runner/CI secret edges explicit, but move behavior defaults into config.
- Done when `rg "os.getenv|os.environ.get|os.environ\\[" api/app` is below `40`, and every remaining read is documented as a runner/secret edge.

### 3. Throat: `main.py` Is Still A Router Knot

Finding: `api/app/main.py` imports and registers dozens of routers directly, with additional late imports near the bottom for renderers, memory, translations, evidence, settlement, and creator economy.

Why it matters: boot is doing discovery, policy, setup, route wiring, startup warming, and compatibility checks in one place. That makes public contract shape harder to see and harder to change.

Tending path:

- Add `api/app/route_manifest.py` with `RouterSpec(module, attr, prefix, tags)`.
- Make `main.py` iterate the manifest.
- Keep startup hooks separate from route registration.
- Done when `main.py` no longer imports individual router modules and route count can be inspected from one manifest.

### 4. Crown: Service Registry Exists But Is Not The Spine

Finding: `ServiceRegistry` registers five contract wrappers at startup (`idea`, `agent`, `runtime`, `inventory`, `federation`). Most services still depend on direct imports, and contracts are hand-maintained wrappers rather than the source of dependency truth.

Why it matters: the registry is useful metadata, but not yet circulation. It describes a small part of the body while real dependency flow bypasses it.

Tending path:

- Let services expose specs through colocated metadata, or register from a manifest.
- Add dependency validation against actual import edges and route ownership.
- Link registry records to specs, runtime events, and memory moments.
- Done when registry covers all major services and `/api/services` can answer "what owns this endpoint and why".

### 5. Solar Plexus: Execution Flow Is Still Too Concentrated

Finding: long execution functions remain: `pipeline_advance_service.maybe_advance` is `320` lines; `agent_tasks_routes.update_task` is `217` lines; `agent_service_crud.create_task` is `194` lines.

Why it matters: task phase transitions, retries, metrics, Telegram, graph updates, and pipeline advancement cross each other. This is where indecision and repeated process cost show up.

Tending path:

- Extract phase transition kernels from router/update paths.
- Keep routers as public contract only: validate input, call service, shape response.
- Move task completion side effects behind small event subscribers.
- Done when no agent/task transition function is over `120` lines and route handlers do not import graph/runtime/telegram directly.

### 6. Sacral: Inventory Extraction Started But The Old Organ Still Dominates

Finding: `api/app/services/inventory_service.py` is still `6146` lines. The extracted package `api/app/services/inventory/` exists and totals `1997` lines, but the facade still holds major logic, including the `686` line `build_spec_process_implementation_validation_flow`.

Why it matters: this is a half-migrated organ. Both shapes exist, so future work has to remember which one is alive.

Tending path:

- Move flow building into `inventory/flow.py`.
- Move process completeness into `inventory/process_completeness.py`.
- Move endpoint traceability into `inventory/endpoint_traceability.py`.
- Leave `inventory_service.py` as a compatibility shell only.
- Done when `inventory_service.py` is under `400` lines.

### 7. Third Eye: Automation Usage Has A Package But Most Tissue Stayed Behind

Finding: `api/app/services/automation_usage_service.py` is `6864` lines. The package `api/app/services/automation_usage/` only contains `constants.py` and `__init__.py` totaling `116` lines.

Why it matters: provider readiness, subscription windows, usage snapshots, runtime validation, installer healing, and summary generation are all in one file. This is where config leakage, hard-coded provider data, and long feedback loops concentrate.

Tending path:

- Split into `providers.py`, `readiness.py`, `usage_snapshots.py`, `validation.py`, `provider_heal.py`, `subscription_windows.py`, and `summary.py`.
- Move provider catalogs and URLs into config.
- Keep the old module as a thin facade during migration.
- Done when `automation_usage_service.py` is under `500` lines and env reads there are zero except secret checks through config/keystore helpers.

### 8. Release Duplicate Tissue: Constants Are Duplicated Across Old And New Organs

Finding: inventory constants exist in both `inventory_service.py` and `inventory/constants.py`. Automation provider config exists in both `automation_usage_service.py` and `automation_usage/constants.py`.

Why it matters: this makes the extracted packages look alive while callers may still use the old constants. Drift is likely.

Tending path:

- Update old facades to import constants from the extracted packages.
- Add tests that assert single-source constants are used.
- Done when duplicated constant bodies are gone.

### 9. Heart: Domain Catalogs Are Still Data In Code

Finding: large module-level catalogs include:

- `frequency_scoring.py::_MARKERS` with `209` entries
- `news_resonance_service.py::STOP_WORDS` with `143` entries
- `concept_auto_tagger.py::_STOPWORDS` with `67` entries
- `concept_resonance_kernel.py::CORE_CONCEPTS` and `CORE_RELATIONSHIPS`
- `mcp_tool_registry.py::TOOLS`
- `page_lineage_service.py::FALLBACK_PAGES`
- `identity_providers.py::PROVIDER_REGISTRY`

Why it matters: domain memory trapped in code cannot be inspected, edited, translated, versioned as content, or linked back to its originating idea/spec.

Tending path:

- Move stable catalogs to `api/config/*.json` when they are operational configuration.
- Move living/domain catalogs to DB-backed graph nodes when they are part of product knowledge.
- Add loaders with schema validation and provenance fields.
- Done when code contains algorithms, not editable domain lists.

### 10. Memory: `/api/memory` Is Not Yet Durable Or Bidirectional

Finding: `api/app/services/memory_service.py` stores moments, principles, and archived moments in in-process dictionaries. The file itself says graph-backed storage is a follow-up. Memory is keyed by `about`, but it is not attached to tasks, specs, code artifacts, runtime events, or commit evidence.

Why it matters: the organism cannot ask "what lives where, why, and how" from memory. The route can recall within a process, but deploy/restart releases it. Code has no durable reciprocal edge back to the memory that explains it.

Tending path:

- Persist memory moments as graph/runtime records with source links.
- Add bidirectional edges:
  - `memory_moment -> about_node`
  - `about_node -> memory_moment`
  - `memory_moment -> code_artifact`
  - `code_artifact -> memory_moment`
  - `memory_moment -> spec`
  - `spec -> memory_moment`
  - `memory_moment -> commit_evidence`
  - `commit_evidence -> memory_moment`
- Ingest this audit as a memory moment about `internal-health` and link it to touched files.
- Done when `/api/memory/recall?about=api/app/services/automation_usage_service.py` can explain what the file does, why it exists, what specs touch it, and what refactor path is active.

### 11. Docs Memory Has Stale Counts

Finding: `docs/STATUS.md`, `docs/SPEC-TRACKING.md`, and `docs/SPEC-COVERAGE.md` contain human-maintained counts and status claims that drift from live structure unless actively regenerated.

Why it matters: stale orientation creates process drag. Agents reread static memory that may contradict code and live endpoints.

Tending path:

- Convert count/status sections into generated snippets or links to live reports.
- Keep human docs for meaning and decisions, not duplicated counters.
- Done when status counts are generated by the same code that powers inventory/proprioception.

## First Walk

1. Remove the remaining model/service inversion.
   - File: `api/app/models/evidence.py`
   - Done: maintainability audit `layer_violation_count=0`

2. Make memory durable and bidirectional for code artifacts.
   - Files: `api/app/services/memory_service.py`, `api/app/models/memory.py`, `api/app/routers/memory.py`, graph/runtime persistence services
   - Done: memory survives restart and recall can traverse code/spec/evidence links both directions

3. Turn `main.py` router imports into a route manifest.
   - Files: `api/app/main.py`, new `api/app/route_manifest.py`
   - Done: route registration is data, not scattered imports

4. Finish inventory extraction.
   - Files: `api/app/services/inventory_service.py`, `api/app/services/inventory/*`
   - Done: old facade under `400` lines

5. Start automation usage extraction with config first.
   - Files: `api/app/services/automation_usage_service.py`, `api/app/services/automation_usage/*`, `api/config/api.json`
   - Done: provider config is loaded from config, and automation env reads are removed from behavior paths

6. Move domain catalogs out of code.
   - First candidates: frequency markers, stop words, core concept relationships, identity providers
   - Done: loaders validate config/DB content and expose provenance

## Better Understanding: Code Memory Shape

The target shape is not "more docs". It is a queryable organism memory:

```text
idea <-> spec <-> code_artifact <-> service_registry_entry <-> runtime_event
  ^          ^          ^                    ^                       ^
  |          |          |                    |                       |
  +----------+----------+---- memory_moment --+-----------------------+
```

Every code artifact should be able to answer:

- What am I?
- Why do I exist?
- Which idea/spec asked for me?
- Which runtime events prove I am alive?
- Which memory moments explain recent decisions?
- Which files are my neighbors?
- What needs to be tended next?

Every memory moment should be able to answer:

- Which code/spec/idea/evidence does this refer to?
- Was it acted on?
- Did runtime prove the action lived?
- Is the memory still supple, or has it become stale sediment?

## Health Metrics To Keep In View

- `layer_violation_count=0`
- `very_large_module_count<=4`
- `long_function_count<40`
- `api/app` direct env reads `<40`, with documented secret/runner exceptions only
- `main.py` route imports `0`
- service registry covers all major public services
- memory moments durable across restart
- code artifact recall can traverse both directions to ideas, specs, evidence, and runtime
