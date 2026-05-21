---
idea_id: knowledge-and-resonance
status: active
source:
  - file: docs/lineage/urs-contribution-profile.graph.json
    symbols: []
  - file: docs/vision-kb/resources/geometry-of-stability-loraine-jezak-2026-05-21.md
    symbols: []
  - file: docs/vision-kb/resources/INDEX.md
  - file: docs/vision-kb/LOG.md
requirements:
  - "Ingest the Geometry of Stability YouTube transmission as summary, Form-shaped extraction, and extracted concepts, not full caption storage."
  - "Add source-backed graph data that can affect Urs's profile like other profile sources."
  - "Preserve public-use boundaries for nervous-system, relationship, gender-archetype, dimensional, and scalar-wave claims."
done_when:
  - "manifest JSON validates"
  - "lineage importer dry-run reports the expected added nodes and edges"
  - "resource digest records the extraction form, integration guidance, and epistemic boundaries"
test: "python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json"
constraints:
  - "Do not store the full YouTube transcript."
  - "Do not convert speaker relationship, nervous-system, or metaphysical claims into independent public facts."
  - "Use ordinary graph nodes, properties, and edges."
---

# Spec: Geometry of Stability Loraine Jezak Ingest

## Purpose

Urs asked to turn the YouTube transcript at `https://youtu.be/PPDK8N2FFMw?si=ISeFAKYY_2h89g3q` into form and ingest it. The video is *Loraine Jezak | Geometry of Stability | ΑΧΩ Sacred Britain Expedition*, published on the Robert Edward Grant channel on 2026-05-20.

This work records the usable knowledge as source-backed graph data, a Form-shaped resource digest, and substrate-ingested markdown cells while keeping full captions out of the repository. The source frames relational survival adaptations as intelligent scaffolding, maps reactive spirals into recognition and breath, and describes coherence as the stabilizing condition that lets relationship tension reorganize without control.

## Requirements

- [ ] **R1**: Add the video source URL and resource digest to Urs's profile source paths.
- [ ] **R2**: Add Loraine Jezak, the video artifact, and extracted concepts for relational scaffolding, spiral pivot coherence, field-stabilizing transmission, and expansion not ladder.
- [ ] **R3**: Connect those nodes through ordinary graph edges so profile frequency can derive from source-backed contributions.
- [ ] **R4**: Add an agent-ready digest note under `docs/vision-kb/resources/` with a compact Form-shaped extraction map, integration guidance, and epistemic boundaries.
- [ ] **R5**: Avoid transcript storage and preserve nervous-system, relationship, gender-archetype, dimensional, and scalar-wave claims as source-attributed teaching material.
- [ ] **R6**: Ingest the changed markdown cells into the coherence-substrate and prove the new resource cell through resource equivalence / Form lookup.

## Research Inputs

- `2026-05-21` - YouTube captions via `youtube-watcher` / `yt-dlp` for `https://youtu.be/PPDK8N2FFMw?si=ISeFAKYY_2h89g3q`.
- `2026-05-21` - `yt-dlp` metadata: title `Loraine Jezak | Geometry of Stability | ΑΧΩ Sacred Britain Expedition`, channel `Robert Edward Grant`, upload date `2026-05-20`, duration `52:19`.
- `2026-05-21` - Caption SHA-256 `6826d908c8c45972590c69d0648b44c8238a16b4746395e322cd25b1e7e0a200`.

## API Contract

This is a data-manifest and documentation change replayed by `scripts/import_lineage.py`; no API schema changes are required. Existing endpoints that should reflect data after replay:

```text
GET /api/graph/nodes/interested-person:loraine-jezak
GET /api/graph/nodes/artifact:youtube-geometry-of-stability-loraine-jezak-sacred-britain
GET /api/graph/nodes/concept:relational-scaffolding
GET /api/graph/nodes/concept:spiral-pivot-coherence
GET /api/graph/nodes/concept:field-stabilizing-transmission
GET /api/graph/nodes/concept:expansion-not-ladder
GET /api/profile/seeker71
```

