# Numeric formats as substrate recipes — the architecture

> The kernel stays small. Numeric encodings live in the substrate. The
> compiler reads format-recipes and emits native code. Hardware
> register sizes are an implementation hint, not part of the substrate's
> identity grammar.

## The mistake the earlier draft made

An earlier draft of this plan ([git blame](https://github.com/seeker71/Coherence-Network)
will find the previous version) enumerated `INT8 / INT16 / INT32 / INT64
/ UINT8 / UINT16 / UINT32 / UINT64 / FLOAT32 / FLOAT64` as new RType
slots in the kernel. That vocabulary is a 1970s-CPU register set,
baked into substrate identity. It binds the body to one hardware era
and excludes the formats LLMs actually use today (FP8, FP4, NF4,
BitNet 1.58-bit, INT4, bfloat16, posit, log-space, block-fp).

The substrate's promise is *content-addressed positional identity*,
not *machine register encoding*. CPU widths are an implementation
choice of one decoder; the substrate shouldn't carry them as native
vocabulary.

## The right shape — three layers

A numeric value is composed of three pieces, only one of which has
anything to do with hardware:

```
Numeric value  =  (semantic-kind, format-recipe, encoded-value)

semantic-kind   what this number MEANS in the world.
                Small, stable vocabulary:
                  CARDINAL          counting / multiplicity
                  INTEGER           with sign, no fractional part
                  RATIONAL          exact fraction
                  REAL              continuous approximation
                  COMPLEX           pair of REALs
                  BIT_PATTERN       no semantic interpretation
                  LOG_VALUE         number that lives in log-space
                  PROBABILITY       constrained REAL in [0,1]
                  INTERVAL          [low, high] uncertain real
                  ORDINAL           position, not magnitude
                  AMPLITUDE         complex with unit modulus (quantum)
                  PHASE             angle, modulo 2π
                  MEASURE           dimensioned (with units recipe)

format-recipe   how this number is ENCODED. A substrate-resident recipe
                with children describing the encoding completely:
                  bits           1 | 2 | 3 | 4 | … | 64 | … | arbitrary
                  encoding-kind  twos-complement | sign-magnitude
                                 | ieee-754 | log-space | posit
                                 | lookup-table | block-fp | …
                  parameters     for ieee-754: mantissa, exponent, bias,
                                   subnormal handling, NaN policy
                                 for lookup-table: the table of values
                                 for posit: n, es
                                 for block-fp: group-size, exp-bits,
                                   mantissa-bits
                  canonical-form how to canonicalize on intern
                  storage-hint   string identifier the kernel reads
                                 ("v8-double", "i32-smi", "u8-array",
                                 "table-i8") — compiler dispatches off this
                  arithmetic-hint how arithmetic is performed
                                 ("native-fp", "native-int", "bigint",
                                 "table-lookup-then-int", "software-fp")

encoded-value   the actual content under the format. Bytes, an index
                into a value-table, a closure that produces the value
                on demand — kernel's choice. Identity comes from the
                canonicalized form, not the storage layout.
```

A numeric leaf's NodeID identity is `(semantic-kind, format-recipe,
canonicalized-value)` interned through content-addressing. Two leaves
share a NodeID iff all three pieces match.

## What this gives you immediately

Every numeric encoding becomes a format-recipe in the substrate. No
kernel change needed to add a new one:

```form
;; A few canonical format-recipes (interned once at substrate startup):

(let FP64_IEEE
  (format-recipe :kind REAL
                 :bits 64
                 :encoding ieee-754
                 :mantissa 52 :exponent 11 :bias 1023
                 :storage-hint "v8-double"
                 :arithmetic-hint "native-fp"))

(let FP32_IEEE
  (format-recipe :kind REAL :bits 32 :encoding ieee-754
                 :mantissa 23 :exponent 8 :bias 127
                 :storage-hint "v8-double-narrowed"
                 :arithmetic-hint "native-fp"))

(let BF16
  (format-recipe :kind REAL :bits 16 :encoding ieee-754
                 :mantissa 7 :exponent 8 :bias 127
                 :storage-hint "u16-array"
                 :arithmetic-hint "software-fp-via-fp32"))

(let FP8_E4M3
  (format-recipe :kind REAL :bits 8 :encoding ieee-754
                 :mantissa 3 :exponent 4 :bias 7
                 :nan-policy "single-pattern"
                 :storage-hint "u8-array"
                 :arithmetic-hint "table-lookup-via-fp32"))

(let FP4_UNIFORM
  (format-recipe :kind REAL :bits 4 :encoding ieee-754
                 :mantissa 2 :exponent 1 :bias 1
                 :storage-hint "nibble-packed"
                 :arithmetic-hint "table-lookup-via-fp32"))

