---
idea_id: digital-influence-inventory
status: implemented
owners: [urs, agent:codex]
files:
  - file: docs/field/urs/tools/digital_influence_inventory.py
  - file: docs/field/urs/output/digital_influence_inventory.md
  - file: docs/field/urs/trace/digital_influence_inventory.json
  - file: docs/field/urs/manifest.json
  - file: api/tests/test_field_story_trace_index.py
acceptance:
  - "A repeatable tool inventories all currently available local digital-history source bodies without committing bulky raw exports."
  - "The field story manifest exposes both human-readable and machine-readable digital influence inventory artifacts."
  - "Tests verify the full YouTube history span, missing 2023/early-2024 attention, and publication language that allows watch/listen history to be public."
test: "cd api && .venv/bin/pytest -q tests/test_field_story_trace_index.py"
---

# Digital Influence Inventory

## Purpose

Map every digital-history source body already available locally so the field story can include the full shape of what entered the field, especially the YouTube history before the current published trace window.

## Context

The current published breath-cycle traces YouTube from `2024-05-07` through `2026-05-07`. Local Google Takeout archives contain a larger watch-history body from `2021-07-31` through `2026-05-07`, plus Audible captures, local browser events, Photos filenames, and project archives.

The contributor has explicitly allowed watch and listen history to be public. This artifact is compact because raw exports are large and awkward for agents, not because watch/listen history needs hiding.

## Requirements

- [x] Inventory local digital-history source files already present under `~/Downloads` and `~/CoherenceFieldAnalysis`.
- [x] Publish compact source counts, date spans, and top influence candidates.
- [x] Identify the missing YouTube history before `2024-05-07`.
- [x] Name high-signal 2023 and early-2024 influence waves that are not yet represented in the published breath-cycle.
- [x] Register the report, JSON trace, and builder in `docs/field/urs/manifest.json`.
- [x] Use publication, attention, and friction language in the generated inventory.

## Files To Modify

- `docs/field/urs/tools/digital_influence_inventory.py` builds the inventory.
- `docs/field/urs/output/digital_influence_inventory.md` is the human-readable report.
- `docs/field/urs/trace/digital_influence_inventory.json` is the machine-readable trace.
- `docs/field/urs/manifest.json` publishes the artifacts and builder.
- `api/tests/test_field_story_trace_index.py` verifies field-story API registration and key counts.

## Acceptance Criteria

- The builder emits Markdown and JSON from local digital-history source bodies.
- The manifest exposes `digital-influence-inventory`, `trace-digital-influence-inventory`, and `digital-influence-inventory-builder`.
- The API test proves the history-only YouTube Takeout has more than 60,000 events and that more than 10,000 2023 YouTube events are not yet represented in the current published trace.
- `api/tests/test_field_story_trace_index.py::test_digital_influence_inventory_registers_full_history_attention` passes.

## Known Gaps

- Follow-up breath: rebuild trace indexes from the full YouTube history-only Takeout, not only the two-year slice.
- Follow-up breath: clean unresolved `here` YouTube rows into real source categories where possible.
- Follow-up breath: deepen Photos and Gmail only when their source-specific shape is useful.

## Assumptions

- Contributor direction allows watch and listen history to be public.
- Bulky raw exports remain local source bodies in this pass so agents can work from compact traces efficiently.

## Non-Goals

- Do not write graph nodes from this inventory.
- Do not commit bulky raw exports in this compact pass.
- Do not parse image pixels or email bodies in this inventory.

## Validation

```bash
python3 docs/field/urs/tools/digital_influence_inventory.py --field-dir docs/field/urs
cd api && .venv/bin/pytest -q tests/test_field_story_trace_index.py
api/.venv/bin/ruff check api/tests/test_field_story_trace_index.py docs/field/urs/tools/digital_influence_inventory.py
```
