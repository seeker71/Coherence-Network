---
idea_id: knowledge-and-resonance
status: active
source:
  - file: api/app/services/frequency_profile_service.py
    symbols: [resolve_entity_id(), get_profile(), profile_hash()]
  - file: scripts/import_lineage.py
    symbols: [replay()]
requirements:
  - "Bare contributor ids resolve to existing contributor-prefixed graph nodes for profile endpoints."
  - "Lineage graph manifests can update nodes and replay explicit graph edges through API or CLI."
  - "Missing seeker71/Urs contribution context is represented as ordinary source-backed graph data."
done_when:
  - "python3 -m pytest -v api/tests/test_frequency_profile_contributor_alias.py passes"
  - "python3 -m pytest -v api/tests/test_import_lineage_edges.py passes"
  - "production GET /api/profile/seeker71 returns the derived contributor profile after deploy"
test: "python3 -m pytest -v api/tests/test_frequency_profile_contributor_alias.py api/tests/test_import_lineage_edges.py"
constraints:
  - "No person-specific profile UI branch."
  - "Do not change scoring weights; profile dimensions still emerge from graph data."
---

# Spec: Profile Contribution-Derived Data

## Purpose

Contributor frequency profiles must be derived from the same graph contribution data path for every contributor. The immediate failure is generic: browsers and profile links often carry a bare contributor id such as `seeker71`, while the graph profile source is stored as `contributor:seeker71`. If the profile endpoint cannot bridge those ordinary identity forms, any contributor with the same storage pattern can appear to have only generic or missing frequencies.

## Requirements

- [ ] **R1**: `GET /api/profile/{id}` resolves a bare contributor id to `contributor:{id}` when that graph node exists, without adding person-specific UI, person-specific scoring, or person-specific routing logic.
- [ ] **R2**: Profile dimensions continue to come from existing graph node properties, graph edges, and source text; this work must not hard-code frequencies or change profile weighting.
- [ ] **R3**: Lineage graph manifests replay explicit edges through `/api/graph/edges` so source-backed contribution records can be modified by API or CLI and then flow into structural profile dimensions.
- [ ] **R4**: Missing Urs/seeker71 context is represented as ordinary graph data with source paths, attribution metadata, domains, keywords, and contribution edges.

## Research Inputs

- `2026-05-06` - Production API check — `GET /api/profile/contributor:seeker71` returned a real graph-derived profile while `GET /api/profile/seeker71` did not.
- `2026-05-06` - `web/app/profile/[contributorId]/page.tsx` — graph node fetch already prefixes contributor ids, but frequency profile fetch used the raw id.
- `2026-05-06` - `docs/lineage/builders-lineage-statement.md` and `docs/lineage/ubud-embodied-lineage.md` — source-backed contribution and teaching context for the profile graph manifest.

## API Contract

### `GET /api/profile/{entity_id}`

If `{entity_id}` is a bare id and `contributor:{entity_id}` exists, the endpoint returns the prefixed contributor node profile.

**Response 200**
```json
{
  "entity_id": "contributor:seeker71",
  "dimensions": 1,
  "hash": "sha256-profile-hash",
  "top": []
}
```

## Data Model

```yaml
LineageManifest:
  presences:
    - id: string
      type: graph node type
      properties:
        source_artifact_id: string
        extraction_method: string
        ingestion_policy: string
  edges:
    - from_id: string
      to_id: string
      type: canonical graph edge type
      strength: number
      created_by: string
      properties: object
```

## Files to Create/Modify

- `api/app/services/frequency_profile_service.py` — generic contributor id resolution before profile derivation.
- `api/app/routers/graph.py` — return resolved entity ids consistently from profile surfaces.
- `api/tests/test_frequency_profile_contributor_alias.py` — API regression test for bare contributor ids.
- `api/tests/test_import_lineage_edges.py` — importer regression test for explicit edge replay.
- `scripts/import_lineage.py` — CLI/API replay updates existing nodes and posts manifest edges.
- `docs/lineage/urs-contribution-profile.graph.json` — ordinary source-backed contribution data manifest.
- `docs/system_audit/maintainability_baseline.json` — refreshed to the verified current `origin/main` maintainability state so this branch is not blocked by pre-existing drift.
- `docs/system_audit/commit_evidence_2026-05-06_profile_contribution_data.json` — required proof artifact.
- `docs/system_audit/model_executor_runs.jsonl` — model executor proof record.

## Acceptance Tests

- `api/tests/test_frequency_profile_contributor_alias.py::test_profile_accepts_bare_contributor_id_when_prefixed_node_exists`
- `api/tests/test_import_lineage_edges.py::test_import_lineage_replays_manifest_edges`
- Manual validation: dry-run `scripts/import_lineage.py` against `docs/lineage/urs-contribution-profile.graph.json` shows six presences and six edges.

## Verification

```bash
python3 -m pytest -v api/tests/test_frequency_profile_contributor_alias.py
python3 -m pytest -v api/tests/test_import_lineage_edges.py
python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json
python3 scripts/import_lineage.py docs/lineage/urs-contribution-profile.graph.json --api http://localhost:8000 --source contributor:seeker71 --dry-run
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-06_profile_contribution_data.json
```

## Out of Scope

- Replacing the current frequency scoring algorithm or changing weights.
- Adding a special Urs-only section to the profile UI.
- Migrating every historic contribution record in this change.

## Risks and Assumptions

- Existing callers may compare profile hashes between bare and prefixed ids; mitigation is to hash the resolved graph id so both forms converge.
- Public graph edge replay accepts only canonical edge types through the API; the manifest uses canonical edge types for deploy compatibility.
- The profile remains only as complete as the source-backed graph data that has been replayed into the target runtime.

## Known Gaps

- Follow-up task: add a broader identity alias registry if non-contributor entity types later need the same bare-id normalization.
- Follow-up task: replay additional historic contribution manifests after this generic path is deployed and verified.
