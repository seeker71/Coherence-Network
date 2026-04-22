---
idea_id: knowledge-and-resonance
status: done
source:
  - file: api/app/models/graph.py
    symbols: [Node, Edge, NodeType, CanonicalEdgeType]
  - file: api/app/routers/sensings.py
    symbols: [SensingCreate, create_sensing(), list_sensings()]
  - file: api/app/services/graph_service.py
    symbols: [create_provenance_edge(), validate_source_edge_provenance()]
  - file: api/app/services/frequency_profile_service.py
    symbols: [get_profile(), resonance(), profile_hash()]
  - file: api/app/config/edge_types.py
    symbols: [CANONICAL_EDGE_TYPES, EDGE_TYPE_FAMILIES]
  - file: api/tests/test_source_artifact_sensing_graph.py
    symbols: [source artifact sensing graph tests]
requirements:
  - "Source artifacts are first-class graph nodes, separate from extracted concepts and product work."
  - "Every inferred semantic edge carries provenance, confidence, and ingestion policy metadata."
  - "External copyrighted sources are ingested as summaries, hashes, and extracted concepts only."
  - "Extracted concepts connect to existing ideas, specs, tasks, implementations, and measurements through canonical edge types."
done_when:
  - "POST /api/sensings with source metadata creates provenance-rich analogous-to edges."
  - "Graph service rejects incomplete inferred-edge provenance."
  - "Frequency profiles expose source-backed and ingestion-policy dimensions."
  - "Source artifact sensing graph tests pass."
test: "cd api && .venv/bin/pytest -q tests/test_source_artifact_sensing_graph.py"
constraints:
  - "No schema migration in this spec."
  - "No full transcript or copyrighted source body committed to the repo."
  - "Use existing graph nodes, graph edges, sensings, and frequency profiles."
---

# Spec: Source Artifact Sensing Graph Integration

## Purpose

Make any meaningful external source usable by the Coherence graph without adding source-specific database structures. A transcript, paper, GitHub issue, news article, meeting note, failed CI log, or user interview should enter the same graph as an artifact, a sensing event, extracted concepts, provenance-rich semantic edges, and optional downstream idea/spec/task work. This prevents inspirational or strategic source material from becoming disconnected prose while keeping copyrighted or private source bodies out of the repository.

## Requirements

- [ ] **R1**: Ingest source material as `type="artifact"` nodes with metadata, source hash, rights policy, and a summary-only ingestion contract.
- [ ] **R2**: Record every ingestion pass as a `type="event"` sensing node with `sensing_kind`, summary, extraction method, related targets, and source artifact reference.
- [ ] **R3**: Represent extracted meanings as ordinary `type="concept"` nodes, never as custom node types tied to one source, author, practice, or domain.
- [ ] **R4**: Connect artifacts, sensings, concepts, ideas, specs, tasks, implementations, and measurements using canonical edge types from the existing graph vocabulary.
- [ ] **R5**: Require provenance on every inferred edge: `source_artifact_id`, `sensing_id`, `extraction_method`, `confidence`, `ingestion_policy`, and short rationale.
- [ ] **R6**: Ensure frequency profile and resonance computation can use the resulting graph through existing properties, content summaries, concept tags, and neighborhoods.

## Research Inputs

- `2026-04-19` - Peace Bathing session transcript and summary PDF at `/Users/ursmuff/Downloads/20260419_Transcript___Summary_Peace_Bathing_Session_04_19_26.pdf` - motivating source artifact for the first concrete ingestion pattern; use summary and extracted concepts only.
- `2026-04-21` - User architecture direction in this thread - requested deep graph node/edge integration and the most abstract generic design possible.
- `2026-04-21` - `api/app/models/graph.py` - existing universal node and edge model with typed nodes, typed edges, properties, phase, and strength.
- `2026-04-21` - `api/app/routers/sensings.py` - existing pattern for storing moments of noticing as graph event nodes.
- `2026-04-21` - `api/app/services/frequency_profile_service.py` - existing profile and resonance layer that computes from properties, content, node type, phase, and graph neighborhood.

## API Contract

No new public API is required for the first implementation. The first slice should use the existing graph and sensing endpoints:

```bash
POST /api/graph/nodes
POST /api/graph/edges
POST /api/sensings
GET /api/profile/{entity_id}
POST /api/resonance
```

Future convenience endpoints may wrap these primitives, but they must remain adapters over the universal graph.

## Data Model

