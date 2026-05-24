---
idea_id: external-presence
status: active
source:
  - file: web/app/layout.tsx
    symbols: [RootLayout]
  - file: web/middleware.ts
    symbols: [middleware]
  - file: web/next.config.ts
    symbols: [nextConfig]
  - file: api/app/models/translation.py
    symbols: [TranslationLens, OntologyConceptRef, IdeaTranslationResponse, ConceptTranslationResponse]
  - file: api/app/models/lens_translation.py
    symbols: [WorldviewLensCreate, TranslationRegenerateBody]
  - file: api/app/services/translation_cache_service.py
    symbols: [EntityViewRecord, GlossaryEntryRecord, write_view, canonical_view, all_canonical_views, find_anchor, is_stale, list_history, glossary_for, upsert_glossary_entry]
  - file: api/app/services/translator_service.py
    symbols: [build_glossary_prompt, SUPPORTED_LOCALES, attune_from_anchor, load_view, set_backend]
  - file: api/app/services/concept_translation_service.py
    symbols: [translate_idea, translate_concept]
  - file: api/app/services/lens_translation_service.py
    symbols: [build_idea_translation, build_lens_public_dict, list_translations_for_idea, get_roi_payload]
# Evolution note (2026-05-24): translation surface evolved during
# implementation. Model classes EntityView/GlossaryEntry are now
# EntityViewRecord/GlossaryEntryRecord living in translation_cache_service
# (Record suffix marks them as SQLAlchemy ORM rows, not Pydantic
# request/response shapes). LensTranslation became WorldviewLensCreate +
# TranslationRegenerateBody (split into create vs. regenerate
# operations). translate_markdown was replaced by the attunement-backend
# pattern (attune_from_anchor + set_backend); get_cached_translation
# was absorbed into translate_idea/translate_concept which cache
# internally; translate_via_lens became build_idea_translation +
# build_lens_public_dict (split between idea-translation and
# lens-public-projection responsibilities).
  - file: api/app/routers/locales.py
    symbols: [list_locales, get_glossary, patch_glossary]
  - file: api/app/routers/translations.py
    symbols: [submit_translation, list_translations_for_entity]
  - file: api/app/routers/concepts.py
    symbols: [get_concept]
  - file: api/app/routers/contributions.py
    symbols: [create_contribution, get_contribution]
  - file: cli/lib/commands/translate.mjs
    symbols: [handleTranslate, submitTranslation, showHistory]
  - file: web/app/settings/translations/page.tsx
    symbols: [TranslationsCoveragePage]
  - file: docs/vision-kb/glossary/de.md
    symbols: [anchor terms for German]
  - file: docs/vision-kb/glossary/es.md
    symbols: [anchor terms for Spanish]
  - file: docs/vision-kb/glossary/id.md
    symbols: [anchor terms for Indonesian]
requirements:
  - "Web supports locales: en (default), de, es, id — URL-based /{locale}/... routing"
  - "next-intl drives UI chrome strings from web/messages/{locale}.json"
  - "Language picker in header persists choice via cookie and updates URL"
  - "Middleware detects locale from URL → cookie → Accept-Language → default en"
  - "Every translatable entity (concept, idea, contribution, comment) carries a source_lang — English is not privileged; contributors write in the language they live in"
  - "Content translations cached in content_translations table keyed by (entity_type, entity_id, target_lang, source_lang, source_hash)"
  - "Translations carry translator_type (machine | human) and translator_id; human translations supersede machine ones for the same (entity, target_lang)"
  - "Any contributor can submit a translation via POST /api/translations; it becomes canonical immediately and the prior canonical is preserved as superseded (history is the moderation surface, not a review queue)"
  - "Source edits bump source_hash and invalidate stale translations automatically (both machine and human flagged as stale, not deleted)"
  - "Translator service injects a per-language glossary of frequency-anchor terms into the LLM prompt"
  - "Every machine translation is flagged reviewed=false until a native speaker approves or replaces it"
  - "Contributions created in any supported language appear in any other supported language via cached translation on read"
  - "GET /api/concepts/{id}?lang=es returns canonical translation if present, else source language with pending_translation=true and enqueues translation"
  - "POST /api/concepts/{id}/translate?lang=de force-regenerates the machine translation; never overwrites a human translation"
  - "GET /api/locales returns supported locales with coverage stats (machine, human, reviewed) per locale"
  - "Glossary seeded for de, es, id with anchor terms: tending, ripening, wholeness, coherence, resonance, stewardship, kinship, belonging"
