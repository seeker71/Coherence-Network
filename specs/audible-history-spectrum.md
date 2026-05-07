---
idea_id: audible-history-spectrum
status: implemented
owners: [urs, agent:codex]
files:
  - file: docs/field/urs/tools/audible_history_spectrum.py
  - file: docs/field/urs/output/audible_history_spectrum.md
  - file: docs/field/urs/trace/audible_history_spectrum.json
  - file: docs/field/urs/manifest.json
  - file: api/tests/test_field_story_trace_index.py
acceptance:
  - "The field-story manifest exposes an Audible-specific report, JSON trace, and builder."
  - "The trace includes library, purchase, and visible listen-history row counts and monthly author/series/work waves."
  - "API tests verify Ryk Brown and the source counts from the captured Audible body."
test: "cd api && .venv/bin/pytest -q tests/test_field_story_trace_index.py"
---

# Audible History Spectrum

## Purpose

Build a first-class Audible-specific spectrum from the source bodies already captured locally. The older digital inventory counted Audible rows, but it did not give agents an efficient way to ask which Audible author, work, or series was active during a given month or how a specific author moved through the field.

## Requirements

- [x] Inventory every local Audible source body currently captured under `~/CoherenceFieldAnalysis/input/audible/playwright`.
- [x] Distinguish library holdings, 2016-2026 purchase history, and visible web listen history in the trace.
- [x] Build monthly influence slices with top authors, works, series, frequency labels, and axis totals.
- [x] Build author, series, and title waves with the standard `month/events/pressure/intensity/inspiration/insight/vitality` shape.
- [x] Register the report, JSON trace, and builder in `docs/field/urs/manifest.json`.
- [x] Name the remaining source-body shape clearly: Audible web exposes visible listen-history rows, while the per-title mobile Listening Log remains app-shaped.

## Files To Modify

- `docs/field/urs/tools/audible_history_spectrum.py` builds the spectrum.
- `docs/field/urs/output/audible_history_spectrum.md` is the human-readable report.
- `docs/field/urs/trace/audible_history_spectrum.json` is the machine-readable trace.
- `docs/field/urs/manifest.json` publishes the artifacts and builder.
- `api/tests/test_field_story_trace_index.py` verifies field-story API registration and key counts.

## Acceptance Criteria

- `api/tests/test_field_story_trace_index.py::test_audible_history_spectrum_registers_captured_history_waves` passes.
- The trace reports exactly 233 library rows, 198 purchase rows, and 50 visible listen-history rows.
- The trace includes at least 80 monthly slices and an author wave for Ryk Brown with 92 Audible events.

## Known Gaps

- Follow-up task: if the Audible mobile Listening Log can be exported later, merge those per-title listen events into this same spectrum rather than creating a separate trace.
- Follow-up task: add chapter-level notes only where legally available notes or table-of-contents data exist.

## Non-Goals

- Do not commit raw Audible auth state or browser sessions.
- Do not claim mobile-only per-title listen logs were captured when they were not visible from the current web source body.

## Assumptions

- Contributor direction allows Audible listening and purchase history to be public.
- Purchase date is treated as the date a work entered the field; visible listen-history date is treated as an explicit listening touch.

## Validation

```bash
python3 docs/field/urs/tools/audible_history_spectrum.py --field-dir docs/field/urs
cd api && .venv/bin/pytest -q tests/test_field_story_trace_index.py
api/.venv/bin/ruff check api/tests/test_field_story_trace_index.py docs/field/urs/tools/audible_history_spectrum.py
python3 scripts/validate_spec_quality.py --file specs/audible-history-spectrum.md
```
