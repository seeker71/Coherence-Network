---
idea_id: data-infrastructure
status: done
source:
  - file: form/form-stdlib/application-graph-node-port.fk
    symbols: [agn-create-node-sql, agn-update-node-sql, agn-delete-node-sql, agn-create-node, agn-update-node, agn-delete-node, agn-application-graph-sql-test]
  - file: form/form-stdlib/tests/application-graph-node-port-band.fk
    symbols: []
  - file: api/app/services/graph_service.py
    symbols: [_record_revision, create_node, update_node, delete_node]
  - file: api/app/models/graph.py
    symbols: [Node, Edge, NodeRevision]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
  - file: api/tests/test_application_graph_node_port_form.py
    symbols: [test_application_graph_port_names_live_table_contract, test_application_graph_band_executes, test_application_graph_sql_carries_revision_and_edge_cleanup_semantics, test_idea_and_spec_forms_name_application_graph_carrier]
requirements:
  - "Form has a native carrier for the live application graph tables used by mutable idea/spec routes."
  - "Create SQL writes graph_nodes and graph_node_revisions with a __create__ revision snapshot."
  - "Update SQL merges graph node properties, advances the per-node revision number, and records fields_changed plus a full snapshot."
  - "Delete SQL clears connected graph_edges before deleting the graph_nodes row."
  - "Ideas and specs name application graph table semantics as proven while keeping public front-door flips out of scope until header-gated preview rows graduate through live DB execution proof."
done_when:
  - 'file_contains("form/form-stdlib/application-graph-node-port.fk", "defn agn-create-node-sql")'
  - 'file_contains("form/form-stdlib/tests/application-graph-node-port-band.fk", "Band verdict: 1111")'
  - 'pytest_passes("api/tests/test_application_graph_node_port_form.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/tests/application-graph-node-port-band.fk && cd ../api && python3 -m pytest -q tests/test_application_graph_node_port_form.py"
constraints:
  - "Do not flip public /api/ideas or /api/spec-registry mutation routes in this slice."
  - "Do not route live mutations through port_kv."
  - "Do not drop graph_node_revisions or graph_edges cleanup semantics."
  - "Do not claim live DB execution proof until a bound route runs the SQL against the application database."
---

# Spec: Application Graph Node SQL Carrier

## Purpose

Mutable idea/spec routes were no longer missing generic graph-node vocabulary or
auth decisions. They were missing the table-native shape of the application
graph itself: direct `graph_nodes` writes, `graph_node_revisions` snapshots, and
connected `graph_edges` cleanup on delete.

This spec adds that missing Form carrier. It emits the SQL a native route row
can execute through the Postgres `pg_exec` carrier, while keeping the public
FastAPI mutation routes unchanged until method-specific request/response
binding, live DB execution proof, response projection, and side effects are
present. A later slice added header-gated native preview rows; this carrier
remains the SQL source for those rows.

## Requirements

- [ ] **R1**: `application-graph-node-port.fk` exposes create/update/delete SQL
  builders over the real application tables: `graph_nodes`,
  `graph_node_revisions`, and `graph_edges`.
- [ ] **R2**: create SQL inserts the node and a revision row with
  `revision_number = 1`, `fields_changed = ["__create__"]`, and a full snapshot.
- [ ] **R3**: update SQL merges `properties`, sets `updated_at`, computes the
  next per-node `revision_number`, records `fields_changed`, and snapshots the
  updated node.
- [ ] **R4**: delete SQL removes connected edges before deleting the node row.
- [ ] **R5**: wrappers expose `agn-create-node`, `agn-update-node`, and
  `agn-delete-node` as `pg_exec` binding points for the live Postgres carrier.

## Research Inputs

- `api/app/services/graph_service.py` - live create/update/delete semantics.
- `api/app/models/graph.py` - table names, columns, revision fields, and edge
  cleanup target.
- `form/form-stdlib/storage-port-db.fk` - existing Postgres-native binding
  pattern.
- `2026-06-08` - User direction: keep moving mutable surfaces toward Form
  native without waiting at bounded checkpoints.

## Files to Create/Modify

- `form/form-stdlib/application-graph-node-port.fk` - application table SQL
  carrier and `pg_exec` binding functions.
- `form/form-stdlib/tests/application-graph-node-port-band.fk` - executable
  carrier proof.
- `api/tests/test_application_graph_node_port_form.py` - repository proof tying
  Form, Python graph service, ORM tables, and route forms.
- `docs/coherence-substrate/ideas-router.form` - route boundary update.
- `docs/coherence-substrate/spec-registry-router.form` - route boundary update.
- `specs/application-graph-node-sql-carrier.md` - this contract.

## Acceptance Tests

- `form/form-stdlib/tests/application-graph-node-port-band.fk`
- `api/tests/test_application_graph_node_port_form.py::test_application_graph_port_names_live_table_contract`
- `api/tests/test_application_graph_node_port_form.py::test_application_graph_band_executes`
- `api/tests/test_application_graph_node_port_form.py::test_application_graph_sql_carries_revision_and_edge_cleanup_semantics`
- `api/tests/test_application_graph_node_port_form.py::test_idea_and_spec_forms_name_application_graph_carrier`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/tests/application-graph-node-port-band.fk
cd api && python3 -m pytest -q tests/test_application_graph_node_port_form.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py tests/test_native_auth_parity_form.py
python3 scripts/validate_spec_quality.py --file specs/application-graph-node-sql-carrier.md
```

## Out of Scope

- Binding public `POST/PATCH/DELETE /api/ideas` or `/api/spec-registry` to the
  native kernel front door.
- Executing the SQL against production or local application databases in this
  slice.
- Contributor-key `last_used_at` updates.
- Resonance re-attunement, idea cache invalidation, or spec cache invalidation.

## Gaps

- GAP-AGN1 follow-up task: `native-graph-mutation-live-db-proof`.
  Auth decisions, generic graph mutation shape, application table SQL, and
  header-gated method-specific preview rows are now native. Public mutation
  still needs live DB execution, response projection, cache invalidation,
  parent/edge side effects, and contributor-key audit proof.
- GAP-AGN2 follow-up task: `native-contributor-key-last-used-update`.
  Contributor-key allow/deny parity is native, but the audit side effect still
  belongs with a table carrier.
- GAP-AGN3 follow-up task: `native-graph-mutation-live-db-proof`.
  The SQL carrier is executable through `pg_exec`; live DB proof should run it
  against the application schema before front-door flip.

## Risks and Assumptions

- The carrier targets the current SQLAlchemy table names and columns. If the ORM
  shape changes, this carrier must change with it.
- SQL proof here is structural, not a production mutation. That is intentional:
  route binding and live DB execution need their own bounded proof.
- Snapshots mirror `Node.to_dict()` by combining common node columns with the
  JSON properties object.
