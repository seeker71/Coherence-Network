---
idea_id: story-frequency-influence-interlinks
status: draft
priority: high
source:
  - file: docs/field/urs/output/chronological_story_with_frequency.md
  - file: docs/field/urs/tools/build_trace_indexes.py
    symbols: [SIGNIFICANT_WORK_RULES, build_significant_work_indexes()]
  - file: api/tests/test_field_story_agent_surface.py
  - file: api/tests/test_field_story_trace_index.py
requirements:
  - "Chronological story links significant works and main listening authors directly to trace API slices."
  - "Childhood frontier works present in the story are included in the significant-work index."
  - "Tests preserve the story links and significant-work trace records."
done_when:
  - "The chronological story includes direct trace links for significant works and primary listening authors."
  - "Karl May stories and Der Lederstrumpf resolve through the significant-work selector."
test: "cd api && .venv/bin/pytest -q tests/test_field_story_agent_surface.py tests/test_field_story_trace_index.py"
constraints:
  - "Do not claim exact chapter matches until chapter notes or lawful chapter summaries exist."
  - "Keep raw private listening archives and authenticated service state out of the repo."
---

# Spec: Story Frequency Influence Interlinks

## Purpose

Make the chronological story easier to navigate as a living influence map by linking each significant work and primary author mention back to compact trace slices, so readers and agents can move from story to evidence without loading raw private archives.

## Requirements

- [ ] Add direct significant-work links in `chronological_story_with_frequency.md` for the formative books and systems-fiction series that shaped the field.
- [ ] Add direct author trace links for the recurring listening authors that carried devotional-body and state-regulation waves.
- [ ] Add Karl May stories and Der Lederstrumpf to the generated significant-work index with authors, aliases, concepts, and probe terms.
- [ ] Add tests that fail if the story loses the trace links or if the childhood frontier works stop resolving through the API selector.

## Files To Modify

- `docs/field/urs/output/chronological_story_with_frequency.md`
- `docs/field/urs/tools/build_trace_indexes.py`
- `docs/field/urs/trace/README.md`
- `docs/field/urs/trace/significant_work_index.jsonl`
- `docs/field/urs/trace/concept_work_map.json`
- `docs/field/urs/trace/manifest.json`
- `docs/field/urs/trace/monthly_spectrum.json`
- `api/tests/test_field_story_agent_surface.py`
- `api/tests/test_field_story_trace_index.py`
- `docs/system_audit/commit_evidence_2026-05-07_story_frequency_interlinks.json`

## Acceptance Criteria

`api/tests/test_field_story_agent_surface.py` verifies the story contains direct significant-work and author trace links. `api/tests/test_field_story_trace_index.py` verifies Karl May stories and Der Lederstrumpf resolve through `/api/field-stories/urs-field-story/trace/significant-work/{value}`.

## Verification

```bash
python3 docs/field/urs/tools/build_trace_indexes.py --input docs/field/urs/output/ten_year_events.jsonl --output-dir docs/field/urs/trace
cd api && .venv/bin/pytest -q tests/test_field_story_agent_surface.py tests/test_field_story_trace_index.py
api/.venv/bin/ruff check docs/field/urs/tools/build_trace_indexes.py api/tests/test_field_story_agent_surface.py api/tests/test_field_story_trace_index.py
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-07_story_frequency_interlinks.json
```

## Out Of Scope

- Exact chapter-to-concept answers are not added in this change.
- Raw Google Takeout, Audible exports, browser sessions, cookies, and paid book text are not committed.

## Risks

- Story links can become stale if trace selectors change, so tests pin the expected paths.
- Manual concept mappings for childhood works are motif-level scaffolding and must not be presented as chapter-level proof.

## Known Gaps

- Follow-up task: ingest lawful chapter notes or tables of contents for linked significant works and upgrade selected links from work-level discovery to exact chapter evidence.