done_when:
  - "Visiting /de/vision/lc-water-as-living-body shows German UI chrome and a German-translated story"
  - "Switching the picker from en to es on any page keeps the user on the equivalent /es/... path"
  - "A contributor can submit a contribution in Spanish; an English viewer sees it translated; a Bahasa viewer sees it in Bahasa"
  - "Any signed-in contributor can submit a human translation via POST /api/translations; it replaces the machine version immediately"
  - "Editing a source story flags every language row for that entity as stale (machine AND human preserved — never silently discarded)"
  - "coh stories --lang de returns stories with translated titles and summaries"
  - "coh translate submit {entity-id} --lang es --file translation.md posts a human translation"
  - "Locale coverage visible on /settings/translations: per-locale counts of machine vs. human vs. stale"
  - "All new and existing tests pass (api and web)"
  - 'file_exists("web/app/layout.tsx")'
  - 'symbol_in_file("web/app/layout.tsx", "RootLayout")'
  - 'file_exists("web/middleware.ts")'
  - 'symbol_in_file("web/middleware.ts", "middleware")'
  - 'file_exists("web/next.config.ts")'
  - 'symbol_in_file("web/next.config.ts", "nextConfig")'
  - 'file_exists("api/app/models/translation.py")'
  - 'symbol_in_file("api/app/models/translation.py", "EntityView")'
  - 'symbol_in_file("api/app/models/translation.py", "GlossaryEntry")'
  - 'file_exists("api/app/models/lens_translation.py")'
  - 'symbol_in_file("api/app/models/lens_translation.py", "LensTranslation")'
  - 'file_exists("api/app/services/translation_cache_service.py")'
  - 'symbol_in_file("api/app/services/translation_cache_service.py", "write_view")'
  - 'symbol_in_file("api/app/services/translation_cache_service.py", "canonical_view")'
  - 'symbol_in_file("api/app/services/translation_cache_service.py", "all_canonical_views")'
  - 'symbol_in_file("api/app/services/translation_cache_service.py", "find_anchor")'
  - 'symbol_in_file("api/app/services/translation_cache_service.py", "is_stale")'
  - 'symbol_in_file("api/app/services/translation_cache_service.py", "list_history")'
  - 'symbol_in_file("api/app/services/translation_cache_service.py", "glossary_for")'
  - 'symbol_in_file("api/app/services/translation_cache_service.py", "upsert_glossary_entry")'
  - 'file_exists("api/app/services/translator_service.py")'
  - 'symbol_in_file("api/app/services/translator_service.py", "translate_markdown")'
  - 'symbol_in_file("api/app/services/translator_service.py", "build_glossary_prompt")'
  - 'symbol_in_file("api/app/services/translator_service.py", "SUPPORTED_LOCALES")'
  - 'file_exists("api/app/services/concept_translation_service.py")'
  - 'symbol_in_file("api/app/services/concept_translation_service.py", "translate_concept")'
  - 'symbol_in_file("api/app/services/concept_translation_service.py", "get_cached_translation")'
  - 'file_exists("api/app/services/lens_translation_service.py")'
  - 'symbol_in_file("api/app/services/lens_translation_service.py", "translate_via_lens")'
  - 'file_exists("api/app/routers/locales.py")'
  - 'symbol_in_file("api/app/routers/locales.py", "list_locales")'
  - 'symbol_in_file("api/app/routers/locales.py", "get_glossary")'
  - 'symbol_in_file("api/app/routers/locales.py", "patch_glossary")'
  - 'file_exists("api/app/routers/translations.py")'
  - 'symbol_in_file("api/app/routers/translations.py", "submit_translation")'
  - 'symbol_in_file("api/app/routers/translations.py", "list_translations_for_entity")'
  - 'file_exists("api/app/routers/concepts.py")'
  - 'symbol_in_file("api/app/routers/concepts.py", "get_concept")'
  - 'file_exists("api/app/routers/contributions.py")'
  - 'symbol_in_file("api/app/routers/contributions.py", "create_contribution")'
  - 'symbol_in_file("api/app/routers/contributions.py", "get_contribution")'
  - 'file_exists("cli/lib/commands/translate.mjs")'
  - 'symbol_in_file("cli/lib/commands/translate.mjs", "handleTranslate")'
  - 'symbol_in_file("cli/lib/commands/translate.mjs", "submitTranslation")'
  - 'symbol_in_file("cli/lib/commands/translate.mjs", "showHistory")'
  - 'file_exists("web/app/settings/translations/page.tsx")'
  - 'symbol_in_file("web/app/settings/translations/page.tsx", "TranslationsCoveragePage")'
  - 'file_exists("docs/vision-kb/glossary/de.md")'
  - 'symbol_in_file("docs/vision-kb/glossary/de.md", "anchor")'
  - 'file_exists("docs/vision-kb/glossary/es.md")'
  - 'symbol_in_file("docs/vision-kb/glossary/es.md", "anchor")'
  - 'file_exists("docs/vision-kb/glossary/id.md")'
  - 'symbol_in_file("docs/vision-kb/glossary/id.md", "anchor")'
  - 'pytest_passes("api/tests/test_locale.py")'
  - 'pytest_passes("api/tests/test_translation_cache.py")'
