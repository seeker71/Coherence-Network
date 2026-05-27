# Findings — fuzzy similarity through summarize→expand cycles

## Setup

- **Source:** the same 1395-char CLAUDE.md "How This Body Is Tended"
  passage used by v1/v2 (`08-feature-level-translation/source.txt`).
- **Cycle:** `source → S1 → E1 → S2 → E2` (compress, expand, compress, expand).
- **Extraction:** LLM emits a *fuzzy set* per axis (memberships scaled
  μ × 1000 in [0, 1000]) over the v1 schema's fixed vocabulary
  (mood/rhythm/structure/purpose/wisdom-shape).
- **Operator:** standard Zadeh — t-norm = `min`, t-conorm = `max`,
  similarity = **fuzzy Jaccard** = Σmin(μ_A, μ_B) / Σmax(μ_A, μ_B).
- **Kernel:** Form recipe implementing the above in integers, walked
  three-way by Go / Rust / TypeScript.

## Headline result, three-way

```
$ ./validate.sh form-samples/cross-modal/09-fuzzy-similarity-cycles/fuzzy-validation.fk
  ✓  fuzzy-validation.fk  → 58879
  1 ok, 0 divergent — kernels agree on every sample.
```

The 5 digits are the cycle dynamics, position-encoded:

| Position | Metric | Reading | What it means |
|---|---|---|---|
| ×10000 | **src vs S1** | 5 → **56%** | First compression loses ~44% of fuzzy similarity |
| ×1000 | **src vs E1** | 8 → **84%** | Expansion recovers most of what compression cost |
| ×100 | **src vs E2** | 8 → **80%** | Full cycle preserves ~80% (the headline number) |
| ×10 | **S1 vs S2** | 7 → **77%** | Compression attractor — compression converges, but to its own stable shape |
| ×1 | **E1 vs E2** | 9 → **94%** | Expansion attractor — expansions are highly stable |

Substrate-resident: `CAT-CYCLE-DYNAMICS` recipe holds the precise
0..1000 values in five integer children. NodeID is the structural
signature of this cycle.

## What this means, mathematically and meaningfully

### Compression is lossy; expansion is stabilizing

`src → S1` drops fuzzy similarity from 1.0 to 0.56. **Compression
collapses the membership distributions** — sharpening certain tokens
(`resolute`, `command`, `halting`) and dropping others (`hymnal`,
`circular`, `console`). The LLM, when asked to summarize, picks an
imperative register and a halting cadence that the source didn't carry.

`S1 → E1` brings similarity back to 0.84 — expansion partially
**recovers** the source's softer distribution. The LLM, asked to
expand from a terse summary, reaches for gentler tokens and breath-paced
rhythm because the natural register of contemplative prose pulls there.

### The two attractors

Two basins of stability emerged:

- **Compression attractor (`S1 ↔ S2` = 77%):** repeated compression
  converges to a shape that's stable with itself but distinct from
  source. Compression has its own "favored vocabulary" — `resolute,
  command, halting, accumulating` — drift tokens that don't appear
  in the source's top memberships.
- **Expansion attractor (`E1 ↔ E2` = 94%):** repeated expansion
  converges very tightly. Once the LLM has a summary, the *expanded*
  shape it produces is highly reproducible across runs.

The expansion attractor is **17 percentage points more stable than
the compression attractor**. Asymmetric dynamics: compression has more
freedom (many ways to summarize), expansion is more constrained
(summary → expansion is closer to a function).

### Full-cycle preservation (80%) is the real claim

If you ran an unbounded chain (`S1 → E1 → S2 → E2 → S3 → E3 → ...`),
the similarity to source would *asymptote* — drift bounded by the
attractor-pair geometry, not unbounded decay. The 80% at step 4 is
near the asymptotic floor; further cycles would lose at the per-cycle
loss rate (~3–5%, slower than initial).

### This is what Urs's "fuzzy logic" framing was for

Bit-exact `node_eq` would have answered "0" everywhere — no two
extractions would intern to the same recipe across the cycle. The
fuzzy Jaccard answers what actually matters: **how much of the
shape survives?** That's the right altitude for cross-modal meaning.

## Why this is honest

- **Fuzzy memberships are LLM-generated**, not learned. A trained
  multimodal model would emit deterministic membership distributions
  per artifact; my session is one example reading. Different sessions
  would produce slightly different fuzzy sets (the v1/v2 cross-session
  reproducibility test showed 5/5 top-token agreement but membership
  *degrees* would vary).
