---
idea_id: living-lineage
status: active
source:
  - file: docs/field/urs/tools/build_trace_indexes.py
    symbols: [compact_volume(), influence_spectrum(), backtrace_samples(), build_indexes()]
  - file: docs/field/urs/trace/manifest.json
    symbols: [field_event_shape]
  - file: api/tests/test_field_story_trace_index.py
    symbols: [test_trace_index_api_returns_author_and_work_waves()]
requirements:
  - "Field trace slices expose richer event shape than counts alone."
  - "Public trace slices include influence spectrum, volume, source mix, and public-safe backtrace samples."
  - "Missing duration is backfilled from existing event traces before it is reported as unknown."
  - "Backtraces link events to month, author, and work trace slices without exposing raw private source bodies."
done_when:
  - "Author, work, and month trace records carry volume, influence_spectrum, source_mix, and backtrace_samples."
  - "The field-story trace API test proves rich fields and duration backfill are present on an author and work slice."
  - "Generated trace manifest documents the richer field_event_shape."
test: "cd api && /Users/ursmuff/source/Coherence-Network/api/.venv/bin/pytest -q tests/test_field_story_trace_index.py"
constraints:
  - "Keep raw source bodies private; publish derived movement and compact backtrace references only."
  - "Do not add cross-device or identity matching."
---

# Spec: Field Event Rich Trace Shape

## Purpose

Field event counts are only an entry point. The public field traces need to show movement: when a presence moved, how much volume was visible, what frequency bands and axes were active, which sources carried the movement, and how an agent can follow a compact backtrace when a deeper trace exists.

This keeps the public surface useful for sensing resonance while staying privacy-light. We publish derived shape and trace links, not raw personal source bodies.

## Requirements

- [x] **R1**: Month, author, and work trace records include `volume`, covering event count, known duration where available, duration coverage, and axis energy.
- [x] **R2**: Month, author, and work trace records include `influence_spectrum`, covering frequency distribution, axis totals, dominant frequency, and dominant axis.
- [x] **R3**: Month, author, and work trace records include `source_mix`, covering source, platform, and evidence counts.
- [x] **R4**: Dated events with missing duration are backfilled from existing event traces by YouTube video id, then author/work, then work title when the source trace carries duration.
- [x] **R5**: Month, author, and work trace records include `backtrace_samples` with event id, source line, evidence, timestamp, frequency, axes, URL host, duration backfill source, and trace links to month, author, and work slices.
- [x] **R6**: The trace manifest documents the public field event shape and its publication boundary.

## Data Model

```yaml
FieldTraceRecord:
  events: integer
  volume:
    events: integer
    known_duration_seconds: integer
    known_duration_hours: number
    duration_event_count: integer
    backfilled_duration_event_count: integer
    axis_energy: integer
  influence_spectrum:
    frequencies: [[name, count]]
    axes: {pressure, intensity, inspiration, insight, vitality}
    dominant_frequency: string | null
    dominant_axis: string | null
  source_mix:
    sources: object
    platforms: object
    evidence: object
  backtrace_samples:
    - event_id: string
      source_line: integer
      duration_backfill: object | null
      trace_links: {month, author, work}
```

## Files to Modify

- `docs/field/urs/tools/build_trace_indexes.py` — build richer trace fields and duration backfill.
- `docs/field/urs/trace/manifest.json` — document the public field event shape.
- `docs/field/urs/trace/monthly_spectrum.json` — regenerated month trace records.
- `docs/field/urs/trace/author_index.jsonl` — regenerated author trace records.
- `docs/field/urs/trace/work_index.jsonl` — regenerated work trace records.
- `docs/field/urs/trace/concept_work_map.json` — regenerated timestamp alignment.
- `api/tests/test_field_story_trace_index.py` — API proof for rich trace fields.

## Acceptance Tests

- `api/tests/test_field_story_trace_index.py::test_trace_index_api_returns_author_and_work_waves`
- Manual validation: inspect the Mose author trace and confirm duration is backfilled from an existing MyActivity trace without publishing raw source bodies.

## Verification

```bash
python3 docs/field/urs/tools/build_trace_indexes.py --input docs/field/urs/output/ten_year_events.jsonl --output-dir docs/field/urs/trace
cd api && /Users/ursmuff/source/Coherence-Network/api/.venv/bin/pytest -q tests/test_field_story_trace_index.py
```

## Out of Scope

- Cross-device matching.
- Publishing raw Google Takeout, browser, Audible, cookie, or session bodies.
- Claiming exact causal influence from correlation alone.

## Risks and Assumptions

- Backfilled duration can be wrong if two different works share the same title; the builder prefers YouTube video id first to keep the strongest match where available.
- Frequency and axis values remain derived signals, not proof of direct causation.

## Known Gaps

- Follow-up task: expose richer trace shape in the home presence cards and trace detail UI once the API data is published.
- Follow-up task: add source-body row hash references to each backtrace sample when the ingestion layer carries per-row hashes directly.
