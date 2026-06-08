---
idea_id: data-infrastructure
status: done
source:
  - file: deploy/kernel-router/production-routes.fk
    symbols: []
  - file: specs/INDEX.md
    symbols: []
  - file: api/app/models/spec_registry.py
    symbols: [SpecRegistryEntry]
  - file: api/tests/test_specs_source_native_route.py
    symbols: [test_specs_source_native_route_is_bound_and_reads_index, test_specs_source_native_route_emits_spec_registry_entry_shape]
  - file: api/tests/test_runtime_surface_native_routes.py
    symbols: [test_real_manifest_native_routes_are_served_zero_and_include_ideas_structure]
  - file: api/tests/test_native_mutation_route_bindings.py
    symbols: [test_native_mutation_preview_routes_are_method_and_header_gated, test_native_mutation_preview_handlers_emit_application_graph_sql]
  - file: form/form-stdlib/application-graph-node-port.fk
    symbols: [agn-create-node, agn-update-node, agn-delete-node]
  - file: form/form-stdlib/tests/application-graph-node-port-band.fk
    symbols: []
  - file: api/tests/test_application_graph_response_projection.py
    symbols: [test_route_forms_name_response_projection_before_public_flip]
requirements:
  - "The kernel-router production manifest exposes a native /api/spec-registry/source-list route."
  - "The route reads specs/INDEX.md directly, without FastAPI or spec_registry_service."
  - "The route emits SpecRegistryEntry-shaped JSON rows for each source-index spec row."
  - "The production manifest binds header-gated method-specific native SQL preview rows for POST/PATCH/DELETE /api/spec-registry without changing default public behavior."
done_when:
  - 'file_contains("deploy/kernel-router/production-routes.fk", "(list \"/api/spec-registry/source-list\" route_specs_source_list)")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "read_file_slice \"specs/INDEX.md\"")'
  - 'pytest_passes("api/tests/test_specs_source_native_route.py")'
test: "cd api && python3 -m pytest -q tests/test_specs_source_native_route.py tests/test_runtime_surface_native_routes.py"
constraints:
  - "Do not change existing /api/spec-registry behavior in this slice."
  - "Do not flip mutable spec create/update/delete paths to native execution for ordinary traffic."
  - "Use source-backed defaults for fields not present in specs/INDEX.md."
---

# Spec: Spec Registry Source Native

## Purpose

Specs have the same Python pressure as ideas: the mutable registry remains in
FastAPI, but the source index already carries a stable read surface. This spec
frees the source-backed spec list from mandatory Python handling by binding a
native kernel-router route that reads `specs/INDEX.md` and emits
`SpecRegistryEntry`-shaped rows.

## Requirements

- [ ] **R1**: `deploy/kernel-router/production-routes.fk` declares `specs_index_text`, `ssl-entry-json`, `ssl-entries-json-from`, and `route_specs_source_list`.
- [ ] **R2**: `route_specs_source_list` reads `specs/INDEX.md` through `read_file_slice`, with the same local/fallback path pattern used by ideas source reads.
- [ ] **R3**: Each source row emits required `SpecRegistryEntry` fields: `spec_id`, `title`, `summary`, metrics defaults, timestamps, `content_path`, and `workspace_id`.
- [ ] **R4**: The production route manifest binds `/api/spec-registry/source-list` to `route_specs_source_list`.
- [ ] **R5**: Runtime-surface reporting counts `/api/spec-registry/source-list` as kernel-first capable.
- [ ] **R6**: The production manifest binds header-gated method-specific native SQL preview rows for `POST /api/spec-registry`, `PATCH /api/spec-registry/*`, and `DELETE /api/spec-registry/*`.

## Research Inputs

- `2026-06-08` - User direction: free ideas and specs from forced Python handling.
- `api/app/routers/spec_registry.py` - live FastAPI carrier for mutable spec registry behavior.
- `api/app/models/spec_registry.py` - `SpecRegistryEntry` response field requirements.
- `specs/INDEX.md` - generated source index grouped by parent idea.
- `deploy/kernel-router/production-routes.fk` - self-contained production native route manifest.

## Files to Create/Modify

- `deploy/kernel-router/production-routes.fk` - native source-backed specs list route.
- `api/tests/test_specs_source_native_route.py` - repository proof for route binding and response shape.
- `api/tests/test_native_mutation_route_bindings.py` - method-specific mutation preview route proof.
- `api/tests/test_runtime_surface_native_routes.py` - capable-route proof includes the specs native route.
- `specs/spec-registry-source-native.md` - this contract.

## Acceptance Tests

- `api/tests/test_specs_source_native_route.py::test_specs_source_native_route_is_bound_and_reads_index`
- `api/tests/test_specs_source_native_route.py::test_specs_source_native_route_emits_spec_registry_entry_shape`
- `api/tests/test_native_mutation_route_bindings.py::test_native_mutation_preview_routes_are_method_and_header_gated`
- `api/tests/test_runtime_surface_native_routes.py::test_real_manifest_native_routes_are_served_zero_and_include_ideas_structure`

## Verification

```bash
cd api && python3 -m pytest -q tests/test_specs_source_native_route.py tests/test_native_mutation_route_bindings.py tests/test_runtime_surface_native_routes.py
python3 scripts/validate_spec_quality.py --file specs/spec-registry-source-native.md
cd form/form-kernel-rust && ./target/release/form-kernel-rust serve --host 127.0.0.1 --port 19186 --workers 1 --routes ../../deploy/kernel-router/production-routes.fk --stdlib ../form-stdlib --upstream http://127.0.0.1:9
python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:19186/api/spec-registry/source-list') as r:
    body = json.loads(r.read())
    print(r.status, r.headers.get('X-Form-Router'), len(body), body[0]['spec_id'], body[-1]['spec_id'])
PY
```

## Out of Scope

- Changing live `/api/spec-registry` list/create/update/delete behavior for ordinary traffic.
- Parsing every spec frontmatter field in Form.
- Replacing language projection, workspace filtering, cards, or mutation routes.

## Gaps

- GAP-SRS1 follow-up task: `spec-registry-live-graph-storage-carrier`. The
  source-backed route is native and the Form graph-node mutation carrier now
  exposes create/replace/delete. The Form auth carrier now preserves
  API-key/contributor-key decision parity, and the Form application graph
  carrier emits direct `graph_nodes` / `graph_node_revisions` / `graph_edges`
  SQL. `POST/PATCH/DELETE /api/spec-registry` also have `X-Form-Native-Preview`
  header-gated native SQL preview rows. Public mutable DB-backed spec registry
  behavior still enters through FastAPI by default until cache invalidation,
  contributor-key audit side effects, and a reversible public gate are proven.
- GAP-SRS2 follow-up task: `spec-source-frontmatter-native-parser`. This route
  reads `specs/INDEX.md`; richer frontmatter fields remain source defaults until
  a native frontmatter parser lands.

## Risks and Assumptions

- `specs/INDEX.md` is generated from spec files and stable enough for a native
  source-backed list.
- Fields not carried by `specs/INDEX.md` use conservative defaults rather than
  claiming DB parity.