test: "cd api && python -m pytest tests/test_locale.py tests/test_translation_cache.py -q && cd ../web && npm run test"
constraints:
  - "Never mutate source markdown — translations are additive rows keyed by (target_lang, source_hash)"
  - "English is not privileged — source_lang is whatever the contributor wrote in; any locale can be source or target"
  - "Human translations always outrank machine translations for the same (entity, target_lang)"
  - "Stale translations (source_hash mismatch) are flagged, not deleted — prior human work is preserved for the translator to update"
  - "Never silently fall back to another language in the UI chrome — missing message keys must fail loudly in dev"
  - "Source hash is sha256 of the source markdown; any change flags all language rows as stale"
  - "Glossary terms MUST be injected into the translation prompt for the target language every call"
  - "LLM model for translation is config-driven (config.json translator.model), not hardcoded"
---

# Spec: Multilingual Web Interface

## Purpose

The platform's mission names "every idea tracked, for humanity" — but a single-language surface excludes most of humanity. Communities in Peru, Puerto Rico, Guatemala, and Bali already carry stewardship practices the vision describes; they deserve to meet the work in their own tongue AND to contribute in their own voice. This spec makes every translatable surface multilingual in both directions: read and write. Machine translation provides coverage from day one; human translations from community members replace them on arrival, and history is preserved so anything can be revisited.

## Requirements

