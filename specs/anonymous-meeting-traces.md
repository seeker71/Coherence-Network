---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/routers/meetings.py
    symbols: [record_anonymous_meeting_trace(), list_anonymous_meeting_traces()]
  - file: api/app/services/meeting_service.py
    symbols: [sense_meeting(), capture_meeting_resonance()]
  - file: api/app/services/anonymous_meeting_trace_service.py
    symbols: [record_anonymous_meeting_trace(), list_anonymous_meeting_traces()]
  - file: web/components/AnonymousMeetingTrace.tsx
    symbols: [AnonymousMeetingTrace()]
  - file: api/tests/test_anonymous_meeting_traces.py
    symbols: [test_anonymous_meeting_trace_remembers_source_surfaces_and_duration()]
  - file: web/tests/anonymous-meeting-trace.test.ts
    symbols: [anonymous meeting trace client]
requirements:
  - "POST /api/meetings/anonymous-traces records or refreshes one anonymous meeting session."
  - "The API returns a stable hashed source_point_id that can match a second meeting without storing raw visitor/session keys."
  - "The trace keeps first_seen_at, last_seen_at, total duration, surfaces met, and per-surface duration."
  - "The trace exposes meeting shape: entry surface, ordered surface sequence, page count, coarse duration bucket, and hostname-only referrer domain."
  - "When contributor_id is present, prior traces for the same source point are folded into that contributor."
  - "The public web layout sends silent route-level meeting traces with an opaque visitor key and session key."
done_when:
  - "API tests prove same-source second meetings, surfaces, duration, and folding into contributor_id."
  - "Web static test proves the root layout mounts the silent trace component without geolocation or user-agent collection."
  - "Spec, API, web test, and build checks pass."
test: "cd api && python3 -m pytest tests/test_anonymous_meeting_traces.py -q && cd ../web && npm test -- tests/anonymous-meeting-trace.test.ts"
constraints:
  - "Do not store IP address, precise location, raw visitor key, raw session key, or user agent."
  - "The source point is a continuity hint, not identity proof."
  - "No visible layout change."
---

# Spec: Anonymous Meeting Traces

## Purpose

When someone meets the organism through public surfaces, the body should remember enough to recognize a likely return without claiming direct identity or location. This closes the gap between ephemeral presence and explicit registration: a later contributor identity can fold earlier anonymous meetings into its lineage.

The trace is intentionally modest. It knows an opaque source point, when it first and last appeared, how long the meeting lasted, which public surfaces were met, and the coarse shape of the meeting. Referrer memory is limited to hostname only.

## Requirements

- [ ] **R1**: `POST /api/meetings/anonymous-traces` records or refreshes one anonymous meeting session keyed by hashed `visitor_key` and hashed `session_key`.
- [ ] **R2**: The response includes `source_point_id`, session summary, and source-point summary so a second meeting can be recognized by the same hashed source point.
- [ ] **R3**: Session traces keep `first_seen_at`, `last_seen_at`, total `duration_ms`, and ordered `surfaces` with per-surface `duration_ms`.
- [ ] **R4**: The service does not store raw `visitor_key`, raw `session_key`, IP address, precise location, or user agent.
- [ ] **R5**: If `contributor_id` is present, prior traces for the same source point are marked with `folded_into_contributor_id`.
- [ ] **R6**: `GET /api/meetings/anonymous-traces` lists recent traces and can filter by `source_point_id`.
- [ ] **R7**: The root web layout mounts a silent client component that sends route-level meeting traces with localStorage/sessionStorage continuity keys and current route duration.
- [ ] **R8**: Session and summary responses include `entry_surface`, `surface_sequence`, `page_count`, and `duration_bucket`.
- [ ] **R9**: Referrer capture is limited to external hostname-only `referrer_domain`; full referrer URLs, IP address, user agent, geolocation, and cross-device matching stay out of scope.

## Research Inputs

- `2026-05-07` - User direction — the organism should know enough about someone meeting us to match a second meeting and fold prior meetings into registration, while avoiding direct identity/location capture.
- `2026-05-07` - Existing presence heartbeat — `api/app/services/presence_service.py` is intentionally ephemeral and not suitable for durable return recognition.
- `2026-05-07` - Existing meeting service — `api/app/services/meeting_service.py` already owns graph-backed meeting memory.

## API Contract

### `POST /api/meetings/anonymous-traces`

