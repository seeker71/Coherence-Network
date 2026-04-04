---
idea_id: pipeline-reliability
status: done
source:
  - file: api/app/services/auto_heal_service.py
    symbols: [graduated severity responses]
  - file: api/app/services/failure_taxonomy_service.py
    symbols: [failure patterns and classification]
  - file: api/app/services/smart_reaper_service.py
    symbols: [incident detection]
requirements:
  - "R1: Coherence monitor -- background service that continuously checks: (a) treasury coherence (reserve ratio >= 1.0), (b)"
  - "R2: Graduated response based on coherence score:"
  - "R3: Key compromise protocol -- any signer can trigger emergency freeze via `POST /api/incidents/freeze` (single-signer a"
  - "R4: Oracle circuit breaker -- if exchange rate oracle returns a price differing > 20% from the 1-hour moving average: (a"
  - "R5: Self-healing audit -- if hash chain gap detected: (a) identify break point (last verified entry to first divergent e"
  - "R6: No silent failures -- every incident, degradation, and recovery is logged in the audit ledger and visible at the pub"
  - "R7: `GET /api/health/coherence` returns full coherence dashboard with all four subsystem scores and overall status."
  - "R8: `GET /api/incidents` returns list of all incidents (open and resolved) with timestamps, severity, actions taken, and"
  - "R9: `POST /api/incidents/freeze` triggers emergency treasury freeze (single-signer authorization)."
  - "R10: `POST /api/incidents/unfreeze` lifts treasury freeze (requires full quorum authorization)."
done_when:
  - "GET /api/health/coherence returns four subsystem scores and overall status"
  - "Graduated response triggers correct action at each threshold (0.95, 0.90, hash break)"
  - "POST /api/incidents/freeze halts treasury with single-signer auth"
  - "POST /api/incidents/unfreeze requires full quorum and coherence score == 1.0"
  - "Oracle circuit breaker freezes rate on >20% deviation and requires 3 clean reads to resume"
  - "Self-healing appends \"healed\" or \"unresolved\" entries on hash chain gaps"
  - "GET /api/incidents returns complete incident history"
  - "All incidents are logged to audit ledger"
  - "All tests pass in test_incident_response.py"
test: "python3 -m pytest api/tests/test_cc_economics.py -x -q"
constraints:
  - "No incident may be suppressed or delayed in public disclosure"
  - "Emergency freeze is single-signer; unfreeze requires full quorum"
  - "Oracle circuit breaker requires exactly 3 consecutive clean reads to resume"
  - "Hash chain gaps with failed reconstruction must remain visible permanently"
---

> **Parent idea**: [pipeline-reliability](../ideas/pipeline-reliability.md)
> **Source**: [`api/app/services/auto_heal_service.py`](../api/app/services/auto_heal_service.py) | [`api/app/services/failure_taxonomy_service.py`](../api/app/services/failure_taxonomy_service.py) | [`api/app/services/smart_reaper_service.py`](../api/app/services/smart_reaper_service.py)

# Spec 125: Incident Response and Self-Healing

**Idea**: `coherence-incident-response` (sub-idea of `coherence-credit-system`)
**Depends on**: Spec 124 (CC economics), Spec 119 (CC internal currency), Spec 118 (unified SQLite store)
**Integrates with**:
- `cc_treasury_service` (treasury freeze/unfreeze, coherence score)
- `cc_oracle_service` (exchange rate circuit breaker)
- `coherence_credit_service` (CC operation pause/resume)
- `unified_db` (audit ledger, incident log persistence)
- `value_lineage_service` (hash chain integrity verification)
- `federation_service` (cross-instance consistency checks)

## Status: Draft

## Purpose

A financial system that hides its problems is a system waiting to betray its users. This spec defines how the Coherence Network detects degradation, responds with graduated severity, recovers through auditable self-healing, and discloses every incident publicly. The coherence monitor is not a dashboard -- it is the trust contract. When treasury backing degrades, when an audit chain breaks, when an oracle returns suspect data, the system responds through transparency and verifiable recovery, not through silence. Every incident, every degradation, every recovery is logged and visible at the public API.

## Requirements

- [ ] R1: Coherence monitor -- background service that continuously checks: (a) treasury coherence (reserve ratio >= 1.0), (b) audit chain integrity (hash verification of ledger entries), (c) idea value coherence (evidence backing for staked ideas), (d) federation coherence (cross-instance consistency). Published at `GET /api/health/coherence`.
- [ ] R2: Graduated response based on coherence score:
  - Score 0.95-1.0: Warning logged, alert emitted, operations continue normally.
  - Score 0.90-0.95: CC minting paused, existing operations continue, admin alert sent.
  - Score < 0.90: All CC operations paused, system enters read-only mode, public disclosure at `/api/health/coherence` with full details.
  - Hash chain broken: Immediate halt, all CC frozen, public incident disclosure.