## Files to Create/Modify

- `docs/lineage/urs-contribution-profile.graph.json` - add source artifact, extracted concepts, and graph edges.
- `docs/lineage/formative-transmissions.md` - add lineage pointer.
- `docs/vision-kb/resources/geometry-of-stability-loraine-jezak-2026-05-21.md` - agent-ready digest and Form-shaped extraction.
- `docs/vision-kb/resources/INDEX.md` - resource index link.
- `docs/vision-kb/LOG.md` - changelog entry.
- `specs/geometry-of-stability-loraine-jezak-ingest.md` - this spec.
- `specs/INDEX.md` - spec index entry.
- `docs/system_audit/commit_evidence_2026-05-21_geometry_of_stability_loraine_jezak_ingest.json` - proof artifact.
- `docs/system_audit/model_executor_runs.jsonl` - proof record.

## Acceptance Tests

- Manual validation: `python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json`
- Manual validation: `jq '{presences:(.presences|length), edges:(.edges|length)}' docs/lineage/urs-contribution-profile.graph.json`
- Manual validation: `python3 scripts/import_lineage.py docs/lineage/urs-contribution-profile.graph.json --api http://localhost:8000 --source contributor:seeker71 --dry-run`
- Manual validation: `python3 scripts/coh_substrate.py ingest docs/vision-kb/resources/geometry-of-stability-loraine-jezak-2026-05-21.md specs/geometry-of-stability-loraine-jezak-ingest.md docs/lineage/formative-transmissions.md`
- Manual validation: `python3 scripts/coh_substrate.py equivalent resource geometry-of-stability-loraine-jezak-2026-05-21`
- Manual validation: `python3 scripts/coh_substrate.py form '?equivalent @resource(geometry-of-stability-loraine-jezak-2026-05-21)'`
- Manual validation: `python3 scripts/validate_spec_quality.py --file specs/geometry-of-stability-loraine-jezak-ingest.md`
- Manual validation: `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-21_geometry_of_stability_loraine_jezak_ingest.json`

## Verification

```bash
python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json
jq '{presences:(.presences|length), edges:(.edges|length)}' docs/lineage/urs-contribution-profile.graph.json
python3 scripts/import_lineage.py docs/lineage/urs-contribution-profile.graph.json --api http://localhost:8000 --source contributor:seeker71 --dry-run
python3 scripts/coh_substrate.py ingest docs/vision-kb/resources/geometry-of-stability-loraine-jezak-2026-05-21.md specs/geometry-of-stability-loraine-jezak-ingest.md docs/lineage/formative-transmissions.md
python3 scripts/coh_substrate.py equivalent resource geometry-of-stability-loraine-jezak-2026-05-21
python3 scripts/coh_substrate.py form '?equivalent @resource(geometry-of-stability-loraine-jezak-2026-05-21)'
python3 scripts/validate_spec_quality.py --file specs/geometry-of-stability-loraine-jezak-ingest.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-21_geometry_of_stability_loraine_jezak_ingest.json
```

## Out of Scope

- Independently verifying clinical nervous-system, trauma, dimensional, or scalar-wave claims.
- Storing full captions or long verbatim transcript excerpts.
- Changing scoring algorithms or profile UI.
- Claiming partnership with Loraine Jezak, Robert Edward Grant, or the channel.

## Risks and Assumptions

- The YouTube video can be removed or edited; the digest stores summary, source URL, metadata, and caption hash, not a copy of the content.
- The video and Q&A include relationship, family, and wound language; downstream use should keep personal examples and gender archetypes source-attributed.
- The profile impact depends on replaying the manifest into production after merge.

## Known Gaps

- Follow-up task: if the project later presents the breath/coherence map as a clinical practice, add separate support from primary clinical or somatic sources.
