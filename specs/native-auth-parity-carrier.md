---
idea_id: data-infrastructure
status: done
source:
  - file: form/form-stdlib/auth-port.fk
    symbols: [auth-require-api-key, auth-require-api-key-from-headers, auth-contributor-key-hash, auth-contributor-key-active?, auth-parity-test]
  - file: form/form-stdlib/tests/auth-port-band.fk
    symbols: []
  - file: form/form-stdlib/kernel-http.fk
    symbols: [kh-request, kh-header, kh-header-value-or]
  - file: form/form-stdlib/sha256.fk
    symbols: []
  - file: form/form-stdlib/hex.fk
    symbols: [hex-encode]
  - file: api/app/middleware/auth.py
    symbols: [require_api_key]
  - file: api/app/services/contributor_key_store.py
    symbols: [verify]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
  - file: api/tests/test_native_auth_parity_form.py
    symbols: [test_auth_port_names_fastapi_parity_surface, test_auth_band_proves_shared_key_contributor_key_and_denials, test_form_auth_band_executes, test_idea_and_spec_forms_name_auth_carrier_before_front_door_flip]
requirements:
  - "Form has a native auth decision carrier for mutation routes that mirrors FastAPI shared API-key and contributor-key decisions."
  - "Contributor keys are compared as SHA-256 hex hashes in Form, not as raw allow-list shortcuts."
  - "The carrier proves allowed, denied, missing, blank, case-insensitive header, and production dev-key misconfiguration cases."
  - "Ideas and specs name auth parity as proven while keeping public mutable front-door flips out of scope until application graph table writes, revision rows, and edge cleanup are native."
done_when:
  - 'file_contains("form/form-stdlib/auth-port.fk", "defn auth-require-api-key")'
  - 'file_contains("form/form-stdlib/tests/auth-port-band.fk", "Band verdict: 1111")'
  - 'pytest_passes("api/tests/test_native_auth_parity_form.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/kernel-http.fk form-stdlib/sha256.fk form-stdlib/hex.fk form-stdlib/auth-port.fk form-stdlib/tests/auth-port-band.fk && cd ../api && python3 -m pytest -q tests/test_native_auth_parity_form.py"
constraints:
  - "Do not bind public /api/ideas or /api/spec-registry mutation routes in this slice."
  - "Do not store live secrets or contributor raw keys in Form source."
  - "Do not weaken contributor-key verification to header presence or raw key allow-lists."
  - "Do not write live mutations to port_kv or file storage."
---

# Spec: Native Auth Parity Carrier

## Purpose

The mutable idea/spec front door can only move when trust moves first. This
spec adds a Form-native auth decision carrier that mirrors the FastAPI
`require_api_key` dependency: read `X-API-Key` case-insensitively, allow the
configured shared API key, allow active contributor keys by SHA-256 hex hash,
return the same 401 detail for missing/blank/wrong keys, and return the same
500 detail when production is configured with `dev-key`.

This is not a public route flip. It closes the auth-decision gap so the next
remaining blocker is the live application graph carrier: direct `graph_nodes`,
`graph_node_revisions`, and edge cleanup parity.

## Requirements

- [ ] **R1**: `form/form-stdlib/auth-port.fk` exposes `auth-require-api-key`
  and `auth-require-api-key-from-headers` over `kh-request`/`kh-header` values.
- [ ] **R2**: `auth-contributor-key-hash` computes `hex(sha256(raw_key))`, so
  Form compares active contributor-key hashes rather than raw source allow-lists.
- [ ] **R3**: `auth-parity-test` covers shared key allow, case-insensitive
  header lookup, contributor-key allow, missing/wrong/blank 401 denial, and
  production `dev-key` 500 misconfiguration.
- [ ] **R4**: `form/form-stdlib/tests/auth-port-band.fk` executes the carrier
  over both direct header lists and a `kh-request` wrapper, with a Python-known
  SHA-256 fixture.
- [ ] **R5**: ideas/spec Form route readings name auth parity as proven and
  leave public mutable front-door flips blocked on application graph table
  writes, revision rows, and edge cleanup.

## Research Inputs

- `api/app/middleware/auth.py::require_api_key` - live FastAPI mutation auth.
- `api/app/services/contributor_key_store.py::verify` - contributor-key hash
  lookup and revoked-key denial.
- `form/form-stdlib/kernel-http.fk` - native HTTP request/header value shape.
- `form/form-stdlib/sha256.fk` and `form/form-stdlib/hex.fk` - hash parity.
- `2026-06-08` - User direction: keep moving mutable surfaces toward Form native.

## Files to Create/Modify

- `form/form-stdlib/auth-port.fk` - native auth decision carrier.
- `form/form-stdlib/tests/auth-port-band.fk` - executable auth parity proof.
- `api/tests/test_native_auth_parity_form.py` - repository proof for carrier,
  Python contract links, and Form execution.
- `docs/coherence-substrate/ideas-router.form` - ideas route boundary update.
- `docs/coherence-substrate/spec-registry-router.form` - spec registry route
  boundary update.
- `specs/native-auth-parity-carrier.md` - this contract.

## Acceptance Tests

- `form/form-stdlib/tests/auth-port-band.fk`
- `api/tests/test_native_auth_parity_form.py::test_auth_port_names_fastapi_parity_surface`
- `api/tests/test_native_auth_parity_form.py::test_auth_band_proves_shared_key_contributor_key_and_denials`
- `api/tests/test_native_auth_parity_form.py::test_form_auth_band_executes`
- `api/tests/test_native_auth_parity_form.py::test_idea_and_spec_forms_name_auth_carrier_before_front_door_flip`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/kernel-http.fk form-stdlib/sha256.fk form-stdlib/hex.fk form-stdlib/auth-port.fk form-stdlib/tests/auth-port-band.fk
cd api && python3 -m pytest -q tests/test_native_auth_parity_form.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py tests/test_graph_node_mutation_carrier_form.py
python3 scripts/validate_spec_quality.py --file specs/native-auth-parity-carrier.md
```

## Out of Scope

- Binding public `POST/PATCH/DELETE /api/ideas` or `/api/spec-registry` to
  native kernel rows.
- Reading live API secrets from config inside Form source.
- Updating `contributor_api_keys.last_used_at`; that side effect belongs to the
  live contributor-key table carrier.
- Direct writes to `graph_nodes`, `graph_edges`, or `graph_node_revisions`.

## Gaps

- GAP-NAPC1 follow-up task: `native-application-graph-nodes-postgres-carrier`.
  Auth decisions are now native; live mutation still needs direct application
  table writes, revision rows, and edge cleanup.
- GAP-NAPC2 follow-up task: `native-contributor-key-last-used-update`.
  The current carrier proves allow/deny parity. The audit side effect that
  refreshes `last_used_at` should land with the application-table carrier.
- GAP-NAPC3 follow-up task: `method-specific-ideas-spec-mutation-routes`.
  Once graph-table parity is exact, bind method-specific native rows without
  stealing existing read surfaces.

## Risks and Assumptions

- The active contributor-key hash list is an injected carrier value in this
  slice. It must come from the live `contributor_api_keys` table before public
  route binding.
- Case-insensitive header lookup is proven in Form through `kh-header` values,
  matching the kernel request shape and FastAPI header semantics.
- The production `dev-key` refusal is a decision parity proof; the live process
  still performs fail-fast startup checks in Python until config/startup
  responsibilities move.