- [ ] R3: Key compromise protocol -- any signer can trigger emergency freeze via `POST /api/incidents/freeze` (single-signer action). Treasury enters lockdown (no outbound transactions). Remaining signers rotate to new multisig. Full audit compares on-chain treasury balance to audit ledger CC supply. Unfreeze only after coherence score verified at 1.0 via `POST /api/incidents/unfreeze` (requires full quorum).
- [ ] R4: Oracle circuit breaker -- if exchange rate oracle returns a price differing > 20% from the 1-hour moving average: (a) freeze exchange rate at last known-good value, (b) alert admins, (c) retry with exponential backoff, (d) resume normal operation only after 3 consecutive reads within 5% of each other.
- [ ] R5: Self-healing audit -- if hash chain gap detected: (a) identify break point (last verified entry to first divergent entry), (b) publish gap details publicly, (c) reconstruct from redundant sources (database records, on-chain data), (d) if reconstruction succeeds append a "healed" entry documenting the gap and fix, (e) if reconstruction fails the gap remains visible forever with an "unresolved" marker.
- [ ] R6: No silent failures -- every incident, degradation, and recovery is logged in the audit ledger and visible at the public API. The system never suppresses or delays disclosure of a problem.
- [ ] R7: `GET /api/health/coherence` returns full coherence dashboard with all four subsystem scores and overall status.
- [ ] R8: `GET /api/incidents` returns list of all incidents (open and resolved) with timestamps, severity, actions taken, and resolution status.
- [ ] R9: `POST /api/incidents/freeze` triggers emergency treasury freeze (single-signer authorization).
- [ ] R10: `POST /api/incidents/unfreeze` lifts treasury freeze (requires full quorum authorization).

## Research Inputs (Required)

