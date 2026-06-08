---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/application-graph-response-projection.fk
    symbols: [agrp-idea-with-score-json, agrp-spec-entry-json, agrp-project-idea-row, agrp-project-spec-row, agrp-free-energy-score, agrp-marginal-cc-score]
  - file: form/form-stdlib/tests/application-graph-response-projection-band.fk
    symbols: []
  - file: form/form-stdlib/integration/application-graph-response-projection-live.fk
    symbols: []
  - file: form/scripts/application-graph-response-projection-test.sh
    symbols: []
  - file: api/tests/test_application_graph_response_projection.py
    symbols: [test_response_projection_names_idea_and_spec_response_shapes, test_response_projection_band_executes_across_sibling_kernels, test_response_projection_live_db_script_runs_or_skips_when_pg_missing, test_route_forms_name_response_projection_before_public_flip]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
requirements:
  - "Form-native projection emits IdeaWithScore-shaped JSON from graph row values without calling FastAPI or idea_service."
  - "Form-native projection emits SpecRegistryEntry-shaped JSON from graph row values without calling FastAPI or spec_registry_service."
  - "The projection computes free_energy_score, marginal_cc_score, remaining cost, value gap, ROI, cost vectors, and value vectors from row fields."
  - "A live DB harness creates graph rows through the Form application graph mutation carrier, reads them back through pg_query, and projects both response shapes."
  - "The proof does not perform the public front-door flip or claim side-effect parity."
done_when:
  - 'file_exists("form/form-stdlib/application-graph-response-projection.fk")'
  - 'file_exists("form/scripts/application-graph-response-projection-test.sh")'
  - 'pytest_passes("api/tests/test_application_graph_response_projection.py")'
test: "form/scripts/application-graph-response-projection-test.sh && cd api && python3 -m pytest -q tests/test_application_graph_response_projection.py"
constraints:
  - "Use a throwaway local PostgreSQL database or caller-supplied test DSN only."
  - "Do not execute against the production application database."
  - "Do not move ordinary public mutation traffic in this slice."
  - "Do not claim cache invalidation, parent/edge side effects, resonance re-attunement, or contributor-key audit updates are complete."
---

# Spec: Native Mutation Response Projection

## Purpose

The live DB proof showed that Form-native mutation wrappers can write and read
application graph rows. This spec proves the next response boundary: those rows
can be projected into the public mutation response shapes without returning to
Python service code.

## Requirements

- [ ] **R1**: `application-graph-response-projection.fk` defines an
  `IdeaWithScore` projection with scalar fields, status/stage mapping, vectors,
  and scoring fields.
- [ ] **R2**: The same module defines a `SpecRegistryEntry` projection with
  spec identity, summary fields, ROI fields, contributor ids, timestamps, source
  path, hash, and workspace id.
- [ ] **R3**: Tab-separated rows from `pg_query` can be parsed into numeric and
  string fields in Form without `str_to_float` or Rust-only formatting.
- [ ] **R4**: The sibling-kernel band returns verdict `111` for idea projection,
  spec projection, and row projection.
- [ ] **R5**: The live harness returns verdict `111111` after creating graph
  rows, reading them back, projecting both response shapes, and cleaning up.

## Research Inputs

- `api/app/models/idea.py` - `IdeaWithScore` response fields.
- `api/app/models/spec_registry.py` - `SpecRegistryEntry` response fields.
- `api/app/services/idea_scoring.py` - scoring and vector formulas.
- `api/app/services/spec_registry_service.py` - graph node to spec projection.
- `specs/native-graph-mutation-live-db-proof.md` - previous live DB execution
  proof.
- `2026-06-08` - User direction: keep walking toward releasing the Python
  dependency rather than stopping at observation.

## Files to Create/Modify

- `form/form-stdlib/application-graph-response-projection.fk` - response
  projection recipes.
- `form/form-stdlib/tests/application-graph-response-projection-band.fk` -
  three-kernel projection band.
- `form/form-stdlib/integration/application-graph-response-projection-live.fk`
  - live DB projection integration.
- `form/scripts/application-graph-response-projection-test.sh` - throwaway
  Postgres harness.
- `api/tests/test_application_graph_response_projection.py` - repository proof.
- `docs/coherence-substrate/ideas-router.form` - ideas route state.
- `docs/coherence-substrate/spec-registry-router.form` - spec route state.
- `specs/native-mutation-response-projection.md` - this contract.

## Acceptance Tests

- `api/tests/test_application_graph_response_projection.py::test_response_projection_names_idea_and_spec_response_shapes`
- `api/tests/test_application_graph_response_projection.py::test_response_projection_band_executes_across_sibling_kernels`
- `api/tests/test_application_graph_response_projection.py::test_response_projection_live_db_script_runs_or_skips_when_pg_missing`
- `api/tests/test_application_graph_response_projection.py::test_route_forms_name_response_projection_before_public_flip`
- Manual validation: `form/scripts/application-graph-response-projection-test.sh`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-response-projection.fk form-stdlib/tests/application-graph-response-projection-band.fk
form/scripts/application-graph-response-projection-test.sh
cd api && python3 -m pytest -q tests/test_application_graph_response_projection.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-response-projection.md
```

## Out of Scope

- Production database writes.
- Ordinary public front-door mutation routing changes.
- Cache invalidation, parent/edge repair outside the live mutation wrapper's
  delete edge cleanup, resonance re-attunement, or contributor-key audit
  updates.

## Gaps

- GAP-NMRP1 follow-up task: `native-mutation-side-effects`. Carry route cache,
  parent/edge repair, resonance, and contributor-key audit side effects natively.
- GAP-NMRP2 follow-up task: `native-mutation-public-flip-gate`. Add a reversible
  public flip gate only after side effects pass.

## Risks and Assumptions

- The projection emits JSON-shaped strings for native response proof. It does
  not yet bind those strings to the ordinary public mutation routes.
- The live harness uses throwaway Postgres when available. In environments
  without `initdb`, it exits as SKIP rather than claiming live DB proof.
- The response projection mirrors current model/service formulas; future Python
  formula changes must update this Form carrier or the parity test should fail.
