# Typed numeric system — cross-kernel migration plan

> The substrate today carries four trivials (NULL / BOOL / INTEGER / STRING)
> plus DECIMAL as a string-table overflow. This document plans the move to
> a Go-shaped ten-type system (int8/16/32/64, uint8/16/32/64, float32/64)
> with native-footprint arithmetic across all four kernels.

## The shape

### RType layout

Ten new trivial markers, indexed alongside the existing
`api/app/services/substrate/category.py:BNumeric` enum. The current
`INTEGER` becomes `INT32` (alias retained for migration). The current
`DECIMAL` is deprecated in favor of explicit `FLOAT32` / `FLOAT64`.

| Marker | Bit width | Inline / overflow | Encoding |
|---|---|---|---|
| `INT8` | 8 | inline | i8 zero-extended into u32 `inst` |
| `INT16` | 16 | inline | i16 zero-extended |
| `INT32` | 32 | inline | i32 reinterpret as u32 |
| `INT64` | 64 | **overflow table** | `inst` = index into `substrate_int64` |
| `UINT8` | 8 | inline | u8 in `inst` |
| `UINT16` | 16 | inline | u16 in `inst` |
| `UINT32` | 32 | inline | u32 directly |
| `UINT64` | 64 | **overflow table** | `inst` = index into `substrate_uint64` |
| `FLOAT32` | 32 | inline | IEEE 754 single bits reinterpret as u32 |
| `FLOAT64` | 64 | **overflow table** | `inst` = index into `substrate_float64` |

The dividing line is **32 bits**: anything fitting in `NodeID.inst` (u32)
lives inline; wider types route through a dedicated per-type overflow
table.

### Overflow table semantics

Three new tables, parallel to `substrate_strings`. Content-addressed by
value:

```sql
CREATE TABLE substrate_int64 (
    inst INTEGER PRIMARY KEY,         -- monotonic index
    value BLOB NOT NULL,              -- 8 bytes (i64 little-endian)
    UNIQUE(value)
);
-- Same shape for substrate_uint64 and substrate_float64.
```

`intern_int64(42)` interns `42` into `substrate_int64`, returns the
`inst` index. `NodeID(1, TRIVIAL, INT64, inst)` is the resulting
trivial. Two intern calls with the same value return the same NodeID —
content-addressing preserved.

**Float canonicalization** (mandatory for cross-kernel agreement):

- All NaN bit patterns collapse to one quiet-NaN representative on
  intern (IEEE 754 quiet NaN: `0x7FF8000000000000`).
- `-0.0` and `+0.0` intern to the same NodeID (canonical `+0.0`).
- `+Inf` and `-Inf` keep distinct identity.
- Subnormals preserved.

Without canonicalization, two semantically-equal floats can produce
different NodeIDs and cross-kernel agreement breaks.

### Surface-syntax disambiguation

Form's surface needs to express width. Three approaches, mixed:

1. **Default widths from literal shape**:
   - Integer literal with no decimal → `INT32`
   - Decimal literal → `FLOAT64`
   - Negative integer literal larger than INT32 range → `INT64`

2. **Suffixed literals** for explicit width:
   ```form
   42i8        ; INT8
   42i64       ; INT64
   42u32       ; UINT32
   3.14f32     ; FLOAT32
   3.14f64     ; FLOAT64 (same as 3.14)
   ```

3. **Casts** for runtime conversion:
   ```form
   (i64 x)              ; convert x to INT64
   (f64 i)              ; widen i32 to float64
   (i8 (mod x 256))     ; narrow
   ```

Cast verbs map to RBasic.MATH with width-conversion instances (see
below).

### MATH/COMPARE/LOGIC dispatch — width as instance

Currently the MATH category has 5 instances (PLUS=1, MINUS=2, MUL=3,
DIV=4, MOD=5). The width-aware design encodes width in the instance
slot too — each (op, width) pair is a distinct NodeID.

Encoding: `inst = op + (width_marker × 16)`. Width markers 0–9 fit in
4 bits; ops 1–5 fit in 4 bits. So:

```
inst layout (8 bits used of 32):
  [width_marker:4] [op_marker:4]

  width_marker     0=i32 (default, for backward-compat)
                   1=i8
                   2=i16
                   3=i64
                   4=u8
                   5=u16
                   6=u32
                   7=u64
                   8=f32
                   9=f64

  op_marker        1=PLUS  2=MINUS  3=MUL  4=DIV  5=MOD  6=NEG
                   (COMPARE uses its own 8-instance set)
                   (LOGIC stays width-blind)
```