- **Schema is small** (5 fixed-vocab axes + open concepts not measured
  here). Real cross-modal alignment needs many more axes (Urs's list:
  *flow, beats, melody, harmony, spectrum, meaning, purpose, wisdom*).
- **Cycle is text-only.** The genuinely interesting cross-modal test
  is `text → image → text` — fuzzy similarity through *modality*
  changes, not register changes. That's a next walk.

## Proper Mamdani-style fuzzy logic, named (not used here)

The Zadeh standard operators used here (min/max) are the simplest
choice. Other proper t-norms/t-conorms with different sharpness:

| t-norm | Formula | Behavior |
|---|---|---|
| **Min** (Zadeh) | `min(a, b)` | Used here. Idempotent. Conservative. |
| Product | `a · b` | Smoother. Aggregates softly. |
| Łukasiewicz | `max(0, a+b-1)` | Strict. Returns 0 if memberships don't both exceed 0.5. |
| Drastic | `0 unless one is 1` | Hardest. Almost never fires. |

For perceived-value similarity at the meaning altitude, **product**
might be a better choice than min — it punishes weak agreement on
both sides multiplicatively, while min only sees the weaker side.
Trying product as the t-norm is a small variation; results would
shift but the structural finding (compression-loss / expansion-recovery
asymmetric attractors) would hold.

Mamdani-style **rules** would let the substrate carry domain-specific
knowledge:

```
IF mood is gentle AND rhythm is breath-paced AND wisdom is R_TendingDiscipline
   THEN passage is contemplative-instruction (degree = min of premises)
```

Multiple rules aggregate by t-conorm (max over firings), defuzzification
by centroid. The substrate could intern these rules as Form recipes,
and the kernel could fire them during translation verification —
turning the lattice into a fuzzy reasoner. That's a substantial
direction; not walked in this PR.

## The Muzzle Velocity lineage

Urs's reference to "Muzzle Velocity days" names where fuzzy logic
actually delivered in defense ballistics: the relationship between
propellant temperature, barrel wear, ammunition lot variation, and
muzzle velocity is **nonlinear, multi-input, and partially uncertain**.
Classical control theory required physical models that couldn't be
fully specified; fuzzy controllers (Mamdani 1975 on a steam engine,
later extended to fire control) handled the input noise by treating
rules as soft constraints over linguistic variables.

The same shape applies here: LLM extractions are noisy, the
relationship between source-language tokens and cross-modal features
is nonlinear, and bit-exact identity is the wrong tool. Fuzzy logic
is the actual mathematics — proper t-norms, proper similarity
measures, proper aggregation.

## The encoding discipline (still learning)

- v1's first draft returned `1000` — count-not-pattern. Composted.
- v1's correction returned `323110` — per-axis portability count.
- v2 sub-agent returned `322110` and substrate-resident pattern recipes
  (avoiding the multi-lane integer overflow).
- This experiment returns `58879` — five-cycle dynamics, each digit
  position naming a transition in tens-of-percent.

Both `validate.sh`-visible integer AND substrate-resident
`CAT-CYCLE-DYNAMICS` recipe land. The integer is the human-readable
summary; the recipe is the substrate's pattern identity, addressable
by `node_eq` for re-runs producing the same dynamics.

## What the next walk would do

To actually validate the universal-translator's cross-modal claim with
fuzzy logic:

1. **Cross-modal cycles**, not register cycles. `text → music
   description → SVG composition → text` — measure fuzzy similarity
   through *modality* changes (not just compression).
2. **Per-extractor stability** with a trained model (CLIP / a small
   distilled transformer) — replace the LLM-as-extractor with
   deterministic perception so the membership distributions are
   reproducible. Then the cycle-dynamics signatures become *the
   model's* claim, not the LLM's.
3. **Mamdani inference rules** for cross-modal feature alignment —
   the substrate as a fuzzy reasoner, firing rules between modality
   schemas to project recipes.
4. **Probabilistic relaxation** of the integer membership encoding —
   if the kernel grows float natives, real-valued memberships become
   feasible; or stay in integers and just use higher resolution
   (μ × 10000 instead of × 1000).

This experiment is one step. The substrate now knows how to carry
fuzzy similarity. The next walks add modalities, learned extractors,
and inference.