- `2026-03-20` - Spec 124 CC economics and value coherence - defines treasury backing invariant and coherence score that this spec monitors and enforces
- `2026-03-19` - Spec 119 CC internal currency - provides CC operation control (pause/resume) that graduated response invokes
- `2026-03-20` - CoinGecko API rate limit documentation (https://docs.coingecko.com/v3.0.1/reference/introduction) - informs oracle circuit breaker retry timing
- `2026-03-18` - NIST SP 800-61r3 Incident Handling Guide (https://csrc.nist.gov/pubs/sp/800/61/r3/final) - graduated response and disclosure practices

## Task Card (Required)

```yaml
goal: Implement coherence monitoring, graduated incident response, oracle circuit breaker, and self-healing audit
files_allowed:
  - api/app/routers/incidents.py
  - api/app/routers/health.py
  - api/app/services/coherence_monitor_service.py
  - api/app/services/incident_response_service.py
  - api/app/services/oracle_circuit_breaker_service.py
  - api/app/services/audit_self_healing_service.py
  - api/app/models/incidents.py
  - api/app/services/unified_models.py
  - api/tests/test_incident_response.py
  - specs/125-incident-response-and-self-healing.md
done_when:
  - GET /api/health/coherence returns four subsystem scores and overall status
  - Graduated response triggers correct action at each threshold (0.95, 0.90, hash break)
  - POST /api/incidents/freeze halts treasury with single-signer auth
  - POST /api/incidents/unfreeze requires full quorum and coherence score == 1.0
  - Oracle circuit breaker freezes rate on >20% deviation and requires 3 clean reads to resume
  - Self-healing appends "healed" or "unresolved" entries on hash chain gaps
  - GET /api/incidents returns complete incident history
  - All incidents are logged to audit ledger
  - All tests pass in test_incident_response.py
commands:
  - python3 -m pytest api/tests/test_incident_response.py -x -v
  - python3 -m pytest api/tests/test_cc_economics.py -x -q
constraints:
  - No incident may be suppressed or delayed in public disclosure
  - Emergency freeze is single-signer; unfreeze requires full quorum
  - Oracle circuit breaker requires exactly 3 consecutive clean reads to resume
  - Hash chain gaps with failed reconstruction must remain visible permanently
```

## API Contract

### `GET /api/health/coherence`

**Request**: No parameters.

**Response 200**
```json
{
  "overall_score": 0.97,
  "overall_status": "warning",
  "subsystems": {
    "treasury": {
      "score": 1.02,
      "status": "healthy",
      "detail": "Reserve ratio 1.02, all CC backed"
    },
    "audit_chain": {
      "score": 1.0,
      "status": "healthy",
      "detail": "Hash chain verified, 14523 entries, 0 gaps"
    },
    "idea_value": {
      "score": 0.91,
      "status": "degraded",
      "detail": "3 staked ideas lack evidence backing"
    },
    "federation": {
      "score": 0.95,
      "status": "warning",
      "detail": "1 peer instance 12min behind sync"
    }
  },
  "active_incidents": 1,
  "cc_operations_status": "normal",
  "checked_at": "2026-03-20T12:00:00Z"
}
```

### `GET /api/incidents`

**Request**
- `status`: string (query, optional) -- filter by "open", "resolved", or "all" (default: "all")
- `limit`: int (query, optional, default: 50)
- `offset`: int (query, optional, default: 0)

**Response 200**
```json
{
  "incidents": [
    {
      "incident_id": "string",
      "severity": "critical",
      "type": "hash_chain_break",
      "summary": "Audit chain gap detected at entry 14201",
      "detected_at": "2026-03-20T11:45:00Z",
      "resolved_at": "2026-03-20T11:52:00Z",
      "status": "resolved",
      "actions_taken": [
        "CC operations halted",
        "Gap published at /api/health/coherence",
        "Reconstructed from database records",
        "Healed entry appended"
      ],
      "coherence_score_at_detection": 0.0,
      "coherence_score_at_resolution": 1.0
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `POST /api/incidents/freeze`

**Request**
```json
{
  "signer_id": "string",
  "reason": "Suspected key compromise on signer-3",
  "signature": "string"
}
```

**Response 201**
```json
{
  "incident_id": "string",
  "status": "frozen",
  "frozen_at": "2026-03-20T12:00:00Z",
  "frozen_by": "string",
  "reason": "Suspected key compromise on signer-3",
  "unfreeze_requires": "full_quorum"
}
```

**Response 403** (invalid signer)
```json
{ "detail": "Invalid signer credentials" }
```

**Response 409** (already frozen)
```json
{ "detail": "Treasury is already frozen" }
```

### `POST /api/incidents/unfreeze`

**Request**
```json
{
  "signer_ids": ["signer-1", "signer-2", "signer-4"],
  "signatures": ["string", "string", "string"],
  "audit_confirmation": {
    "on_chain_balance_usd": 145000.0,
    "ledger_cc_outstanding": 138000.0,
    "coherence_score": 1.05
  }
}
```

**Response 200**
```json
{
  "incident_id": "string",
  "status": "resolved",
  "unfrozen_at": "2026-03-20T14:00:00Z",
  "quorum_signers": ["signer-1", "signer-2", "signer-4"],
  "coherence_score_verified": 1.05
}
```

**Response 400** (coherence score < 1.0)
```json
{ "detail": "Cannot unfreeze: coherence score 0.98 is below 1.0" }
```

**Response 403** (insufficient quorum)
```json
{ "detail": "Unfreeze requires full quorum. Received 2 of 3 required signatures." }
```

## Data Model

```yaml
CoherenceHealth:
  properties:
    overall_score: { type: float, ge: 0 }
    overall_status: { type: string, enum: [healthy, warning, degraded, critical, halted] }
    subsystems: { type: "dict[str, SubsystemHealth]" }
    active_incidents: { type: int, ge: 0 }
    cc_operations_status: { type: string, enum: [normal, minting_paused, read_only, frozen] }
    checked_at: { type: datetime }

SubsystemHealth:
  properties:
    score: { type: float, ge: 0 }
    status: { type: string, enum: [healthy, warning, degraded, critical] }
    detail: { type: string }

Incident:
  properties:
    incident_id: { type: string, min_length: 1 }
    severity: { type: string, enum: [info, warning, critical, emergency] }
    type: { type: string, enum: [treasury_degradation, hash_chain_break, oracle_anomaly, federation_desync, key_compromise, coherence_violation] }
    summary: { type: string }
    detected_at: { type: datetime }
    resolved_at: { type: "datetime | None", default: null }
    status: { type: string, enum: [open, mitigating, resolved] }
    actions_taken: { type: "list[str]" }
    coherence_score_at_detection: { type: float }
    coherence_score_at_resolution: { type: "float | None", default: null }

FreezeRequest:
  properties:
    signer_id: { type: string, min_length: 1 }
    reason: { type: string, min_length: 1 }
    signature: { type: string, min_length: 1 }

UnfreezeRequest:
  properties:
    signer_ids: { type: "list[str]", min_items: 1 }
    signatures: { type: "list[str]", min_items: 1 }
    audit_confirmation: { type: AuditConfirmation }

AuditConfirmation:
  properties:
    on_chain_balance_usd: { type: float, ge: 0 }
    ledger_cc_outstanding: { type: float, ge: 0 }
    coherence_score: { type: float, ge: 1.0 }

OracleCircuitBreakerState:
  properties:
    status: { type: string, enum: [normal, tripped, recovering] }
    frozen_rate: { type: "float | None" }
    frozen_at: { type: "datetime | None" }
    deviation_pct: { type: "float | None" }
    consecutive_clean_reads: { type: int, ge: 0, default: 0 }
    required_clean_reads: { type: int, default: 3 }

AuditHealingEntry:
  properties:
    entry_id: { type: string }
    type: { type: string, enum: [healed, unresolved] }
    gap_start_entry: { type: string }
    gap_end_entry: { type: string }
    reconstructed_from: { type: "list[str]" }
    detail: { type: string }
    created_at: { type: datetime }

IncidentRow (SQLAlchemy):
  table: cc_incidents
  columns:
    incident_id: { type: string, primary_key: true }
    severity: { type: string }
    type: { type: string }
    summary: { type: string }
    detected_at: { type: datetime }
    resolved_at: { type: "datetime | None" }
    status: { type: string }
    actions_taken_json: { type: string }
    coherence_score_at_detection: { type: float }
    coherence_score_at_resolution: { type: "float | None" }

OracleReadingRow (SQLAlchemy):
  table: cc_oracle_readings
  columns:
    id: { type: string, primary_key: true }
    rate: { type: float }
    source: { type: string }
    moving_avg_1h: { type: float }
    deviation_pct: { type: float }
    accepted: { type: bool }
    created_at: { type: datetime }
```

## Files to Create/Modify

- `api/app/models/incidents.py` - Pydantic models: CoherenceHealth, SubsystemHealth, Incident, FreezeRequest, UnfreezeRequest, AuditConfirmation, OracleCircuitBreakerState, AuditHealingEntry
- `api/app/services/coherence_monitor_service.py` - Background monitor: treasury check, audit chain verification, idea value check, federation check, composite score computation
- `api/app/services/incident_response_service.py` - Graduated response logic, freeze/unfreeze orchestration, incident CRUD, audit ledger logging
- `api/app/services/oracle_circuit_breaker_service.py` - Rate deviation detection, circuit trip/recovery, moving average computation, consecutive clean read tracking
- `api/app/services/audit_self_healing_service.py` - Hash chain gap detection, redundant source reconstruction, healed/unresolved entry creation
- `api/app/routers/incidents.py` - FastAPI router: POST /api/incidents/freeze, POST /api/incidents/unfreeze, GET /api/incidents
- `api/app/routers/health.py` - Modify existing health router: add GET /api/health/coherence endpoint
- `api/app/services/unified_models.py` - Add IncidentRow, OracleReadingRow SQLAlchemy models
- `api/tests/test_incident_response.py` - Tests covering all requirements

## Acceptance Tests

- `api/tests/test_incident_response.py::test_coherence_health_returns_four_subsystems`
- `api/tests/test_incident_response.py::test_coherence_health_overall_score_computation`
- `api/tests/test_incident_response.py::test_graduated_response_warning_at_095`
- `api/tests/test_incident_response.py::test_graduated_response_minting_paused_at_090`
- `api/tests/test_incident_response.py::test_graduated_response_readonly_below_090`
- `api/tests/test_incident_response.py::test_graduated_response_halt_on_hash_break`
- `api/tests/test_incident_response.py::test_freeze_single_signer_succeeds`
- `api/tests/test_incident_response.py::test_freeze_invalid_signer_rejected`
- `api/tests/test_incident_response.py::test_freeze_already_frozen_409`
- `api/tests/test_incident_response.py::test_unfreeze_requires_full_quorum`
- `api/tests/test_incident_response.py::test_unfreeze_rejected_below_coherence_1`
- `api/tests/test_incident_response.py::test_unfreeze_insufficient_quorum_403`
- `api/tests/test_incident_response.py::test_oracle_circuit_breaker_trips_on_20pct_deviation`
- `api/tests/test_incident_response.py::test_oracle_circuit_breaker_freezes_rate`
- `api/tests/test_incident_response.py::test_oracle_circuit_breaker_requires_3_clean_reads`
- `api/tests/test_incident_response.py::test_oracle_circuit_breaker_rejects_partial_recovery`
- `api/tests/test_incident_response.py::test_self_healing_detects_hash_gap`
- `api/tests/test_incident_response.py::test_self_healing_appends_healed_entry`
- `api/tests/test_incident_response.py::test_self_healing_marks_unresolved_on_failure`
- `api/tests/test_incident_response.py::test_self_healing_gap_permanently_visible`
- `api/tests/test_incident_response.py::test_all_incidents_logged_to_audit_ledger`
- `api/tests/test_incident_response.py::test_incidents_list_filters_by_status`
- `api/tests/test_incident_response.py::test_no_silent_failure_all_events_public`

## Concurrency Behavior

- **Read operations** (coherence health, incident list): Safe for concurrent access; no locking required.
- **Freeze operation**: Uses database-level advisory lock to prevent race between concurrent freeze requests. First writer wins; second gets 409.
- **Unfreeze operation**: Signature collection may span multiple requests. Final unfreeze is atomic: verify quorum + coherence score + commit in single transaction.
- **Coherence monitor**: Runs as a single background task with configurable interval (default 30 seconds). Does not block API requests. Writes results to a shared state object read by the health endpoint.
- **Oracle circuit breaker**: State transitions (normal -> tripped -> recovering -> normal) are serialized via database row lock on circuit breaker state.

## Verification

```bash
python3 -m pytest api/tests/test_incident_response.py -x -v
python3 -m pytest api/tests/test_cc_economics.py -x -q
python3 scripts/validate_spec_quality.py specs/125-incident-response-and-self-healing.md
```

## Out of Scope

- Actual multisig wallet integration (signature verification is stubbed; real wallet integration is a separate spec)
- Email/SMS/PagerDuty alert delivery (alerts are logged and available via API; external notification channels are separate)
- Automated key rotation mechanics (protocol is defined; cryptographic implementation is separate)
- Federation coherence monitor implementation details (checks federation_service sync status; deep federation healing is separate)
- UI for incident dashboard (API-first; web spec separate)

## Risks and Assumptions

- **Risk**: Background monitor could consume excessive resources on large audit chains. Mitigation: hash chain verification is incremental (only verifies entries since last check), not full-chain on every cycle.
- **Risk**: Single-signer freeze could be abused by a malicious signer. Mitigation: freeze is a safety action (stops outbound only); it cannot move funds. Unfreeze requires full quorum, so a single bad actor can halt but not steal.
- **Assumption**: Quorum size is configurable and defaults to N-of-N (all signers). This is the most conservative default. Can be relaxed to (N-1)-of-N via config.
- **Assumption**: Oracle moving average is computed from readings stored in `cc_oracle_readings` table. Requires at least 12 readings (1 per 5 min for 1 hour) before circuit breaker is active. Before that, all readings are accepted.
- **Risk**: Self-healing reconstruction could produce incorrect data if redundant sources disagree. Mitigation: reconstruction requires all redundant sources to agree. Any disagreement results in "unresolved" marker, not a best-guess heal.

## Known Gaps and Follow-up Tasks

- Follow-up task: Real multisig wallet integration for freeze/unfreeze signature verification
- Follow-up task: External alerting channels (email, Telegram, PagerDuty) for incident notifications
- Follow-up task: Federation coherence deep healing (beyond sync status check)
- Follow-up task: Coherence monitor interval tuning based on production load profiling
- Follow-up task: Incident severity auto-escalation (warning -> critical if unresolved for > 1 hour)
- Follow-up task: Historical coherence score time series for trend analysis

## Failure and Retry Behavior

- **Monitor check failure**: If any subsystem check throws an exception, that subsystem scores 0.0 and an incident is created. The monitor does not crash -- it continues checking other subsystems.
- **Freeze endpoint failure**: If database write fails, return 503. Signer should retry. Treasury remains in its pre-freeze state (safe default: not frozen is less dangerous than a failed freeze that reports success).
- **Unfreeze endpoint failure**: If any step fails (quorum verification, coherence check, DB commit), return 503. Treasury remains frozen (safe default: frozen is the conservative state).
- **Oracle circuit breaker retry**: Exponential backoff starting at 30 seconds, doubling to max 5 minutes. After 1 hour of continuous failure, escalate to critical incident.
- **Self-healing reconstruction failure**: No retry. Mark gap as "unresolved" immediately. Manual intervention required. The system never guesses.

## Decision Gates

- Quorum configuration: N-of-N (all signers) vs (N-1)-of-N for unfreeze. Current spec defaults to all signers. Needs product decision if relaxation is desired.
- Coherence monitor interval: 30 seconds default. May need tuning for production. Should this be admin-configurable at runtime?
- Oracle circuit breaker 20% threshold: is this the right sensitivity? Too tight causes false trips; too loose misses real anomalies. Needs calibration against historical CoinGecko variance.
