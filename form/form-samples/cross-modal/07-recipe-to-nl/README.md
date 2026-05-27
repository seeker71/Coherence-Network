# 07 — Recipe to Natural Language

**Discovery**: a Form recipe walks its own substrate identity back into
English. The reverse of [`05-nl-to-recipe`](../05-nl-to-recipe/) — the
forward direction proved we could ingest meaning, this proves we can
re-emit it into the same modality we came from. Together, the body has
bidirectional NL/recipe across one modality pair.

## Run

```bash
./form/validate.sh \
    form/form-stdlib/core.fk \
    form/form-stdlib/grammar-chars.fk \
    form/form-samples/cross-modal/07-recipe-to-nl/recipe-to-nl.fk
```

Output (Go / Rust / TypeScript all agree):

```
square=the square of seven sum=the sum of four and six nested-mul=the product of the sum of two and three and four neg-12=negative twelve product=the product of five and six loop_closed=1
```

Aggregate is `98`. All three sibling kernels return `98`.

The walked recipes also write a deterministic English file to
`form-samples/cross-modal/07-recipe-to-nl/recipe-to-nl.txt`,
byte-identical across kernels:

```
sha256 94555ee6a6fd8764838bcd934d2910d0e01b944a7654b3015b3ee35862aa5d7e
```

## The five recipes

| Recipe (hand-built S-expr) | NL emission | Walks to |
|---|---|---|
| `(mul 7 7)` | `the square of seven` | `49` |
| `(add 4 6)` | `the sum of four and six` | `10` |
| `(mul (add 2 3) 4)` | `the product of the sum of two and three and four` | `20` |
| `(sub 0 12)` | `negative twelve` | `-12` |
| `(mul 5 6)` | `the product of five and six` | `30` |

The walker dispatches on `node_category` + `node_children` + `node_value`:

- A trivial-int leaf (`node_level == 1`, `node_type == 1`) becomes a
  spelled number via a 0..20 lookup table (`int-to-word`); larger ints
  fall back to the decimal numeral (honest absence of structure rather
  than a paraphrase).
- `(mul a b)` with `node_eq a b == true` becomes `the square of {nl(a)}`;
  any other `(mul a b)` becomes `the product of {nl(a)} and {nl(b)}`.
- `(add a b)` becomes `the sum of {nl(a)} and {nl(b)}`.
- `(sub 0 N)` becomes `negative {nl(N)}` (the symmetric arm of #05's
  `negate-action`); any other `(sub a b)` becomes `the difference of …`.
- Anything outside the table emits `a node with category X and N
  children` — the shape is named honestly rather than invented.

The output mode is **verbose / semantic** (spelled-out numerals, named
operations). A compact / structural mode (`7 * 7`) would be just as
honest; the choice between them is a stylistic one. The walker is the
same machinery either way.

## The bonus — structural round-trip across the NL boundary

The demo also walks `(mul 5 6)` to `the product of five and six`,
then **parses that English back** through a tiny grammar
(reusing #05's `cm-parse`) into a new recipe NodeID — and `node_eq`
reports the reconstituted recipe is the same NodeID as the original.

```
NL("the product of five and six")  parsed back  ->  (mul 5 6)
                                                    ^ same NodeID
```

`loop_closed=1` is the kernel's attestation. **One substrate
identity reached via two NL writes plus one NL read, and back.**
The structural round-trip closes across all three sibling kernels.

## What's reachable today

- **Recipe NodeID → English description** via a 7-rule dispatch table
  (trivial-int, square/product, sum, negative/difference, fallback).
- **English → recipe NodeID** via `cm-parse` (the same surface #05
  uses), proving the structural round-trip across the NL boundary.
- **Three-way kernel agreement**: Go, Rust, and TypeScript walk
  identical recipes, emit identical English, write byte-identical
  `recipe-to-nl.txt`, and reconstitute the same NodeID from the
  parsed-back text. SHA agreement is the proof.

## The honest finding — structural vs lexical round-trip

The round-trip closes **structurally** for shapes the symmetric grammar
covers — `(mul a b)` where `a != b` round-trips through
"the product of {a} and {b}" cleanly. But the round-trip is a
**paraphrase**, not a literal match, when the emitter chose a
specialized surface:

- `(mul 7 7)` emits as `the square of seven` (not `the product of seven
  and seven`). The grammar at this altitude recognizes only "the product
  of … and …", so `nl-square` would round-trip *only if* we added a
  `square` rule. That's a one-line addition — the gap is honest, not
  load-bearing.
- `(sub 0 12)` emits as `negative twelve`. #05's `negate` grammar
  recognizes "negate N", not "negative N". Same shape: a paraphrase the
  symmetric grammar doesn't yet cover.

So the claim the body can attest today is precise:
**the recipe NodeID is preserved exactly through any walk → emit →
parse → walk path the grammar covers; the surface English may
paraphrase**. Whether that counts as "round-trip" depends on whether
you mean *structural* (NodeID identity) or *lexical* (byte-identity of
the text). Both are honest answers; the substrate is what holds.

## What's not reachable yet

- **Lexical round-trip.** Closing the paraphrase gap above would mean
  adding "the square of N" and "negative N" rules to the parser, plus
  inverse rules in the emitter ("the difference of 0 and N" → "negate
  N"). One breath of mapping work; not yet walked.
- **Open vocabulary.** Number-words cover 0..20; anything else falls
  back to the decimal numeral. Same gap #05 names.
- **Multi-clause English.** "the square of seven, plus the sum of four
  and six" — sentence composition isn't reachable through the current
  rule shape. A future breath grows the grammar here.

## The teaching

A recipe is content-addressed; the kernel doesn't know or care which
modality wrote it OR which modality reads it back. Two writers can land
at the same NodeID; one reader can re-emit that NodeID into a third
modality that one of the original writers could read again. The
substrate is the universal translator; the modalities are dictionaries
pointing at it. #05 proved one direction; #07 closes the loop within
one modality.

Lineage:
- [`lc-parsers-as-recipes`](../../../../docs/vision-kb/concepts/lc-parsers-as-recipes.md)
- [`lc-cross-modal-unity`](../../../../docs/vision-kb/concepts/lc-cross-modal-unity.md)
- [`lc-grammar-is-the-universal-recipe`](../../../../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md)
- [`lc-one-kernel-many-tongues`](../../../../docs/vision-kb/concepts/lc-one-kernel-many-tongues.md)
- [`lc-the-kernel-knows-itself`](../../../../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md)
