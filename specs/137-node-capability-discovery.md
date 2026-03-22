# Spec 137: Node Capability Discovery

## Purpose

Federation nodes currently report empty `providers` and `capabilities` during registration (spec 132). This means the hub cannot route tasks to nodes that actually have the right tools and models available. This spec adds auto-detection of locally available AI executors (claude, cursor, openrouter API keys), system tools (docker, git, python, node), and hardware characteristics so that each node reports a truthful capability manifest to the hub at registration and heartbeat time. This enables the hub to make informed task-routing decisions and gives operators visibility into fleet capabilities.

## Requirements

- [ ] R1: A `CapabilityProbe` service auto-detects available AI executors by checking: `shutil.which("claude")`, `shutil.which("cursor")`, `shutil.which("agent")`, and presence of `OPENROUTER_API_KEY` env var.
- [ ] R2: `CapabilityProbe` detects available system tools by checking `shutil.which()` for: `docker`, `git`, `python3`, `node`, `npm`, `gh`.
- [ ] R3: `CapabilityProbe` reads hardware metadata: CPU count (`os.cpu_count()`), total memory (`psutil.virtual_memory().total` or `/proc/meminfo` fallback), and GPU presence (check for `nvidia-smi` or Apple Silicon via `platform.processor()`).
- [ ] R4: `CapabilityProbe` loads available models from `config/model_routing.json` (if present) and reports them grouped by executor.
- [ ] R5: `CapabilityProbe.probe()` returns a `NodeCapabilities` Pydantic model with fields: `executors`, `tools`, `hardware`, `models_by_executor`, `probed_at`.
- [ ] R6: `get_node_metadata()` in `node_identity_service.py` calls `CapabilityProbe.probe()` to populate `providers` and `capabilities` instead of returning empty values.
- [ ] R7: Node registration payload to hub includes the full capability manifest; hub stores it in `capabilities_json`.
- [ ] R8: Heartbeat optionally refreshes capabilities when `refresh_capabilities=true` query param is set.
- [ ] R9: Hub exposes `GET /api/federation/nodes/capabilities` returning aggregated fleet capability summary (which executors/tools are available across how many nodes).
- [ ] R10: Probe is non-blocking and completes within 5 seconds; individual tool checks that hang are skipped with a 2-second timeout per check.

## Research Inputs (Required)

- `2026-03-21` - [Spec 132: Federation Node Identity](specs/132-federation-node-identity.md) - defines node registration API and `capabilities_json` storage; this spec fills that field with real data.
- `2026-03-21` - [node_identity_service.py](api/app/services/node_identity_service.py) - current `get_node_metadata()` returns empty providers/capabilities.
- `2026-03-21` - [model_routing_loader.py](api/app/services/agent_routing/model_routing_loader.py) - config-driven model routing that informs which models a node can access.
- `2026-03-21` - [agent_runner.py](api/scripts/agent_runner.py) - existing `shutil.which()` patterns for executor detection.

## Task Card (Required)

```yaml
goal: Auto-detect node capabilities (executors, tools, hardware, models) and report them to hub during registration/heartbeat
files_allowed:
  - api/app/services/capability_probe.py
  - api/app/services/node_identity_service.py
  - api/app/models/federation.py
  - api/app/routers/federation.py
  - api/app/services/federation_service.py
  - api/tests/test_capability_probe.py
  - api/tests/test_node_capability_discovery.py
done_when:
  - CapabilityProbe.probe() returns detected executors, tools, hardware, and models
  - get_node_metadata() populates providers and capabilities from probe results
  - registration payload includes capability manifest stored in capabilities_json
  - GET /api/federation/nodes/capabilities returns fleet summary
  - all tests pass
commands:
  - cd api && pytest -q tests/test_capability_probe.py tests/test_node_capability_discovery.py
constraints:
  - do not modify existing federation endpoints beyond adding capability refresh
  - probe must complete within 5 seconds total
  - no new external dependencies beyond psutil (already in requirements)
```

## API Contract (if applicable)

### `GET /api/federation/nodes/capabilities`

Returns aggregated capability summary across all online nodes.

**Response 200**
```json
{
  "total_nodes": 3,
  "executors": {
    "claude": { "node_count": 2, "node_ids": ["a1b2c3d4e5f60789", "f9e8d7c6b5a40321"] },
    "cursor": { "node_count": 1, "node_ids": ["a1b2c3d4e5f60789"] },
    "openrouter": { "node_count": 3, "node_ids": ["a1b2c3d4e5f60789", "f9e8d7c6b5a40321", "1122334455667788"] }
  },
  "tools": {
    "docker": { "node_count": 2 },
    "git": { "node_count": 3 },
    "python3": { "node_count": 3 },
    "node": { "node_count": 1 }
  },
  "hardware_summary": {
    "total_cpus": 28,
    "total_memory_gb": 96.0,
    "gpu_capable_nodes": 1
  }
}
```

### `POST /api/federation/nodes/{node_id}/heartbeat?refresh_capabilities=true`

Existing heartbeat endpoint; when `refresh_capabilities=true`, request body may include updated capabilities.

**Request Body** (extended)
```json
{
  "status": "online",
  "capabilities": {
    "executors": ["claude", "openrouter"],
    "tools": ["docker", "git", "python3", "node", "npm", "gh"],
    "hardware": {
      "cpu_count": 10,
      "memory_total_gb": 32.0,
      "gpu_available": false,
      "gpu_type": null
    },
    "models_by_executor": {
      "claude": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
      "openrouter": ["openrouter/free"]
    },
    "probed_at": "2026-03-21T15:00:00Z"
  }
}
```

