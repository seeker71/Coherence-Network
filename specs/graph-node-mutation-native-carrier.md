---
idea_id: data-infrastructure
status: done
source:
  - file: form/form-stdlib/graph-node-port.fk
    symbols: [gn-create-node, gn-replace-node, gn-delete-node, gn-node-active?, gn-mutation-test]
  - file: form/form-stdlib/tests/graph-node-mutation-carrier-band.fk
    symbols: []
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [mutate_idea_recipe, ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [browse_specs_recipe, mutate_specs_recipe, spec_registry_router_structure, spec_registry_router_reading]
  - file: api/tests/test_graph_node_mutation_carrier_form.py
    symbols: [test_graph_node_port_exposes_create_replace_delete_mutations, test_graph_node_mutation_band_proves_memory_file_and_reopen, test_ideas_and_specs_name_the_native_mutation_carrier]
  - file: api/tests/test_spec_registry_router_form.py
    symbols: [test_spec_registry_router_form_declares_route_shapes_and_structure, test_spec_registry_router_form_describes_live_and_native_carriers]
  - file: api/tests/test_ideas_router_form.py
    symbols: [test_ideas_router_form_names_native_mutation_carrier]
requirements:
  - "The graph-node Form port exposes create, replace, and delete mutation operations over the storage port."
  - "The mutation carrier is proven over memory and durable file storage with one shared Form band, including recreate after tombstone."
  - "Ideas and specs name the native mutation carrier while keeping the live auth/Postgres front-door gap explicit."
done_when:
  - 'file_contains("form/form-stdlib/graph-node-port.fk", "defn gn-create-node")'
  - 'file_contains("form/form-stdlib/graph-node-port.fk", "defn gn-delete-node")'
  - 'pytest_passes("api/tests/test_graph_node_mutation_carrier_form.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/cell-log-store.fk form-stdlib/storage-port.fk form-stdlib/storage-port-file.fk form-stdlib/graph-node-port.fk form-stdlib/tests/graph-node-mutation-carrier-band.fk && cd ../api && python3 -m pytest -q tests/test_graph_node_mutation_carrier_form.py tests/test_spec_registry_router_form.py tests/test_ideas_router_form.py"
constraints:
  - "Do not flip public /api/ideas or /api/spec-registry mutation paths in this slice."
  - "Do not introduce a parallel public mutation store for live users."
  - "Keep API-key, contributor-key, and application graph_nodes Postgres parity named before front-door binding."
---

# Spec: Graph Node Mutation Native Carrier

## Purpose

Ideas and specs can now leave the Python-only mutation vocabulary at the carrier
level. This spec adds native Form graph-node create, replace, and delete
operations over the existing storage port and proves that the same mutation
recipe works over memory and durable file storage. The public HTTP mutation
paths remain FastAPI until native auth parity and direct application
`graph_nodes` Postgres writes are exact.

## Requirements

- [ ] **R1**: `form/form-stdlib/graph-node-port.fk` declares `gn-create-node`, `gn-replace-node`, `gn-delete-node`, and `gn-node-active?`.
- [ ] **R2**: `gn-create-node` refuses an already-active node and `gn-replace-node` refuses a missing or tombstoned node.
- [ ] **R3**: `gn-delete-node` tombstones a node and removes it from active counts and typed indexes; a later `gn-create-node` on that tombstoned id restores active counts.
- [ ] **R4**: `form/form-stdlib/tests/graph-node-mutation-carrier-band.fk` proves the same mutation contract over memory and file carriers, including tombstone restore and reopen persistence.
- [ ] **R5**: `docs/coherence-substrate/ideas-router.form` and `docs/coherence-substrate/spec-registry-router.form` name the native mutation carrier and the remaining live-front-door boundary.

## Research Inputs

- `2026-06-08` - User direction: move mutable ideas/spec surfaces toward Form-native handling.
- `api/app/routers/ideas.py` - live idea create/update routes and auth boundary.
- `api/app/routers/spec_registry.py` - live spec create/update/delete routes and auth boundary.
- `api/app/services/graph_service.py` - application graph-node create/update/delete semantics.
- `form/form-stdlib/graph-node-port.fk` - native graph-node storage port surface.
- `form/form-stdlib/storage-port.fk` - carrier abstraction for memory/file/db storage.

## Files to Create/Modify

- `form/form-stdlib/graph-node-port.fk` - native create, replace, delete, active-state, and mutation proof functions.
- `form/form-stdlib/tests/graph-node-mutation-carrier-band.fk` - carrier-agnostic mutation proof.
- `docs/coherence-substrate/ideas-router.form` - ideas mutation carrier reading.
- `docs/coherence-substrate/spec-registry-router.form` - spec registry route and mutation carrier reading.
- `api/tests/test_graph_node_mutation_carrier_form.py` - repository proof for native mutation carrier naming.
- `api/tests/test_spec_registry_router_form.py` - repository proof for the spec registry Form expression.
- `api/tests/test_ideas_router_form.py` - idea router mutation carrier assertion.
- `specs/graph-node-mutation-native-carrier.md` - this contract.

## Acceptance Tests

- `form/form-stdlib/tests/graph-node-mutation-carrier-band.fk`
- `api/tests/test_graph_node_mutation_carrier_form.py::test_graph_node_port_exposes_create_replace_delete_mutations`
- `api/tests/test_graph_node_mutation_carrier_form.py::test_graph_node_mutation_band_proves_memory_file_and_reopen`
- `api/tests/test_graph_node_mutation_carrier_form.py::test_ideas_and_specs_name_the_native_mutation_carrier`
- `api/tests/test_spec_registry_router_form.py::test_spec_registry_router_form_declares_route_shapes_and_structure`
- `api/tests/test_spec_registry_router_form.py::test_spec_registry_router_form_describes_live_and_native_carriers`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/cell-log-store.fk form-stdlib/storage-port.fk form-stdlib/storage-port-file.fk form-stdlib/graph-node-port.fk form-stdlib/tests/graph-node-mutation-carrier-band.fk form-stdlib/tests/graph-node-port-band.fk
cd api && python3 -m pytest -q tests/test_graph_node_mutation_carrier_form.py tests/test_spec_registry_router_form.py tests/test_ideas_router_form.py
python3 scripts/validate_spec_quality.py --file specs/graph-node-mutation-native-carrier.md
```

## Out of Scope

- Binding public `/api/ideas` or `/api/spec-registry` mutation routes directly to the kernel-router.
- Replacing API-key or contributor-key auth with a weaker header-presence check.
- Writing live user mutations to a parallel file or KV store.
- Replacing graph edge cleanup, revision rows, or language projection behavior.

## Gaps

- GAP-GNMC1 follow-up task: `native-api-key-contributor-key-auth-parity`.
  Kernel handlers can see request headers, but the live front door must preserve
  shared API key and contributor-key verification before mutating paths flip.
- GAP-GNMC2 follow-up task: `native-application-graph-nodes-postgres-carrier`.
  The current native storage DB carrier writes `port_kv`; live parity needs
  direct `graph_nodes`, `graph_edges`, and `graph_node_revisions` writes.
- GAP-GNMC3 follow-up task: `method-specific-ideas-spec-mutation-routes`.
  Once auth and application Postgres writes are exact, bind POST/PATCH/DELETE
  rows without stealing existing GET surfaces.

## Risks and Assumptions

- Logical tombstones are the right storage-port delete shape because the port has no physical delete primitive, and recreate-after-tombstone must restore active counts rather than inheriting the deleted marker.
- Front-door mutation should wait for exact auth and application-table parity rather than exposing a weaker native route.
- The carrier proof is valuable now because it lets future route binding use one tested mutation recipe instead of re-inventing create/update/delete per endpoint.
