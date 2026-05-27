# Re-extracted features from `targets/composition.svg`

The LLM reads the SVG (the rendered visual, plus its companion .md) and
emits a feature-recipe with the same discipline.

- **MOOD:** `gentle` — muted earth palette, soft gradient, varying line
  weights, no hard edges. Gentle, unambiguous.
- **RHYTHM:** `breath-paced` — concentric arcs expand progressively (radii
  100, 130, 160, 180), suggesting breath expansion; stroke-dasharray
  creates rhythmic gaps in the line.
- **STRUCTURE:** `spiral` — literal spiral at center; concentric arcs
  reinforce circular-return shape.
- **PURPOSE:** `invite` — visual composition INVITES contemplation; it
  doesn't command in the way prose does. **Diverges from source's
  `instruct`.**
- **WISDOM-SHAPE:** `R_FieldHoldingPresence` — the periphery breath-marks
  hold a field around the central spiral; the incomplete arcs let-go
  without forced closure. Field-holding rather than tending-discipline.
  **Diverges from source's `R_TendingDiscipline`.**
- **CONCEPTS:**
  1. `spiral-of-attention`
  2. `concentric-presence`
  3. `organic-texture`
  4. `periphery-honoring`
  5. `incomplete-arc`

**None of the source's concept tokens reappear.** Visual modality emits a
distinct concept vocabulary (spatial, formal) where the source emitted a
semantic vocabulary (tissue, circulation, composting).

## What survives, what doesn't (vs source)

| Feature | Survived? |
|---|---|
| Mood (gentle) | ✓ |
| Rhythm (breath-paced) | ✓ |
| Structure (spiral) | ✓ |
| Purpose (instruct) | ✗ → invite |
| Wisdom-shape (R_TendingDiscipline) | ✗ → R_FieldHoldingPresence |
| Concepts | ✗ (different vocabulary — spatial/formal) |

3 of 6 feature axes preserved — same pattern as melody re-extraction.
