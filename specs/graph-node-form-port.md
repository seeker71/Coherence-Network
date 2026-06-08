---
idea_id: data-infrastructure
status: done
source:
  - file: form/form-stdlib/graph-node-port.fk
    symbols: []
  - file: form/form-stdlib/tests/graph-node-port-band.fk
    symbols: []
  - file: api/app/services/graph_service.py
    symbols: [get_node, list_nodes, count_nodes]
  - file: api/tests/test_graph_node_form_port.py
    symbols: [test_graph_node_form_port_exposes_read_functions, test_graph_node_form_port_tracks_type_indexes_and_counts, test_graph_node_form_band_proves_memory_and_durable_file_carriers, test_python_graph_service_contract_still_names_same_functions]
requirements:
  - "Form exposes graph-node put/get/exists/count/list functions above the existing storage port."
  - "The graph-node port preserves type counts and typed indexes across create, update, and retype operations."
  - "A Form band proves the same graph-node contract over memory and durable file carriers."
done_when:
  - 'file_exists("form/form-stdlib/graph-node-port.fk")'
  - 'file_contains("form/form-stdlib/graph-node-port.fk", "defn gn-count-nodes")'
  - 'file_contains("form/form-stdlib/graph-node-port.fk", "defn gn-list-nodes")'
  - 'file_contains("form/form-stdlib/tests/graph-node-port-band.fk", "Band verdict: 11111")'
  - 'pytest_passes("api/tests/test_graph_node_form_port.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/cell-log-store.fk form-stdlib/storage-port.fk form-stdlib/storage-port-file.fk form-stdlib/graph-node-port.fk form-stdlib/tests/graph-node-port-band.fk"
constraints:
  - "Do not change api/app/services/graph_service.py behavior in this slice."
  - "Do not add a parallel Python graph-node service."
  - "Keep the storage backend swappable through storage-port carriers."
---

# Spec: Graph Node Form Port

## Purpose

The ideas router can only move more routes native when the graph-node storage
functions are visible in Form. This spec exposes the smallest useful graph-node
surface as a Form port layered on `storage-port.fk`: write a node, read a node,
test existence, count by type, and list nodes by type.

## Requirements

- [ ] **R1**: `form/form-stdlib/graph-node-port.fk` declares `gn-put-node`, `gn-get-node`, `gn-node-exists?`, `gn-count-nodes`, `gn-list-node-ids`, and `gn-list-nodes`.
- [ ] **R2**: The port keeps node type metadata, total counts, typed counts, and typed indexes in storage-port keys.
- [ ] **R3**: Updating an existing node with the same type does not duplicate typed indexes or counts.
- [ ] **R4**: Retyping a node decrements the old typed count/index and increments the new typed count/index.
- [ ] **R5**: The proof band runs the same contract through the memory carrier and the durable file carrier, then reopens the file store to prove persistence.

## Research Inputs

- `2026-06-08` - User direction: expose graph-node functions so ideas can move more native.
- `api/app/services/graph_service.py` - current Python source of truth for `get_node`, `list_nodes`, and `count_nodes`.
- `api/app/services/idea_graph_adapter.py` - ideas already read graph nodes with `list_nodes(type="idea")` and `count_nodes(type="idea")`.
- `form/form-stdlib/storage-port.fk` - carrier-agnostic storage interface.
- `form/form-stdlib/storage-port-file.fk` - durable file carrier used as native proof.

## Files to Create/Modify

- `form/form-stdlib/graph-node-port.fk` - Form graph-node port over storage-port.
- `form/form-stdlib/tests/graph-node-port-band.fk` - memory/file carrier proof.
- `api/tests/test_graph_node_form_port.py` - repository-level contract proof.
- `docs/coherence-substrate/INDEX.md` - public substrate map entry.
- `docs/coherence-substrate/ideas-router.form` - gap updated now that the graph-node read port exists.
- `specs/graph-node-form-port.md` - this contract.

## Acceptance Tests

- `api/tests/test_graph_node_form_port.py::test_graph_node_form_port_exposes_read_functions`
- `api/tests/test_graph_node_form_port.py::test_graph_node_form_port_tracks_type_indexes_and_counts`
- `api/tests/test_graph_node_form_port.py::test_graph_node_form_band_proves_memory_and_durable_file_carriers`
- `api/tests/test_graph_node_form_port.py::test_python_graph_service_contract_still_names_same_functions`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/cell-log-store.fk form-stdlib/storage-port.fk form-stdlib/storage-port-file.fk form-stdlib/graph-node-port.fk form-stdlib/tests/graph-node-port-band.fk
cd api && python3 -m pytest -q tests/test_graph_node_form_port.py
python3 scripts/validate_spec_quality.py --file specs/graph-node-form-port.md
```

## Out of Scope

- Changing FastAPI graph endpoint behavior.
- Replacing SQLAlchemy-backed production graph persistence in this slice.
- Native HTTP JSON projection for `/api/ideas` data routes.

## Gaps

- GAP-GN1: The port is proven over memory and file carriers. Follow-up task:
  `graph-node-form-postgres-carrier` can add a live Postgres graph-node carrier
  to the same storage-port shape.
- GAP-GN2: closed by `specs/ideas-graph-projection-form.md` and
  `specs/native-mutation-response-projection.md`. Native read projection and
  mutation response projection now have Form carriers; ordinary mutable traffic
  still waits on side effects and reversible public gating.

## Risks and Assumptions

- The port intentionally stores a durable string envelope, not host records.
- Ordering is insertion/index order; existing Python `list_nodes` sorts by
  `updated_at` and remains the carrier for public API behavior until route
  projection lands.