**Response 200**
```json
{
  "node_id": "a1b2c3d4e5f60789",
  "status": "online",
  "last_seen_at": "2026-03-21T15:05:00Z",
  "capabilities_refreshed": true
}
```

## Data Model (if applicable)

```yaml
NodeCapabilities:
  properties:
    executors: { type: list[string], description: "Available AI executors" }
    tools: { type: list[string], description: "Available system tools" }
    hardware:
      type: object
      properties:
        cpu_count: { type: int }
        memory_total_gb: { type: float }
        gpu_available: { type: bool }
        gpu_type: { type: string, nullable: true }
    models_by_executor: { type: dict[string, list[string]] }
    probed_at: { type: datetime }

FleetCapabilitySummary:
  properties:
    total_nodes: { type: int }
    executors: { type: dict[string, ExecutorSummary] }
    tools: { type: dict[string, ToolSummary] }
    hardware_summary:
      type: object
      properties:
        total_cpus: { type: int }
        total_memory_gb: { type: float }
        gpu_capable_nodes: { type: int }
```

## Files to Create/Modify

- `api/app/services/capability_probe.py` - **new**: `CapabilityProbe` class with `probe()` method for auto-detection.
- `api/app/services/node_identity_service.py` - **modify**: integrate `CapabilityProbe` into `get_node_metadata()`.
- `api/app/models/federation.py` - **modify**: add `NodeCapabilities`, `FleetCapabilitySummary` Pydantic models.
- `api/app/routers/federation.py` - **modify**: add `GET /api/federation/nodes/capabilities` endpoint; extend heartbeat with `refresh_capabilities` param.
- `api/app/services/federation_service.py` - **modify**: add fleet capability aggregation query.
- `api/tests/test_capability_probe.py` - **new**: unit tests for probe logic with mocked `shutil.which`.
- `api/tests/test_node_capability_discovery.py` - **new**: integration tests for registration with capabilities and fleet summary endpoint.

## Acceptance Tests

- `api/tests/test_capability_probe.py::test_probe_detects_available_executor`
- `api/tests/test_capability_probe.py::test_probe_detects_missing_executor`
- `api/tests/test_capability_probe.py::test_probe_detects_system_tools`
- `api/tests/test_capability_probe.py::test_probe_reads_hardware_metadata`
- `api/tests/test_capability_probe.py::test_probe_loads_models_from_config`
- `api/tests/test_capability_probe.py::test_probe_completes_within_timeout`
- `api/tests/test_node_capability_discovery.py::test_registration_includes_capabilities`
- `api/tests/test_node_capability_discovery.py::test_heartbeat_refreshes_capabilities`
- `api/tests/test_node_capability_discovery.py::test_fleet_capabilities_endpoint`

## Concurrency Behavior

- **Probe execution**: stateless, read-only detection; safe to run concurrently from multiple processes.
- **Registration writes**: upsert on `node_id` PK (inherited from spec 132); capability data is overwritten atomically in `capabilities_json`.
- **Fleet aggregation**: read-only query across `federation_nodes`; safe for concurrent access.

## Verification

```bash
python3 scripts/validate_spec_quality.py
cd api && pytest -q tests/test_capability_probe.py tests/test_node_capability_discovery.py
```

## Out of Scope

- Dynamic capability negotiation or capability-based task routing (follow-up spec).
- Benchmarking node performance or ranking nodes by speed.
- Continuous background monitoring of capability changes (polling/watch).
- Authentication or authorization for the fleet capabilities endpoint.
- Model availability verification (e.g., actually calling an API to confirm quota).

## Risks and Assumptions

- Risk: `shutil.which()` may return stale results if PATH changes after process start. Mitigation: probe is re-run on registration and on-demand via heartbeat refresh.
- Risk: `psutil` may not be installed in all environments. Mitigation: fall back to `/proc/meminfo` parsing on Linux, report `null` on failure.
- Risk: GPU detection is platform-specific and may miss non-NVIDIA GPUs. Mitigation: start with NVIDIA (`nvidia-smi`) and Apple Silicon (`platform.processor()`) only; document as known limitation.
- Assumption: `config/model_routing.json` accurately reflects which models a node can access via each executor.
- Assumption: nodes have permission to run `shutil.which()` checks without elevated privileges.

## Known Gaps and Follow-up Tasks

- Follow-up: capability-based task routing — hub selects node based on required executor/tool match.
- Follow-up: capability change notifications — detect when a tool is installed/removed between heartbeats.
- Follow-up: model availability verification — probe actual API endpoints to confirm quota/access.
- Follow-up: extend hardware detection to cover disk space and network bandwidth.

## Failure/Retry Reflection

- Failure mode: individual tool check hangs (e.g., `shutil.which` on network filesystem).
  - Blind spot: probe exceeds 5-second budget, delaying registration.
  - Next action: implement per-check 2-second timeout via `concurrent.futures.ThreadPoolExecutor`; skip timed-out checks and report them as unavailable.

- Failure mode: `psutil` import fails.
  - Blind spot: hardware section reports all nulls, reducing routing value.
  - Next action: catch `ImportError`, fall back to OS-specific methods, log warning.

- Failure mode: `model_routing.json` is missing or malformed.
  - Blind spot: `models_by_executor` is empty; hub cannot match model-requiring tasks.
  - Next action: return empty model list per executor; log warning at probe time.

## Decision Gates (if any)

- Confirm whether `psutil` is an acceptable dependency or if pure-stdlib fallbacks are preferred.
- Confirm whether fleet capabilities endpoint should require authentication in a follow-up or be open by default.
