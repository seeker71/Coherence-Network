# Spec 109: Open Responses Interoperability Layer

## Summary

Introduce a **provider-agnostic normalization adapter** in the agent execution path so that task payloads
can flow through any supported provider (claude, codex, gemini, openrouter) without per-provider prompt
rewrites. Calls made through the adapter are recorded with a `request_schema: open_responses_v1` marker
so operators can audit which tasks ran through the normalized path and verify routing evidence.

---

## Purpose

Reduce provider lock-in and simplify model routing by introducing a normalized Open Responses interface
in the agent execution path, so task execution can move across providers without per-provider payload
rewrites.

**Problem today**: Each executor produces slightly different payload shapes for task instructions,
context, and output. Switching a running task from `claude` to `codex` requires a prompt rewrite at
the call site. This makes cross-provider A/B testing, load-balancing, and fallback chains brittle.

**Solution**: A thin `OpenResponsesAdapter` wraps the outbound task payload into a schema-versioned
envelope (`open_responses_v1`) and maps the response back to the internal `NormalizedResponseCall`
model. Existing provider-specific code is unchanged; the adapter is inserted *between* routing and
execution.

---

## Requirements

- [ ] **R1 — Adapter**: Add `OpenResponsesAdapter` in `api/app/services/` that can normalize any
      task execution payload (prompt, model, executor) into an `open_responses_v1`-shaped envelope
      and back to the internal response structure.
- [ ] **R2 — Multi-provider parity**: At least two providers (e.g., `claude` and `codex`) can
      execute a `spec`-type task through the same adapter without task-level prompt rewrites.
- [ ] **R3 — Route evidence persistence**: For each call made through the adapter, persist a
      `NormalizedResponseCall` record (task_id, provider, model, request_schema, output_text,
      timestamp_utc) via `provider_usage_service.py`.
- [ ] **R4 — Schema model**: `api/app/models/schemas.py` contains a `NormalizedResponseCall`
      Pydantic model with the fields defined in the Data Model section.
- [ ] **R5 — No regression**: All existing `test_agent.py` tests continue to pass unmodified.
- [ ] **R6 — Usage visibility**: `GET /api/agent/usage` response includes a
      `normalized_calls_count` field showing how many calls used `open_responses_v1`.

---

## Research Inputs

- `api/app/services/agent_service_executor.py` — executor selection, command templates, provider classification
- `api/app/services/agent_routing/model_routing_loader.py` — tier/model resolution
- `api/app/services/agent_routing/provider_classification.py` — provider/billing classification
- `api/app/services/agent_routing/` — full routing configuration surface
- `api/config/model_routing.json` — live routing config (providers: claude, codex, cursor, gemini, openrouter)
- Related specs: 002 (Agent Orchestration API), 169 (Smart Reap)

---

## Task Card

```yaml
goal: >
  Reduce provider lock-in and simplify model routing by introducing a normalized Open Responses
  interface in the agent execution path, so task execution can move across providers without
  per-provider payload rewrites.
files_allowed:
  - api/app/services/agent_service.py
  - api/app/services/open_responses_adapter.py   # new file
  - api/app/services/provider_usage_service.py
  - api/app/models/schemas.py
  - api/tests/test_open_responses.py              # new test file
done_when:
  - OpenResponsesAdapter class exists in api/app/services/open_responses_adapter.py
  - NormalizedResponseCall Pydantic model in api/app/models/schemas.py
  - provider_usage_service persists normalized call records with request_schema=open_responses_v1
  - Two providers (claude + codex) produce identical normalized envelope fields for same spec task
  - GET /api/agent/usage returns normalized_calls_count
  - All existing test_agent.py tests pass without modification
commands:
  - cd api && python -m pytest tests/test_open_responses.py -v
  - cd api && python -m pytest tests/test_agent.py -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
  - no changes to existing routing logic — adapter wraps, does not replace
```

---

## API Contract

### Existing endpoint enhanced: GET /api/agent/usage

No new endpoints are required for the initial rollout. The existing `/api/agent/usage` endpoint
gains one additional field.

