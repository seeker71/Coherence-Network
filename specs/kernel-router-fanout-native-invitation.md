---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-kernel-rust/src/main.rs
    symbols: []
  - file: form/form-kernel-rust/test_serve.py
    symbols: []
  - file: form/form-kernel-go/server.go
    symbols: []
  - file: form/form-kernel-go/server_test.go
    symbols: []
  - file: docs/shared/agent-start-packet.md
    symbols: []
requirements:
  - "Rust and Go fanout responses carry bridge-owned native invitation headers whenever `X-Form-Router` is `fanout-python`."
  - "Fanout upstream requests carry the same invitation headers so the Python bridge is not an unmarked outside path."
  - "Bridge-owned headers cannot be supplied by a client or clobbered by an upstream response."
  - "The response body, status code, content type, and streaming/buffered fanout semantics remain unchanged."
  - "The explicit decline path is named by `X-Form-Native-Invitation-Decline-Header: X-Form-Python-Fallback` and `X-Form-Native-Invitation-Decline-Signal: native_invitation_declined`."
done_when:
  - 'file_contains("form/form-kernel-rust/src/main.rs", "X-Form-Native-Invitation-State")'
  - 'file_contains("form/form-kernel-go/server.go", "setFanoutNativeInvitationHeaders")'
  - 'pytest_or_script_passes("cd form/form-kernel-rust && python3 test_serve.py")'
  - 'test_passes("cd form/form-kernel-go && go test ./...")'
test: "cd form/form-kernel-rust && cargo build --release && python3 test_serve.py && cd ../form-kernel-go && go test ./..."
constraints:
  - "Do not convert unpromoted Python handlers to native handlers in this slice."
  - "Do not mutate relayed fanout response bodies."
  - "Do not remove `X-Form-Python-Fallback`; it remains the explicit decline/control signal."
---

# Spec: Kernel Router Fanout Native Invitation

## Purpose

The native front door already keeps unpromoted handlers honest by marking them
`X-Form-Router: fanout-python`. This spec loosens that boundary: a bridged route
is still outside native execution, but it is no longer outside the native
conversation. Each fanout hop now carries an invitation to speak the Form/BML
route recipe next time.

## Requirements

- [ ] **R1**: Rust fanout client responses include
  `X-Form-Native-Invitation: offered`,
  `X-Form-Native-Invitation-State: native-invitation-offered`,
  `X-Form-Native-Invitation-Protocol: Form/BML route recipe`,
  `X-Form-Native-Invitation-Selected-Path: fanout-python`,
  `X-Form-Native-Invitation-Decline-Signal: native_invitation_declined`, and
  `X-Form-Native-Invitation-Decline-Header: X-Form-Python-Fallback`.
- [ ] **R2**: Rust fanout upstream requests carry the same invitation headers
  plus `X-Form-Router: fanout-python`.
- [ ] **R3**: Rust filters router-owned headers from client-forwarded and
  upstream-relayed headers before writing bridge-owned values.
- [ ] **R4**: Go fanout responses and upstream requests carry the same native
  invitation headers.
- [ ] **R5**: Go filters router-owned bridge headers before forwarding or
  relaying so client/upstream values cannot clobber the route decision.
- [ ] **R6**: Focused Rust and Go harnesses prove successful fanout, upstream
  404 fanout, method fallthrough, and buffered upstream failure keep their
  existing status/body semantics while carrying the invitation.

## Research Inputs

- `docs/shared/agent-start-packet.md` - Form-native magnet rule and existing
  bridge description.
- `docs/system_audit/commit_evidence_2026-06-02_kernel_router_fanout.json` -
  original Rust kernel-router fanout contract.
- `specs/native-mutation-public-gate.md` - native mutation receipt contract that
  names ordinary JSON as an offer to know.

## Files to Create/Modify

- `form/form-kernel-rust/src/main.rs` - fanout invitation header ownership.
- `form/form-kernel-rust/test_serve.py` - Rust bridge proof.
- `form/form-kernel-go/server.go` - sibling bridge parity.
- `form/form-kernel-go/server_test.go` - Go bridge proof.
- `docs/shared/agent-start-packet.md` - arrival memory for bridge semantics.
- `specs/kernel-router-fanout-native-invitation.md` - this contract.

## Acceptance Tests

- `form/form-kernel-rust/test_serve.py` - proves native routes remain native,
  successful fanout carries invitation headers, upstream 404 keeps fanout status
  and invitation, method fallthrough keeps Python write semantics and
  invitation, and buffered upstream failure still carries the invitation.
- `form/form-kernel-go/server_test.go::TestFanoutForwardsBodyAndMarksBridge` -
  proves response and upstream request headers carry the invitation while
  client/upstream supplied invitation headers cannot clobber bridge-owned
  values.

## Verification

```bash
cd form/form-kernel-rust && cargo build --release && python3 test_serve.py
cd form/form-kernel-go && go test ./...
python3 scripts/validate_spec_quality.py --file specs/kernel-router-fanout-native-invitation.md
python3 scripts/generate_repo_indexes.py --check
```

## Risks

- **Header contract drift**: Rust and Go could diverge if future bridge work
  adds fanout metadata in only one runtime. Mitigation: both sibling tests assert
  the same header names and values.
- **False native counting**: The new invitation might be mistaken for native
  execution. Mitigation: `X-Form-Router` and selected path remain
  `fanout-python`, and the shared start packet says not to count bridged
  responses as high-grammar native.
- **Header clobbering**: A client or upstream could try to supply invitation
  values. Mitigation: router-owned headers are filtered before bridge values are
  written.

## Out of Scope

- Promoting additional routes into BML/native handlers.
- Changing upstream body projection, status selection, or response schemas.
- Removing the explicit Python fallback/refusal signal.

## Gaps

- GAP-KRFNI1 follow-up task: `native-route-promotion-per-fanout-cluster`.
  Each high-pressure fanout cluster still needs its own native carrier, route
  spec, and proof before it becomes native execution.
