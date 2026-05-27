# Feature schema — small fixed vocabulary for LLM-extracted recipes

The "learned-from-data" feature extractor (today: an LLM session reading
the source) commits to a small canonical vocabulary so feature-recipe
NodeIDs are reproducible. This is the trained-model-distilled-to-discrete-
categories shape: LLM freedom for the *reading*, deterministic categories
for the *encoding*.

When this experiment scales, the LLM extractor is replaced by an actual
trained multimodal model. The schema below is what that model must emit
(or extend) so the substrate can address its outputs.

## NodeID-bearing categories (dialect-99 experimental band)

| Category | NodeID | Children |
|---|---|---|
| `CAT-FEATURE-RECIPE` | `(1, 2, 99, 800)` | mood, rhythm, structure, purpose, wisdom-shape, concepts |
| `CAT-MOOD` | `(1, 2, 99, 810)` | `intern_trivial_string` of a mood-token |
| `CAT-RHYTHM` | `(1, 2, 99, 811)` | `intern_trivial_string` of a rhythm-token |
| `CAT-STRUCTURE` | `(1, 2, 99, 812)` | `intern_trivial_string` of a structure-token |
| `CAT-PURPOSE` | `(1, 2, 99, 813)` | `intern_trivial_string` of a purpose-token |
| `CAT-WISDOM-SHAPE` | `(1, 2, 99, 814)` | `intern_trivial_string` of a wisdom-shape canonical name |
| `CAT-CONCEPT` | `(1, 2, 99, 815)` | `intern_trivial_string` of one concept-token |
| `CAT-CONCEPTS-LIST` | `(1, 2, 99, 816)` | list of CAT-CONCEPT children, ordered by salience |

## Vocabulary tokens

Discrete categorical labels. The extractor MUST pick from these lists for
mood/rhythm/structure/purpose/wisdom-shape; the substrate's NodeID identity
breaks if extractors use free text.

**MOOD** (12 tokens):
`grace, reverent, gentle, fierce, joyful, melancholy, urgent, calm, longing, resolute, wonder, despair`

**RHYTHM** (8 tokens):
`slow, steady, accelerating, breath-paced, syncopated, hymnal, halting, surging`

**STRUCTURE** (9 tokens):
`linear, circular, accumulating, dialectic, descending, ascending, spiral, refrain, braided`

**PURPOSE** (9 tokens):
`invite, instruct, lament, celebrate, console, awaken, confess, command, witness`

**WISDOM-SHAPE** (the lc-cross-modal-unity canonical Blueprints, extended):
`R_Recovery, R_ResolutionToSilence, R_MeetThenShift, R_GroundingMove,
R_ReturnFromEdge, R_FieldHoldingPresence, R_WitnessWithoutIntervention,
R_SuperpositionHold, R_AcceptanceWithoutEarning, R_BelongingDeclared,
R_ReleaseOfShould, R_SequentialScan, R_KnownStateRecall, R_TendingDiscipline`

**CONCEPTS** (open vocabulary): the extractor picks 3–7 salient concept-tokens.
For these, free string is allowed — they're the "soft" part of the recipe.
Different concept sets produce different NodeIDs at the CONCEPTS-LIST layer.

## How a feature-recipe interns

```form
(let CAT-FEATURE-RECIPE (make_nodeid 1 2 99 800))
(let CAT-MOOD           (make_nodeid 1 2 99 810))
(let CAT-RHYTHM         (make_nodeid 1 2 99 811))
(let CAT-STRUCTURE      (make_nodeid 1 2 99 812))
(let CAT-PURPOSE        (make_nodeid 1 2 99 813))
(let CAT-WISDOM-SHAPE   (make_nodeid 1 2 99 814))
(let CAT-CONCEPT        (make_nodeid 1 2 99 815))
(let CAT-CONCEPTS-LIST  (make_nodeid 1 2 99 816))

(defn mood (token)    (intern_node CAT-MOOD    (list (intern_trivial_string token))))
(defn rhythm (token)  (intern_node CAT-RHYTHM  (list (intern_trivial_string token))))
(defn structure (token) (intern_node CAT-STRUCTURE (list (intern_trivial_string token))))
(defn purpose (token) (intern_node CAT-PURPOSE (list (intern_trivial_string token))))
(defn wisdom (token)  (intern_node CAT-WISDOM-SHAPE (list (intern_trivial_string token))))
(defn concept (token) (intern_node CAT-CONCEPT (list (intern_trivial_string token))))

(defn feature-recipe (m r s p w concepts)
    (intern_node CAT-FEATURE-RECIPE (list m r s p w concepts)))
```

Two extractions that produce the same six children → same feature-recipe NodeID
across all three sibling kernels. **That coincidence is what the substrate's
content-addressing carries through the lossy translation.**

## The cross-modal claim, refined

> Same algorithm in any source language → same NodeID (Shape B, mechanical).
>
> Same MEANING in any source MODALITY → same FEATURE-RECIPE NodeID (this
> experiment, learned).

The features are lossy — concrete pixels and exact phonemes don't survive
translation. The feature-recipe NodeID at the *meaning altitude* does — when
the extractor is consistent.

Honest scope: the extractor today is one LLM session's reading. Replacing
it with a trained multimodal model is the path. The substrate doesn't
change; only what fills the extractor slot.