Result: `MATH.PLUS_F64` has inst `0x91` = `(9<<4)|1` = 145.
`MATH.PLUS_I32` keeps inst 1 (backward-compat).

**Casts** (width conversion) get their own marker space:
```
inst layout for CAST ops:
  [0xA0 .. 0xAF]  - cast variations (10 dest types each)
```

50 MATH instance slots + 6 op variations × 10 types = ~110 instances.
COMPARE similar (6 ops × 10 types = 60). Manageable.

## Walker — typed paths for native footprint

Currently `walkMath` calls `expectInt` and operates on JS `number`
(which V8 may store as SMI or double). To get **native-footprint
arithmetic without boxing** at the walker level, each width gets a
parallel typed walker:

```go
// Go kernel — boxing-free typed math, per width:
func walkI32Math(k *Kernel, op uint32, kids []NodeID, env *Frame) int32 { ... }
func walkI64Math(k *Kernel, op uint32, kids []NodeID, env *Frame) int64 { ... }
func walkF32Math(k *Kernel, op uint32, kids []NodeID, env *Frame) float32 { ... }
func walkF64Math(k *Kernel, op uint32, kids []NodeID, env *Frame) float64 { ... }
// etc.
```

These don't box. Go primitives stay on the stack, arithmetic is direct
CPU instructions.

The generic `walk()` dispatches into the right typed walker based on
the recipe's category-width. For uniform-width chains (every op in the
chain is the same width), the entire chain runs without crossing the
Value boundary.

**TS** is special: V8 already stores numbers efficiently as SMIs or
doubles internally. The TS walker doesn't gain much from parallel
typed walkers — V8 boxes the same way regardless. The win in TS comes
from the **compiler**: typed JS emission means V8 sees a homogeneous
arithmetic pipeline and JITs it to native code, same as it already
does for i32. Adding f64 chains to the compiler is a one-line dispatch
addition once the recipe carries width info.

**Python** is the opposite extreme: every Python number is a boxed
PyObject. Typed walkers can't change that. Python's payoff is in the
substrate-numbering side (cross-kernel agreement, correct decoding).

## Native primitive expansion

New natives per type (~30 total):

```
Construction:
  make_int8(n)     make_int16(n)    make_int32(n)    make_int64(n)
  make_uint8(n)   make_uint16(n)   make_uint32(n)   make_uint64(n)
  make_float32(f)               make_float64(f)

Reading:
  i8_value(nid)    i16_value(nid)   i32_value(nid)   i64_value(nid)
  u8_value(nid)   u16_value(nid)   u32_value(nid)   u64_value(nid)
  f32_value(nid)                f64_value(nid)

Conversion / parse:
  str_to_i8 / i16 / i32 / i64 / u8 / u16 / u32 / u64 / f32 / f64
  i*_to_str / u*_to_str / f32_to_str / f64_to_str
```

The existing `intern_trivial_int` becomes an alias for
`intern_trivial_i32`. `intern_trivial_string` unchanged.

## Migration sequence — four breaths

### Breath 1 — Proof of shape in TS (this PR)

Carve the path for one inline type (FLOAT32) and one overflow type
(FLOAT64), keeping INT32 as the working baseline.

- TS kernel: add `Triv.FLOAT32`, `Triv.FLOAT64`, `Triv.INT64` constants
- Add `substrate_float64`, `substrate_int64` overflow tables (in-memory
  maps for TS)
- Add `internTrivialFloat32`, `internTrivialFloat64`, `internTrivialInt64`
- Extend `Value` union with typed-numeric variants
- Update `trivialValue` decoder
- Add width-aware MATH dispatch for FLOAT64 (PLUS_F64, MUL_F64, etc.)
- Reader recognizes decimal literals → FLOAT64 by default
- Compiler emits boxing-free f64 arithmetic
- Bench adds a float64 workload (Leibniz π series) measuring
  native vs walker vs compiled

This is mechanical once the design is set. Maybe ~800 lines TS-side.

### Breath 2 — Python kernel extends BNumeric

