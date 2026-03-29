# Belief Systems Translation — Idea Lens Engine (Minimal Core)

**Idea ID**: `belief-systems-translation-idea-lens-engine`  
**Supersedes nothing; narrows**: [`specs/181-belief-systems-translation.md`](./181-belief-systems-translation.md) (full product spec)  
**Status**: draft  
**Date**: 2026-03-29

---

## Summary

The **Idea Lens Engine** is the minimal capability to take a **stored idea** (canonical title/description) and produce a **structured, lens-tagged restatement** for a named **worldview lens**—without replacing or editing the source idea. The same underlying idea can be read through different belief-system filters so contributors reduce accidental cross-worldview friction. This document scopes **only** the core path: **readable lens catalog**, **one translation fetch per (idea, lens)** with **deterministic caching**, and **validation errors** for missing resources. Optional features from spec 181 (custom lens CRUD, ROI metrics, news POV, web polish, async precompute, reach indices) are **out of scope** here unless explicitly pulled into a follow-up spec.

---

## Requirements

1. **Builtin lenses**: At API startup, six lenses are available with stable `lens_id` values: `libertarian`, `engineer`, `institutionalist`, `entrepreneur`, `spiritual`, `systemic` (names/descriptions/archetype axes per spec 181 or equivalent config file).
2. **List lenses**: `GET /api/lenses` returns HTTP 200 and a JSON list of lenses (each includes at least `lens_id`, `name`, `is_builtin`).
3. **Get one translation**: `GET /api/ideas/{idea_id}/translations/{lens_id}` returns HTTP 200 with an `IdeaTranslation` body when both `idea_id` and `lens_id` exist; includes `spec_ref` identifying this feature slice and `source_hash` derived from canonical idea content.
4. **Caching**: If a translation already exists for `(idea_id, lens_id)` and the idea’s content hash is unchanged, the same stored translation is returned (`cached: true`). If missing or stale, generate once, persist, return (`cached` reflects first-time vs repeat).
5. **Errors**: Unknown `lens_id` or unknown `idea_id` returns **404** with a JSON `detail`, not 500.
6. **Tests**: Automated tests cover list lenses, successful translation, cache hit, and 404 paths for the minimal scope (file path to be listed in **Files to Create/Modify** during implementation).

---

## API changes

| Method | Path | Behavior |
|--------|------|----------|
| `GET` | `/api/lenses` | List builtin (and any pre-seeded) lenses. |
| `GET` | `/api/ideas/{idea_id}/translations/{lens_id}` | Return cached or generated `IdeaTranslation`. Optional query `contributor_id` may be omitted in the minimal slice; if present, `resonance_delta` may be `null` until belief profiles are wired. |

**Explicitly not in this minimal spec**: `POST /api/lenses`, `POST .../translations/{lens_id}` force-regenerate, `GET /api/lenses/roi`, bulk `GET .../translations`, news routes, web UI changes.

---

## Data model

**WorldviewLens** (read model for list/get):

- `lens_id` (string, slug)
- `name`, `description` (strings)
- `archetype_axes` (map string → float in \[0, 1\])
- `is_builtin` (bool)
- `created_at` (ISO 8601 UTC)

**IdeaTranslation** (response for GET translation):

- `idea_id`, `lens_id`
- `original_name` (string)
- `translated_summary` (string)
- `emphasis` (list of strings)
- `risk_framing`, `opportunity_framing` (strings)
- `resonance_delta` (float or null)
- `cached` (bool)
- `generated_at` (ISO 8601 UTC)
- `source_hash` (string)
- `spec_ref` (string; e.g. `spec-lens-min` or aligned with implementation)

Persistence: store translations keyed by `(idea_id, lens_id)` with `source_hash` for invalidation when idea text changes.

---

## Verification criteria

- `cd api && pytest` (or targeted test module once added) passes for the new minimal tests.
- Manual smoke: `GET /api/lenses` returns six builtin `lens_id` values; `GET /api/ideas/{valid_id}/translations/engineer` returns non-empty `translated_summary` and consistent `spec_ref` across calls; invalid lens returns 404.

---

## Risks

- **LLM framing drift**: Restatements may over- or under-emphasize facets of the idea. **Mitigation**: Canonical idea text remains authoritative in the UI/API; translations are labeled as lens-filtered; store `source_hash` for audit.
- **Cost/latency**: First-generation translation calls an LLM. **Mitigation**: Cache on `(idea_id, lens_id, source_hash)`; minimal scope avoids bulk precompute.
- **Scope creep**: Implementers may pull in full spec 181. **Mitigation**: Treat this file as the binding minimal contract; defer CRUD, ROI, and web to separate tasks.

---

## Files to Create/Modify (implementation pointer; not binding until implementation task lists them)

- API router/service/repo for lenses + translations only
- Builtin lens seed data
- Focused tests for the six requirements above

---

## See also

- [`specs/181-belief-systems-translation.md`](./181-belief-systems-translation.md) — full Idea Lens Engine product definition
- [`specs/169-belief-system.md`](./169-belief-system.md) — contributor belief profiles (for future `resonance_delta`)
