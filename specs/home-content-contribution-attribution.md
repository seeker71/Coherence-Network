---
idea_id: home-content-contribution-attribution
status: active
source:
  - file: api/app/routers/translations.py
    symbols: [submit_translation()]
  - file: api/app/routers/entity_views.py
    symbols: [upsert_view()]
  - file: api/app/routers/views.py
    symbols: [views_ping()]
  - file: api/app/routers/concepts.py
    symbols: [upsert_concept_view()]
  - file: api/app/routers/ideas.py
    symbols: [get_idea(), list_ideas()]
  - file: api/app/services/entity_view_attribution_service.py
    symbols: [record_view_attribution(), credit_view_source()]
  - file: web/hooks/useViewTracking.ts
    symbols: [useReadPing()]
  - file: web/app/ideas/[idea_id]/IdeaReadPing.tsx
    symbols: [IdeaReadPing()]
  - file: web/app/ideas/[idea_id]/page.tsx
    symbols: [IdeaDetailPage()]
  - file: web/app/vision/[conceptId]/edit/_components/StoryEditor.tsx
    symbols: [StoryEditor()]
  - file: cli/lib/commands/content.mjs
    symbols: [handleContent()]
  - file: web/components/content/EditablePageContent.tsx
    symbols: [EditablePageIntro(), EditablePageMarkdown()]
  - file: web/components/content/AttributedExternalLink.tsx
    symbols: [AttributedExternalLink()]
  - file: web/app/page.tsx
    symbols: [Home()]
  - file: web/app/come-in/page.tsx
    symbols: [ComeInPage()]
  - file: web/app/silence/page.tsx
    symbols: [SilencePage()]
  - file: web/app/with-us/page.tsx
    symbols: [WithUsPage()]
  - file: web/app/vision/page.tsx
    symbols: [VisionPage()]
  - file: web/app/ideas/page.tsx
    symbols: [IdeasPage()]
  - file: web/app/resonance/page.tsx
    symbols: [ResonancePage()]
  - file: web/app/invest/page.tsx
    symbols: [InvestPage()]
  - file: web/app/pipeline/page.tsx
    symbols: [PipelinePage()]
  - file: web/app/nodes/page.tsx
    symbols: [NodesPage()]
  - file: web/app/contribute/page.tsx
    symbols: [ContributePage()]
requirements:
  - "R1 — content view writes via API create attribution records tied to contribution ledger entries."
  - "R2 — view pings can credit CC back to the source contribution for the viewed content."
  - "R3 — CLI exposes a content edit command that uses the same API attribution path."
  - "R4 — home-linked static or dashboard page copy can be represented as page/<route> entity views and read attention can flow back to those source contributions."
  - "R5 — external developer links from the home page can be represented as asset/<id> source contributions and click attention can flow back to those sources."
done_when:
  - "API tests prove translation writes return source_contribution_id and view pings credit source authors."
  - "CLI exposes `coh content set` for file-backed content edits."
  - "Home-linked page routes mount explicit page read pings and render canonical page views when supplied."
  - "Home-page external developer links send attributed asset click pings."
test: "cd api && .venv/bin/python -m pytest tests/test_entity_view_attribution.py -q"
constraints:
  - "Do not change existing home page layout."
  - "Do not add authentication requirements to public read tracking."
  - "Keep attribution append-only."
---

# Spec: Home Content Contribution Attribution

## Purpose

Home-page links lead to concepts, ideas, and static invitation surfaces whose text should be editable as living content rather than static one-off pages. A contributor who edits a view should receive an append-only contribution record, and later view attention should be traceable back to that source contribution so CC can flow back to the author.

## Requirements

- [ ] **R1**: `POST /api/translations` and `POST /api/entity-views/{entity_type}/{entity_id}` MUST create an attribution record when an `author_id` is supplied, returning `source_contribution_id`.
- [ ] **R2**: `POST /api/views/ping` MUST credit the latest source contribution for the viewed concept/entity with a small append-only `attention` ledger entry.
- [ ] **R3**: The CLI MUST expose `coh content set <entity_type> <entity_id> --lang <lang> --file <path>` to modify content through the same API path and show attribution output.
- [ ] **R4**: `page` MUST be a supported generic entity type so routes such as `/with-us`, `/pipeline`, and `/contribute` can be edited with `coh content set page <id> ...` and credited by page read pings.
- [ ] **R5**: Home-page external developer links MUST send best-effort read pings with stable `asset` entity ids so seeded source contributions can receive attention credit even though offsite page views are not observable.