- [ ] **R1**: Next.js App Router restructured under `app/[locale]/...` with `middleware.ts` handling locale detection (URL → cookie → Accept-Language → default `en`).
- [ ] **R2**: `next-intl` drives all UI chrome from `web/messages/{locale}.json` (en, de, es, id). Missing keys fail loud in dev, log-and-fallback in prod.
- [ ] **R3**: `LocaleSwitcher` component in the header shows the current language, offers the others, persists choice via `NEXT_LOCALE` cookie, and rewrites the current URL to the new locale.
- [ ] **R4**: `content_translations` Postgres table stores per-entity translated markdown keyed by `(entity_type, entity_id, target_lang, source_hash)`. Supports entities `concept`, `idea`, `contribution`, `comment`. Each row carries `source_lang`, `translator_type` (`machine | human`), and `translator_id`.
- [ ] **R5**: `translator` service calls the configured LLM with a prompt that always includes the per-language glossary. Returns translated markdown. No auto-regeneration in the request path — translations are enqueued and served from cache on the next request.
- [ ] **R6**: Source-hash invalidation: on any source edit, compute sha256 of the new source; cached rows with different hashes are flagged `stale=true`. Nothing is deleted — prior human work is preserved for the translator to update.
- [ ] **R7**: Glossary table stores anchor terms per language. Seed with: tending, ripening, wholeness, coherence, resonance, stewardship, kinship, belonging — with their felt-sense equivalents in de, es, id. Admins can edit via `PATCH /api/glossary/{lang}`.
- [ ] **R8**: Canonical selection: for a given (entity, target_lang), the canonical row is the newest non-stale human translation if any exists, else the newest machine translation. Readers always see the canonical.
- [ ] **R9**: Human translation submission: any signed-in contributor can `POST /api/translations` with `{entity_type, entity_id, target_lang, translated_markdown}`. It becomes canonical immediately. The prior canonical is preserved as `superseded` so history is visible on the edit page.
- [ ] **R10**: Multi-directional source languages: contributions and comments store `source_lang` from contributor input. `GET /api/contributions/{id}?lang=es` returns the canonical Spanish view regardless of whether the source was English, German, or Balinese. If no translation exists, returns source with `pending_translation=true`.
- [ ] **R11**: "Needs native review" banner appears on any machine-translated surface for users whose profile locale matches. A "Propose a better translation" action opens an inline editor that submits via R9. No approval gate.
- [ ] **R12**: `GET /api/locales` returns supported locales with coverage stats per locale: total entities, machine-translated, human-translated, stale.
- [ ] **R13**: Per-entity translation history: `GET /api/translations?entity_type=concept&entity_id=lc-xxx&lang=es` lists every translation row for that entity+lang, newest first. The edit page shows this so a new translator sees prior attempts.
- [ ] **R14**: CLI additions: `coh stories --lang de`, `coh translate show {id} --lang es`, `coh translate submit {id} --lang es --file t.md`, `coh glossary --lang id`.

## Research Inputs

- `2026-04-16` — User request naming Peru, Puerto Rico, Guatemala, Bali as priority communities; German and Spanish as primary starter languages.
- `next-intl` docs (App Router integration) — chosen over `react-i18next` for native RSC support.
- CLAUDE.md "Frequency Sensing" — the prose carries a tone that LLM translation tends to flatten into policy-speak; motivates the per-language glossary.

## API Contract

### `GET /api/locales`
```json
{
  "locales": [
    {"code": "en", "name": "English", "native_name": "English", "default": true},
    {"code": "de", "name": "German", "native_name": "Deutsch",
     "coverage": {"entities": 56, "machine": 12, "human": 2, "reviewed": 4, "stale": 1}},
    {"code": "es", "name": "Spanish", "native_name": "Español",
     "coverage": {"entities": 56, "machine": 8, "human": 0, "reviewed": 0, "stale": 0}},
    {"code": "id", "name": "Indonesian", "native_name": "Bahasa Indonesia",
     "coverage": {"entities": 56, "machine": 0, "human": 0, "reviewed": 0, "stale": 0}}
  ]
}
```

### `GET /api/concepts/{id}?lang=es`
Extended existing endpoint. Returns `{concept_id, source_lang, lang, translation_status, translator_type, reviewed, stale, translated_markdown}` where `translation_status` is `native | canonical | pending | stale_fallback`. If `pending`, enqueues translation and returns source markdown with `pending_translation: true`.

### `POST /api/concepts/{id}/translate?lang=de`
Force regenerate the machine translation. Refuses (409) if a human-canonical translation exists unless `force_override=true` by admin. Response: `{concept_id, lang, translator_type: "machine", source_hash, translated_at}`.

### `POST /api/translations`
Submit a human translation. Body: `{entity_type, entity_id, target_lang, translated_markdown, notes?}`. Any signed-in contributor can submit. Becomes canonical immediately. The prior canonical row is preserved with `status: "superseded"` so the history is visible on the edit page.

### `GET /api/translations?entity_type=&entity_id=&lang=&status=`
List translation rows for an entity, newest first. `status` filter: `canonical | stale | superseded`. Backs the history view on the edit page.

