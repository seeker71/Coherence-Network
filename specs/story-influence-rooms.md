---
idea_id: story-influence-rooms
status: draft
priority: high
source:
  - file: docs/field/urs/output/chronological_story_with_frequency.md
  - file: docs/field/urs/anchors/influence_anchors.json
  - file: docs/field/urs/anchors/manual_reading_anchors.json
  - file: docs/lineage/urs-contribution-profile.graph.json
  - file: api/tests/test_field_story_agent_surface.py
requirements:
  - "Chronological story includes a linked room for each known significant work, primary listening author, and named influence anchor."
  - "All trace links embedded in the story resolve through the field-story API router."
  - "Non-trace influence rooms link to existing people pages, presence notes, lineage notes, or anchor artifacts."
done_when:
  - "Story readers can reach works, authors, teachers, practices, and trusted research from the story itself."
  - "Tests verify every embedded trace API link resolves."
test: "cd api && .venv/bin/pytest -q tests/test_field_story_agent_surface.py tests/test_field_story_trace_index.py"
constraints:
  - "Do not add raw private archives or authenticated service state."
  - "Keep exact chapter claims out until chapter notes or lawful chapter summaries exist."
---

# Spec: Story Influence Rooms

## Purpose

Give the chronological story enough linked space for the people, practices, authors, books, series, and research currents that shaped the field, without bloating the chronological flow or forcing readers to hunt through raw traces.

## Requirements

- [ ] Add a linked `Influence Rooms` section to `chronological_story_with_frequency.md`.
- [ ] Include all significant-work trace slices and the main state-carrier author trace slices already known to the field story.
- [ ] Include linked rooms for named teachers, researchers, practices, people pages, presence notes, and lineage evidence.
- [ ] Add tests that verify required rooms are present and every embedded trace API link resolves.

## Files To Modify

- `docs/field/urs/output/chronological_story_with_frequency.md`
- `api/tests/test_field_story_agent_surface.py`
- `specs/story-influence-rooms.md`
- `docs/system_audit/commit_evidence_2026-05-07_story_influence_rooms.json`

## Acceptance Criteria

`api/tests/test_field_story_agent_surface.py` verifies required influence-room links and follows all embedded `/api/field-stories/urs-field-story/trace/...` links through the API router. `api/tests/test_field_story_trace_index.py` continues to verify significant-work trace lookup behavior.

## Verification

```bash
cd api && .venv/bin/pytest -q tests/test_field_story_agent_surface.py tests/test_field_story_trace_index.py
api/.venv/bin/ruff check api/tests/test_field_story_agent_surface.py api/tests/test_field_story_trace_index.py
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-07_story_influence_rooms.json
```

## Out Of Scope

- No new runtime API selector is added.
- No raw Google Takeout archives, Audible exports, cookies, or authenticated browser state are committed.

## Risks

- Long story link sections can become visually heavy, so this change keeps the chronological flow intact and places the catalog in a dedicated room.
- Some influences are evidence-backed by manual anchors rather than trace counts; the story labels them through existing anchor and lineage artifacts.

## Known Gaps

- Follow-up task: add exact chapter/work passage links only after lawful chapter notes, table-of-contents data, or summaries are available.
