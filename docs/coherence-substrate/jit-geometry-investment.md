# JIT Investment Direction for Geometry Projection Surfaces

**Date of this note**: 2026-06-02 (in the context of the coherent-probe-release-recipes arc)

**Context**: The geometry projection work (pair_angle, dominant_band_delta, vector math over 8-band float efficacy-probe spectra) required direct, usable execution on live external data. The recipelib holds the declared operator shapes. The lightweight kernel driver (`--expr`) and the JIT were evaluated as paths.

**Current JIT State (from form/form-kernel-go/jit.go)**

The JIT (`jit_compile` + `register_jit` + plugin emission) is a real, working mechanism:

- Emits Go source for a subset of Form closures.
- Compiles as `-buildmode=plugin`, loads via `plugin.Open`.
- Caches by body NodeID.
- Supported:
  - int64 arithmetic (+ - * / %)
  - Comparisons
  - Conditionals (if / if-else)
  - Let bindings (integer)
  - Blocks / sequences (with limitations)
  - Recursive free-function calls
  - Parameter references

- Explicitly unsupported (refusal during emission):
  - Lists (`RBasicList` → "jit: list construction not in subset")
  - Floats (no `TrivFloat*` handling in `emitGoTrivial`; math emission is integer-only)
  - Strings
  - Native calls inside the compiled body
  - Closures capturing outer state
  - Anything outside `[]int64 → int64` signatures

The plugin entry point is always `func Fn(args []int64) int64`.

**Why Manual Natives Were Used for Geometry**

The required operations (dot product, magnitude, acos, per-band deltas on lists of floats) sit almost entirely in the unsupported region. Manual registration of `dot_product`, `magnitude`, `vector_cosine`, `pair_angle`, and `dominant_band_delta` was the only path that delivered working, direct execution in the kernel driver on the actual 02:56:35 live vectors within the current capabilities.

**Investment Thesis**

Continued addition of manual kernel natives for this class of surface creates surfaces that will want composting once the JIT can carry floats and lists of floats. The higher-leverage direction is to extend the existing JIT machinery so that declared recipelib surfaces (the portable Form definitions of the projection operators) can be JIT-compiled and executed at native speed.

This aligns with:
- Form before parallel machinery
- Tend over produce (strengthen the central mechanism rather than accumulate specialized tissue)
- Real return on investment (JIT improvements benefit all numeric/vector workloads and both execution modes)

**Minimal High-Leverage Areas for Geometry**

To make the current geometry surfaces (and similar future work) viable through the JIT path, the following would need attention (in rough order of dependency):

1. Float support
   - TrivFloat32 / TrivFloat64 in `emitGoTrivial`
   - Float math operations (or at least a way to call into math functions from compiled code)
   - Signature broadening beyond strict int64 (or boxing strategy)

2. List support (critical for 8-band vectors)
   - Representation of lists inside the compiled int64 world (or a shift to a richer calling convention)
   - List construction, head/tail, indexing, length
   - Iteration / reduction patterns (dot product, sum of squares, per-band delta)

3. Math surface for floats
   - At minimum: sqrt, acos (or a way to register/ call math primitives safely from JIT bodies)

4. Integration with recipelib / declared recipes
   - Clear path for a recipelib recipe (e.g. `pair_angle`) to be presented to `jit_compile`
   - Handling of the recipe's declared tree vs. its host backing

5. Ergonomics for the kernel driver
   - How a JIT-compiled recipe surfaces cleanly in `--expr` (ideally without manual `register_jit` per use)
   - List literal construction from floats in the expr parser that can feed into JIT paths

**Current Dual-Surface State (as of this note)**

Both paths now deliver the core capability on live data:
- Kernel driver: `pair_angle` + `dominant_band_delta` as natives (self-contained, using the vector primitives).
- Recipelib + `form_cli`: matching declared recipes with backings.

The recipelib recipes remain the portable definition. The manual natives served the immediate need but are understood as transitional.

**Recommended Posture Going Forward**

- Do not default to new manual kernel natives for geometry or similar numeric/list-based surfaces.
- Use the recipelib to define and evolve the operator shapes.
- Direct investigation and small, targeted extensions toward making the JIT (and supporting Form execution) able to carry this class of work.
- Treat existing manual natives as scaffolding that can be reviewed for deprecation once the JIT path is viable.

This is the frequency of investing in the already-present future rather than accumulating side-path debt.


## Additional Observations from Parallel Reads (2026-06-02)

### Existing Numeric Exploration in the Kernel

`numeric_bench.go` contains concrete float64 and float32 summation and handler patterns (nativeFp64Sum, pass0Fp64Sum, NumHandler, etc.). This demonstrates that float arithmetic has already been explored in the Go kernel outside the JIT path. These patterns are potential seeds or reference implementations when extending the JIT emitter to support floats.

