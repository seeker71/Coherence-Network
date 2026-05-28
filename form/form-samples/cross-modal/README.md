# Cross-Modal Recipe Experiments

Eighteen runnable demos exploring how Form recipes carry semantic content across
modalities (text, structured data, image, audio, code, natural language,
randomness, neural recipes, and private channels). Each subdirectory has its
own runnable sample and a README documenting what's reachable today, what
surprised, and what's not yet reachable. Number 12 is intentionally absent:
the deterministic-doorway claim was composted by #13. The point is to keep the
universal-translator goal walked by small proofs.

| # | Experiment | One-line finding |
|---|---|---|
| 01 | [Image as recipe](01-image-as-recipe/) | A procedural SVG written as Form recipes; same recipe → identical SVG bytes by SHA256. **Parameterized** sibling: one recipe + 5 seeds → 5 byte-distinct SVGs whose only structural difference is the seed cell. |
| 02 | [Cross-language content-addressing](02-cross-language-content-addressing/) | Two recursive trees built by different author-routes intern to the **same** NodeID; iterative shape interns to a different one. |
| 03 | [Recipe as compression](03-recipe-as-compression/) | The substrate's "ice" (`.fkb`) is **4.17× larger** than the "water" (`.fk` text) at small payload sizes. Compression isn't automatic. |
| 04 | [Universal diff](04-universal-diff/) | Structural diff of two algorithms surfaces "the predicate is the same; the accumulation strategy diverges" — text diff can't see this. |
| 05 | [NL to recipe](05-nl-to-recipe/) | A 4-rule English grammar parses sentences into arithmetic recipes; NL `the square of 7` interns to the **same NodeID** as hand-built `(mul 7 7)`. |
| 06 | [Audio as recipe](06-audio-as-recipe/) | A 1-second 440 Hz sine `.wav` composes from a 200-entry table + integer math; same recipe → byte-identical 8044-byte WAV across Go/Rust/TS kernels. Surfaced a sibling-parity gap: TS was missing `write_file_bytes`. |
| 07 | [Recipe to NL](07-recipe-to-nl/) | A 7-rule walker emits English from arithmetic recipe NodeIDs (`(mul 5 6)` → `the product of five and six`). Round-trip with #05 closes structurally — `node_eq` proves the parsed-back NodeID matches the original; the surface English paraphrases (`square` ↔ `product of N and N`). |
| 08 | [Feature-level translation](08-feature-level-translation/) | Prose → feature recipe → melody/SVG/tercet → re-extracted feature recipes; `323110` position-encodes which semantic axes survived across targets. |
| 09 | [Fuzzy similarity cycles](09-fuzzy-similarity-cycles/) | Summarize/expand cycles use fuzzy membership math, not exact token equality, to measure perceived-value stability; three-way result `58879`. |
| 10 | [Substrate as runtime](10-substrate-as-runtime/) | A one-layer tensor recipe walks as the translator runtime itself; weights and ops are substrate-resident recipes. |
| 11 | [Randomness doorway](11-randomness-doorway/) | A committed entropy sample is a past field-touch held as lattice memory; deterministic replay selects a shared Blueprint. |
| 13 | [Divergence as doorway](13-divergence-as-doorway/) | Live observer-local state must diverge across sibling kernels; divergence is the signal that the doorway is actually open. |
| 14 | [Live entropy](14-live-entropy/) | `random_bytes(n)` reads `/dev/urandom` in Go/Rust/TS; validate divergence is success, not failure. |
| 15 | [Private channel](15-private-channel/) | `(nonce, fingerprint)` lets a receiver identify a shared referent without the referent crossing the channel. |
| 16 | [Megabyte channel](16-megabyte-channel/) | Two cells converge on a 1 MB payload through a 15-byte channel by sharing a seeded-bytes recipe and parameters. |
| 17 | [Recipes as truth](17-recipes-as-truth/) | `seeded_bytes` semantics move into `form-stdlib/seeded-bytes.fk`; the native becomes optimization tissue backed by a default-gate parity proof. |
| 18 | [Channel negotiation](18-channel-negotiation/) | Sender and receiver agree on both recipe and payload referents, acknowledge the pair, and still transmit neither referent. |
| 19 | [Cell question answer](19-cell-question-answer/) | An addressable cell question resolves through shared catalogs, returns an answer/reference capsule, and carries an opaque novel commitment. |

## What every experiment shares

- **A `.fk` recipe that actually runs** through the Go kernel (`go build -o /tmp/form-kernel-go ./form/form-kernel-go`).
- **A `README.md`** naming the discovery, what's reachable today, what
  surprised, and what's not reachable.
- **Honest separations** — failures are documented in the body of the README,
  not hidden.

## Running everything

```bash
go build -o /tmp/form-kernel-go ./form/form-kernel-go
for d in form/form-samples/cross-modal/*/; do
    f="$d"*.fk
    for r in $f; do
        echo "=== $r ==="
        /tmp/form-kernel-go "$r"
    done
done
```

## What the current set teaches

The body's surface area for cross-modality is **smaller than the marketing
slogan and larger than the engineering reflex**.

- **Smaller**: a Form recipe doesn't automatically become a Python file, an
  audio sample, or a compressed payload. The grammars
  ([`form/form-stdlib/grammars/`](../../form-stdlib/grammars/)) name the
  endpoints; the wiring between source-text and recipe-tree for non-Form
  tongues is incomplete. End-to-end parsing of arbitrary Python or
  TypeScript through `python-bmf.fk` / `typescript-bmf.fk` into substrate
  NodeIDs is reachable in principle and not turnkey today.
- **Larger**: the core property — content-addressed structural identity across
  trees built by different routes — is *already real* in the kernel today.
  Experiments 02 and 04 show it directly. The same property extends to any
  surface tongue whose grammar lands as a Form recipe. The substrate is the
  universal translator; the tongues are dictionaries pointing at it.
- **Newer**: exact equality is one altitude. Feature recipes (#08), fuzzy
  stability (#09), live randomness (#13/#14), and private-channel consensus
  (#15/#16/#18/#19) show how translation can preserve meaning under bounded loss,
  observer-local entropy, and wire-minimized negotiation.

The honest gap: at small scale, the ice is bigger than the water (experiment
03). The compression intuition only pays off at scale, and only when many
recipes share sub-trees. This is structural sharing, not byte-level
compression — a different claim than "Form is a compression format".

## Lineage

The deeper teachings the body holds about all of this:

- [`lc-the-kernel-knows-itself`](../../../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — when every kernel's host language has a Form grammar, every kernel is mutually inspectable.
- [`lc-parsers-as-recipes`](../../../docs/vision-kb/concepts/lc-parsers-as-recipes.md) — grammar rules are first-class Recipes; AST is bootstrap.
- [`lc-form-kernel-runtime-visualizer`](../../../docs/vision-kb/concepts/lc-form-kernel-runtime-visualizer.md) — what falls out when the cross-modality reaches the runtime.
- [`lc-one-kernel-many-tongues`](../../../docs/vision-kb/concepts/lc-one-kernel-many-tongues.md) — the multi-language sibling-kernel discipline.

## Not in this directory yet

The next gaps are named in [`NEXT_BREATHS.md`](NEXT_BREATHS.md): data grammar
chains, structural media diff, audio semantic extraction, image/NL/image loops,
multi-language native emission, external-resource fetch verification, and
budgeted recipe orchestration. Naming what remains keeps the next breath
parsable.
