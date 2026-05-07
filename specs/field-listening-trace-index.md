# Field Listening Trace Index

## Purpose

Publish token-efficient listening trace indexes for Urs's field story so agents can answer month, author, and work influence questions without loading raw event streams.

## Requirements

- [x] Build a monthly frequency spectrum from `docs/field/urs/output/ten_year_events.jsonl`.
- [x] Interlink author and work records with stable IDs that month records can reference.
- [x] Provide compact API and MCP slices for month, author, and work questions.
- [x] Keep raw service archives, cookies, browser sessions, and extracted Takeout files out of the repo.

## Files To Modify

- `docs/field/urs/trace/README.md`
- `docs/field/urs/trace/manifest.json`
- `docs/field/urs/trace/monthly_spectrum.json`
- `docs/field/urs/trace/author_index.jsonl`
- `docs/field/urs/trace/work_index.jsonl`
- `docs/field/urs/tools/build_trace_indexes.py`
- `docs/field/urs/manifest.json`
- `api/app/services/field_story_service.py`
- `api/app/services/field_story_mcp_tools.py`
- `api/app/routers/field_stories.py`
- `api/tests/test_field_story_trace_index.py`
- `docs/system_audit/commit_evidence_2026-05-07_field_listening_trace_index.json`

## Acceptance Criteria

- `api/tests/test_field_story_trace_index.py` verifies manifest registration, API trace lookup, and MCP trace lookup.
- Month lookup returns one compact month object with primary influence, frequency spectrum, axes, and linked authors/works.
- Author and work lookup return compact monthly waves with the shared wave schema.

## Verification

```bash
python3 docs/field/urs/tools/build_trace_indexes.py --input docs/field/urs/output/ten_year_events.jsonl --output-dir docs/field/urs/trace
cd api && .venv/bin/pytest -q tests/test_field_story_trace_index.py
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-07_field_listening_trace_index.json
```

## Out Of Scope

- Raw Google Takeout archives, Audible exports, authenticated browser state, cookies, and extracted service files are not committed.
- This spec does not reclassify the source frequency rules beyond filtering generic platform shells from top influence links.

## Risks

- Source events with missing dates remain outside monthly spectrum answers until a dated source is available.
- Titles with identical names can resolve to the highest-event work when queried by title; linked work IDs remain exact.

## Known Gaps

- Follow-up task: add richer semantic classification once the frequency rules are revised beyond keyword bands.
