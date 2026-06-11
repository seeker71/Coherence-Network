---
idea_id: idea-realization-engine
status: draft
source:
  - file: form/form-stdlib/i18n.fk
    symbols: [i18n-load, i18n-string, i18n-locales-available]
  - file: form/form-stdlib/grammars/natural-bmf.fk
    symbols: [natural-src-word]
  - file: form/form-stdlib/intrinsic-cast.fk
    symbols: [ic-nothing, ic-nothing?]
  - file: form/form-stdlib/form-ontology.json
    symbols: []
  - file: docs/coherence-substrate/i18n-as-recipe-corpus.form
    symbols: []
  - file: docs/coherence-substrate/prose-as-recipe.form
    symbols: []
  - file: docs/coherence-substrate/universal-translator.form
    symbols: []
  - file: form/validate.sh
    symbols: []
requirements:
  - "Meaning cells come from the real corpus: word-level translation pairs are drawn from web/messages/{en,de,es,id}.json through i18n.fk — the meaning identity IS the shared key-path cell. No invented vocabulary, no statistical alignment."
  - "Each (locale, surface) pair interns as a word cell pointing at its meaning cell. The same surface appearing under two key-paths composes as two senses — ambiguity is data the structure carries, never a silent first pick."
  - "Translation is a structural walk: translate(surface, from-locale, to-locale) = surface -> word cell -> meaning cell -> target-locale word cell -> surface. The pivot is the shared cell, not the symbol — labels can drift, identity holds."
  - "A surface with no word cell in the from-locale realizes to nothing — the core-axioms third state, same carrier intrinsic casting uses for failed casts — never an empty string, never a thrown error."
  - "Round-trip law as counted evidence: for uniquely-mapped surfaces, translate(translate(w, A, B), B, A) = w; the band counts unique vs ambiguous vs missing over the selected corpus subset and reports the counts, hiding nothing."
  - "The translation lane proves three-way: a root-word-translation-band driven by the real corpus files passes identically in Go, Rust, and TypeScript via form/validate.sh."
done_when:
  - 'file_exists("form/form-stdlib/root-word-translation.fk")'
  - 'file_exists("form/form-stdlib/tests/root-word-translation-band.fk")'
  - "The band passes three-way (Go, Rust, TypeScript agree) under form/validate.sh."
  - "A word-level en surface translates to its de surface through the shared key-path cell, and the same walk returns it home (round-trip identity on a uniquely-mapped surface)."
  - "An unknown surface realizes to nothing in all three kernels; an ambiguous surface returns its sense list as data."
  - "The band reports corpus coverage counts (word-level keys selected, unique mappings, ambiguous surfaces, missing locale surfaces)."
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/language-model.fk form-stdlib/json.fk form-stdlib/codec.fk form-stdlib/structured-codec.fk form-stdlib/json-codec.fk form-stdlib/cache.fk form-stdlib/i18n.fk form-stdlib/form-ontology-loader.fk form-stdlib/intrinsic-cast.fk form-stdlib/root-word-translation.fk form-stdlib/tests/root-word-translation-band.fk"
constraints:
  - "Real data over mocks: the corpus is web/messages/*.json read through i18n.fk's cache layer; the spec adds no invented word lists."
  - "Translation walks are structural only — no frequency ranking, no fuzzy matching, no statistical fallback in this slice."
  - "Unknown surface is nothing, never an empty string; ambiguity returns all senses, never a silent first pick."
  - "No parallel translation service beside the body: the translator is recipes in the same lattice, runnable through validate.sh like any band."
  - "Existing i18n.fk surfaces (i18n-load, i18n-string) keep working unchanged; this slice composes on top of them."
---

# Form Root-Word Translation — meaning as the shared cell, surfaces as doors

## Purpose

The machine-language axis of translation is proven: five dialects lift through canonical recipes and back out, and yesterday's intrinsic-cast work showed dialect semantics living as ontology data. The human-language axis has named teachings (prose-as-recipe, the WORD domain, i18n-as-recipe-corpus) but no running proof. This spec is the smallest honest band that answers *"can Form carry meaning?"* the way the lift bands answered *"can Form carry computation?"* — translation by structural mapping through shared meaning cells, proven three-way on real parallel data the body already holds.

The corpus is not a toy: `web/messages/{en,de,es,id}.json` carries ~2300 key-paths per locale, each key-path a semantic identity with four observed surface emissions. A subset of those values are single words — real ground-truth word-level pairs. The meaning cell IS the key-path; the translator pivots on it the way the substrate pivots on Blueprints: a translator that cannot lie, because the lattice refuses equivalences that are not structurally present.

## Requirements

- [ ] **R1 — meaning cells from the real corpus.** Word-level pairs drawn from `web/messages/*.json` via `i18n.fk`; meaning identity is the shared key-path cell.
- [ ] **R2 — word cells with senses.** Each (locale, surface) is a word cell referencing its meaning cell; duplicate surfaces compose as sense lists.
- [ ] **R3 — translation as structural walk.** surface → word cell → meaning cell → target word cell → surface. The pivot is the cell, never the symbol.
- [ ] **R4 — nothing on unknown.** Unknown surfaces realize to `nothing` (TrivNull `1.1.4.0`) — the same third state failed casts use.
- [ ] **R5 — round-trip law as counted evidence.** Unique mappings round-trip exactly; unique/ambiguous/missing counts are reported, not hidden.
- [ ] **R6 — three-way proof band.** `root-word-translation-band` passes identically in Go, Rust, and TypeScript.

