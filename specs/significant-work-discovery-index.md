---
idea_id: significant-work-discovery-index
status: draft
priority: high
source:
  - file: docs/field/urs/tools/build_trace_indexes.py
    symbols: [SIGNIFICANT_WORK_RULES, build_significant_work_indexes()]
  - file: api/app/services/field_story_service.py
    symbols: [get_field_story_trace_slice()]
  - file: api/app/services/field_story_mcp_tools.py
    symbols: [get_field_story_trace()]
requirements:
  - "Significant works are indexed as compact discovery records with aliases, authors, child works, concept links, probe terms, and source boundaries."
  - "Vision concepts can return the works most related to them without loading the full listening event stream."
  - "API and MCP trace selectors expose significant-work and concept discovery slices."
done_when:
  - "GET /api/field-stories/urs-field-story/trace/significant-work/Spellmonger returns Spellmonger Universe with concept links and child works."
  - "GET /api/field-stories/urs-field-story/trace/concept/lc-network returns related significant works and probe terms."
test: "cd api && .venv/bin/pytest -q tests/test_field_story_trace_index.py"
constraints:
  - "Do not claim exact chapter matches until chapter-level source material is present."
  - "Do not include raw Google Takeout archives, Audible files, cookies, or private browser session data in the repo."
---

# Spec: Significant Work Discovery Index

## Purpose

Make the works that shaped the field discoverable in a compact, source-grounded way so agents and people can ask which books, series, authors, and concepts are resonating without loading the full personal event stream or inventing unsupported chapter-level evidence.

## Requirements

- [ ] Add significant work records for the high-impact books and series named in the field story, including `Spellmonger`, `Daemon`, `Ringworld`, `The Expanse`, `Kingkiller Chronicle`, `Sword of Truth`, `First Law`, `Frontiers Saga`, `Viridian Gate`, `Momo`, `Die unendliche Geschichte`, and Peter F. Hamilton systems fiction.
- [ ] Link each significant work to vision concept ids, chapter probe terms, and source boundaries that distinguish evidence-backed series/work discovery from not-yet-evidence-backed exact chapter claims.
- [ ] Generate `significant_work_index.jsonl` and `concept_work_map.json` from local source artifacts so CLI, API, MCP, and future agents can use compact slices.
- [ ] Expose `significant-work` and `concept` trace selectors through the field story API and MCP tool schema.

## Files To Modify

- `docs/field/urs/tools/build_trace_indexes.py`
- `docs/field/urs/trace/significant_work_index.jsonl`
- `docs/field/urs/trace/concept_work_map.json`
- `docs/field/urs/trace/manifest.json`
- `docs/field/urs/trace/README.md`
- `docs/field/urs/manifest.json`
- `api/app/services/field_story_service.py`
- `api/app/services/field_story_mcp_tools.py`
- `api/tests/test_field_story_trace_index.py`
- `docs/system_audit/commit_evidence_2026-05-07_significant_work_discovery_index.json`

## Acceptance Criteria

`api/tests/test_field_story_trace_index.py` covers the significant-work selector, concept selector, API behavior, and MCP tool dispatch for the new discovery indexes.

## Verification

```bash
python3 docs/field/urs/tools/build_trace_indexes.py --input docs/field/urs/output/ten_year_events.jsonl --output-dir docs/field/urs/trace
cd api && .venv/bin/pytest -q tests/test_field_story_trace_index.py
api/.venv/bin/ruff check docs/field/urs/tools/build_trace_indexes.py api/app/services/field_story_service.py api/app/services/field_story_mcp_tools.py api/tests/test_field_story_trace_index.py
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-07_significant_work_discovery_index.json
```

## Out Of Scope

- Raw private listening archives, cookies, browser sessions, and paid audiobook content are not committed.
- Exact chapter-to-concept answers are not claimed until chapter notes, tables of contents, or legally available chapter text are ingested.

## Risks

- Manual concept mappings can overfit if they are treated as final ontology instead of editable discovery scaffolding.
- Chapter probe terms are useful for guided discovery but can be mistaken for proof if the precision boundary is not shown clearly.

## Known Gaps

- Follow-up task: ingest lawful chapter-level notes or tables of contents for the significant works, then upgrade matching from guided probes to evidence-backed chapter links.