**Response addition**:
```json
{
  "normalized_calls_count": 14,
  "...existing fields...": "..."
}
```

- `normalized_calls_count` (int): total calls where `request_schema == "open_responses_v1"`.
- Field is always present; defaults to `0` if no normalized calls have been made.
- If provider_usage_service is unavailable, field returns `0` (not 503).

### No new routes

The adapter is an **internal service component**, not an API endpoint. External callers interact
only with existing task and usage endpoints.

---

### Input Validation

- `task_id`: non-empty string, max 128 chars
- `provider`: non-empty string, one of `["claude", "codex", "gemini", "openrouter", "cursor"]`
- `model`: non-empty string, max 256 chars
- `request_schema`: must equal `"open_responses_v1"` for normalized calls
- `output_text`: string, may be empty (task pending), max 65536 chars
- Invalid/missing required fields on internal model construction → raise `ValueError` (not 422, as
  this is a service-layer model, not an HTTP request boundary)

---

## Data Model

### NormalizedResponseCall (Pydantic)

```python
class NormalizedResponseCall(BaseModel):
    task_id: str                      # References agent task
    provider: str                     # e.g. "claude", "codex"
    model: str                        # e.g. "claude-sonnet-4-6"
    request_schema: str               # Always "open_responses_v1"
    output_text: str                  # Raw provider output, may be empty
    timestamp_utc: datetime           # UTC ISO 8601 when call was recorded
    executor: Optional[str] = None    # e.g. "claude" (runner executor label)
    task_type: Optional[str] = None   # e.g. "spec", "impl"
```

### OpenResponsesEnvelope (internal, not persisted)

```python
@dataclass
class OpenResponsesEnvelope:
    schema_version: str = "open_responses_v1"
    task_id: str = ""
    model: str = ""
    provider: str = ""
    messages: list[dict] = field(default_factory=list)  # [{role, content}]
    metadata: dict = field(default_factory=dict)        # task_type, executor, etc.
```

The adapter converts the internal task prompt → `OpenResponsesEnvelope` → provider call →
provider response → `NormalizedResponseCall` for persistence.

---

## Files to Create/Modify

| File | Action | What changes |
|------|--------|--------------|
| `api/app/services/open_responses_adapter.py` | **Create** | `OpenResponsesAdapter` class with `normalize_request()` and `normalize_response()` methods |
| `api/app/models/schemas.py` | **Modify** | Add `NormalizedResponseCall` Pydantic model |
| `api/app/services/provider_usage_service.py` | **Modify** | Add `record_normalized_call(call: NormalizedResponseCall)` and `get_normalized_calls_count() -> int` |
| `api/app/services/agent_service.py` | **Modify** | Import and call adapter in execution path; expose count via usage summary |
| `api/tests/test_open_responses.py` | **Create** | Unit + integration tests per Verification Scenarios below |

---

## Verification Scenarios

The reviewer will run these scenarios against the test suite and, where indicated, against the
production API. Each scenario must pass or the implementation is incomplete.

---

### Scenario 1 — Adapter round-trip for claude provider

**Goal**: Verify that a task payload normalized through `OpenResponsesAdapter` produces the
expected envelope structure and that the response is correctly recorded.

**Setup**:
```python
from app.services.open_responses_adapter import OpenResponsesAdapter
adapter = OpenResponsesAdapter()
```

**Action**:
```python
envelope = adapter.normalize_request(
    task_id="test-task-001",
    provider="claude",
    model="claude-sonnet-4-6",
    executor="claude",
    task_type="spec",
    prompt="Write a spec for X"
)
```

**Expected result**:
```python
assert envelope.schema_version == "open_responses_v1"
assert envelope.task_id == "test-task-001"
assert envelope.provider == "claude"
assert envelope.model == "claude-sonnet-4-6"
assert len(envelope.messages) >= 1
assert envelope.messages[0]["role"] == "user"
assert "Write a spec for X" in envelope.messages[0]["content"]
assert envelope.metadata["task_type"] == "spec"
```