## Data Model

**Meaning cell** — one per selected key-path. The key-path string is the door; the interned cell is the identity.

**Word cell** — one per (locale, surface, meaning) triple:

```
(word-cell locale surface meaning-cell)
```

**Sense list** — the value of looking up a surface in a locale: a list of meaning cells. Length 1 = unique; length > 1 = ambiguous (data, not error); empty = unknown → `nothing`.

**Selection rule** — a corpus key-path enters the word table when its surface in the *source* locale is a single word (no spaces) and the target locale carries a non-empty surface for the same key-path. The rule is a Form predicate in `root-word-translation.fk`, so the subset is reproducible from the corpus alone.

## Files to Create/Modify

- `form/form-stdlib/root-word-translation.fk` — create: word/meaning cell interning from the i18n corpus, sense lookup, the translation walk, round-trip + coverage counters
- `form/form-stdlib/tests/root-word-translation-band.fk` — create: the three-way band
- `specs/INDEX.md` — regenerate

No ontology rows are needed for the first slice if the word/meaning cells intern as composed recipes over existing categories; if named Blueprint rows earn their place (WORD-CELL, MEANING-CELL), they follow the casts pattern: rows + `gen_bp_table.py` + loader bindings in the same commit.

## Acceptance Tests

`form/form-stdlib/tests/root-word-translation-band.fk` (single aggregate, distinct weights per group, same discipline as `tests/intrinsic-cast-band.fk`), run three-way via `form/validate.sh`:

- **Group A — the walk.** A uniquely-mapped en surface reaches its de surface through the meaning cell; same for en→es; the reverse walk returns home (round-trip identity).
- **Group B — honesty lanes.** Unknown surface → `nothing` (verified via `ic-nothing?`); ambiguous surface → sense list with length > 1, and translating a specific sense (by meaning cell) stays exact.
- **Group C — coverage counts.** Selected word-level keys, unique mappings, ambiguous surfaces, and missing-locale gaps are counted; the counts are asserted as equalities so corpus drift is visible, not silent.
- **Group D — structural identity.** The same meaning cell reached from two locales is `node_eq`; two word cells for the same (locale, surface, meaning) intern to the same NodeID (content-addressing law).

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/language-model.fk form-stdlib/json.fk form-stdlib/codec.fk form-stdlib/structured-codec.fk form-stdlib/json-codec.fk form-stdlib/cache.fk form-stdlib/i18n.fk form-stdlib/form-ontology-loader.fk form-stdlib/intrinsic-cast.fk form-stdlib/root-word-translation.fk form-stdlib/tests/root-word-translation-band.fk
python3 scripts/validate_spec_quality.py --file specs/form-root-word-translation.md
```

## Out of Scope

- Sentence-level translation and grammar transfer (word order, agreement) — that is the natural-bmf lift composing with this table, a later slice.
- Statistical ranking, frequency data, embedding similarity — the slice proves the structural lane pure; hybrid lanes come only after the pure lane has proof.
- The seven-keys cross-domain translation (`universal-translator.form`) and assemblage-point dispatch (`word-recipes-by-assemblage-point.form`) — companions, not dependencies.
- New locales beyond the four the corpus already carries.

## Risks and Assumptions

- The corpus speaks UI register (labels, buttons, headings) — the word table inherits that register. Honest: this proves the *mechanism* on real data; vocabulary breadth grows with the corpus, not with this spec.
- Single-word selection in the source locale does not guarantee single words in the target (German compounds, Spanish phrases). The walk returns whatever surface the meaning cell carries — multi-word targets are valid surfaces, not errors.
- `i18n.fk` reads `../web/messages/*.json` relative to `form/`; the band runs where `validate.sh` runs, so the paths hold. If corpus files move, the band names it as a missing-locale count, not a crash.

## Known Gaps and Follow-up Tasks

- Follow-up: sentence-level translation — the natural-bmf lift composing with the word table — once this band proves the word lane.
- Follow-up: broaden the corpus register — a `concepts` section in `web/messages/*.json` lifts coverage without code changes (the same opening `tests/concept-i18n-band.fk` already names).
- Follow-up: assemblage-point dispatch on word cells (`word-recipes-by-assemblage-point.form`) when a consumer needs the dispatch-table shape.

## Task Card

- **goal**: Prove translation by structural mapping through shared meaning cells, three-way, on the body's real parallel corpus.
- **files_allowed**: `form/form-stdlib/root-word-translation.fk`, `form/form-stdlib/tests/root-word-translation-band.fk`, `specs/form-root-word-translation.md`, `specs/INDEX.md` (+ ontology/bp/loader only if named rows earn their place)
- **done_when**: band three-way; round-trip identity on unique mappings; nothing on unknown; coverage counts asserted.
- **commands**: see Verification.
- **constraints**: real corpus only; structural walks only; nothing on unknown; no parallel service.
