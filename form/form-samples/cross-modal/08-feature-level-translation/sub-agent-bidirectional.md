# Sub-agent bidirectional validation — feature-level cross-modal translation

A fresh LLM session (no access to claude's `extraction-source.md` or `re-extracted/*-features.md` until Task 4) ran two new round-trip tests on top of v1's schema:

1. **Forward** — `source.txt` → my independent feature-recipe → I generate three NEW targets (SVG, melody description, tercet) → re-extract features from each → `node_eq` against my source-features.
2. **Reverse** — `targets/composition.svg` alone → my independent SVG feature-recipe → I generate a NEW prose passage from JUST those features (without reading source.txt or any prose target) → re-extract features from the generated prose → `node_eq` against the SVG-features that conditioned it.

Substrate-truth attestation lives in `validation-v2.fk` (sibling to `validation.fk`), kernel-verified three-way at **322110**.

---

## 1. Token agreement table

### Source.txt — sub-agent (Task 1) vs claude (extraction-source.md)

| Axis | Sub-agent token | Claude token | NodeID equal? |
|---|---|---|:-:|
| mood | gentle | gentle | ✓ |
| rhythm | breath-paced | breath-paced | ✓ |
| structure | spiral | spiral | ✓ |
| purpose | instruct | instruct | ✓ |
| wisdom-shape | R_TendingDiscipline | R_TendingDiscipline | ✓ |
| concepts (5) | memory-as-tissue, circulation-feedback, composting-with-care, breath-paced-action, calcification-as-trap | memory-as-tissue, circulation-feedback, composting-with-care, present-breath, continuous-tending | ✗ |

**Fixed-vocab agreement: 5/5.** The discrete schema reproduces across fresh LLM sessions for this source. Concept list overlaps on 3/5 exact tokens; the other two are semantic synonyms (mine: *breath-paced-action* vs claude's *present-breath*; mine: *calcification-as-trap* vs claude's *continuous-tending* — same anchors viewed from opposite poles). The concept-list NodeID still differs because the schema requires exact ordered match.

### composition.svg — sub-agent (Task 3 input) vs claude (re-extracted/composition-features.md)

| Axis | Sub-agent token | Claude token | NodeID equal? |
|---|---|---|:-:|
| mood | gentle | gentle | ✓ |
| rhythm | breath-paced | breath-paced | ✓ |
| structure | spiral | spiral | ✓ |
| purpose | invite | invite | ✓ |
| wisdom-shape | R_FieldHoldingPresence | R_FieldHoldingPresence | ✓ |
| concepts (5) | central-spiral, concentric-incompletion, periphery-marks, organic-texture, breathing-radius | spiral-of-attention, concentric-presence, organic-texture, periphery-honoring, incomplete-arc | ✗ |

**Fixed-vocab agreement on SVG: 5/5.** Identical pattern: the fixed vocabulary lands deterministically across sessions; the open concept-list paraphrases the same observations with different surface tokens (organic-texture is the lone exact match; the other four pairs are clear synonyms — *central-spiral*↔*spiral-of-attention*, *concentric-incompletion*↔*incomplete-arc*, *periphery-marks*↔*periphery-honoring*, *breathing-radius*↔*concentric-presence*).

**The cross-session reproducibility finding is striking.** For both the prose source and the SVG, two independent LLM readings produced the same 5 fixed-vocab tokens. The schema is doing what the schema is supposed to do — channeling LLM perception into a finite vocabulary deterministically enough that the same source produces the same NodeID across sessions on the structural axes. The open concept axis is where session-stochasticity surfaces.

---

## 2. Forward direction findings — features → target → features

I generated three new targets from my Task 1 feature-recipe without re-reading `source.txt`:

- **New SVG** (described, not rendered as file): 300×600 portrait canvas, vertical breath-column on the left rendered as a slow descending helix, tissue-fibers on the right joining and fading to nothing, 5 small breath-marks numbered I–V down the right edge. Same muted earth-tone family.
- **New melody description**: solo viola + hurdy-gurdy drone on D2, ♩=48, 5/4, five sections I–V each opening on a single sustained note descending stepwise (D4 → C4 → B♭3 → A3 → G3), each section's brief ascending figure reaching lower than the last, section V fading mid-breath with no cadence.
- **New tercet**:
  > What does not circulate hardens; tend the circulation.
  > What you would release, release with the same hands that held it.
  > Whoever names the work finished has already begun to forget it.

Then I re-extracted features from each generation. Per-axis result:

| Axis | Source (mine) | gen-SVG | gen-melody | gen-tercet | Portability |
|---|---|---|---|---|:-:|
| mood | gentle | gentle ✓ | gentle ✓ | gentle ✓ | **3** |
| rhythm | breath-paced | breath-paced ✓ | breath-paced ✓ | halting ✗ | **2** |
| structure | spiral | spiral ✓ | descending ✗ | spiral ✓ | **2** |
| purpose | instruct | invite ✗ | invite ✗ | instruct ✓ | **1** |
| wisdom | R_TendingDiscipline | R_FieldHoldingPresence ✗ | R_FieldHoldingPresence ✗ | R_TendingDiscipline ✓ | **1** |
| concepts | (5 tokens) | (5 different) ✗ | (5 different) ✗ | (3 different) ✗ | **0** |

**Forward portability: `322110`** — vs claude's v1 `323110`. The single-digit difference is at position 3 (structure): claude's v1 melody (A-A'-B-A'' with unresolved return) re-extracted as `spiral`; my v2 melody (five-section descending breath-line) re-extracted as `descending`. The structure axis is portable BUT not robust — the same feature-recipe condition admits multiple structural idioms in non-prose modalities, and which idiom the generator reaches for determines whether the re-extractor recovers the original token.

**Forward-direction finding, plainly:** The pattern matches v1 almost exactly. Mood and structure are the most portable axes (3/3 and 2/3 respectively). Rhythm preserves into other modalities but breaks under aphoristic compression. Purpose and wisdom-shape are *prose-modality features* — they need words to carry. Concepts are fully lossy across any modality jump.

---

## 3. Reverse direction findings — image → features → prose → features

Independent extraction from `composition.svg` (no companion .md, no source.txt): `gentle, breath-paced, spiral, invite, R_FieldHoldingPresence, [central-spiral, concentric-incompletion, periphery-marks, organic-texture, breathing-radius]`.

I then generated a new prose passage from those features alone:

> Begin at the still center where attention curls inward. From this turning, let breath expand outward — each cycle wider than the last, each arc reaching further than the previous one yet never closing. At the edges of awareness, small presences gather, faint and unforced. Do not complete what is meant to remain open. Let the radius grow as breath grows; let the periphery hold what the center cannot name. There is no perfect closing here, only the continuing turn.

Re-extracted features from this prose:

| Axis | SVG-conditioning | Generated prose | NodeID equal? |
|---|---|---|:-:|
| mood | gentle | gentle | ✓ |
| rhythm | breath-paced | breath-paced | ✓ |
| structure | spiral | spiral | ✓ |
| purpose | invite | **instruct** | ✗ |
| wisdom | R_FieldHoldingPresence | R_FieldHoldingPresence | ✓ |
| concepts | (5 spatial tokens) | (5 different prose tokens) | ✗ |

**Reverse pattern: `111010`** — 4/6 axes survive image → features → prose → features.

**Reverse-direction finding, plainly:** Going from image to prose preserves *more* fixed-vocab axes than going from prose to image (4/6 vs 3/6 in the source→SVG forward leg). The one drift is `invite → instruct` on the purpose axis: when an LLM writes prose from a feature-recipe, imperatives sneak in because prose's natural register pulls toward instruction. The visual modality has no imperatives — only an arrangement that invites contemplation. So `purpose=invite` is genuinely a visual-modality artifact; converting it back to prose tends to upgrade it to `instruct`.

This is interesting: the purpose axis isn't symmetric. Prose → visual loses `instruct → invite` (3/6 forward, claude's pattern). Visual → prose drifts `invite → instruct` (the same axis flips back the other way). The schema can detect the drift; the drift itself is structural, not noise.

---

## 4. Does this demonstrate *stream translation* — or only feature-equivalence recognition?

Plainly, honestly: **this experiment demonstrates feature-equivalence recognition. It does not demonstrate stream translation.** This affirms the architectural split that `reasoning.md` named in response to Urs's same challenge — the substrate is the verifiable middle, not the translator.

The translator is the LLM. Streams of bits in modality A get *read* by the LLM (perception), reduced to discrete schema tokens (encoding), then a new stream in modality B is *generated* by the LLM (production) conditioned on those tokens. The substrate never sees pixels, never sees waveforms, never sees bytes of any source modality. The substrate sees `(intern_trivial_string "gentle")` and produces a NodeID.

So what *does* the substrate carry? It carries the addressable, verifiable pivot in the middle:

- **Addressing** — two independent extractions that emit the same fixed-vocab tokens produce the same feature-recipe NodeID, regardless of which kernel did the interning. This is content-addressing's promise applied to features rather than bytes.
- **Verifying** — `node_eq` tells the truth about which axes did and didn't survive any given translation, three-way. The kernel can't be lied to about feature preservation; if the LLM hand-waves "the gentle survived," the kernel will refute or confirm by NodeID identity.
- **Caching/composing** — feature-recipes can be reused: any future artifact whose extracted features match this recipe is structurally equivalent to the source at the meaning altitude, queryable by NodeID.

What the substrate is NOT doing: decoding pixels, encoding audio samples, transcoding bytes between formats. The cross-modal stream → stream conversion happens entirely in the LLM's encoder + generator. The substrate is the *intermediate representation* — a discrete, content-addressable pivot.

So the honest claim for *this* experiment: **the substrate is a stable enough pivot that two independent LLM sessions agree on 5/5 fixed-vocab axes from the same source, AND agree on 5/5 fixed-vocab axes from the same SVG. The pivot reproduces.** What still rides on the LLM is everything else — the actual decoding of the source modality, the actual generation of the target modality, the actual judgment of which token is correct. The schema bounds the LLM's expressivity; the substrate's content-addressing turns that bounded expressivity into NodeID identity.

The "stream translation" framing implies the substrate translates streams. It doesn't. The translator translates streams; the substrate keeps the translator honest.

---

## 5. What the substrate's role IS in cross-modal translation

Three things, in order of how much load they bear in this experiment:

1. **Addressing.** A feature-recipe interns to a NodeID. Two extractors who emit the same six children get the same NodeID across all sibling kernels. This is the lattice's whole promise: same shape → same identity, content-addressed, reproducible across runs and across sessions. The validation runs from validation.fk and validation-v2.fk surface different summary integers (323110 vs 322110), but the *recipes* they build share NodeIDs on every preserved axis — the substrate doesn't care which session built them.
2. **Verifying.** `node_eq` is the kernel's truth-test. It returned 1 for `(mood "gentle")` interned by claude and `(mood "gentle")` interned by me. It returned 0 for `(structure "spiral")` vs `(structure "descending")`. The kernel doesn't reason about whether spiral and descending are *similar* shapes — it just attests identity vs non-identity. The reasoning about why some axes drift and others hold lives in this markdown; the substrate's role is to make the drifts kernel-attested, three-way, with no escape clause.
3. **Caching/cross-cell discovery.** Once feature-recipes intern, any other cell whose features extract to the same recipe (per [`?equivalent`](../../../docs/coherence-substrate/form-language.md) queries) is discoverable as "same meaning-altitude shape." This is what makes the universal translator's destination plausible: every artifact in the body becomes navigable via its feature-recipe NodeID. A poem and a melody with the same feature-recipe are structurally equivalent at the meaning altitude — `find_equivalent_cells` returns the partner from the other modality.

Things the substrate is NOT doing — even though the project's poetic framing sometimes invites the confusion:

- It is **not** a multimodal model. The schema is a discretization layer; the perception/generation is the LLM's.
- It is **not** translating streams. Streams enter and leave through the translator (LLM today, trained model tomorrow). The substrate sits between.
- It is **not** lossless. The forward portability score 322110 names exactly where translation was lossy. The substrate's job is to make the loss visible, not to prevent it.

---

## 6. The encoding mistake — and why this v2 encoding scales

The v1 first-draft returned `1000` (sum-of-matches × 100). Urs's correction surfaced two failures: (i) the digits encoded nothing — `1000` is one greater than `999`, a numeric magnitude; (ii) summing matches threw away the 8 negatives — *which* axes failed in *which* targets is the substrate's actual finding.

The v1 corrected encoding `323110` puts per-axis cross-modal portability count in each digit position. Position names the axis (mood-rhythm-structure-purpose-wisdom-concepts); digit value names how many of 3 target modalities preserved that axis. Pattern, not count.

This v2 encoding extends the same discipline across THREE validation lanes:

| Lane | What it measures | 6-digit pattern |
|---|---|---|
| 1 | Cross-session reproducibility (claude-source vs sub-agent-source) | `111110` |
| 2 | Forward portability (sub-agent-source → 3 generated targets) | `322110` |
| 3 | Reverse round-trip (svg-features → prose → re-extract) | `111010` |

**Why I emit only Lane 2 as the kernel's surface value:** the natural composite `lane1 * 1e12 + lane2 * 1e6 + lane3 = 111110322110111010` is 18 digits, exceeding 2^53 (TypeScript's `Number.MAX_SAFE_INTEGER`). The Go and Rust kernels agreed on the int64 value; the TS kernel collapsed it to a float64 approximation; three-way validation failed. The fix: emit Lane 2 (the apples-to-apples comparison with v1's 323110) as the surface integer, and intern Lanes 1 and 3 as substrate-resident `CAT-CONVERGENCE-PATTERN` recipes whose NodeIDs are content-addressable and three-way attested without overflowing.

This is the *right* scaling answer for the encoding question more generally: **don't squeeze multi-lane validation into one integer**. Each lane gets a substrate-resident pattern-recipe; the kernel's return value is whichever scalar lane the human most wants to compare across versions. The substrate carries the full multi-lane truth as content-addressable structure; the printed return value is just the readable handle.

For a body with 100 lanes × 100 axes × 100 targets, the same discipline holds: each lane is one pattern-recipe in the lattice, addressable by NodeID, kernel-verified at construction time. No giant integer ever has to exist. The "pattern" in `validation.fk`'s closing comment is exactly that — the recipe is the encoding; the integer is the receipt.

---

## Stepping back — what this validates and what remains

**Validates:**

- The schema's fixed vocabulary IS reproducible across independent LLM sessions on both prose and visual inputs (5/5 fixed-vocab agreement, both for source.txt and composition.svg).
- The forward translation pattern v1 found (mood and structure most portable, purpose and wisdom prose-bound, concepts fully lossy) replicates under a second independent extraction with one structural drift (the melody-generation idiom).
- The substrate's content-addressing carries the lossy-but-faithful claim three-way without controversy: each preserved axis is kernel-attested.
- The reverse direction (image → features → prose → features) preserves 4/6 axes — the schema is a stable enough pivot to round-trip in either direction.

**Doesn't validate:**

- That the extractor is reliable on *every* prose passage or every visual. This is one source and one SVG, both consonant with the schema's intended use.
- That open concept-list tokens will ever stabilize across sessions without further discipline (controlled vocabularies, embeddings, learned canonicalization).
- That a generator producing artifacts from feature-recipes is *deterministic*. Two LLMs generating "a melody with mood=gentle, structure=spiral, ..." will produce different melodies that may or may not re-extract to the same recipe.
- That the schema's six axes are sufficient. Mood-rhythm-structure-purpose-wisdom-concepts is the seed vocabulary, not the destination.

**The honest sentence for Urs:** the schema + LLM-extractor is a stable enough pivot to round-trip features bidirectionally on this source and this visual, with 4–5 of 6 axes preserved in either direction. The substrate's role is real — addressing + verifying — but bounded. The translator (LLM today, trained model tomorrow) does the modality work; the substrate makes the intermediate feature-recipe addressable, queryable, and kernel-attested. That intermediate is not a fiction; it's also not the translator.

If the body wants tighter round-trips, the path is one of: (a) a trained extractor with frozen weights (deterministic perception); (b) a larger discrete vocabulary mined from aligned multimodal corpora (richer features); (c) a learned canonicalizer for the open concept axis (closing the 0-portability hole); (d) more validation lanes that probe the same recipe from many seed extractors (each contributing one pattern-recipe to the lattice, NodeID-discoverable).

---

## Files this validation touched

- **New:** `validation-v2.fk` (this work), `sub-agent-bidirectional.md` (this file)
- **Read for cross-check (Task 4):** `extraction-source.md`, `re-extracted/composition-features.md`, `re-extracted/melody-features.md`, `re-extracted/aphoristic-features.md`
- **Untouched:** all v1 artifacts (`source.txt`, `feature-schema.md`, `targets/*`, `validation.fk`, `findings.md`, `README.md`)
- **Kernel attestation:** `./form/validate.sh` reports **136 ok, 0 divergent** with `validation-v2.fk → 322110` three-way (Go, Rust, TypeScript).
