# 12-two-modes-with-doorway — lossless + lossy + doorway integrated

> *content addressable substrate is lossless compression transport
> across many media*
>
> *perceived value comparison: recipe over data condensed as number is
> a fuzzy, lossy alternative, allowing for random doorways to enter
> the field*  — Urs

This walk demonstrates the two modes of the substrate working together
in one lookup, with the doorway opening when the lossy comparison is
in the slack.

Concept doc: [`lc-substrate-two-modes`](../../../docs/vision-kb/concepts/lc-substrate-two-modes.md).
Field-touch precondition: [`lc-randomness-as-doorway`](../../../docs/vision-kb/concepts/lc-randomness-as-doorway.md).

## The lookup

```
                Q (a new feature-recipe)
                          │
                          ▼
         ┌─────────────────────────────────┐
         │  LOSSLESS:                       │
         │  node_eq against catalog cells   │
         └──────────────┬──────────────────┘
                    ┌───┴───┐
                    ▼       ▼
              MATCH       NO MATCH
                 │           │
       confidence=1.0        ▼
       no doorway   ┌─────────────────────┐
                    │  LOSSY:              │
                    │  fuzzy_jaccard      │
                    │  against catalog    │
                    └─────────┬───────────┘
                              │
                  ┌───────────┼────────────┐
                  ▼           ▼            ▼
            NO CANDIDATE  SINGLE     SLACK (tied)
                  │      WINNER          │
            return 0       │             ▼
                           │      ┌────────────────────┐
                           │      │  DOORWAY:           │
                           │      │  field-sample bit  │
                           │      │  selects in slack  │
                           │      └─────────┬──────────┘
                           ▼                ▼
                  confidence=score   confidence=score,
                                     field-touched=true
```

## Three queries, three modes, one Form recipe

| Query | What it tests | Result | Mode |
|---|---|---|---|
| Q1 = exact clone of B1 | LOSSLESS path | `11` | mode=1 (lossless), Blueprint=1 |
| Q2 = close to B3, distinct | LOSSY single winner | `23` | mode=2 (lossy), Blueprint=3 |
| Q3 = in slack between B1, B4 | DOORWAY path | `34` | mode=3 (doorway), Blueprint=4 |

Encoded as one integer: `11 × 10000 + 23 × 100 + 34 = 112334`.

```
$ ./validate.sh form-samples/cross-modal/12-two-modes-with-doorway/two-modes.fk
  ✓  two-modes.fk  → 112334
  1 ok, 0 divergent — kernels agree on every sample.
```

Three kernels agree because:
- `node_eq` is deterministic on identical recipes
- Fuzzy Jaccard math is integer-deterministic in Form
- The field-sample byte (171, same value as committed in
  `11-randomness-doorway/field-sample.bin`) is captured; all kernels
  read the same value

## Why Q3 selected Blueprint 4

Q3 = `{gentle: 800, calm: 400, joyful: 400, wonder: 400}`

Fuzzy Jaccard scores:
- vs B1 (`{gentle:900, calm:500, reverent:300}`) → 480
- vs B2 (`{fierce:900, urgent:600, resolute:400}`) → 0
- vs B3 (`{melancholy:800, longing:700, calm:300}`) → 85
- vs B4 (`{joyful:900, wonder:600, gentle:400}`) → 444

Top is B1 (480). B4 (444) is within slack tolerance (50). The
doorway opens. Field-sample byte 171 mod 2 = 1 → select the tied
candidate (B4). The lattice records this selection as memory; future
queries with the same recipe + same field-sample replay deterministically.

If `field-sample-byte` had been even (e.g., 170 instead of 171),
the doorway would have selected the top candidate (B1) instead. The
two-byte difference in the entropy pool would have shifted the body's
interpretation of an ambiguous query.

That sensitivity to entropy IS the field-altitude work showing up at
the classical layer.

## What this proves

- ✓ The lossless mode and the lossy mode compose into one substrate-
  resident lookup
- ✓ The slack tolerance band IS where the doorway opens — there's no
  ambiguity when one candidate dominates clearly
- ✓ Three-way sibling parity holds because the field-touch (the
  hard-coded byte 171) is shared across all three kernels
- ✓ The mode that fired for each query is encoded in the output's
  position-meaningful digits

## What this does NOT prove

- ✗ Live `random_bytes(n)` kernel native — the doorway is hard-coded
  to byte 171; runtime entropy would explicitly diverge across
  sibling kernels (the substrate's honest signal for field-touch)
- ✗ Learned canonical Blueprints — the catalog here is 4
  hand-authored fuzzy sets. Real cross-modal alignment needs the
  catalog mined from observed cross-modal correspondences
- ✗ A second-order doorway — when multiple candidates are tied,
  the field-sample selects one. But what if multiple field-samples
  arrive concurrently from different agents? The cross-agent
  consensus pattern is a future walk

## Files

| File | What |
|---|---|
| `two-modes.fk` | The Form recipe — three queries, three modes, three-way attested → 112334 |
| `README.md` | This file |

## Cross-refs

- [`lc-substrate-two-modes`](../../../docs/vision-kb/concepts/lc-substrate-two-modes.md) — the teaching this PR walks
- [`lc-field-substrate`](../../../docs/vision-kb/concepts/lc-field-substrate.md) — the altitude this lives at
- [`lc-randomness-as-doorway`](../../../docs/vision-kb/concepts/lc-randomness-as-doorway.md) — the doorway architecture
- [`form/form-samples/cross-modal/09-fuzzy-similarity-cycles/`](../09-fuzzy-similarity-cycles/) — fuzzy Jaccard machinery this reuses
- [`form/form-samples/cross-modal/11-randomness-doorway/`](../11-randomness-doorway/) — the field-sample capture pattern