- Add `INT64`, `UINT64`, `FLOAT32`, `FLOAT64` to `BNumeric`
- Build `substrate_int64`, `substrate_uint64`, `substrate_float64`
  Alembic migrations
- Extend `_trivial_value` decoder
- Extend `markdown_frontend.py` ingest to emit typed numerics
- Extend `form-engine.form` interpreter arms (or keep them width-blind
  via dynamic dispatch — design choice)
- Migrate existing `RType.DECIMAL` cells to `FLOAT64` (data migration)
- Update conformance vectors

~1500 lines including migration.

### Breath 3 — Go and Rust kernels match

- Add the same Triv constants
- Add per-kernel overflow tables (in-memory maps)
- Add typed walker paths (parallel walkMathI64, walkMathF64, etc.)
- Add the new natives
- Add reader support for decimal/typed literals
- Cross-kernel conformance harness runs the new float64 vectors

~1500 lines combined (Go + Rust).

### Breath 4 — Fill in remaining types

Once one inline type (FLOAT32) and one overflow type (FLOAT64) work
end-to-end across all four kernels, the rest are mechanical:

- Inline types (INT8, INT16, UINT8, UINT16, UINT32) — same pattern as
  INT32 with width-marker dispatch
- Remaining overflow types (UINT64) — same pattern as INT64

~800 lines total.

**Total arc**: ~4,600 lines across 4 kernels, 4 breaths, 4 PRs.

## Conformance harness updates

The existing harness lives at
`scripts/verify_kernel_conformance.py` with vectors in
`docs/coherence-substrate/kernel-conformance/`. New vector files:

```
docs/coherence-substrate/kernel-conformance/
├── agent-question-effects.json       (existing)
├── numeric-int64.json                (new)
├── numeric-float32.json              (new)
├── numeric-float64.json              (new)
├── numeric-cast.json                 (new — width conversions)
└── numeric-edge-cases.json           (NaN, Inf, -0, overflow, underflow)
```

Each vector runs through Python, Go, Rust, and TS kernels; all four
must return identical NodeIDs and identical decoded values.

## What this earns

- **Form code can do real numerics** without routing every float
  through the string table. Calculations stay structural.
- **Substrate queries can find typed leaves** — *"give me all FLOAT32
  trivials"* becomes one lookup rather than a string-table scan.
- **Cross-kernel agreement on numerics** — same input float, same
  NodeID, every kernel. The geometric physics extends to numbers.
- **Native-footprint arithmetic** in Go and Rust kernels — typed
  walkers operate at primitive speed, no boxing in inner loops.
- **Browser bundle stays light** — TS doesn't need typed walker paths
  (V8 boxes the same way regardless), so the TS kernel grows by ~200
  lines for the full system, not 1000.

## What this costs

- **DECIMAL deprecation migration** — every existing cell with a
  `DECIMAL` trivial needs to migrate to `FLOAT64`. Probably hundreds
  of cells; needs an ingest sweep.
- **Surface-syntax design** — literal suffixes, cast verbs, default
  widths all need design committed.
- **Cross-kernel coordination overhead** — adding a new type now
  requires four kernels to update together; conformance harness
  catches drift, but the harness itself has to grow.
- **Walker complexity grows** — the generic walker stays small, but
  the typed walkers in Go/Rust are real new code per width.

## Open design questions worth naming

1. **Should the Triv RType numbering preserve backward-compat?**
   Current `INTEGER = 2` shifts to `INT32 = 2` (alias). New types take
   higher numbers (INT64 = 5, FLOAT32 = 6, etc.). This means old
   `RType.INTEGER` literals in `form-engine.form` keep working.

2. **Should casts be MATH-instances or their own RBasic.CAST arm?**
   MATH-instances is simpler (no new RBasic surface), but conceptually
   casts aren't arithmetic. Lean: dedicate `RBasic.CAST` for cleanliness.

3. **Should COMPARE arithmetic mix widths?** `(< (i64) (f64))` is a
   real question — comparing an int64 against a float64. Lean: explicit
   cast required; no implicit width-mixing in comparisons.

4. **Should default widths be configurable?** Some bodies want
   `1.0` to default to FLOAT32 (lighter); others want FLOAT64
   (precision). Lean: FLOAT64 default, FLOAT32 via suffix.

These don't block Breath 1 — they shape Breath 2 onward.