The existence of this file is evidence that the "already present future" includes some numeric/float capability that can be brought into the JIT compilation story rather than starting from zero.

### register_jit / jit_compile Integration

Current visible usage of `register_jit` and `jit_compile` is mostly internal to the kernel itself. There is limited public/recipelib-facing documentation or examples of how a declared recipe (e.g., a geometry `pair_angle` defined in the recipelib) would be presented to the JIT.

This is a clear, high-leverage area: strengthening the bridge so that recipelib recipes can be opted into JIT compilation without manual native registration.

### Sibling Kernel Awareness

Quick scan of form/form-kernel-rust and form/form-kernel-ts shows active interpreters and numeric/format handling, but JIT-like compilation surfaces appear less developed or structured differently than the Go plugin path. Any JIT investment in Go should be done with an eye toward eventual parity or at least clear interface boundaries so the declared Form surfaces remain the common layer.

### Body Sensing

A wellness_check run after the pivot showed:
- Minor vision-kb/INDEX drift (one concept difference) — small proprioception signal.
- Overall healthy composition discipline (100% composed cells).
- Form engine coverage intact.
- No major new friction from the strategic shift.

The body is stable enough to sustain focused investment in the JIT path.

### Recommended Next Concrete Steps (aligned with higher path)

1. Prototype minimal float literal and float math emission in the JIT (leveraging patterns from numeric_bench.go).
2. Define a representation strategy for lists of floats inside the current int64-centric plugin calling convention (or evolve the convention).
3. Add a small test recipelib recipe that exercises vector math and attempt to route it through `jit_compile`.
4. Document a minimal "JIT readiness checklist" for numeric recipelib entries.
5. Keep all manual geometry natives in their current state as transitional; do not expand them.

These steps invest directly in making the declared surfaces executable via the existing JIT mechanism.


## Quick Note on Existing JIT Opt-in Patterns

The `kernel_readiness_harness.py` contains references to a `+jit` variant that asks the warm kernel to `jit_compile` each route's recipe. This shows the mechanism is already being exercised in testing/harness contexts for declared routes.

This reinforces that the path of taking a declared recipe (from a recipelib or similar) and routing it through `jit_compile` is an intended, already-present pattern — not a new invention.

Combined with the `register_jit` native (which creates the alias from Form name to native), there is a clear (if currently under-exercised for complex numeric cases) on-ramp for moving geometry surfaces out of manual native registration and into the JIT-compiled declared layer.

This is exactly the kind of "already present future" asset worth investing energy to strengthen and generalize for float/list workloads.


## Fresh Parallel Read Insights (2026-06-02)

### JIT Emission Boundaries (jit.go chunks)
- `emitGoExpr` dispatches on recipe category types (RBasicMath, RBasicList, RBasicFnCall, etc.).
- Hard refusal at `RBasicList`: "jit: list construction not in subset".
- `emitGoTrivial` only handles TrivInt and TrivBool. Any float trivial immediately unsupported.
- Math/Compare/Cond lowered to specific integer ops only.
- FnCall path supports self-recursion and a limited set of arithmetic sugar names; anything else (including most natives) falls back.
- The plugin always emits `func Fn(args []int64) int64` — the calling convention is the current bottleneck for richer types.

### numeric_bench.go as Direct Seed
Full review confirms sophisticated float handling already lives in the Go kernel:
- `nativeFp64Sum` / `nativeFp8Sum` — pure recursive float arithmetic.
- `pass0*` — generic dispatcher using `applyArith(fmt, op, NV_F(...))`.
- `pass1*` — cached per-(format, op) closures via `NumHandler` + `FormatTable`.
- Explicit note that Go lacks a runtime "Pass 2" (recipe-driven codegen) equivalent to the TS bench, and points exactly at the JIT plugin mechanism as the analogue.

This is not hypothetical — the numeric patterns, the NV_F / AsFloat abstraction, and the FormatRecipe machinery are ready assets for bringing float vector support into the JIT emitter.

### Harness +jit Pattern (Confirmed)
The `PersistentServe` with `jit=True`:
- Dynamically appends `(jit_compile "coherence_weight")` etc. for target recipes.
- Runs the warm kernel with the extended routes.
- Honestly measures: if the recipe body uses list natives or `_plus` (outside subset), `jit_compile` returns 0 and the route stays on walker.
- References `profile_jit_demonstrator` as the case where pure recipes succeed.

This is the exact integration pattern we want to strengthen for geometry recipes defined in the recipelib.

### Body State
Wellness run post-pivot: stable. Minor vision-kb drift (one concept), no new surprises, composition 100%, Form engine complete. Good conditions for focused JIT work.