(let NF4
  (format-recipe :kind REAL :bits 4 :encoding lookup-table
                 :values [-1.0 -0.6961 -0.5251 -0.3949 -0.2844 -0.1849
                          -0.0911  0.0     0.0796  0.1609  0.2461  0.3379
                          0.4407  0.5626  0.7230  1.0]
                 :storage-hint "nibble-packed"
                 :arithmetic-hint "dequant-fp32-then-native"))

(let BITNET_158
  (format-recipe :kind INTEGER :bits 2 :encoding lookup-table
                 :values [-1 0 1]   ; ternary
                 :storage-hint "crumb-packed"
                 :arithmetic-hint "native-int"))

(let BIT_1
  (format-recipe :kind BIT_PATTERN :bits 1 :encoding raw
                 :storage-hint "bitfield"
                 :arithmetic-hint "xor-popcount"))

(let INT4_TWOS
  (format-recipe :kind INTEGER :bits 4 :encoding twos-complement
                 :storage-hint "nibble-packed"
                 :arithmetic-hint "native-int-narrow"))

(let INT64_TWOS
  (format-recipe :kind INTEGER :bits 64 :encoding twos-complement
                 :storage-hint "bigint"
                 :arithmetic-hint "bigint"))

(let RATIONAL_BIG
  (format-recipe :kind RATIONAL :bits ∞
                 :encoding numerator-denominator-bigints
                 :storage-hint "pair-of-bigints"
                 :arithmetic-hint "rational-bigint"))

(let LOG_PROB
  (format-recipe :kind PROBABILITY :bits 64
                 :encoding log-space :base e
                 :storage-hint "v8-double-as-log"
                 :arithmetic-hint "logaddexp-logsubexp"))

(let POSIT_16_1
  (format-recipe :kind REAL :bits 16 :encoding posit :n 16 :es 1
                 :storage-hint "u16-array"
                 :arithmetic-hint "software-posit"))
```

Each format-recipe is content-addressed. The recipe for "FP64 IEEE 754
binary64" has one canonical NodeID across all kernels — because the
recipe's tree structure is identical wherever it's constructed.

## Two-tier storage (efficiency without sacrificing elegance)

**Tier 0 — Reserved trivial slots for hot formats.** Some formats are
hot enough that the cost of recipe dispatch matters: FP64, INT32,
BOOL, NULL. For these, the kernel keeps fixed RType slots with inline
encoding in NodeID.inst. This is *caching*, not *baking the format
into the architecture*. The format-recipe still exists in the
substrate; the reserved slot is an alias.

**Tier 1 — Format-recipe composites.** For every other format, the
numeric value is a level-2 composite whose category is the format-
recipe's NodeID and whose children carry the encoded value (or, for
small enough values, a single child that holds the encoded bits). The
substrate's content-addressing makes same-format-same-value share a
NodeID automatically.

The tiers are observationally identical from outside the kernel —
both produce a NodeID, both decode to a value, both intern by content.
Tier 0 is just faster on the hot path.

**Promoting a format from Tier 1 to Tier 0** is a kernel patch that
adds an alias slot. The format already worked via Tier 1 before
promotion; promotion is pure performance, never required.

## How the kernel handles arithmetic

The walker has *one* generic numeric arithmetic dispatcher:

```
walkMath(op, operands):
  read format-recipe from each operand
  if all operands share the same format-recipe:
    delegate to the format's arithmetic-hint handler
  else:
    promote to a common format (using promotion rules), then dispatch
