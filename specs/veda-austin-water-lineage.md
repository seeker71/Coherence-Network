---
idea_id: knowledge-and-resonance
status: active
source:
  - file: docs/lineage/urs-contribution-profile.graph.json
    symbols: [presences, edges]
requirements:
  - "Represent Veda Austin as ordinary source-backed profile graph data, not special UI."
  - "Represent the Gaia Open Minds episode as an artifact with summary-only extracted concepts."
  - "Connect the trusted researcher, episode artifact, and water-as-record-keeper concept to the contributor profile graph."
done_when:
  - "manifest JSON validates"
  - "lineage importer dry-run reports the expected nodes and edges"
  - "production profile shows the added source-backed water lineage after replay"
test: "python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json"
constraints:
  - "Do not store transcript text or long Gaia page excerpts."
  - "Use ordinary graph nodes, properties, and edges."
---

# Spec: Veda Austin Water Lineage

## Purpose

Urs identified Veda Austin as a researcher he fully trusts and pointed to the Gaia episode `Water: Akashic Record Keeper?` as knowledge that belongs in the profile graph. This should enter the same contribution-derived profile path as other teachings, so the trust signal and water-intelligence concepts can affect frequencies through graph data rather than bespoke rendering.

## Requirements

- [ ] **R1**: Add Veda Austin as an ordinary source-backed graph presence with a trust attestation from `contributor:seeker71`.
- [ ] **R2**: Add the Gaia episode as an artifact node using summary-only metadata from the public page: title, series, episode, duration, host, featuring, URL, domains, and keywords.
- [ ] **R3**: Add `concept:water-as-record-keeper` as a reusable extracted concept connected to the Gaia artifact and to the existing embodied-lineage source concept.
- [ ] **R4**: Connect `contributor:seeker71` to Veda Austin through canonical graph edges so the profile service can derive structural resonance without special-case UI.

## Research Inputs

- `2026-05-06` - Gaia public page — `Water: Akashic Record Keeper?`, Open Minds S30:E4, 47 minutes, hosted by Regina Meredith and featuring Veda Austin.
- `2026-05-06` - User attestation — Veda Austin is another researcher Urs fully trusts.

## API Contract

This is a data-manifest change replayed by `scripts/import_lineage.py`; no API schema changes are required. Existing endpoints that should reflect the data after replay:

```text
GET /api/graph/nodes/interested-person:veda-austin
GET /api/graph/nodes/artifact:gaia-water-akashic-record-keeper
GET /api/graph/nodes/concept:water-as-record-keeper
GET /api/profile/seeker71
```

## Data Model

```yaml
TrustedResearcherNode:
  id: interested-person:veda-austin
  type: interested-person
  trust_attestation:
    attested_by: contributor:seeker71
    attestation: researcher fully trusted by Urs
ArtifactNode:
  id: artifact:gaia-water-akashic-record-keeper
  type: artifact
  canonical_url: https://www.gaia.com/video/water-akashic-record-keeper
ConceptNode:
  id: concept:water-as-record-keeper
  type: concept
```

## Files to Create/Modify

- `docs/lineage/urs-contribution-profile.graph.json` — add Veda Austin, the Gaia episode artifact, water-as-record-keeper concept, and graph edges.
- `specs/veda-austin-water-lineage.md` — this spec.
- `docs/system_audit/commit_evidence_2026-05-06_veda_austin_water_lineage.json` — proof artifact.
- `docs/system_audit/model_executor_runs.jsonl` — proof record.

## Acceptance Tests

- Manual validation: `python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json`
- Manual validation: `python3 scripts/import_lineage.py docs/lineage/urs-contribution-profile.graph.json --api http://localhost:8000 --source contributor:seeker71 --dry-run`
- Manual validation after deploy: production graph nodes and profile include Veda Austin / water-as-record-keeper dimensions.

## Verification

```bash
python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json
python3 scripts/import_lineage.py docs/lineage/urs-contribution-profile.graph.json --api http://localhost:8000 --source contributor:seeker71 --dry-run
python3 scripts/validate_spec_quality.py --file specs/veda-austin-water-lineage.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-06_veda_austin_water_lineage.json
```

## Out of Scope

- Scraping or storing Gaia transcript/full video content.
- Adding person-specific UI rendering.
- Changing frequency profile scoring or edge weighting algorithms.

## Risks and Assumptions

- Gaia page metadata may change; the manifest stores only the currently verified public page summary and URL.
- Trust is represented as Urs's attestation, not as an objective endorsement claim by the system.
- The profile impact depends on replaying the manifest into production after merge.

## Known Gaps

- Follow-up task: add a dedicated public page for Veda Austin if the people/profile content layer needs a human-readable researcher page.
