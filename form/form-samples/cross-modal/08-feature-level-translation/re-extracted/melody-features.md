# Re-extracted features from `targets/melody.md`

The LLM reads the melody description fresh — same extraction discipline as
the source — and emits a feature-recipe.

- **MOOD:** `gentle` — A minor at pp dynamics, slow tempo, cello drone, no
  louder than mezzo-piano. Unambiguously gentle.
- **RHYTHM:** `breath-paced` — 56 BPM in 6/8, 6-bar phrases (~13s each)
  matching contemplative breath cycles.
- **STRUCTURE:** `spiral` — A → A' (transposed up a third) → B (descent
  into lower octave) → A'' (return, but unresolved final note). The
  return-deepened shape is structurally spiral.
- **PURPOSE:** `invite` — pure music doesn't instruct in the imperative
  way prose does. The melody contemplates and invites the listener
  inward. **Diverges from source's `instruct`.**
- **WISDOM-SHAPE:** `R_FieldHoldingPresence` — the cello drone holds a
  field; the unresolved final note holds presence rather than declaring
  closure. The "discipline" specificity that prose carries doesn't
  emerge from pure sound — the field-holding shape does. **Diverges from
  source's `R_TendingDiscipline`.**
- **CONCEPTS:**
  1. `descent-and-return`
  2. `held-presence`
  3. `contemplative-time`
  4. `unfinished-closure`
  5. `motif-as-breath`

**None of the source's concept tokens reappear.** Conceptually, the
melody re-extraction is a *parallel* semantic field, not the same one.

## What survives, what doesn't (vs source)

| Feature | Survived? |
|---|---|
| Mood (gentle) | ✓ |
| Rhythm (breath-paced) | ✓ |
| Structure (spiral) | ✓ |
| Purpose (instruct) | ✗ → invite |
| Wisdom-shape (R_TendingDiscipline) | ✗ → R_FieldHoldingPresence |
| Concepts | ✗ (entirely different vocabulary) |

3 of 6 feature axes preserved their NodeID across the prose→melody translation.
