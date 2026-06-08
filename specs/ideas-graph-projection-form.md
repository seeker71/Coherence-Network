---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/ideas-graph-projection.fk
    symbols: []
  - file: form/form-stdlib/tests/ideas-graph-projection-band.fk
    symbols: []
  - file: form/form-stdlib/graph-node-port.fk
    symbols: []
  - file: deploy/kernel-router/production-routes.fk
    symbols: []
  - file: api/app/models/idea.py
    symbols: [IdeaPortfolioResponse, IdeaWithScore, IdeaSummary, PaginationInfo]
  - file: api/tests/test_ideas_graph_projection_form.py
    symbols: [test_ideas_graph_projection_declares_schema_functions, test_ideas_graph_projection_emits_required_idea_with_score_fields, test_ideas_graph_projection_band_proves_memory_file_and_reopen, test_ideas_graph_projection_is_bound_as_native_manifest_preview_route]
requirements:
  - "Form projects graph-node envelopes into an IdeaPortfolioResponse-shaped JSON body."
  - "The projection filters graph nodes to type=idea through graph-node-port list semantics."
  - "A Form band proves the projection over memory and durable file carriers."
  - "The production kernel-router manifest binds a fixture-backed native preview route that returns the same portfolio response shape."
done_when:
  - 'file_exists("form/form-stdlib/ideas-graph-projection.fk")'
  - 'file_contains("form/form-stdlib/ideas-graph-projection.fk", "defn igp-portfolio-json")'
  - 'file_contains("form/form-stdlib/tests/ideas-graph-projection-band.fk", "Band verdict: 11111")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "(list \"/api/ideas/graph-projection\"    route_ideas_graph_projection)")'
  - 'pytest_passes("api/tests/test_ideas_graph_projection_form.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/cell-log-store.fk form-stdlib/storage-port.fk form-stdlib/storage-port-file.fk form-stdlib/graph-node-port.fk form-stdlib/ideas-graph-projection.fk form-stdlib/tests/ideas-graph-projection-band.fk"
constraints:
  - "Do not change existing /api/ideas response behavior in this slice."
  - "Bind only a fixture-backed native preview route until a live graph storage carrier is available."
  - "Keep the projection layered on graph-node-port, not a parallel Python adapter."
---

# Spec: Ideas Graph Projection in Form

## Purpose

Graph-node functions are now visible in Form, but native ideas reads also need
schema projection. This spec adds the missing projection layer: a graph-node
envelope becomes an `IdeaPortfolioResponse`-shaped JSON body with ideas,
summary, and pagination. It proves the shape over the same storage carriers as
the graph-node port, binds a fixture-backed kernel-router preview route for the
same response shape, and preserves the live FastAPI `/api/ideas` behavior.

## Requirements

- [ ] **R1**: `form/form-stdlib/ideas-graph-projection.fk` declares `igp-field`, `igp-idea-json`, `igp-portfolio-json-from-nodes`, and `igp-portfolio-json`.
- [ ] **R2**: The projection reads ideas through `gn-list-nodes carrier store "idea"` so non-idea graph nodes do not enter the portfolio response.
- [ ] **R3**: The idea JSON includes the required `IdeaWithScore` fields with conservative defaults when graph properties are absent.
- [ ] **R4**: The summary JSON carries `total_ideas`, `unvalidated_ideas`, `validated_ideas`, and value totals.
- [ ] **R5**: The proof band runs the projection over memory and durable file carriers, then reopens the file carrier to prove persistence.
- [ ] **R6**: `deploy/kernel-router/production-routes.fk` binds `/api/ideas/graph-projection` to a native fixture-backed preview handler that emits the same portfolio response shape.

## Research Inputs

- `2026-06-08` - User confirmation to continue moving toward Form-native graph reads.
- `form/form-stdlib/graph-node-port.fk` - carrier-agnostic graph-node get/list/count port.
- `api/app/models/idea.py` - `IdeaPortfolioResponse`, `IdeaWithScore`, `IdeaSummary`, and `PaginationInfo` field requirements.
- `api/app/services/idea_graph_adapter.py` - current Python projection from graph nodes into ideas.

## Files to Create/Modify

- `form/form-stdlib/ideas-graph-projection.fk` - Form graph-node-to-idea read projection.
- `form/form-stdlib/tests/ideas-graph-projection-band.fk` - memory/file/reopen proof.
- `deploy/kernel-router/production-routes.fk` - native fixture-backed graph projection route.
- `api/tests/test_ideas_graph_projection_form.py` - repository-level contract proof.
- `docs/coherence-substrate/INDEX.md` - substrate map entry.
- `docs/coherence-substrate/ideas-router.form` - gap wording updated from schema projection to route binding.
- `specs/ideas-graph-projection-form.md` - this contract.

## Acceptance Tests

- `api/tests/test_ideas_graph_projection_form.py::test_ideas_graph_projection_declares_schema_functions`
- `api/tests/test_ideas_graph_projection_form.py::test_ideas_graph_projection_emits_required_idea_with_score_fields`
- `api/tests/test_ideas_graph_projection_form.py::test_ideas_graph_projection_band_proves_memory_file_and_reopen`
- `api/tests/test_ideas_graph_projection_form.py::test_ideas_graph_projection_is_bound_as_native_manifest_preview_route`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/cell-log-store.fk form-stdlib/storage-port.fk form-stdlib/storage-port-file.fk form-stdlib/graph-node-port.fk form-stdlib/ideas-graph-projection.fk form-stdlib/tests/ideas-graph-projection-band.fk
cd form/form-kernel-rust && ./target/release/form-kernel-rust serve --host 127.0.0.1 --port 19184 --workers 1 --routes ../../deploy/kernel-router/production-routes.fk --stdlib ../form-stdlib --upstream http://127.0.0.1:9
curl -i http://127.0.0.1:19184/api/ideas/graph-projection
cd api && python3 -m pytest -q tests/test_ideas_graph_projection_form.py
python3 scripts/validate_spec_quality.py --file specs/ideas-graph-projection-form.md
```

## Out of Scope

- Changing public `/api/ideas` behavior.
- Binding live DB-backed `/api/ideas` traffic to the kernel-router preview route.
- Parsing every optional graph-node property into the public schema.

## Gaps

- GAP-IGP1 follow-up task: `ideas-live-graph-storage-carrier`. The projection
  is bound into the production route manifest through fixture rows; the follow-up
  replaces the fixture with live graph storage when the carrier is available.
- GAP-IGP2 follow-up task: `ideas-graph-property-json-projection`. Optional
  graph-node properties still emit conservative defaults.

## Risks and Assumptions

- Conservative defaults keep the response schema valid without claiming full
  parity with Python scoring.
- `phase` maps to `manifestation_status` as `ice=validated`, `water=partial`,
  and all other values `none`, matching the current graph adapter direction.
