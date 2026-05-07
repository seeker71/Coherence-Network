# Urs Listening Trace Index

Compact derived indexes for answering influence questions without loading raw listening traces.

## Files

- `manifest.json` - coverage, thresholds, privacy boundary, and query shapes.
- `monthly_spectrum.json` - one object per `YYYY-MM` with frequency counts, axes, primary influence, and linked top authors/works.
- `author_index.jsonl` - one author per line with ID, name, top works, peak months, and compact monthly wave.
- `work_index.jsonl` - one work per line with ID, author link, peak months, and compact monthly wave.

## Query Flow

For "what was the primary influence during April 2026?", load:

```bash
jq '.months["2026-04"]' docs/field/urs/trace/monthly_spectrum.json
```

For "how did Mose move through the field?", load:

```bash
rg -m1 '"name":"Mose - Topic"|"name": "Mose - Topic"' docs/field/urs/trace/author_index.jsonl | jq .
```

For a work, resolve by title or use the linked ID from a month/author result:

```bash
rg -m1 '"title":"Naturaleza \\(Mose Edit\\)"|"title": "Naturaleza \\(Mose Edit\\)"' docs/field/urs/trace/work_index.jsonl | jq .
```

The wave arrays use:

```json
["month", "events", "pressure", "intensity", "inspiration", "insight", "vitality"]
```

## API and MCP

- Month slice: `/api/field-stories/urs-field-story/trace/month/2026-04`
- Author slice: `/api/field-stories/urs-field-story/trace/author/Mose%20-%20Topic`
- Work slice: `/api/field-stories/urs-field-story/trace/work/{work_id}`
- MCP tool: `get_field_story_trace` with `selector` set to `month`, `author`, or `work`.

## Rebuild

```bash
python3 docs/field/urs/tools/build_trace_indexes.py \
  --input docs/field/urs/output/ten_year_events.jsonl \
  --output-dir docs/field/urs/trace
```

Raw Google Takeout archives, Audible exports, browser sessions, cookies, and extracted service files stay outside the repo.
