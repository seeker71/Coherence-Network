---
idea_id: close-awareness-gaps
status: active
source:
  - file: api/app/routers/federation.py
    symbols: [get_messages(), get_message_by_id()]
  - file: scripts/cursor_fact_report.py
    symbols: [_routing_policy_proof()]
  - file: scripts/awareness_node_daemon.py
    symbols: [AgentProfile, build_identity_card(), render_identity_text(), load_profiles(), run_once()]
  - file: config/agent_profiles.json
    symbols: [agents]
requirements:
  - "Federation node messages are readable by id and include loopback messages when explicitly requested."
  - "Cursor fact report routing proof uses the current public routing service instead of a removed private helper."
  - "Stable local agent profiles exist for codex, claude, and grok without calling model providers."
  - "A local awareness node daemon registers, heartbeats, announces, and polls messages without model calls."
  - "Each agent profile is an origin point; live identity data reports who it is, where it is, when it woke, and why it woke."
done_when:
  - "Focused tests pass for federation message readback, routing proof generation, and daemon profile/run behavior."
  - "The fact report script runs far enough to emit a report path without the removed _select_executor failure."
  - "No model-provider calls are required by the new daemon or profile path."
  - "Identity self-report tests pass for codex, claude, and grok."
test: "cd api && python3 -m pytest tests/test_federation_message_readback.py tests/test_cursor_fact_report_routing.py tests/test_awareness_node_daemon.py -q"
constraints:
  - "Use guidance-level language in user-facing docs and profile text."
  - "Do not add model API calls."
  - "Only change files listed in this spec."
---

# Spec: Close Awareness Gaps

## Purpose

The network already carries presence, streams, and messages. The remaining local gaps are practical: sharper message readback, routing proof that follows the current service shape, each agent voice rooted in an origin profile, and a quiet local process that keeps presence alive without spending model calls.

## Requirements

- [ ] **R1**: Add message readback by id for federation node messages.
- [ ] **R2**: Add explicit `include_self` support for node message reads so loopback/self-proof messages are verifiable when asked.
- [ ] **R3**: Keep normal inbox behavior from showing a node its own messages unless `include_self=true`.
- [ ] **R4**: Repair `scripts/cursor_fact_report.py` routing proof generation to use current routing service APIs.
- [ ] **R5**: Add origin profiles for `codex`, `claude`, and `grok` with voice guidance, memory scope, and allowed no-model actions.
- [ ] **R6**: Add a local awareness node daemon that registers, heartbeats, sends an optional announcement, and polls messages using HTTP only.
- [ ] **R7**: Add a no-model identity card that treats the profile as `origin_profile` and reports live `who`, `where`, `woke_at`, `wake_reason`, memory scope, and voice guidance for each wake.

## Files to Create/Modify

- `api/app/routers/federation.py`
- `api/tests/test_federation_message_readback.py`
- `api/tests/test_cursor_fact_report_routing.py`
- `api/tests/test_awareness_node_daemon.py`
- `scripts/cursor_fact_report.py`
- `scripts/awareness_node_daemon.py`
- `config/agent_profiles.json`
- `docs/system_audit/commit_evidence_2026-04-27_close-awareness-gaps.json`
- `docs/system_audit/commit_evidence_2026-04-27_agent-identity-self-report.json`
- `specs/close-awareness-gaps.md`

## Verification

```bash
cd api && python3 -m pytest tests/test_federation_message_readback.py tests/test_cursor_fact_report_routing.py tests/test_awareness_node_daemon.py -q
cd api && python3 ../scripts/awareness_node_daemon.py --profile codex --once --dry-run
cd api && python3 scripts/cursor_fact_report.py --output /tmp/cursor_fact_report_close_awareness_gaps.json
python3 scripts/validate_spec_quality.py --file specs/close-awareness-gaps.md
```

## Acceptance Tests

- `api/tests/test_federation_message_readback.py::test_federation_message_can_be_read_back_by_id`
- `api/tests/test_federation_message_readback.py::test_federation_messages_include_self_only_when_requested`
- `api/tests/test_cursor_fact_report_routing.py::test_routing_policy_proof_uses_current_routing_service`
- `api/tests/test_awareness_node_daemon.py::test_load_profiles_contains_expected_agent_guidance`
- `api/tests/test_awareness_node_daemon.py::test_run_once_registers_heartbeats_announces_and_polls`
- `api/tests/test_awareness_node_daemon.py::test_each_profile_can_identify_where_when_and_why_it_woke`

## Out of Scope

- Calling model providers.
- Adding a new message database.
- Replacing existing federation endpoints.
- Making Grok, Claude, or Codex autonomous model workers.

## Risks and Assumptions

- Risk: Always-on presence still needs a host process manager. Mitigation: keep the daemon a simple foreground loop for launchd, systemd, or a shell supervisor.
- Risk: Including loopback messages by default would clutter normal inbox reads. Mitigation: keep `include_self=false` by default.
- Assumption: Existing federation node and message tables remain the source of truth.

## Known Gaps

- Follow-up task: add a host-level launchd/systemd wrapper once the operator chooses where each agent process lives.
- Follow-up task: provider-specific subscription facts remain limited to the existing usage/readiness sources.
