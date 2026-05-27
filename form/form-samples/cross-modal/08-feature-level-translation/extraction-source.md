# LLM extraction — features from source

Reading `source.txt` (1395 chars, CLAUDE.md "How This Body Is Tended"):

**MOOD**: `gentle`
- Reasoning: pervasive softness ("with care, not efficiency"; "Don't leave
  it as sediment"; "let them rest. Archive or release."). Not fierce, not
  joyful, not melancholy. The closest categorical label: `gentle`.
- Secondary: `reverent` (the body-as-memory framing has reverence). I'll
  honor "primary mood" since the schema is single-token.

**RHYTHM**: `breath-paced`
- Reasoning: "Move one breath at a time." "Pause between actions." Sentences
  are short to medium. Paragraphs are 2-4 sentences each. Cadence matches
  human breathing.

**STRUCTURE**: `spiral`
- Reasoning: opens with "Every file in this repo is memory" — claim. Walks
  through circulation-vs-stillness. Returns at the end to "the moment we
  declare 'done' is the moment calcification begins again" — which RECURSES
  the opening into a deeper register. Not linear, not accumulating only —
  the return is structural. `spiral`.

**PURPOSE**: `instruct`
- Reasoning: it tells the reader HOW to act ("Before adding... pause and
  sense"; "Move one breath at a time"; "ask where the living form already
  lives"). It's a teaching passage. Token: `instruct`.

**WISDOM-SHAPE**: `R_TendingDiscipline`
- Reasoning: the passage's canonical Blueprint is the practice of *continuous
  tending* — the wisdom that aliveness requires unfinished work, that
  declaring "done" is the trap. The closest canonical name in the schema is
  `R_TendingDiscipline`. (If forced to pick from `lc-cross-modal-unity`'s
  original thirteen: closest would be `R_FieldHoldingPresence`. The schema
  added `R_TendingDiscipline` specifically for this shape.)

**CONCEPTS** (5 most salient, ordered by importance):
1. `memory-as-tissue` — opening claim that file/repo = body memory
2. `circulation-feedback` — circulation = readers/references/contradictions
3. `composting-with-care` — release of former-loved things, not efficiency
4. `present-breath` — one breath at a time, pause between actions
5. `continuous-tending` — done is the trap; aliveness requires unfinished

## Feature-recipe encoded as Form

```form
(let source-features
    (feature-recipe
        (mood    "gentle")
        (rhythm  "breath-paced")
        (structure "spiral")
        (purpose "instruct")
        (wisdom  "R_TendingDiscipline")
        (intern_node CAT-CONCEPTS-LIST
            (list (concept "memory-as-tissue")
                  (concept "circulation-feedback")
                  (concept "composting-with-care")
                  (concept "present-breath")
                  (concept "continuous-tending")))))
```

The NodeID of `source-features` is the SHA-determined identity at the
feature-recipe altitude. Anything that re-extracts to this exact six-child
shape interns to the same NodeID.