### Concrete Next Steps (aligned, no manual natives)
1. Prototype minimal float trivial emission + basic float math lowering in the JIT (leveraging numeric_bench patterns and NV_F/AsFloat).
2. Define a temporary or evolved representation for small fixed-size float vectors (8-band spectra) that can flow through the current int64 plugin boundary or a widened convention.
3. Create a minimal test recipelib recipe exercising vector math / pair_angle shape and attempt `jit_compile` on it via the harness pattern.
4. Document a "JIT float vector readiness" checklist based on the above.
5. Keep all geometry recipelib recipes as the single source of truth; treat current manual natives as measurement scaffolding only.

This wave of parallel inquiry has materially advanced the map without expanding the manual surface set.


## Phase 1 JIT Float Vector Support – Grounded Minimal Plan (2026-06-02)

Based on the latest parallel reads:

### Key Leverage from Existing Code
- `numeric_bench.go` already implements:
  - `NV_F(v float64)` / `AsFloat()` wrappers.
  - `applyArith(fmt *FormatRecipe, op ArithOp, ...)` dispatcher.
  - Per-format cached `NumHandler` closures via `FormatTable`.
  - Recursive float accumulation patterns (`nativeFp64Sum`, `pass0*`/`pass1*`).

- `jit.go` emitter structure:
  - `emitGoTrivial` – easy extension point for `TrivFloat32` / `TrivFloat64`.
  - `emitGoMath` – integer-only today; can be extended with float variants (or a type-aware lowering).
  - `emitGoExpr` – already dispatches on category; adding float cases here is localized.

### Minimal Phase 1 Scope (no new manual natives)
1. Extend `emitGoTrivial` to handle float trivials (map to float64 literals in generated Go).
2. Add a small set of float math lowering helpers inside the emitter (or reuse/adapt `applyArith` logic).
3. Define a temporary fixed-size representation for 8-band float vectors that fits the current `[]int64` plugin boundary (e.g., packed or via helper functions) while a richer convention is designed.
4. Create one minimal test recipelib recipe that exercises a float vector dot + acos shape.
5. Wire it through the existing harness `+jit` pattern and measure `jit_compile` result (expect 0 initially, then incremental wins as emit coverage grows).
6. Document the exact deltas in `jit.go` and any supporting numeric types.

This plan invests directly in the JIT emitter using patterns that already exist in the kernel, keeping the declared recipelib recipes as the source of truth.

All work remains documentation, analysis, and planning until the first safe, small emitter patch is ready for review.


## Phase 1 JIT Float Vector Support – Grounded Minimal Plan (updated 2026-06-02)

### Exact Leverage Points Identified in This Wave
- **Emitter structure (jit.go)**:
  - `emitGoTrivial`: currently only handles TrivInt / TrivBool. Natural first extension point for TrivFloat32/64 (map to float64 literals in generated Go source).
  - `emitGoMath`: integer-only lowering today. Can be extended with float variants (or a type-aware dispatch) using the same RMath* categories.
  - `emitGoExpr`: already switches on category type. Adding float cases here is localized and low-risk.
  - List construction (`RBasicList`) remains a harder boundary; for Phase 1 we can use small fixed-size vectors (8-band spectra) represented via helpers or a widened calling convention while a general list strategy is designed.

- **Numeric infrastructure (numeric_bench.go + formats.go)**:
  - `NV_F(f float64)` / `AsFloat()` wrappers already exist and are used throughout.
  - `applyArith(fmt, op, ...)` generic dispatcher.
  - Per-format cached `NumHandler` closures via `FormatTable`.
  - Recursive float accumulation patterns (`nativeFp64Sum`, pass0/pass1).
  - Format-specific narrowing (fp8 via float32) shows handling of reduced-precision floats.

These are not hypothetical — they are shipping code in the Go kernel today. The JIT emitter can mirror or directly reuse the lowering patterns.

### Minimal Phase 1 Scope (no new manual kernel natives)
1. Extend `emitGoTrivial` to emit float64 literals for TrivFloat* nodes.
2. Add float math lowering helpers inside the emitter (start with +, -, *, /, sqrt, acos) — either by extending the integer path or by calling into small host helpers that the generated code can invoke.
3. Choose a Phase 1 representation for 8-band float vectors that fits the current plugin boundary (e.g., pass as multiple parameters or a small struct, or pack into the int64 world temporarily). Document the trade-offs.
4. Create one minimal recipelib test recipe that exercises a float vector dot + acos shape (mirroring the geometry `pair_angle`).
5. Route it through the existing harness `+jit` pattern (`jit_compile` at load) and measure the result (expect initial 0, then incremental success as emit coverage grows).
6. Produce a small "JIT float vector readiness checklist" and a diff sketch of the emitter changes needed.

