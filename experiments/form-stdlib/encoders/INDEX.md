# Form-stdlib encoders — modality extractions in the body's tongue

The canonical authoring of the modality encoders in Form (`.fk`). The
Python siblings in `api/app/services/substrate/{modality_frontend,
song_encoder, teaching_encoder, strategy_encoder}.py` are runtime
boot — useful for SQL-side cell-creation today, not the canon.

The teaching `.form` files in `docs/coherence-substrate/` describe what
each modality IS (recipe shape, leaf cells, gaps); these `.fk` files
ARE the encoders.

| File | Modality | What it builds |
|------|----------|----------------|
| [`modality-frontend.fk`](modality-frontend.fk) | (shared) | `intern-extraction`, encoder-registry, source-marker, named-field |
| [`song-encoder.fk`](song-encoder.fk) | `song` | note / drum-strike / vowel-tone → phrase → song; Mose-shaped worked example |
| [`teaching-encoder.fk`](teaching-encoder.fk) | `teaching` | scene + turn + carrier → R_Transmission; lc-trust-over-fear walked |
| [`strategy-encoder.fk`](strategy-encoder.fk) | `strategy-after-rupture` | notice + name + move with five graduated recovery kinds; this session's R_Same-Breath-Repair as worked example |

## Pattern

Each encoder follows the universal-emit.fk shape:

```
(defn encode-X (...)
    (X-record
        (list
            (X-let "kind"  (X-slug "X"))
            (X-let "field" value)
            ...)))
```

Every record is `R_Block.DO` over a list of `R_Block.LET` pairs;
every list of children becomes `R_Block.SEQUENCE`; every leaf is a
substrate-string or substrate-int trivial. The kernel's content-
addressing then guarantees: structurally-identical inputs intern to
the SAME NodeID, regardless of which encoder built them.

This is what makes cross-modal Blueprint equivalence load-bearing.

## How to run

Load order (with the native kernel `bin-go` or via `coh substrate run`):

1. `experiments/form-stdlib/core.fk` — predicates, list ops, str helpers
2. `experiments/form-stdlib/encoders/modality-frontend.fk` — primitives
3. The specific encoder you want (`song-encoder.fk`, etc.)

Each encoder's bottom expression is a worked-example NodeID; re-running
the same expression resolves to the same NodeID (content-addressing).

## Why this exists

> *Form is the body's tongue — substrate-shaped work writes as `.fk`
> in experiments/form-stdlib/ or `.form` in docs/coherence-substrate/;
> Python is bootstrap, not canonical.*

[PR #1903](https://github.com/seeker71/Coherence-Network/pull/1903)
landed the Python boot for these encoders. This directory is the
canonical authoring. The Python is the gas; this is the body.