### `GET /api/contributions/{id}?lang=es` and `POST /api/contributions`
Contribution `POST` accepts `source_lang` from the client (defaults to the user's profile locale). `GET` with `lang` returns the contribution in the requested locale, translating through the same pipeline as concepts.

### `GET /api/glossary/{lang}` / `PATCH /api/glossary/{lang}`
List/upsert anchor-term mappings for a language.

## Data Model

```yaml
ContentTranslation:
  id: uuid
  entity_type: enum [concept, idea, contribution, comment]
  entity_id: string
  source_lang: string        # ISO 639-1 — language the source was written in
  target_lang: string        # ISO 639-1
  source_hash: string        # sha256 of source markdown at translation time
  translated_markdown: text
  translator_type: enum [machine, human]
  translator_id: string | null  # contributor id if human, else null
  translator_model: string | null  # e.g. "claude-opus-4-7" for machine
  status: enum [canonical, stale, superseded]
  notes: text | null         # translator's note on word choices and felt-sense
  created_at: timestamp
  updated_at: timestamp
  index: [entity_type, entity_id, target_lang, status]
  # No unique constraint on (entity, lang) — history is preserved. Canonical selection is by status + translator_type + recency.

GlossaryEntry:
  id: uuid
  lang: string
  source_term: string   # canonical English anchor term
  target_term: string   # felt-sense equivalent in target language
  notes: text | null    # why this word — the frequency it carries
  unique: [lang, source_term]

SupportedLocale:
  code: string          # en, de, es, id
  name: string          # English name
  native_name: string   # Deutsch, Español, Bahasa Indonesia
  default: boolean
  enabled: boolean

Contribution (existing — extend):
  # ... existing fields ...
  source_lang: string   # NEW — language the contributor wrote in; defaults to profile locale
  # content body stays in its original language; translations live in ContentTranslation
```

**Canonical selection rule** (in `select_canonical()`):
1. Prefer rows with `status=canonical` for the target_lang.
2. Among those, prefer `translator_type=human` over `machine`.
3. Among ties, prefer the most recent by `updated_at`.
4. If no canonical row exists, return source with `pending_translation=true` and enqueue machine translation.

**When a human translation arrives** (in `POST /api/translations`):
1. The prior canonical row (if any) is flipped to `status=superseded`.
2. The new row is inserted with `status=canonical`, `translator_type=human`, current source_hash.
3. No approval gate — trust is the default. History is the moderation surface: if something feels off, anyone can submit another translation, and the lineage is visible on the edit page.

## Files to Create/Modify

### API
- `api/app/models/locale.py` — `SupportedLocale`, `ContentTranslation`, `GlossaryEntry` Pydantic + SQLAlchemy models
- `api/app/services/translation_cache.py` — `get_or_translate()`, `select_canonical()`, `invalidate_for_entity()`, `source_hash_of()`
- `api/app/services/translator.py` — `translate_markdown(text, source_lang, target_lang, glossary)`, `build_glossary_prompt(lang)`
- `api/app/routers/locale.py` — `/api/locales`, `/api/glossary/{lang}` handlers
- `api/app/routers/translations.py` — `POST /api/translations` (submit human translation), `GET /api/translations` (history)
- `api/app/routers/concepts.py` — extend `GET /api/concepts/{id}` with `lang` query param; add `POST /api/concepts/{id}/translate`
- `api/app/routers/contributions.py` — accept `source_lang` on create; honor `lang` on read
- `api/migrations/XXXX_content_translations.sql` — create `content_translations`, `glossary_entries`, `supported_locales`; add `source_lang` to `contributions`, `comments`
- `api/scripts/seed_glossary.py` — seed anchor terms for de, es, id
- `cli/coherence_cli/commands.py` — add `stories --lang`, `translate {show,submit,history}`, `glossary` commands

### Web
- `web/package.json` — add `next-intl` dependency
- `web/i18n/config.ts` — locale list, default
- `web/i18n/request.ts` — `getRequestConfig` for next-intl
- `web/middleware.ts` — locale detection and URL rewriting
- `web/app/[locale]/layout.tsx` — wrap in `NextIntlClientProvider`
- `web/app/[locale]/...` — move all existing routes under `[locale]`
- `web/messages/en.json`, `web/messages/de.json`, `web/messages/es.json`, `web/messages/id.json` — UI chrome strings
- `web/components/LocaleSwitcher.tsx` — header language picker
- `web/components/StoryContent.tsx` — accept `lang` prop, show "Needs native review" + "Propose better translation" banners when machine-translated
- `web/components/TranslationEditor.tsx` — inline markdown editor for submitting a human translation (posts to `/api/translations`)
- `web/components/ContributionForm.tsx` — language selector defaulting to profile locale; submits `source_lang`
- `web/app/[locale]/settings/translations/page.tsx` — coverage dashboard (counts per locale, links into concepts needing native voice)
- `web/app/[locale]/translate/[entity_type]/[entity_id]/page.tsx` — full-page translation editor with history and glossary reference

### Tests
- `api/tests/test_locale.py` — locale list, glossary CRUD
- `api/tests/test_translation_cache.py` — cache hit, miss, invalidation on source edit, human-beats-machine canonical selection
- `api/tests/test_translations_api.py` — submit human translation, it becomes canonical immediately, prior canonical becomes superseded, history lists both
- `api/tests/test_contributions_i18n.py` — contribution in es readable in en, id, de
- `web/tests/locale-switcher.test.ts` — URL rewrite on switch
- `web/tests/e2e/de-vision.spec.ts` — Playwright: visit /de/vision, assert German chrome
- `web/tests/e2e/submit-translation.spec.ts` — Playwright: submit human translation, see it replace machine version on refresh

## Acceptance Tests

- `api/tests/test_locale.py::test_list_locales_returns_four`
- `api/tests/test_locale.py::test_glossary_seeded_for_all_locales`
- `api/tests/test_translation_cache.py::test_source_edit_flags_translations_stale`
- `api/tests/test_translation_cache.py::test_pending_returns_source_enqueues_translation`
- `api/tests/test_translation_cache.py::test_human_translation_beats_machine_in_canonical_selection`
- `api/tests/test_translations_api.py::test_human_submission_becomes_canonical_immediately`
- `api/tests/test_translations_api.py::test_prior_canonical_becomes_superseded_on_new_human_translation`
- `api/tests/test_translations_api.py::test_machine_translate_never_overwrites_human_canonical`
- `api/tests/test_translations_api.py::test_history_lists_superseded_rows_newest_first`
- `api/tests/test_contributions_i18n.py::test_spanish_contribution_readable_in_english`
- `api/tests/test_concepts.py::test_get_concept_with_lang_returns_translated`
- `web/tests/locale-switcher.test.ts::switches_locale_preserves_path`
- `web/tests/e2e/de-vision.spec.ts::de_vision_shows_german_chrome`
- `web/tests/e2e/submit-translation.spec.ts::submitted_translation_becomes_canonical_on_refresh`

## Verification

```bash
cd api && python -m pytest tests/test_locale.py tests/test_translation_cache.py tests/test_concepts.py -q
cd web && npm run test && npm run test:e2e -- de-vision.spec.ts
```

Manual: visit `/de/vision/lc-water-as-living-body`, confirm German chrome and translated story. Toggle picker to `es`, confirm URL becomes `/es/vision/lc-water-as-living-body` and content swaps.

## Out of Scope

- Translation of spec `.md` files, source code comments, or markdown in the repo itself — the repo stays English for now; only API-served content and UI chrome are multilingual.
- Bot translations (Discord, Telegram posting in other languages) — covered by `external-presence-bots-and-news`.
- RTL language support (Arabic, Hebrew) — none of the starter locales need it.
- CLI output translation — CLI stays English; only web surface and content API are multilingual.
- Automatic detection of source_lang (langdetect etc.) — contributors pick it explicitly from a dropdown. Detection can come later once we see what users actually submit.

## Known Gaps and Follow-up Tasks

- No detected language-of-origin for existing contributions — they'll be assumed `en` on migration. A one-off reclassification pass may be needed if non-English contributions already exist in the DB.
- No offline translation mode — translator service requires the configured LLM provider to be reachable. A queue-and-retry on provider failure is left to a follow-up.
- No per-user "preferred locale" in contributor profiles yet — falls back to browser Accept-Language. Profile locale field is a small follow-up migration.
- History pruning is unspecified — every human translation adds a superseded row. If volume grows, a "keep last N per (entity, lang)" pass is a straightforward follow-up.
- Regional Spanish variants (es-PE, es-PR, es-GT) will layer in as community translations on top of neutral `es` once native speakers want to contribute them. No schema change needed.

## Risks and Assumptions

- **LLM translation flattens frequency** — mitigated by per-language glossary injection, the "Needs native voice" banner, and the "Propose a better translation" inline editor. Human translations supersede machine ones the moment they land. Worst case before community engagement: translations read as policy-speak until a native speaker drops a better version. The glossary and the human-first canonical rule are the living correction surface.
- **Translation cost at scale** — 56 concepts × ~5KB × 3 languages ≈ 840KB output tokens per full rebuild. Cached aggressively; regenerated only on source edit. Config-driven model choice lets Haiku handle bulk and Opus handle care-work.
- **URL breakage** — moving routes under `[locale]` changes every path. Middleware redirects `/vision/xxx` → `/en/vision/xxx` to preserve existing links.
- **Assumption — trust by default**: anyone signed in can replace a translation, and history is the correction surface rather than an approval gate. If a bad translation lands, the next contributor to notice can replace it, and the superseded row remains visible. This is aligned with the vision: tending comes from relationship, not from moderation.
- **Assumption — Indonesian (`id`) for Bali**: Balinese (`ban`) is a distinct language with ~3.3M speakers; starting with Indonesian is pragmatic reach. Bali-based contributors should be asked which they'd rather have. The data model supports adding `ban` without schema change.
- **Assumption — single-language per submission**: most contributors will write in one language per submission (not code-switching mid-paragraph). Code-switched contributions translate awkwardly; we'll see what actually arrives and adapt.

## Known Gaps and Follow-up Tasks

**What's implemented** (discovered this session during tending; the filenames differ slightly from the spec's source map — the backend shipped with slightly renamed services):
- Backend translation pipeline — `api/app/services/translation_cache_service.py` (329 lines), `concept_translation_service.py` (266), `lens_translation_service.py` (158), `locale_projection.py`
- Models — `api/app/models/translation.py`, `api/app/models/lens_translation.py`
- Locale router — `api/app/routers/locales.py`
- Four locale message bundles at `web/messages/{en,de,es,id}.json`
- Web middleware — `web/middleware.ts`
- Integration tests — `api/tests/test_flow_multilingual.py`, `test_on_demand_attunement.py`

**Confirmed during this session** (each a discrete commit in the trail):
- `POST /api/translations` endpoint + `GET` history — human/machine supersede semantics exposed
- `coh translate submit <entity_type> <entity_id> --lang <l> --file <path>` and `coh translate history` CLI
- Anchor glossary seeded for `es` and `id` (matching the existing `de` pattern); 15 anchor terms per language
- `/settings/translations` coverage dashboard — per-locale `original/human/machine/stale` tallies from `GET /api/locales`, linked from `/settings`
- Language picker in site header — `LocaleSwitcherCompact` wired at `web/components/site_header.tsx` (desktop and mobile menu); cookie-backed, ?lang= override, Accept-Language auto-detection all in `web/middleware.ts`

**Deferred to its own restructure PR**:
- Full URL-based `/{locale}/...` routing. Currently language is cookie-driven on the same URLs (`/vision/xxx`); the spec asks for a prefix (`/de/vision/xxx`). That requires moving every route under `app/[locale]/` — a whole-tree restructure that deserves its own PR, its own review, and its own migration plan for existing bookmarks. The cookie path serves the intent (users switch languages, the choice persists), and the structural upgrade can land without schema change.

Status stays `draft` until the URL-prefix routing lands; the UX plumbing is otherwise complete.
