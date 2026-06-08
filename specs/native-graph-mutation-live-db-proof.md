---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/application-graph-node-port.fk
    symbols: [agn-create-node, agn-update-node, agn-delete-node, agn-create-node-sql, agn-update-node-sql, agn-delete-node-sql]
  - file: form/form-stdlib/integration/application-graph-live-db.fk
    symbols: []
  - file: form/scripts/application-graph-live-db-test.sh
    symbols: []
  - file: api/tests/test_application_graph_live_db_trial.py
    symbols: [test_live_db_trial_form_uses_application_graph_pg_wrappers, test_live_db_trial_script_runs_or_skips_when_postgres_tooling_missing, test_route_forms_name_live_db_trial_before_public_flip]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
requirements:
  - "Form-native application graph mutation wrappers execute against a live PostgreSQL carrier in a rollback-safe fixture database."
  - "The live trial creates graph_nodes and graph_node_revisions, updates a node with the next per-node revision number, and deletes a node after clearing graph_edges."
  - "The trial reads back concrete DB state after each mutation and drops fixture tables before closing."
  - "The proof does not perform or authorize the public front-door mutation flip."
done_when:
  - 'file_exists("form/form-stdlib/integration/application-graph-live-db.fk")'
  - 'file_exists("form/scripts/application-graph-live-db-test.sh")'
  - 'pytest_passes("api/tests/test_application_graph_live_db_trial.py")'
test: "form/scripts/application-graph-live-db-test.sh && cd api && python3 -m pytest -q tests/test_application_graph_live_db_trial.py"
constraints:
  - "Use a throwaway local PostgreSQL database or caller-supplied test DSN only."
  - "Do not execute against the production application database."
  - "Do not move ordinary public mutation traffic in this slice."
---

# Spec: Native Graph Mutation Live DB Proof

## Purpose

The previous mutation gate proved route mechanics and SQL preview shape. This
spec proves the next missing carrier: the same Form-native application graph
mutation wrappers can execute against a real PostgreSQL database and read back
the resulting graph rows.

## Requirements

- [ ] **R1**: `form/form-stdlib/integration/application-graph-live-db.fk`
  connects through `pg_connect` and creates rollback-safe fixture tables for
  `graph_nodes`, `graph_node_revisions`, and `graph_edges`.
- [ ] **R2**: The live trial calls `agn-create-node`, then reads back the node
  and first revision snapshot.
- [ ] **R3**: The live trial calls `agn-update-node`, then reads back the
  updated node and verifies the per-node revision count reaches `2`.
- [ ] **R4**: The live trial inserts a fixture edge, calls `agn-delete-node`,
  and verifies both the target node and connected edge are gone.
- [ ] **R5**: The harness drops fixture tables and returns verdict `1111111`
  on a real execution pass.

## Research Inputs

- `form/form-stdlib/integration/pg-carrier-integration.fk` - existing Rust
  Postgres carrier proof pattern.
- `form/scripts/pg-carrier-test.sh` - existing throwaway Postgres harness.
- `form/form-stdlib/application-graph-node-port.fk` - native application graph
  mutation wrappers and SQL builders.
- `2026-06-08` - User direction: keep walking toward releasing the Python
  dependency rather than stopping at observation.

## Files to Create/Modify

- `form/form-stdlib/integration/application-graph-live-db.fk` - live DB trial.
- `form/scripts/application-graph-live-db-test.sh` - throwaway Postgres harness.
- `api/tests/test_application_graph_live_db_trial.py` - local proof.
- `docs/coherence-substrate/ideas-router.form` - ideas route state names the
  live DB trial.
- `docs/coherence-substrate/spec-registry-router.form` - spec route state names
  the live DB trial.
- `specs/native-graph-mutation-live-db-proof.md` - this contract.

## Acceptance Tests

- `api/tests/test_application_graph_live_db_trial.py::test_live_db_trial_form_uses_application_graph_pg_wrappers`
- `api/tests/test_application_graph_live_db_trial.py::test_live_db_trial_script_runs_or_skips_when_postgres_tooling_missing`
- `api/tests/test_application_graph_live_db_trial.py::test_route_forms_name_live_db_trial_before_public_flip`
- Manual validation: `form/scripts/application-graph-live-db-test.sh`

## Verification

```bash
form/scripts/application-graph-live-db-test.sh
cd api && python3 -m pytest -q tests/test_application_graph_live_db_trial.py tests/test_application_graph_node_port_form.py tests/test_native_mutation_ab_observation.py
python3 scripts/validate_spec_quality.py --file specs/native-graph-mutation-live-db-proof.md
```

## Out of Scope

- Production database writes.
- Ordinary public front-door mutation routing changes.
- Cache invalidation, parent/edge repair outside the deleted node edge cleanup,
  resonance re-attunement, or contributor-key audit updates.

## Gaps

- GAP-NGMLDB1: closed by `specs/native-mutation-response-projection.md`. Form
  now projects live mutation rows into `IdeaWithScore` and `SpecRegistryEntry`
  response shapes without FastAPI.
- GAP-NGMLDB2: closed by `specs/native-mutation-side-effects.md`. The native
  carrier now executes cache-invalidation receipt, parent-edge repair,
  contributor-key audit, and rollback receipt against throwaway Postgres.
- GAP-NGMLDB3: closed by `specs/native-mutation-route-side-effect-binding.md`.
  Native route runners now bind application graph mutation execution to
  side-effect execution in throwaway Postgres.
- GAP-NGMLDB4: closed by `specs/native-mutation-public-gate.md`. The public gate
  now carries route-local rollback receipt proof.
- GAP-NGMLDB5 follow-up task: `native-mutation-deployed-public-canary`. Deploy
  and observe the `X-Form-Native-Public-Gate` canary before any no-header flip.

## Risks and Assumptions

- The harness uses a throwaway local Postgres when available. In environments
  without `initdb`, it exits as SKIP rather than claiming live DB proof.
- The proof verifies application graph table effects, not complete route
  semantics.
- The public route still fans out to FastAPI by default.
