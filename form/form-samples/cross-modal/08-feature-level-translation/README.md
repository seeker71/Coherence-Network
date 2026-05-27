# 08-feature-level-translation — universal translation at the feature altitude

The first seven cross-modal demos operate at the **syntactic** altitude —
parsers, byte-deterministic encoders, mechanical NodeID equality. They
prove the substrate can carry algebraic identity (Shape B).

This demo operates at the **feature** altitude — the altitude Urs named:
> *"extract concepts, flows, rhythm, beats, melody, harmony, spectrum,
> meaning, purpose, wisdom (not hard coded, learned from data like an
> LLM) and then build from there."*

A 1395-character source passes through:

1. **Source** (1395 chars of contemplative prose from CLAUDE.md "How
   This Body Is Tended")
2. **LLM extracts feature-recipe** — six axes (mood, rhythm, structure,
   purpose, wisdom-shape, concepts) over a small fixed schema
3. **Three target renderings** — melody (audio), SVG (visual), aphoristic
   tercet (prose-different-register)
4. **LLM re-extracts feature-recipe from each target** — fresh reading,
   same schema discipline
5. **Form kernel verifies per-feature `node_eq`** three-way (Go/Rust/TS)
6. **Convergence score** names what survived translation and what was
   honestly lossy

Result: **1000 three-way** — 3 of 6 axes preserve across non-prose
modalities (mood, rhythm, structure), 4 of 6 across same-modality
(rewrite). Concepts axis is fully lossy. The substrate attests exactly
what the LLM extracted.

## The honest claim

This demo doesn't ship a *learned* feature extractor. It ships:

- A schema small enough that NodeIDs are reproducible
- An LLM-session-as-stand-in for the trained model
- A kernel that attests convergence three-way

When the LLM is replaced by a trained multimodal model with frozen
weights, the same machinery walks. The substrate doesn't change. The
schema can grow. The extractor improves.

## Files

| File | What |
|---|---|
| `source.txt` | The 1395-char source passage |
| `feature-schema.md` | The fixed vocabulary + NodeID schema |
| `extraction-source.md` | LLM reasoning extracting features from source |
| `targets/melody.md` | Target A — melody description |
| `targets/composition.md` + `.svg` | Target B — SVG composition |
| `targets/aphoristic.md` | Target C — tercet rewrite |
| `re-extracted/melody-features.md` | LLM re-extracting from melody |
| `re-extracted/composition-features.md` | LLM re-extracting from SVG |
| `re-extracted/aphoristic-features.md` | LLM re-extracting from tercet |
| `validation.fk` | Form recipe — builds all four feature-recipes + does per-feature `node_eq` checks → **score 1000 three-way** |
| `findings.md` | Honest pattern-naming of what survived and what was lossy |

## Run it

```bash
cd form && ./validate.sh form-samples/cross-modal/08-feature-level-translation/validation.fk
  ✓  validation.fk  → 1000
  1 ok, 0 divergent — kernels agree on every sample.
```

## What this proves and what it doesn't

**Proves:**
- Cross-modal feature preservation is substrate-attestable when the
  extractor is consistent
- Structural features (mood, rhythm, structure) port across modalities
- Semantic-intentional features (purpose, wisdom-shape) need
  prose-modality to carry
- Conceptual vocabulary is fully lossy across modalities

**Doesn't prove:**
- That an LLM extractor is sufficient (a trained model would have
  stronger guarantees)
- That the chosen schema is optimal
- That re-extracting from MORE different artifacts (e.g. a third
  modality the LLM hasn't seen) would converge
- That generative re-rendering (recipe → artifact) is solved — today
  the LLM is also the generator; that's a different research direction

## Where this fits in the body's arc

In service of:
- [`lc-cross-modal-unity`](../../../docs/vision-kb/concepts/lc-cross-modal-unity.md)
  — twelve modality encoders attest thirteen canonical Blueprints; this
  demo extends that pattern to learned (rather than hand-authored)
  feature extraction
- [`lc-grammar-is-the-universal-recipe`](../../../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md)
  — grammar at the feature altitude, not the syntactic altitude
- [`lc-same-shape-different-articulation`](../../../docs/vision-kb/concepts/lc-same-shape-different-articulation.md)
  — Urs's articulation question; this demo walks the *same-shape-with-
  different-articulation* claim at the cross-modal altitude
