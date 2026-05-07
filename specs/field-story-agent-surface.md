---
idea_id: profile-contribution-derived-data
status: implemented
priority: high
source:
  - file: docs/field/urs/manifest.json
  - file: api/app/services/field_story_service.py
  - file: api/app/routers/field_stories.py
  - file: api/app/services/mcp_tool_registry.py
  - file: mcp-server/coherence_mcp_server/server.py
  - file: web/app/field/urs/page.tsx
requirements:
  - "Publish the curated local field story, anchors, reports, summaries, and analyzer scripts into the repo."
  - "Expose story artifacts through API endpoints so agents can read canonical narrative, anchors, spectrum, and reports."
  - "Allow API-submitted field story contributions to record attribution in the contribution ledger."
  - "Expose MCP tools for agents to read story artifacts and submit contributed corrections or additions."
  - "Publish a web surface with view tracking so attention can flow back to source contribution records."
done_when:
  - "GET /api/field-stories/urs-field-story returns the canonical story and artifact manifest."
  - "GET /api/field-stories/urs-field-story/artifacts/<id> returns individual markdown/json/text artifacts."
  - "POST /api/field-stories/urs-field-story/contributions records a source contribution id."
  - "MCP registry exposes get_field_story, get_field_story_artifact, and contribute_field_story."
  - "The /field/urs web route renders the field story and tracks page reads."
test: "cd api && .venv/bin/pytest -q tests/test_field_story_agent_surface.py"
constraints:
  - "Do not publish raw Google Takeout zips, extracted HTML, browser cookies, or private authenticated source exports."
  - "Keep raw input traces local; publish curated artifacts, summaries, and analyzers only."
  - "Story corrections must keep source attribution and not overwrite the canonical source silently."
---

# Spec: Field Story Agent Surface

## Purpose

The personal field analysis must become a Coherence Network substrate that multiple agents can inspect and improve through the same surfaces as other source-backed contributions.

The repo holds the canonical published artifacts. The API exposes them as structured resources. MCP exposes the same API to external agents. The web route makes the story viewable and sends read pings so views can credit source contributions.

## Requirements

- [x] **R1**: Publish curated local field story artifacts, anchors, reports, summaries, and analyzer scripts while excluding raw Google Takeout archives, extracted private exports, cookies, and browser data.
- [x] **R2**: Expose story metadata, individual artifacts, frequency spectrum data, and submitted corrections through API endpoints under `/api/field-stories`.
- [x] **R3**: Expose equivalent MCP tools so external agents can read canonical story context and submit attributed contributions through the API.
- [x] **R4**: Publish a web route for the field story that participates in existing read attribution and contribution feedback flows.

## Research Inputs

- `2026-05-07` - Local field analysis workspace — curated story, listening analysis, influence anchors, meeting/event anchors, and contribution-derived profile data.
- `2026-05-07` - Coherence Network contribution ledger — source attribution model used for submitted field story corrections.

## API Contract

### `GET /api/field-stories`

Returns available published field stories and their artifact manifests.

### `GET /api/field-stories/{slug}`

Returns one field story manifest, canonical story artifact, frequency bands, and grouped artifacts.

### `GET /api/field-stories/{slug}/artifacts/{artifact_id}`

Returns one markdown, JSON, JSONL, text, or Python artifact by manifest id.

### `GET /api/field-stories/{slug}/spectrum`

Returns frequency bands and anchor summaries for one field story.

### `POST /api/field-stories/{slug}/contributions`

Records an attributed correction, addition, or insight and returns the source contribution id.

## Data Model

```yaml
FieldStory:
  slug: string
  title: string
  summary: string
  canonical_story_artifact: string
  artifacts: list[FieldStoryArtifact]
  frequency_bands: list[FieldStoryFrequencyBand]

FieldStoryContribution:
  contributor_id: string
  contribution_type: correction | addition | insight | view | resonance
  target_artifact_id: string?
  content: object
  attribution:
    source_url: string?
    source_label: string?
```

## Files to Create/Modify

- `docs/field/urs/manifest.json` - published field story manifest.
- `docs/field/urs/anchors/*.json` - curated influence, event, project, education, and resource anchors.
- `docs/field/urs/output/*` - canonical story, summaries, event streams, and derived reports.
- `docs/field/urs/tools/*` - analyzer scripts used to derive the published outputs.
- `api/app/services/field_story_service.py` - artifact loading and attributed contribution persistence.
- `api/app/services/field_story_mcp_tools.py` - API MCP tool handlers for field story resources.
- `api/app/routers/field_stories.py` - HTTP API surface.
- `api/app/main.py` - router registration.
- `mcp-server/coherence_mcp_server/server.py` - npm MCP tool surface.
- `mcp-server/tests/test_awareness_streaming.py` - MCP dispatch coverage.
- `api/tests/test_field_story_agent_surface.py` - API and contribution coverage.
- `web/app/field/urs/page.tsx` - web field story route with read attribution.
- `web/app/page.tsx` - home navigation entry point.
- `docs/system_audit/commit_evidence_2026-05-07_field_story_api_mcp_publish.json` - delivery evidence.

## Acceptance Tests

- `api/tests/test_field_story_agent_surface.py`
- `api/tests/test_entity_view_attribution.py`
- `api/tests/test_meeting_resonance_capture.py`
- `mcp-server/tests/test_awareness_streaming.py`
- Manual validation through `THREAD_RUNTIME_START_SERVERS=1 ./scripts/verify_worktree_local_web.sh --start`.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/field-story-agent-surface.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-07_field_story_api_mcp_publish.json
cd api && python3 -m pytest -q tests/test_field_story_agent_surface.py tests/test_entity_view_attribution.py tests/test_meeting_resonance_capture.py
cd mcp-server && python3 -m pytest -q tests/test_awareness_streaming.py
cd web && npm run build
THREAD_RUNTIME_START_SERVERS=1 ./scripts/verify_worktree_local_web.sh --start
```

## Out of Scope

- Raw private export publication.
- Browser-cookie, authenticated-session, or Google Takeout archive storage in git.
- Silent canonical story overwrite without contribution attribution.

## Risks and Assumptions

- Published artifacts are curated summaries and normalized outputs rather than raw listening-history exports.
- Contributions may need moderation or review before becoming canonical story updates.

## Known Gaps and Follow-up Tasks

- None for the publish surface covered by this spec.
