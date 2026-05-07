# Urs Listening Trace Index

Compact derived indexes for answering influence questions without loading raw listening traces.

## Files

- `manifest.json` - coverage, thresholds, publication shape, and query flows.
- `monthly_spectrum.json` - one object per `YYYY-MM` with frequency counts, axes, primary influence, and linked top authors/works.
- `author_index.jsonl` - one author per line with ID, name, top works, peak months, and compact monthly wave.
- `work_index.jsonl` - one work per line with ID, author link, peak months, and compact monthly wave.
- `significant_work_index.jsonl` - one significant formative work/series per line with impact basis, linked vision concepts, children titles, and chapter-discovery probes.
- `concept_work_map.json` - concept-first lookup from `lc-*` vision concepts to significant works and probe terms.
- `audible_history_spectrum.json` - Audible-specific source-body trace with duration-weighted monthly influence.
- `audible_duration_metadata.json` - compact Audible catalog runtime metadata used to weight Audible influence by listening duration or book length.
- `../output/chronological_story_with_frequency.md` - narrative story with direct links back into significant-work, author, and concept trace slices.

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

For a formative work or series, resolve by title, alias, or ID:

```bash
rg -m1 '"title":"Spellmonger Universe"|"aliases":.*"Spellmonger"' docs/field/urs/trace/significant_work_index.jsonl | jq .
```

For "which works relate to `lc-network`?", load:

```bash
jq '.concepts["lc-network"]' docs/field/urs/trace/concept_work_map.json
```

For reading the story and opening each influence as it appears, use:

```bash
rg '/api/field-stories/urs-field-story/trace' docs/field/urs/output/chronological_story_with_frequency.md
```

The wave arrays use:

```json
["month", "events", "pressure", "intensity", "inspiration", "insight", "vitality"]
```

## API and MCP

- Month slice: `/api/field-stories/urs-field-story/trace/month/2026-04`
- Author slice: `/api/field-stories/urs-field-story/trace/author/Mose%20-%20Topic`
- Work slice: `/api/field-stories/urs-field-story/trace/work/{work_id}`
- Significant work slice: `/api/field-stories/urs-field-story/trace/significant-work/Spellmonger`
- Concept slice: `/api/field-stories/urs-field-story/trace/concept/lc-network`
- MCP tool: `get_field_story_trace` with `selector` set to `month`, `author`, `work`, `significant-work`, or `concept`.

## Chapter Discovery Boundary

The significant-work index can answer concept-to-work questions now. It does not claim exact chapter matches until chapter notes, table of contents, or legally available chapter text have been ingested.

Each significant-work record includes:

- `concept_links` - why the work resonates with a vision concept.
- `chapter_probe_terms` - efficient search terms for chapter notes/text.
- `deep_discovery.needs_for_exact_chapters` - the minimum source material needed to make exact chapter links.
- `deep_discovery.chapter_links` - the future slot for exact book/chapter/concept evidence.

Example flow for "which chapter in which Spellmonger book relates to `lc-network`?":

```bash
curl https://api.coherencycoin.com/api/field-stories/urs-field-story/trace/concept/lc-network
curl https://api.coherencycoin.com/api/field-stories/urs-field-story/trace/significant-work/Spellmonger
```

Then search only the Spellmonger chapter notes/text for the `lc-network` probe terms: `Sevendor`, `mageland`, `vassal`, `duchy`, `supply`, `alliance`, `market`.

## Rebuild

```bash
python3 docs/field/urs/tools/build_trace_indexes.py \
  --input docs/field/urs/output/ten_year_events.jsonl \
  --output-dir docs/field/urs/trace
```

Raw Google Takeout archives, Audible exports, browser sessions, cookies, and extracted service files remain source bodies until their shape belongs directly in repo.
