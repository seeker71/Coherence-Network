# Form-stdlib encoders — modality extractions in the body's tongue

The encoders for the modality lattice. The Go kernel (`bin-go`) walks
these `.fk` files directly; the teaching `.form` files in
`docs/coherence-substrate/` describe what each modality IS (recipe
shape, leaf cells, gaps), these `.fk` files ARE the encoders.

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

```
bin-go core.fk encoders/modality-frontend.fk encoders/<modality>-encoder.fk
```

The Go kernel walks `.fk` natively. Each encoder's bottom expression
is a worked-example NodeID; re-running the same expression resolves
to the same NodeID (content-addressing).

Verified NodeIDs from [PR #1904](https://github.com/seeker71/Coherence-Network/pull/1904):

- song → `@1.2.9.399`
- teaching → `@1.2.9.496`
- strategy → `@1.2.9.394`