## API Contract

### `POST /api/translations`

Extends the existing response with:

```json
{
  "source_contribution_id": "clr_..."
}
```

### `POST /api/views/ping`

Extends the existing response with:

```json
{
  "credited_source_contribution_id": "clr_..."
}
```

## Files to Create/Modify

- `specs/home-content-contribution-attribution.md` — this spec
- `api/app/routers/translations.py` — return attribution for content writes
- `api/app/routers/entity_views.py` — return attribution for generic view writes
- `api/app/routers/concepts.py` — return attribution for concept view writes
- `api/app/routers/ideas.py` — render idea detail/list content from canonical views
- `api/app/routers/views.py` — credit view attention to source contribution
- `api/app/services/entity_view_attribution_service.py` — attribution map and credit logic
- `api/tests/test_entity_view_attribution.py` — API regression tests
- `web/hooks/useViewTracking.ts` — allow explicit entity read pings
- `web/app/ideas/[idea_id]/IdeaReadPing.tsx` — client ping for idea detail reads
- `web/app/ideas/[idea_id]/page.tsx` — install idea detail read ping
- `web/app/vision/[conceptId]/edit/_components/StoryEditor.tsx` — save story edits through attributed concept views
- `web/components/content/EditablePageContent.tsx` — reusable page entity rendering + read pings
- `web/components/content/AttributedExternalLink.tsx` — click attribution for offsite home developer links
- `web/app/page.tsx` — use attributed external developer links
- `web/app/come-in/page.tsx` — render attributed page content for `/come-in`
- `web/app/silence/page.tsx` — render attributed page content for `/silence`
- `web/app/with-us/page.tsx` — render attributed page content for `/with-us`
- `web/app/vision/page.tsx` — read ping for `/vision` page content
- `web/app/ideas/page.tsx` — read ping for `/ideas` page content
- `web/app/resonance/page.tsx` — read ping for `/resonance` page content
- `web/app/invest/page.tsx` — render attributed page content for `/invest`
- `web/app/pipeline/page.tsx` — render attributed page content for `/pipeline`
- `web/app/nodes/page.tsx` — render attributed page content for `/nodes`
- `web/app/contribute/page.tsx` — render attributed page content for `/contribute`
- `cli/bin/coh.mjs` — register the CLI content command
- `cli/lib/commands/content.mjs` — CLI content edit/read surface
- `cli/README.md` — document content command
- `cli/README.template.md` — document content command
- `docs/system_audit/model_executor_runs.jsonl` — proof record
- `docs/system_audit/commit_evidence_2026-05-05_home_content_contribution_attribution.json` — commit evidence

## Acceptance Tests

- `api/tests/test_entity_view_attribution.py::test_translation_write_records_source_contribution`
- `api/tests/test_entity_view_attribution.py::test_view_ping_credits_latest_source_contribution`
- `api/tests/test_entity_view_attribution.py::test_page_entity_view_records_source_and_attention`
- `api/tests/test_entity_view_attribution.py::test_external_asset_click_credits_seeded_source`

## Verification

```bash
cd api && .venv/bin/python -m pytest tests/test_entity_view_attribution.py -q
```

## Out of Scope

- Editing React layout/chrome directly from the API; page entity views own editable page copy.
- Changing the home page visual design.
- Paying on-chain currency; this only records CC ledger credit.

## Risks and Assumptions

- Assumes `author_id` is the contributor id for public content edits.
- Append-only attention entries may grow quickly; existing ledger retention policy should handle future pruning if needed.

## Known Gaps

- Follow-up task: seed source contributions for existing home-page page and external asset entities in production data, for example `page/with-us`, `page/pipeline`, `asset/npm:coherence-cli`, and `asset/github-coherence-network`.