**Edge case — missing task_id**:
```python
with pytest.raises(ValueError, match="task_id"):
    adapter.normalize_request(task_id="", provider="claude", model="claude-sonnet-4-6",
                              executor="claude", task_type="spec", prompt="p")
```

---

### Scenario 2 — Two-provider parity: claude and codex produce identical envelope schema

**Goal**: Confirm that `claude` and `codex` tasks normalized through the adapter produce
structurally identical envelopes (same schema_version, same field set, same message format),
demonstrating provider-agnostic normalization.

**Setup**: Clean adapter instance; no running API needed.

**Action**:
```python
adapter = OpenResponsesAdapter()
env_claude = adapter.normalize_request(
    task_id="t1", provider="claude", model="claude-sonnet-4-6",
    executor="claude", task_type="spec", prompt="Write a spec"
)
env_codex = adapter.normalize_request(
    task_id="t2", provider="codex", model="gpt-5.3-codex-spark",
    executor="codex", task_type="spec", prompt="Write a spec"
)
```

**Expected result**:
```python
assert env_claude.schema_version == env_codex.schema_version == "open_responses_v1"
assert set(vars(env_claude).keys()) == set(vars(env_codex).keys())
assert env_claude.messages[0]["role"] == env_codex.messages[0]["role"] == "user"
assert env_claude.messages[0]["content"] == env_codex.messages[0]["content"]
# Provider field differs (by design):
assert env_claude.provider == "claude"
assert env_codex.provider == "codex"
```

---

### Scenario 3 — Normalized call persistence and usage count

**Goal**: Verify that `record_normalized_call()` persists a `NormalizedResponseCall` and that
`get_normalized_calls_count()` reflects the cumulative total.

**Setup**:
```python
from app.services.provider_usage_service import record_normalized_call, get_normalized_calls_count
from app.models.schemas import NormalizedResponseCall
from datetime import datetime, timezone

initial_count = get_normalized_calls_count()
```

**Action**:
```python
call = NormalizedResponseCall(
    task_id="task-persist-001",
    provider="claude",
    model="claude-sonnet-4-6",
    request_schema="open_responses_v1",
    output_text="# Spec output",
    timestamp_utc=datetime.now(timezone.utc),
    executor="claude",
    task_type="spec"
)
record_normalized_call(call)
new_count = get_normalized_calls_count()
```

**Expected result**:
```python
assert new_count == initial_count + 1
```

**Full create-read cycle** (also verifies the /usage endpoint):
```bash
API=https://api.coherencycoin.com
# Baseline count
BEFORE=$(curl -s $API/api/agent/usage | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('normalized_calls_count', 0))")
# Submit a task that goes through the normalized path
curl -s -X POST $API/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type":"spec","prompt":"test open responses","executor":"claude"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])"
# After the task is processed, count must be BEFORE+1
AFTER=$(curl -s $API/api/agent/usage | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('normalized_calls_count', 0))")
python3 -c "assert $AFTER >= $BEFORE, 'count did not increment'"
```

**Edge case — duplicate task_id**:
Calling `record_normalized_call()` twice with the same `task_id` must NOT raise; both records are
stored (last-write-wins semantics). Count increments by 2.

---

### Scenario 4 — GET /api/agent/usage returns normalized_calls_count

**Goal**: Confirm the API endpoint exposes the new field.

**Setup**: Production API running at `https://api.coherencycoin.com`

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/agent/usage
```

**Expected result**:
- HTTP 200
- Response body is JSON containing `"normalized_calls_count"` key
- Value is a non-negative integer
```bash
curl -s https://api.coherencycoin.com/api/agent/usage \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'normalized_calls_count' in d, 'missing field'; assert isinstance(d['normalized_calls_count'], int), 'wrong type'; print('OK', d['normalized_calls_count'])"
```

**Edge case — provider_usage_service unavailable**:
If the internal service raises, the endpoint must still return HTTP 200 with
`"normalized_calls_count": 0` (not 503, not missing field).

---

### Scenario 5 — No regression: existing agent tests pass

**Goal**: Verify the adapter integration does not break any pre-existing agent test.

**Setup**: Fresh test run in the `api/` directory.

**Action**:
```bash
cd api && python -m pytest tests/test_agent.py -q --tb=short
```

**Expected result**:
```
All N tests pass (0 failures, 0 errors)
```
The test count must be ≥ the count before the feature was introduced (no tests deleted).

**Edge case — adapter import error**:
If `open_responses_adapter` fails to import (e.g., missing dependency), agent_service must still
function and existing tests must still pass. The adapter should be imported with a try/except guard
in agent_service; if unavailable, calls proceed without normalization and `normalized_calls_count`
stays 0.

---

## Acceptance Tests (CI commands)

```bash
# Unit tests for new adapter and model
cd api && python -m pytest tests/test_open_responses.py -v

