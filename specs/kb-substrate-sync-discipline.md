---
idea_id: knowledge-and-resonance
status: active
source:
  - file: scripts/coh_substrate.py
    symbols: [cmd_kb_sync_audit, cmd_ingest_paths]
  - file: docs/coherence-substrate/agents-tending-edges.md
    symbols: [Living Collective KB concept]
  - file: docs/vision-kb/SCHEMA.md
    symbols: [After Enrichment, Deepening a Concept]
requirements:
  - "Make KB/substrate drift visible for canonical Living Collective concepts."
  - "Give agents an add/update/delete practice for keeping substrate NamedCells current alongside KB markdown and DB sync."
  - "Name currently unmodeled KB surfaces so resources, transmissions, and language views do not disappear from awareness."
done_when:
  - "A substrate audit command reports missing, stale, path-drift, wrong-domain, and duplicate-id concept rows."
  - "The audit can prune reviewed stale or wrong-domain live NamedCells."
  - "KB/substrate guidance is documented in substrate and KB maintenance docs."
  - 'file_exists("scripts/coh_substrate.py")'
  - 'symbol_in_file("scripts/coh_substrate.py", "cmd_kb_sync_audit")'
  - 'symbol_in_file("scripts/coh_substrate.py", "cmd_ingest_paths")'
  - 'file_exists("docs/coherence-substrate/agents-tending-edges.md")'
  - 'symbol_in_file("docs/coherence-substrate/agents-tending-edges.md", "Living")'
  - 'file_exists("docs/vision-kb/SCHEMA.md")'
  - 'symbol_in_file("docs/vision-kb/SCHEMA.md", "After")'
  - 'symbol_in_file("docs/vision-kb/SCHEMA.md", "Deepening")'
test: "python3 -m py_compile scripts/coh_substrate.py && python3 scripts/coh_substrate.py kb-sync-audit --strict"
constraints:
  - "Do not add a new persistent table."
  - "Do not treat resources, transmissions, or language views as modeled substrate domains until a separate domain design lands."
  - "Keep pruning limited to live NamedCells; do not delete interned Blueprint or Recipe nodes."
---

# Spec: KB Substrate Sync Discipline

## Purpose

The Knowledge Base has three active surfaces: Markdown for human/agent editing, graph DB sync for runtime concept pages, and the coherence-substrate for structural grounding. Prior practice handled add/update for some cells but left delete hygiene and drift sensing implicit.

This spec adds a visible audit for canonical `docs/vision-kb/concepts/lc-*.md` files and documents the add/update/delete discipline so agents keep substrate cells current whenever they tend KB concepts.

## Requirements

- [ ] **R1**: Add `python3 scripts/coh_substrate.py kb-sync-audit` to compare canonical concept files with live substrate `@concept(...)` NamedCells.
- [ ] **R2**: Report missing concept cells, stale/deleted cells, path drift, wrong-domain ingests, and duplicate frontmatter ids.
- [ ] **R3**: Count language views, resources, and transmissions as unmodeled KB surfaces for awareness.
- [ ] **R4**: Support reviewed pruning with `--prune-stale`, limited to stale or wrong-domain live NamedCells.
- [ ] **R5**: Document add/update/delete substrate practice in substrate edge guidance and KB schema maintenance guidance.

## Research Inputs

- `2026-05-14` - `python3 scripts/coh_substrate.py kb-sync-audit` before pruning - surfaced one wrong-domain `memory/lc-sacred-imagination` row and no missing canonical concept cells.
- `2026-05-14` - `python3 scripts/coh_substrate.py kb-sync-audit --strict` after pruning - verified 114 canonical concept files, 114 substrate concept cells, and zero strict drift rows.

## Files to Create/Modify

- `scripts/coh_substrate.py` - add KB/substrate audit and reviewed stale-cell pruning.
- `docs/coherence-substrate/agents-tending-edges.md` - add KB concept substrate add/update/delete practice.
- `docs/coherence-substrate/INDEX.md` - document audit CLI and current boundary.
- `docs/vision-kb/SCHEMA.md` - add substrate sync to KB maintenance and deepening guidance.
- `specs/kb-substrate-sync-discipline.md` - this spec.
- `specs/INDEX.md` - regenerated spec index.
- `docs/system_audit/commit_evidence_2026-05-14_sacred_imagination_embodiment.json` - expanded proof artifact.
- `docs/system_audit/model_executor_runs.jsonl` - expanded proof record.

## Acceptance Tests

- Manual validation: `python3 -m py_compile scripts/coh_substrate.py`
- Manual validation: `python3 scripts/coh_substrate.py kb-sync-audit`
- Manual validation: `python3 scripts/coh_substrate.py kb-sync-audit --prune-stale`
- Manual validation: `python3 scripts/coh_substrate.py kb-sync-audit --strict`
- Manual validation: `python3 scripts/coh_substrate.py --json kb-sync-audit`
- Manual validation: `python3 scripts/validate_spec_quality.py --file specs/kb-substrate-sync-discipline.md`

## Verification

```bash
python3 -m py_compile scripts/coh_substrate.py
python3 scripts/coh_substrate.py kb-sync-audit
python3 scripts/coh_substrate.py kb-sync-audit --prune-stale
python3 scripts/coh_substrate.py kb-sync-audit --strict
python3 scripts/coh_substrate.py --json kb-sync-audit
python3 scripts/validate_spec_quality.py --file specs/kb-substrate-sync-discipline.md
```

## Out of Scope

- Adding substrate domains for resources, transmissions, or language views.
- Deleting interned substrate Blueprint or Recipe nodes.
- Changing the graph DB concept sync contract.

## Risks and Assumptions

- Risk: pruning could remove a live cell that should have been kept under a renamed path. Mitigation: pruning is opt-in and only follows an explicit audit display.
- Risk: agents may treat unmodeled KB surfaces as errors. Mitigation: the audit labels them as awareness, not strict drift.
- Assumption: canonical concept files are `docs/vision-kb/concepts/*.md` whose stem does not contain a language suffix.

## Known Gaps

- Resources, transmissions, and language views remain counted but unmodeled in the substrate. A later spec should decide whether these become distinct domains or projected views over concept/source cells.
- Follow-up: write a substrate domain design spec for resources, transmissions, and language views before modeling those KB surfaces as first-class cells.
