# Spec — Translate Ideas Through Belief Systems and Worldviews

**Task ID**: `task_a53eff65d08fad5f`  
**Primary implementation spec**: [`specs/181-belief-systems-translation.md`](./181-belief-systems-translation.md) (Idea Lens Engine)  
**Related**: [`specs/169-belief-system.md`](./169-belief-system.md), [`api/app/services/translate_service.py`](../api/app/services/translate_service.py) (concept-level lenses)  
**Status**: specification (product)  
**Date**: 2026-03-28

---

## Summary

The same idea means different things to different people. A decentralized network can read as **freedom** (libertarian), **efficiency** (engineer), **threat** (institutional), or **opportunity** (entrepreneur). Coherence Network should **translate** ideas through multiple structured worldview **lenses**—not to replace or distort source content, but to help people see **how their perspective connects to others** and to reduce accidental cross-worldview friction. This extends to **news ingestion** with optional **point-of-view filters**, and to **every idea** being viewable **through any registered worldview** in the catalog.

This document is the **task contract** for `task_a53eff65d08fad5f`. Detailed API shapes, data models, file lists, and ROI metrics are normative in **spec 181**; this file adds **verification scenarios**, **evidence requirements**, and explicit answers to the **open question** on measurable proof.

---

## Purpose

- **Bridge perspectives**: Make epistemic diversity a first-class feature so contributors do not talk past each other when the underlying idea is shared.
- **Preserve substance**: Translations are **labeled reframings**; canonical idea text and provenance remain authoritative.
- **Enable measurement**: Expose counters and rates so the network can show whether perspective-bridging is **working** and improve clarity of that proof **over time** (see [Proof and improvement loop](#proof-and-improvement-loop)).

---

## Requirements

- [ ] **Lens catalog**: The API exposes a list of worldview lenses (builtin + registered), each with stable `lens_id`, human-readable name, and axis metadata consistent with contributor belief models (see spec 169).
- [ ] **Per-idea translation**: For any stored idea, a client can request a **translation** for a given `lens_id` and receive structured fields (summary restatement, emphasis, risk/opportunity framing, optional resonance vs a contributor profile).
- [ ] **Caching**: Translations are cached deterministically from idea content hash + lens so repeat reads are cheap and auditable.
- [ ] **News POV (phase-aligned with spec 181)**: Ingested items can be viewed through a selected lens where the news pipeline exists; MVP may be **opt-in toggle** before defaulting to personalized lens.
- [ ] **Web UX**: Idea detail supports choosing a lens and viewing the translation beside the original (spec 181).
- [ ] **ROI / health**: An aggregate endpoint reports usage so **independent parties** can verify adoption without database access.
- [ ] **Safety and errors**: Unknown `lens_id` → **404**; validation failures → **422**; duplicate lens registration → **409** (not silent overwrite).

---

## Research Inputs (Required)

| Date | Source | Relevance |
|------|--------|-----------|
| 2026-03-28 | [`specs/181-belief-systems-translation.md`](./181-belief-systems-translation.md) | Canonical API and data model for this feature family. |
| 2026-03-28 | [`specs/169-belief-system.md`](./169-belief-system.md) | Aligns `archetype_axes` / worldview axes with contributor profiles for `resonance_delta`. |
| 2026-03-28 | Moral foundations / cognitive pluralism literature (Haidt et al., public summaries) | Informs lens design: lenses describe **framing stances**, not immutable identity labels. |

---

## API Changes (Summary)

Normative detail: **spec 181**. At minimum the product must ship:

- `GET /api/lenses`, `GET /api/lenses/{lens_id}`, `POST /api/lenses`
- `GET /api/ideas/{idea_id}/translations` and `GET|POST .../translations/{lens_id}`
- `GET /api/lenses/roi` for aggregate proof metrics

Optional extension (when news API exists): `GET /api/news/{article_id}/translations/{lens_id}` as described in spec 181.

---

## Data Model (Summary)

See spec 181 for `WorldviewLens`, `IdeaTranslation`, and cache keying on `(idea_id, lens_id, source_hash)`. Existing code in `translate_service.py` provides **discipline/worldview enums and keyword framing**; spec 181’s persistence and HTTP layer **supersede** ad-hoc usage for the full product feature.

---

## Files to Create or Modify (Implementation)

Delegated to **spec 181** § Files to Create/Modify. Typical set:

- `api/app/routers/lenses.py`, `api/app/services/lens_service.py`, `api/app/models/lens.py`, repos, `api/app/main.py` router include
- `api/app/config/builtin_lenses.json`
- `api/tests/test_belief_systems_translation.py`
- `web/app/ideas/[id]/page.tsx`, optional `web/app/lenses/page.tsx`

---

## Verification Scenarios

These scenarios are the **acceptance contract**. A reviewer may run them against **production** (`https://api.coherencycoin.com`) once the implementation from spec 181 is deployed. Replace placeholders with real IDs from responses.

### Scenario 1 — Lens catalog is live and bounded

**Setup**: API is reachable; no auth required for read-only lens list (per deployed policy).  
**Action**:

```bash
curl -sS "https://api.coherencycoin.com/api/lenses" | jq '{total: (.lenses|length), first: .lenses[0].lens_id}'
```

**Expected result**: HTTP **200**; JSON includes `lenses` array with `length >= 6`; each element has non-empty `lens_id` and `name`; `total` matches array length.  
**Edge case**: If `GET /api/lenses` returns **404**, feature is not deployed—**fail** the contract. If malformed JSON—**fail**.

---

### Scenario 2 — Translate one idea through the engineer lens

**Setup**: At least one idea exists (`GET /api/ideas?limit=1`).  
**Action**:

```bash
IDEA_ID=$(curl -sS "https://api.coherencycoin.com/api/ideas?limit=1" | jq -r '.ideas[0].id // empty')
curl -sS -w "\nHTTP_CODE:%{http_code}\n" "https://api.coherencycoin.com/api/ideas/${IDEA_ID}/translations/engineer" | head -c 4000
```

**Expected result**: HTTP **200**; body includes non-empty `translated_summary` (string length > 0), `lens_id` == `"engineer"`, `idea_id` == `IDEA_ID`, and `spec_ref` == `"spec-181"` when implementation follows spec 181.  
**Edge case**: `IDEA_ID` empty—skip with note “no ideas in environment” or create idea via approved API first; `GET` with unknown idea id must return **404**, not **500**.

---

### Scenario 3 — Invalid lens returns 404, not server error

**Setup**: Valid `IDEA_ID` from Scenario 2.  
**Action**:

```bash
curl -sS -o /tmp/lens_err.json -w "%{http_code}" \
  "https://api.coherencycoin.com/api/ideas/${IDEA_ID}/translations/__no_such_lens__xyz__"
echo
cat /tmp/lens_err.json | jq .
```

**Expected result**: HTTP **404**; JSON `detail` explains not found / unknown lens.  
**Edge case**: HTTP **500** is a **failure**—implementation must not leak stack traces in production JSON.

---

### Scenario 4 — Register custom lens then conflict on duplicate

**Setup**: Operator permissions if `POST /api/lenses` is protected; otherwise anonymous per deploy policy.  
**Action**:

```bash
curl -sS -X POST "https://api.coherencycoin.com/api/lenses" \
  -H "Content-Type: application/json" \
  -d '{"lens_id":"contract-test-lens-a53","name":"Contract Test","description":"POV test","archetype_axes":{"pragmatic":0.7}}' \
  -w "\nHTTP:%{http_code}\n"
curl -sS -X POST "https://api.coherencycoin.com/api/lenses" \
  -H "Content-Type: application/json" \
  -d '{"lens_id":"contract-test-lens-a53","name":"Dup","description":"Dup","archetype_axes":{"pragmatic":0.7}}' \
  -w "\nHTTP:%{http_code}\n"
```

**Expected result**: First call **201** with `lens_id` == `contract-test-lens-a53`; second call **409** with conflict semantics.  
**Edge case**: If **401/403**, document auth requirement in spec 181 and use authenticated curl in verification; **500** is a failure.

---

### Scenario 5 — ROI endpoint proves measurable usage

**Setup**: After at least one successful translation in Scenario 2.  
**Action**:

```bash
curl -sS "https://api.coherencycoin.com/api/lenses/roi" | jq '{total_translations_generated, cross_lens_engagement_rate, spec_ref}'
```

**Expected result**: HTTP **200**; numeric `total_translations_generated >= 1` once translations occurred; `spec_ref` == `"spec-181"`; `cross_lens_engagement_rate` is a number in a documented range (e.g. 0.0–1.0).  
**Edge case**: Zeros everywhere immediately after deploy **before** any use—acceptable only if Scenario 2 was not run; after Scenario 2, `total_translations_generated` should increment (implementation-defined monotonic counter).

---

## Proof and Improvement Loop

**Open question**: *How can we improve this idea, show whether it is working yet, and make that proof clearer over time?*

| Horizon | Signal | How it gets clearer |
|---------|--------|---------------------|
| **Now** | `GET /api/lenses/roi` | Publish baseline; screenshot or saved JSON in `docs/system_audit/` with timestamp proves deploy. |
| **Weeks** | Week-over-week growth of `total_translations_generated`, `unique_ideas_translated` | Same endpoint; trend line in ops dashboard (follow-up). |
| **Behavioral** | `cross_lens_engagement_rate` | Rising rate implies people leave siloed default views. |
| **Quality** | User-reported “translation misleading” friction events (if/when friction API tags exist) | Downward trend = better prompts/cache invalidation. |

**Improvements not blocked on code**: curated lens copy, clearer UI labels (“Reframing, not replacement”), contributor education.

---

## Independently Verifiable Evidence

Anyone (no insider access) should be able to confirm the feature:

1. **HTTPS**: `curl -sS https://api.coherencycoin.com/api/lenses` returns lens catalog (200).  
2. **HTTPS**: Translation URL for a public idea returns 200 with structured body (per Scenario 2).  
3. **Attestation**: A merged PR link to `Coherence-Network` with files from spec 181 + CI green.  
4. **Optional**: Public web URL `https://coherencycoin.com/ideas/<id>` showing lens selector (after web deploy).

---

## Risks and Assumptions

- **Risk**: LLM or template reframing misrepresents the idea. **Mitigation**: Original always primary; translations labeled; cache invalidates on source change.  
- **Risk**: Lenses stereotype groups. **Mitigation**: Epistemic framing, not demographic labels; copy review.  
- **Assumption**: Spec 169 belief axes exist or degrade gracefully for `resonance_delta`.

---

## Known Gaps and Follow-up Tasks

- News pipeline integration for article-level translations (spec 181).  
- Auth for `POST /api/lenses` and force-regenerate (spec 181).  
- CLI `cc lenses translate` convenience (optional).  
- Dashboard charting for ROI time series.

---

## Task Card (Implementation Handoff)

```yaml
goal: Ship worldview lens catalog, per-idea translations, ROI metrics, and idea UI per spec 181.
files_allowed:
  - (see specs/181-belief-systems-translation.md § Files to Create/Modify)
done_when:
  - All Verification Scenarios in this document pass against production API.
  - pytest api/tests/test_belief_systems_translation.py passes locally and in CI.
commands:
  - cd api && pytest -q tests/test_belief_systems_translation.py
  - curl scenarios from § Verification Scenarios
constraints:
  - Do not modify tests to match broken behavior; fix implementation.
  - No scope beyond spec 181 + this contract unless new spec approved.
```

---

## See Also

- [`specs/181-belief-systems-translation.md`](./181-belief-systems-translation.md)