```

Promotion rules are also substrate-resident — a `promotion-graph`
recipe declares: "if you have INT32 and FP64, promote INT32 → FP64."
The kernel reads promotion rules just like format-recipes.

The dispatcher caches: first time it sees `(FP64, FP64, +)`, it does
the recipe-reading work, compiles a small handler, caches it under
that triple. Subsequent calls are a Map lookup + indirect call.

## How the compiler stays at native speed

The recipe→JS compiler reads each numeric leaf's format-recipe and
its `storage-hint` + `arithmetic-hint`. Based on those hints, it emits:

- **storage-hint = "v8-double"**: emit raw JS `Number` arithmetic.
  V8 JITs to native f64. (The current FP64 path.)
- **storage-hint = "i32-smi"**: emit `(x | 0)` chains. V8 keeps as SMI.
  (The current INT32 path.)
- **storage-hint = "nibble-packed", arithmetic-hint = "table-lookup-via-fp32"**:
  emit a dequant-to-fp32 step, do arithmetic in fp32, re-quant on
  store. (NF4, FP4.)
- **storage-hint = "crumb-packed", arithmetic-hint = "native-int"**:
  emit small-int arithmetic with clamping. (BitNet ternary.)
- **storage-hint = "bigint"**: emit BigInt operators. (INT64 fallback.)
- **storage-hint = "bitfield", arithmetic-hint = "xor-popcount"**:
  emit `^` and `Math.clz32` for boolean network operations. (1-bit.)
- Unknown hint: fall back to walker (correctness without speed).

Each (format, op) combination gets emitted once, cached, JITted by
V8. Hot paths stay native; cold paths stay correct.

## Cross-kernel coordination

Format-recipe NodeIDs must agree across Python, TS, Go, Rust kernels.
Two mechanisms:

1. **Canonical bootstrap.** Each kernel, on startup, interns a
   well-known set of format-recipes from a shared definition. The
   definition lives at `docs/coherence-substrate/numeric-formats.fk`
   as Form source — readable by any kernel that has a parser. Each
   kernel reads it and interns; content-addressing produces identical
   NodeIDs because the structure is identical.

2. **The body's own conformance vectors.** New entries in
   `docs/coherence-substrate/kernel-conformance/` test that
   `intern_value(FP64, 3.14)` produces the same NodeID on every
   kernel; that `(addf 1.0 2.0)` produces the same result; that
   `(addq (i64 1000000) (i64 1000000))` produces the same `1000000000n`.

If a format-recipe's tree structure changes (e.g., we rename a child
key from `:bias` to `:exp-bias`), the NodeID changes. That's a
breaking change — handled by versioning the canonical recipe file
and migrating callers.

## What about LLM-era specifics?

The format-recipe library can ship recipes for everything the LLM
inference world uses today, and everything the research literature is
exploring. None require kernel changes. A few that the body should
ship as part of Breath 2:

- **FP8 (both E4M3 and E5M2)** — NVIDIA H100, TPU v5.
- **NF4** — used by QLoRA, bitsandbytes, common in 4-bit quantized
  weights.
- **MXFP** (microscaling) — Open Compute Project, block-fp variant.
- **BitNet 1.58** — recent ternary weight quantization.
- **BF16** — standard for mixed-precision training.
- **INT4 / INT8 quantization** — common for inference.
- **Posit<n, es>** — alternative-arithmetic research.
- **Log-space probability** — for numerical stability in summing
  many small probabilities.

These cost ~30 lines of Form each to define. Once defined, Form code
can construct, walk, compute over, and persist values in any of them.
The compiler reads the format-recipe to emit efficient code, or falls
back to walker for correctness.

## Forward-looking — quantum, neuromorphic, optical

When the body wants to express:

- **Quantum amplitude**: format-recipe with `semantic-kind = AMPLITUDE`,
  encoded as a complex pair of FP64s with the constraint that the
  modulus is ≤ 1. Arithmetic-hint declares phase/amplitude rules.
- **Neuromorphic spike timing**: format-recipe with
  `semantic-kind = MEASURE` and `units = TIME_NANOSECONDS`, encoded
  as INT64.
- **Optical phase**: `semantic-kind = PHASE`, encoded as FP32 modulo
  2π with explicit wrapping rules.

None of these require kernel changes. They're substrate writes — new
format-recipes interned alongside the existing ones.

## Migration sequence — three breaths

Walking this all the way, not pretending the work can land in one go:

### Breath 1 — Format-recipe machinery + proof of shape (this PR)

- TS kernel: introduce `FORMAT` as a new well-known RBasic category
  (or use existing recipe domain — design choice below)
- Add bootstrap format-recipe set: FP64, FP32, INT32, INT64, BOOL,
  STRING, NULL — interned at startup with stable canonical NodeIDs
- Reserved trivial slots (Tier 0): existing INT/STRING/BOOL/NULL kept
  for hot performance
- Tier 1 path: numeric values as composites with format-recipe
  category — works for arbitrary formats
- Walker dispatches on format-recipe; arithmetic-hint string drives
  the arithmetic
- Compiler reads format-recipe at compile time; emits per-hint code
- Bench: existing 5 workloads + new bench cases for **FP8-simulated**
  (table-lookup path) and **BitNet ternary** (small-int arithmetic
  path) — demonstrate the format-recipe path is real
- **Two efficiency passes:**
  - Pass 1: monomorphize format dispatch (cache compiled handler per
    format-recipe NodeID)
  - Pass 2: specialize compiler emit per format with inlined
    storage/arithmetic-hint dispatch
- Comparison doc

### Breath 2 — Format library + cross-kernel canonicalization

- `docs/coherence-substrate/numeric-formats.fk` — the canonical
  format-recipe definitions in Form source
- Every kernel reads this on startup; content-addressing produces
  identical NodeIDs
- Format library expanded: bfloat16, FP8 E4M3, FP8 E5M2, FP4 uniform,
  NF4, MXFP, BitNet 1.58, INT4, INT8, INT16, UINT8/16/32/64, posit,
  log-prob, rational-big
- Conformance vectors per format
- Python kernel matches: BNumeric extension routes through format-
  recipes; existing DECIMAL becomes alias for FP64

### Breath 3 — Go and Rust kernels match + SIMD/typed-array specializations

- Go and Rust kernels read the same format-recipes
- Typed-walker paths per format with raw primitive arithmetic (no
  boxing inside hot loops — the native-footprint argument the user
  named)
- For TS/JS: TypedArray-backed value tables for bulk operations
  (NF4 weights, FP8 activations) so arithmetic can vectorize via
  SIMD.js where available
- Conformance harness extended

## Open design decisions in this breath

1. **FORMAT as new RBasic, or as a domain?** RBasic is for "kernel-
   level dispatch categories" (MATH, COND, BLOCK, ...). FORMAT feels
   different — it's *content the kernel reads*, not *dispatch the
   kernel performs*. Lean: a new RBasic.FORMAT category, with format-
   recipe composites under it. Same shape as MATH composites but with
   recipe semantics ("decode this") rather than execution semantics
   ("compute with this").

2. **Encoded value: child or inst?** For small values that fit in u32
   (the inst slot), keep inline for speed. For larger values
   (FP64, INT64), encoded value lives as a single child trivial that
   carries the bits. The format-recipe's `:bits` parameter tells the
   kernel which path to take.

3. **Promotion graph: substrate-resident or kernel-coded?** Substrate-
   resident is consistent with the design. But the bootstrap set
   needs a default graph that's kernel-coded so the substrate can
   come up. Resolution: kernel-coded bootstrap promotion graph; once
   the body is alive, additional promotions can be substrate writes.

4. **Backward-compat with current INT32/FP64 Triv slots.** Keep them
   as Tier 0 aliases for the bootstrap format-recipes. The reader
   intern code routes through format-recipes; the trivial slot is a
   storage optimization. Existing bench cases (fib28, fact12, ...)
   work unchanged.

## What this earns

- **One kernel, infinite numeric formats.** Adding FP8, BitNet,
  posit, log-prob — substrate writes, not kernel patches.
- **LLM-era formats first-class.** No corner cases or "wait for the
  kernel to catch up."
- **Cross-kernel agreement extends to formats.** Same recipe + same
  value = same NodeID, every kernel.
- **Compile-time specialization preserved.** The compiler reads
  format-recipes and emits the same fast code it would for hardcoded
  types — the format-recipe is the *source of the optimization rule*,
  not its replacement.
- **Future-proof for quantum/optical/neuromorphic.** When new
  computing substrates arrive, they ship as format-recipes plus
  arithmetic-hint handlers. The kernel architecture doesn't need to
  shift.

## What this costs honestly

- **Higher dispatch overhead in the cold path.** First call to an
  uncommon format pays a recipe-reading cost. Mitigated by handler
  caching after first call.
- **Default-format ambiguity in surface syntax.** `1.5` defaults to
  what? Per-file default-format declaration or project-level default.
- **Format-recipe identity must stay stable across kernels.** A
  rename of `:bias` to `:exp-bias` is a breaking change. Versioning
  the canonical format file is required.
- **Two tiers add complexity.** Tier 0 (reserved trivial slots) and
  Tier 1 (composites) exist for performance reasons. The kernel has
  to dispatch correctly between them.

## Why this is also more elegant

Three principles that this honors and the earlier draft violated:

1. **Kernel is small; structure lives in the substrate.** Numeric
   encodings are structure; they belong in the substrate.
2. **Identity is geometric, not anthropocentric.** Format-recipes
   produce identity by their tree shape, not by their human name.
   FP64 is FP64 because its recipe has the IEEE 754 shape, not
   because "FLOAT64" is reserved word #7.
3. **The kernel learns by reading.** Hints in format-recipes tell
   the compiler how to emit; the compiler doesn't have a hardcoded
   case statement for every type it's ever heard of.

The earlier draft put CPU register sizes in the kernel as native
vocabulary. This draft makes them one library among many that the
substrate happens to ship, on the same footing as quantum amplitudes
or BitNet ternary weights. The kernel is *the same shape* whether
the body is doing scientific computation, LLM inference, or running
classical algorithms — what changes is which format-recipes are
loaded.