```yaml
SourceArtifactNode:
  type: artifact
  id: artifact-{stable-source-slug}
  name: string
  description: short summary
  properties:
    artifact_kind: transcript_summary_pdf | paper | issue | news_item | meeting_note | ci_log | interview | other
    source_uri: string
    source_sha256: string
    rights: internal | public | external_copyrighted_source | private
    ingestion_policy: summary_and_extracted_concepts_only | full_text_allowed | metadata_only
    observed_at: ISO-8601 timestamp
    language: string

SensingEventNode:
  type: event
  id: sensing-{stable-source-slug}-{timestamp}
  properties:
    sensing_kind: wandering | skin | breath | integration
    source: local_pdf_ingestion | api_ingestion | agent_review | human_review
    summary: string
    content: summary or reflection, not restricted source body
    source_artifact_id: string
    extraction_method: manual_summary | llm_summary | parser | human_review
    related_to: list[node_id]
    metadata:
      extracted_concept_ids: list[string]
      quote_policy: no_full_text_republication | short_excerpt_allowed | full_text_allowed

ExtractedConceptNode:
  type: concept
  id: concept-{generic-slug}
  name: string
  description: reusable concept definition
  properties:
    domains: list[string]
    keywords: list[string]
    concept_tags: list[string]
    source_count: integer

ProvenanceEdgeProperties:
  source_artifact_id: string
  sensing_id: string
  extraction_method: manual_summary | llm_summary | parser | human_review
  confidence: number
  ingestion_policy: string
  rationale: short explanation of why the edge exists
```

The motivating Peace Bathing source should instantiate this generic shape as an artifact node, one sensing event, and concept nodes such as `concept-source-spark`, `concept-gestational-field`, `concept-release-as-freedom`, and `concept-belonging-gravity`. Those concepts are examples, not schema additions.

## Files to Create/Modify

- `specs/source-artifact-sensing-graph-integration.md` - generic source artifact, sensing, concept, and provenance graph contract.
- `api/app/routers/sensings.py` - validates source-backed sensing metadata and creates provenance-rich edges when source artifact metadata is present.
- `api/app/services/graph_service.py` - validates and creates provenance-rich inferred edges.
- `api/app/services/frequency_profile_service.py` - exposes source-backed, ingestion-policy, and extraction-method dimensions from node and edge metadata.
- `api/tests/test_source_artifact_sensing_graph.py` - artifact, sensing, edge provenance, and profile behavior tests.

## Acceptance Tests

- `api/tests/test_source_artifact_sensing_graph.py::test_source_artifact_sensing_creates_provenance_edge_and_profile`
- `api/tests/test_source_artifact_sensing_graph.py::test_provenance_edge_helper_rejects_incomplete_metadata`
- Manual validation: confirm the Peace Bathing PDF is referenced only by path and summary intent, with no full transcript body committed.

## Verification

```bash
cd api && .venv/bin/pytest -q tests/test_source_artifact_sensing_graph.py
cd api && .venv/bin/pytest -q tests/test_concept_story_crud.py tests/test_knowledge_resonance.py
cd api && /opt/homebrew/bin/ruff check app/services/graph_service.py app/routers/sensings.py app/services/frequency_profile_service.py tests/test_source_artifact_sensing_graph.py
python3 scripts/validate_spec_quality.py --file specs/source-artifact-sensing-graph-integration.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-04-22_source-artifact-sensing-graph.json
```

## Out of Scope

- Adding a schema migration or new graph tables.
- Publishing, copying, or storing full external transcript text.
- Adding a dedicated Peace Bathing feature surface.
- Changing resonance scoring weights before implementation tests exist.
- Replacing existing idea, spec, task, or sensing endpoints.

## Risks and Assumptions

- Risk: `properties` can become an untyped dumping ground; mitigate by validating artifact, sensing, and provenance payload shapes in implementation tests.
- Risk: concept extraction can overfit to one source; mitigate by keeping extracted concepts generic and connecting source-specific language through provenance metadata.
- Risk: copyrighted material can leak into repo or public API responses; mitigate with `ingestion_policy`, source hashes, summaries, and explicit quote policy.
- Assumption: the existing graph service remains the source of truth for concepts, events, artifacts, ideas, specs, tasks, and measurements.
- Assumption: profile and resonance services can consume added graph neighborhoods without new storage primitives.

## Known Gaps and Follow-up Tasks

- Follow-up task: add a source ingestion script that extracts summaries and concept candidates from local files without storing restricted full text.
- Follow-up task: add a convenience ingestion endpoint or CLI wrapper if repeated source ingestion becomes common.
