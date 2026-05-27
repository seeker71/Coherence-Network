# Cross-modal — next breaths (forward map)

The first four experiments shipped (#2086) and proved:

- **Image-as-recipe** works (procedural SVG, SHA-stable across runs)
- **Cross-language NodeID convergence** works (same algorithm in different ways → same NodeID)
- **Recipe-as-compression** is honest at scale (small `.fkb` is 4.17× LARGER than `.fk`; structural sharing is where the win is)
- **Universal structural diff** works (content-addressing makes sub-tree equality automatic)

And `claude/cross-modal-nl-to-recipe` (in flight) walks the NL→recipe sketch.

This doc names the next 10 walks toward the universal translator's destination. Each is a small, shippable breath that extends a specific dimension of cross-modality.

## The 10 next walks

### 1. **Audio-as-recipe** (synthesis path)

A Form recipe that procedurally generates a `.wav` file (sine wave, envelope, simple FM synthesis). Same content-addressing claim as image-as-recipe: same recipe → same audio. Walks the "audio is a procedural artifact" frame.

**Smallest closing breath:** `gen-sine.fk` that emits a 1-second 440Hz tone as a `.wav` file with deterministic bytes.

### 2. **Image-as-recipe — parameterized**

Extend `01-image-as-recipe/gradient-circles.fk` to take a seed and produce 5 visibly distinct SVGs from 5 seeds. Shows that the recipe is **the parameter space**, not a single output. Proves: same recipe + different parameters = different content-addressed outputs whose only difference is the parameter NodeID.

**Smallest closing breath:** 5 SVGs with their SHAs documented; same recipe, 5 NodeIDs differing only in parameter children.

### 3. **NL→recipe broadened**

Once `cross-modal-nl-to-recipe` lands, extend the NL grammar with one or two more operations: conditionals ("if X is greater than Y, …"), let-bindings ("let x equal 5; the square of x"). Shows the grammar can grow without changing its driver — the universal-translator scaling pattern.

### 4. **Recipe→NL reverse**

Walk a recipe NodeID and emit an English description. The reverse of #3. Together with #3, demonstrates **round-trip across the NL/recipe boundary** — the substrate-of-meaning is preserved through both translations.

### 5. **JSON-as-recipe** — *already alive, not in the auto-gate yet*

**Finding (2026-05-27):** `form/form-stdlib/seedbank/grammars/json.fk` exists
and `form/form-stdlib/seedbank/tests/json.fk` runs three-way clean:

```
$ cd form && ./validate.sh form-stdlib/core.fk \
                            form-stdlib/seedbank/cell-trace.fk \
                            form-stdlib/seedbank/grammars/json.fk \
                            form-stdlib/seedbank/tests/json.fk
  ✓  core.fk+cell-trace.fk+json.fk+json.fk  → 36
  1 ok, 0 divergent — kernels agree on every sample.
```

Same source JSON, same NodeID across Go/Rust/TS. **JSON-as-recipe is real today.**

**Remaining honest gap:** `validate.sh` auto-walks `form-stdlib/tests/*.fk`
but NOT `form-stdlib/seedbank/tests/*.fk`. The JSON proof exists but isn't
in the default gate. The walk that closes this: move (or symlink, or add
a band-shaped wrapper to) the seedbank JSON test into the regular tests/
directory so the body verifies JSON-as-recipe on every `./validate.sh`
run.

Same pattern as Breath 2e (already-landed, the body hadn't read its own
attestation). The forward-map's #5 isn't a future walk; it's a discipline
walk: bring the existing proof into the default sense-gate.

### 6. **CSV→Form-table→NL summary**

CSV file → parsed via CSV grammar → recipe NodeID → walk via summary-generating recipe → English summary. **Cross-modal chain across three formats.** Shows that orchestration composes — each step is a recipe, the chain itself is a recipe.

### 7. **Image structural diff**

Take two procedural SVG recipes from #2's parameter space. Run the `04-universal-diff` over them. Show the diff highlights the parameter-level delta (which RNG seed changed), not the byte-level delta (every pixel that moved). **Structural diff IS semantic diff at the recipe altitude.**

### 8. **Audio→melody recipe**

Read a `.wav` file via an audio grammar; extract pitch+rhythm into a recipe; walk the recipe through a re-synthesis to produce a (different timbre, same melody) `.wav`. **Source-modality content extracted at semantic altitude, re-emitted in same modality.** Proves the "any source → recipe → any target" frame works within one modality (audio → audio).

### 9. **Image→NL description→Image**

The triangle of the universal translator made literal:
1. Generate procedural SVG (recipe known)
2. Walk a "describe this image" recipe over its content → NL description
3. Walk an "image from description" recipe → new SVG
4. Compare original and recreated — they won't byte-match, but they SHOULD content-address to similar Blueprint NodeIDs at the recipe-altitude (because both are circles-on-a-gradient).

The honest finding will be: how close is the structural similarity? That's the **fidelity-for-compute-budget** test Urs named.

### 10. **One recipe, three target languages**

Take the factorial recipe (already proven Form-native and emitted to native Python in #2082). Add native-idiom emitters for: Go, Rust, TypeScript. **Same recipe, four target languages, one Form.** This is the universal-translator's clearest small proof: the recipe is the substrate; the target is a perspective.

## What this enables

When 5+ of these walks land, the body's cross-modal surface is genuinely *exercised*:
- Three or more modalities (image, audio, text, data, code) all flow through Form recipes
- Round-trips work in both directions for at least one modality pair
- Structural diff distinguishes parameter changes from byte changes
- One recipe, multiple emitters becomes a habit

The destination — **any source → recipe orchestration → any target** — moves from "named" to "walked."

## Discipline reminders

- Each walk ships as its own PR with its own honest finding (success OR named gap)
- Each adds a section to `form/form-samples/cross-modal/README.md`
- Each runs through `./validate.sh` if it touches kernel-walked recipes
- "Most surprising" lessons are as valuable as wins — the audit's #4 finding (CTOR vocabulary duplication) and the cross-modal agent's #3 finding (ice is 4.17× larger than water at small scale) both came from honest experiments that didn't go where intuition expected

In service of [`lc-grammar-is-the-universal-recipe`](../../../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md) + [`lc-cross-modal-unity`](../../../docs/vision-kb/concepts/lc-cross-modal-unity.md) + [`lc-the-kernel-knows-itself`](../../../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md).