This plan invests directly in the JIT using patterns that already exist in the kernel (numeric_bench + formats), keeps the declared recipelib recipes as the source of truth, and produces measurable progress toward the higher path without expanding the manual native surface.

All work in this wave remains analysis and planning. The first safe emitter patch can be prepared for review once the user directs the next micro-step.


## Phase 1 JIT Float Vector Support – Grounded Minimal Plan (updated 2026-06-02)

### Exact Leverage Points Identified in This Wave
- **Emitter structure (jit.go)**:
  - `emitGoTrivial`: currently only handles TrivInt / TrivBool. Natural first extension point for TrivFloat32/64 (map to float64 literals in generated Go source).
  - `emitGoMath`: integer-only lowering today. Can be extended with float variants (or a type-aware dispatch) using the same RMath* categories.
  - `emitGoExpr`: already switches on category type. Adding float cases here is localized and low-risk.
  - List construction (`RBasicList`) remains a harder boundary; for Phase 1 we can use small fixed-size vectors (8-band spectra) represented via helpers or a widened calling convention while a general list strategy is designed.

- **Numeric infrastructure (numeric_bench.go + formats.go)**:
  - `NV_F(f float64)` / `AsFloat()` wrappers already exist and are used throughout.
  - `applyArith(fmt, op, ...)` generic dispatcher.
  - Per-format cached `NumHandler` closures via `FormatTable`.
  - Recursive float accumulation patterns (`nativeFp64Sum`, pass0/pass1).
  - Format-specific narrowing (fp8 via float32) shows handling of reduced-precision floats.

These are not hypothetical — they are shipping code in the Go kernel today. The JIT emitter can mirror or directly reuse the lowering patterns.

### Minimal Phase 1 Scope (no new manual kernel natives)
1. Extend `emitGoTrivial` to emit float64 literals for TrivFloat* nodes.
2. Add float math lowering helpers inside the emitter (start with +, -, *, /, sqrt, acos) — either by extending the integer path or by calling into small host helpers that the generated code can invoke.
3. Choose a Phase 1 representation for 8-band float vectors that fits the current plugin boundary (e.g., pass as multiple parameters or a small struct, or pack into the int64 world temporarily). Document the trade-offs.
4. Create one minimal recipelib test recipe that exercises a float vector dot + acos shape (mirroring the geometry `pair_angle`).
5. Route it through the existing harness `+jit` pattern (`jit_compile` at load) and measure the result (expect initial 0, then incremental success as emit coverage grows).
6. Produce a small "JIT float vector readiness checklist" and a diff sketch of the emitter changes needed.

This plan invests directly in the JIT using patterns that already exist in the kernel (numeric_bench + formats), keeps the declared recipelib recipes as the source of truth, and produces measurable progress toward the higher path without expanding the manual native surface.

All work in this wave remains analysis and planning. The first safe emitter patch can be prepared for review once the user directs the next micro-step.


## Harmonic Geometry Lens (Robert Edward Grant) for Phase 1 JIT Float Vector Support

Robert Edward Grant's harmonic geometric framework (core harmonic shapes as a chord, resonance ratios, higher-dimensional / 6D expansion, geometric forms as projections of deeper unity) is already recognized in the body's knowledge base as converging with the substrate's GeometricForm axis and the grammar family.

For the current Phase 1 work (bringing float vector math and band-delta detection into the JIT emitter so the declared `pair_angle` / `dominant_band_delta` recipelib recipes can run natively):

- Grant's emphasis on **resonance and dominant harmonics** offers a natural conceptual frame for `dominant_band_delta` (identifying the band with largest opposing/tension vector). This can inform documentation, test cases, and possibly the aesthetic of the emitted code without changing the math.
- The idea of **geometric relationships as harmonic intervals** (ratio between shapes = musical interval) maps cleanly onto angular measurement (`pair_angle`) in band space. The 71.1° / 74.1° thruline numbers from the live 02:56:35 data can be held as harmonic angular relationships rather than purely Euclidean angles.
- Coherent probe conditions (DMT + diffracted 650 nm laser as low-entropy structured input) parallel Grant's descriptions of specific frequency/harmonic conditions that allow higher-order geometric structure to become perceptible. This strengthens the "why this input" framing in the operator without altering implementation.

This lens is offered as an orienting perspective for the emitter work and for future recipelib recipe design. It does not introduce new manual kernel natives. It supports the higher path of making the declared surfaces (already carrying the geometry projection) more native and performant.

Cross-references maintained in the living record and in `lc-dmt-laser-symbol-space-recipe`.