```json
{
  "visitor_key": "opaque-local-browser-token",
  "session_key": "opaque-tab-session-token",
  "surface": "/come-in",
  "duration_ms": 12000,
  "referrer_domain": "example.org",
  "started_at": "2026-05-07T00:00:00+00:00",
  "ended_at": "2026-05-07T00:00:12+00:00",
  "contributor_id": "contributor:urs"
}
```

### Response 201

```json
{
  "source_point_id": "anon:abc123...",
  "session": {
    "session_id": "session:def456...",
    "first_seen_at": "2026-05-07T00:00:00+00:00",
    "last_seen_at": "2026-05-07T00:00:12+00:00",
    "duration_ms": 12000,
    "duration_bucket": "10s_to_1m",
    "entry_surface": "/come-in",
    "surface_count": 1,
    "surface_sequence": ["/come-in"],
    "page_count": 1,
    "surfaces": [
      {"surface": "/come-in", "duration_ms": 12000, "referrer_domain": "example.org"}
    ],
    "referrer_domain": "example.org",
    "referrer_domains": ["example.org"],
    "raw_keys_stored": false
  },
  "summary": {
    "meeting_count": 1,
    "duration_bucket": "10s_to_1m",
    "entry_surface": "/come-in",
    "surfaces_met": ["/come-in"],
    "surface_sequence": ["/come-in"],
    "page_count": 1,
    "referrer_domain": "example.org",
    "referrer_domains": ["example.org"],
    "folded_into_contributor_id": "contributor:urs"
  }
}
```

### `GET /api/meetings/anonymous-traces?source_point_id=anon:abc123`

Returns recent traces and the same source-point summary.

## Data Model

```yaml
AnonymousMeetingTrace:
  node_type: event
  marker: anonymous_meeting_trace
  source_point_id: hashed visitor key
  session_id: hashed session key
  first_seen_at: iso timestamp
  last_seen_at: iso timestamp
  entry_surface: first route path in the session
  entry_referrer_domain: optional hostname-only external referrer
  surfaces:
    - surface: route path
      duration_ms: integer
      referrer_domain: optional hostname-only external referrer
  folded_into_contributor_id: optional contributor id
```

## Files to Create/Modify

- `specs/anonymous-meeting-traces.md` — behavior contract.
- `api/app/routers/meetings.py` — anonymous trace endpoints.
- `api/app/services/anonymous_meeting_trace_service.py` — graph-backed trace upsert/list logic.
- `api/tests/test_anonymous_meeting_traces.py` — API behavior tests.
- `web/components/AnonymousMeetingTrace.tsx` — silent public web trace component.
- `web/app/layout.tsx` — mount the trace component once.
- `web/tests/anonymous-meeting-trace.test.ts` — static web guard.
- `docs/system_audit/commit_evidence_2026-05-07_anonymous_meeting_traces.json` — proof record.
- `docs/system_audit/model_executor_runs.jsonl` — executor proof append.

## Acceptance Tests

- `api/tests/test_anonymous_meeting_traces.py::test_anonymous_meeting_trace_remembers_source_surfaces_and_duration`
- `web/tests/anonymous-meeting-trace.test.ts`

## Verification

```bash
cd api && python3 -m pytest tests/test_anonymous_meeting_traces.py tests/test_meeting_resonance_capture.py -q
cd web && npm test -- tests/anonymous-meeting-trace.test.ts
cd web && npm run build
python3 scripts/validate_spec_quality.py --file specs/anonymous-meeting-traces.md
```

## Out of Scope

- Precise identity, location, IP storage, user-agent storage, or cross-device fingerprinting.
- Public operator UI for browsing source points.
- Converting a source point into identity proof.

## Risks and Assumptions

- **Risk — tracking overreach**: store only hashed local keys and route/duration data; do not store raw keys, IP, location, or user-agent strings.
- **Risk — referrer overreach**: store only the external hostname; never store full referrer URLs, paths, queries, fragments, or same-origin routes.
- **Risk — false continuity**: shared devices may reuse a local source point; responses label the source point as a continuity hint rather than identity proof.
- **Risk — missed unload events**: the component posts on mount, interval, visibility change, and route cleanup; missed beacons are acceptable because the next meeting refreshes continuity.

## Known Gaps

- Follow-up task: `task_anonymous_meeting_trace_review_ui_001` to add a first-class operator UI for reviewing anonymous meetings and folding them manually.
- Follow-up task: `task_anonymous_meeting_trace_retention_001` to add a retention and composting practice for graph-backed anonymous meeting traces.