# Regression: existing agent tests
cd api && python -m pytest tests/test_agent.py -q

# Combined
cd api && python -m pytest tests/test_open_responses.py tests/test_agent.py -v --tb=short
```

---

## Concurrency Behavior

- **Record writes** (`record_normalized_call`): append-only; no read-modify-write; safe under concurrent load.
- **Count reads** (`get_normalized_calls_count`): eventually consistent; may lag by one record under
  extreme concurrency. Acceptable for MVP.
- **Adapter** (`normalize_request`, `normalize_response`): pure functions with no shared state;
  fully thread-safe.

---

## Failure and Retry Behavior

- **Invalid envelope fields**: `normalize_request()` raises `ValueError` with field name in message.
- **Provider unavailable**: adapter raises `ProviderUnavailableError`; caller is responsible for retry.
- **Persistence failure**: `record_normalized_call()` logs warning and swallows exception to avoid
  blocking task execution. Route evidence is best-effort.
- **Schema version mismatch**: if `request_schema != "open_responses_v1"`, `normalize_response()`
  raises `ValueError("unknown schema version")`.

---

## Out of Scope

- Full migration of every legacy provider integration in one pass (phased rollout).
- Changes to UI rendering for task output display.
- Tool-call schema parity across providers (tracked as follow-up
  `task_open_responses_tool_schema_parity_001`).
- Streaming responses through the normalized adapter.
- Authentication/authorization changes.

---

## Risks and Assumptions

| # | Risk | Likelihood | Mitigation |
|---|------|-----------|------------|
| R1 | Provider-specific capabilities (tool calls, structured output) don't map 1:1 | Medium | Additive `provider_extensions` field in envelope metadata; unmapped features pass through unchanged |
| R2 | Existing agent execution contracts break when adapter is inserted | Low | Adapter wraps, never replaces; guarded import with fallback |
| R3 | `provider_usage_service` write failures block task execution | Low | Exception swallowed; evidence is best-effort, not required for correctness |
| R4 | `normalized_calls_count` drift between in-memory and persisted store | Medium | Acceptable for MVP; can be reconciled in follow-up |

**Assumptions**:
- Current `agent_service.py` has a clear injection point before provider call where adapter can be inserted.
- `provider_usage_service.py` has an extensible record-write interface (not read-only).
- `claude` and `codex` both accept `messages: [{role, content}]` as their primary prompt format (confirmed by `executor_config.py`).

---

## Known Gaps and Follow-up Tasks

- `task_open_responses_tool_schema_parity_001` — normalize tool-call schema parity across providers.
- `task_open_responses_streaming_001` — extend adapter to handle streaming responses.
- `task_open_responses_ui_evidence_001` — surface `normalized_calls_count` on the web dashboard.

---

## Decision Gates

- **Gate 1** (before impl): Confirm whether normalization applies to all task types (`spec`, `test`,
  `impl`, `review`, `heal`) or only `spec` for the initial rollout. Recommendation: all task types,
  guarded by `OPEN_RESPONSES_ENABLED=true` env var (default false for safety).
- **Gate 2** (before merge): Confirm that appending `normalized_calls_count` to `/api/agent/usage`
  response is non-breaking for all existing consumers (check web frontend usage of this endpoint).

---

## Verification (spec quality)

```bash
python3 scripts/validate_spec_quality.py --file specs/109-open-responses-interoperability-layer.md
```
