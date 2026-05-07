---
idea_id: influence-breath-cycle
status: implemented
owners: [urs, agent:codex]
files:
  - file: docs/field/urs/tools/influence_breath_cycle.py
  - file: docs/field/urs/output/influence_breath_cycle.md
  - file: docs/field/urs/trace/influence_breath_cycle.json
  - file: docs/field/urs/manifest.json
  - file: api/tests/test_field_story_trace_index.py
acceptance:
  - "A repeatable tool reads derived YouTube/Audible/browser trace indexes and writes a compact influence breath-cycle summary."
  - "The field story manifest exposes both human-readable and machine-readable breath-cycle artifacts."
  - "Tests verify the YouTube source count, unroomed influence candidates, and all trace links emitted in the report."
test: "cd api && .venv/bin/pytest -q tests/test_field_story_trace_index.py"
---

# Influence Breath Cycle

## Purpose

Walk the influence field in repeated, efficient breaths so agents and humans can sense what is already held, what still wants a room, and where the YouTube history has high-signal influence waves that should not be lost in raw event volume.

## Context

The field story already publishes compact monthly, author, work, significant-work, and concept indexes. Those indexes make precise questions cheap, but they do not yet give a single awareness loop for the next pass through the field.

YouTube history is especially large: the derived event trace contains tens of thousands of `youtube-takeout` events, plus MyActivity and YouTube Music traces. Loading the raw stream is wasteful and private. The right shape is a compact breath-cycle artifact derived from existing indexes.

## Requirements

- [x] Read only published derived artifacts, not raw Takeout archives, cookies, authenticated browser state, or paid text.
- [x] Emit a JSON summary with source counts, already-roomed authors, unroomed author candidates, unroomed work candidates, strongest monthly waves, and next actions.
- [x] Emit a Markdown report that is easy for a human to scan and easy for an agent to follow through trace links.
- [x] Register both artifacts in `docs/field/urs/manifest.json`.
- [x] Register the builder tool in the manifest so the breath can be rerun after future Takeout/Audible/browser imports.
- [x] Verify all emitted trace links resolve through the field story API.

## Files To Modify

- `docs/field/urs/tools/influence_breath_cycle.py` builds the compact awareness artifact.
- `docs/field/urs/output/influence_breath_cycle.md` is the human-readable breath-cycle report.
- `docs/field/urs/trace/influence_breath_cycle.json` is the machine-readable breath-cycle summary.
- `docs/field/urs/manifest.json` publishes the report, summary, and builder as field story artifacts.
- `api/tests/test_field_story_trace_index.py` verifies registration, source counts, unroomed candidates, and generated trace links.

## Acceptance Criteria

- The builder emits both Markdown and JSON from the derived field story trace indexes.
- The manifest exposes `influence-breath-cycle`, `trace-influence-breath-cycle`, and `influence-breath-cycle-builder`.
- `api/tests/test_field_story_trace_index.py` proves the YouTube-derived source count is present and follows all generated trace links.

## Risks

- A generated timestamp changes when the breath is rerun. This is acceptable for a generated awareness artifact, but commits should rerun once immediately before validation.
- Some artist names may be platform shells or aliases. The cycle marks candidates, not final story rooms.
- Frequency classification still inherits current analyzer vocabulary; unclassified candidates may need later reclassification.

## Known Gaps

- Follow-up task: add native Google Photos metadata when a connector or Takeout image index is available.
- Follow-up task: add exact chapter-level book links after lawful chapter notes or summaries exist.
- Follow-up task: merge Gmail and Calendar discoveries through a connector-derived anchor input.

## Non-Goals

- Do not publish raw Google Takeout archives or extracted browser files.
- Do not claim exact chapter-level book links without lawful chapter notes or summaries.
- Do not promote every candidate into the chronological story automatically; the cycle names candidates for the next discerning breath.

## Validation

```bash
python3 docs/field/urs/tools/influence_breath_cycle.py --field-dir docs/field/urs
cd api && .venv/bin/pytest -q tests/test_field_story_trace_index.py
api/.venv/bin/ruff check tests/test_field_story_trace_index.py ../docs/field/urs/tools/influence_breath_cycle.py
```
