---
idea_id: knowledge-and-resonance
status: active
source:
  - file: docs/lineage/urs-contribution-profile.graph.json
    symbols: [presences, edges]
  - file: docs/vision-kb/resources/orion-architect-sovereign-ai-2026-05-06.md
    symbols: [Executive Summary, Epistemic Note]
requirements:
  - "Ingest the ORION Architect YouTube video as summary and extracted concepts, not full caption storage."
  - "Add source-backed graph data that can affect Urs's profile like other profile sources."
  - "Preserve claim boundaries for cryptography, platform security, and quantum-timeline assertions."
done_when:
  - "manifest JSON validates"
  - "lineage importer dry-run reports the expected added nodes and edges"
  - "resource digest records integration guidance and epistemic boundaries"
test: "python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json"
constraints:
  - "Do not store the full YouTube transcript."
  - "Do not convert speaker technical claims into verified facts."
  - "Use ordinary graph nodes, properties, and edges."
---

# Spec: ORION Architect Sovereign AI Digest

## Purpose
Urs asked to ingest and digest the YouTube video `https://youtu.be/SPWo2D1Ue60`. The video features Robert Edward Grant presenting ORION Architect as a sovereign AI platform and describes platform sovereignty, post-quantum-security claims, progressive web app distribution, non-extractive economics, and AI as a mirror.

This work records the usable knowledge as source-backed graph data and a vision-kb resource digest while keeping technical security claims explicitly bounded as speaker claims unless separately verified.

## Requirements
- [ ] **R1**: Add the video source URL to Urs's profile source paths.
- [ ] **R2**: Add Robert Edward Grant, the video artifact, and extracted concepts for sovereign AI architecture, non-extractive AI platforms, and AI as sovereign mirror.
- [ ] **R3**: Connect those nodes through ordinary graph edges so profile frequency can derive from source-backed contributions.
- [ ] **R4**: Add an agent-ready digest note under `docs/vision-kb/resources/` with integration guidance and epistemic boundaries.
- [ ] **R5**: Avoid transcript storage and preserve all cryptography/security/quantum claims as attributed source claims.

## Research Inputs
- `2026-05-06` - YouTube captions via `youtube-watcher` for `https://youtu.be/SPWo2D1Ue60`.
- `2026-05-06` - `yt-dlp` metadata: title `Robert Edward Grant ORION Architect: Sovereign AI, Quantum Security & End of Big Tech Control [PT 1]`, channel `Soma Flow: Somatic Biogeometric Harmonics`.

## API Contract
This is a data-manifest and documentation change replayed by `scripts/import_lineage.py`; no API schema changes are required. Existing endpoints that should reflect data after replay:

```text
GET /api/graph/nodes/interested-person:robert-edward-grant
GET /api/graph/nodes/artifact:youtube-orion-architect-sovereign-ai-part-1
GET /api/graph/nodes/concept:sovereign-ai-architecture
GET /api/graph/nodes/concept:non-extractive-ai-platform
GET /api/graph/nodes/concept:ai-as-sovereign-mirror
GET /api/profile/seeker71
```

## Files to Create/Modify
- `docs/lineage/urs-contribution-profile.graph.json` - add source artifact, extracted concepts, and graph edges.
- `docs/vision-kb/resources/orion-architect-sovereign-ai-2026-05-06.md` - agent-ready digest.
- `docs/vision-kb/resources/INDEX.md` - resource index link.
- `docs/vision-kb/LOG.md` - changelog entry.
- `specs/orion-architect-sovereign-ai-digest.md` - this spec.
- `docs/system_audit/commit_evidence_2026-05-06_orion_architect_sovereign_ai_digest.json` - proof artifact.
- `docs/system_audit/model_executor_runs.jsonl` - proof record.

## Acceptance Tests
- Manual validation: `python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json`
- Manual validation: `python3 scripts/import_lineage.py docs/lineage/urs-contribution-profile.graph.json --api http://localhost:8000 --source contributor:seeker71 --dry-run`
- Manual validation: `python3 scripts/validate_spec_quality.py --file specs/orion-architect-sovereign-ai-digest.md`
- Manual validation: `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-06_orion_architect_sovereign_ai_digest.json`

## Verification
```bash
python3 -m json.tool docs/lineage/urs-contribution-profile.graph.json >/tmp/urs_manifest_validated.json
jq '{presences:(.presences|length), edges:(.edges|length)}' docs/lineage/urs-contribution-profile.graph.json
python3 scripts/import_lineage.py docs/lineage/urs-contribution-profile.graph.json --api http://localhost:8000 --source contributor:seeker71 --dry-run
python3 scripts/validate_spec_quality.py --file specs/orion-architect-sovereign-ai-digest.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-06_orion_architect_sovereign_ai_digest.json
```

## Out of Scope
- Verifying ORION's cryptographic implementation.
- Storing full captions or long verbatim transcript excerpts.
- Changing scoring algorithms or profile UI.
- Claiming partnership with Robert Edward Grant or ORION.

## Risks and Assumptions
- The YouTube video can be removed or edited; the digest stores summary and source URL, not a copy of the content.
- Technical claims around quantum security and platform compromise are high-impact and must remain speaker-attributed until independently verified.
- The profile impact depends on replaying the manifest into production after merge.

## Known Gaps
- Follow-up task: independently verify any cryptography/security claims before presenting them as technical facts.
