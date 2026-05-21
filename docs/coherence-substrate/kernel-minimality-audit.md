# Kernel minimality audit — 2026-05-22

A walk of every native + every dispatch arm in the three form-kernels.
For each: **primitive** (couldn't be expressed via simpler primitives —
must stay in kernel) or **composable** (could be moved to `core.fk` /
removed once a Form recipe replaces it).

The user's principle: *the kernel should be minimal. Add a JIT later to
generate native assembly for specialized recipes once the generic
recipes are fully typed with hardware types.* — Urs, 2026-05-22 night.

## Native primitives (Rust kernel, parity with Go + TS)

### TRULY PRIMITIVE — stay

| Native | Why it can't be composed |
|---|---|
| `print` | External I/O side effect — no composition produces a side effect |
| `read_file` | External I/O — touches filesystem |
| `make_nodeid` | The atom of the lattice — every higher recipe is composed from NodeID literals |
| `intern_trivial_int` | Bridges integer literal → trivial Recipe |
| `intern_trivial_string` | Bridges string literal → trivial Recipe |
| `intern_node` | Composes children into a composite Recipe — the substrate-write primitive |
| `node_category` | Reads a Recipe's category NodeID (introspection) |
| `node_children` | Reads a Recipe's children list (introspection) |
| `node_value` | Reads a trivial Recipe's underlying value (introspection) |
| `node_eq` | Compares NodeIDs structurally — kernel can't be composed |
| `walk_recipe` | The evaluation primitive — invokes the kernel's interpreter on a Recipe |
| `native_blueprint` | Reads a native's Form category — meta-introspection |
| `trace` | Debugging output — touches stderr |
| `str_len` | Byte-length of a string — character-level primitive |
| `char_at` | Byte-at-index of a string — character-level primitive |
| `str_eq` | String equality — character-level primitive |
| `str_concat` | String concatenation — character-level primitive |
| `int_to_str` | Integer → string conversion — character-level primitive (no list of chars at this layer) |
| `str_to_int` | String → integer conversion — character-level primitive |
| `ord` | Character → byte-codepoint — character-level primitive |
| `list` | List constructor — collection primitive |
| `cons` | List head-prepend — collection primitive |
| `head` | List first element — collection primitive |
| `tail` | List rest — collection primitive |
| `empty` | Empty list constructor — collection primitive |

**Count: 25 truly primitive natives.**

### COMPOSABLE — could move to core.fk and be removed from kernel

| Native | Compose as |
|---|---|
| `len` | Recursive: `(defn len (xs) (if (nil? xs) 0 (add 1 (len (tail xs)))))` |
| `nth` | Recursive: `(defn nth (xs n) (if (eq n 0) (head xs) (nth (tail xs) (sub n 1))))` |
| `range` | Recursive: `(defn range (a b) (if (ge a b) (empty) (cons a (range (add a 1) b))))` |
| `sum` | Foldl: `(defn sum (xs) (foldl plus 0 xs))` — already in core.fk |
| `min` | Foldl: `(defn min (xs) (foldl min2 (head xs) (tail xs)))` |
| `max` | Foldl: `(defn max (xs) (foldl max2 (head xs) (tail xs)))` |
| `abs` | Conditional: `(defn abs (n) (if (negative? n) (sub 0 n) n))` — already in core.fk |
| `substring` | Recursive walk via char_at + str_concat |
| `_plus` | Polymorphic — composable via type-check + dispatch on (int+int) vs (str+str) |

**Count: 9 composable natives.** The kernel could be **25 natives instead of 36**
(a 30% reduction). Each composable already has its core.fk equivalent or one
breath's authoring away.

### Composition path forward

1. **Author core.fk equivalents** for `len`, `nth`, `range`, `min`, `max`, `substring`.
   `sum`, `abs` already there; `_plus` waits for a polymorphic dispatch story.
2. **Update existing .fk files** that call kernel natives to use the core.fk
   versions where the kernel native is composable.
3. **Remove kernel registrations** for composables in all three kernels,
   one PR per ~3 natives so the body stays consistent at each commit.
4. **Verify sibling parity** at every step — Go + Rust + TS produce
   byte-identical NodeIDs throughout.

## Dispatch arms (the RBasic categories the kernel walks)

The kernel currently walks ~28 RBasic categories (see
`api/app/services/substrate/category.py` lines 174-310). Many are
**structural-passthrough only** today — interned but not executed.

### Always-executing arms (must stay)

`BLOCK`, `COND`, `MATH`, `COMPARE`, `LOGIC`, `LOOP`, `JUMP`, `CALL`,
`ACCESS`, `WRITE`, `MATCH`, `LIST` — 12 arms that the kernel actually
dispatches on during recipe walk.

### Passthrough arms (intern only, semantics deferred)

`CHOICE`, `STATE`, `EXCEPTION`, `DELEGATE`, `REVERSE`, `COMMON`,
`METHOD`, `REACTIVE`, `PROJECTION`, `TRY`, `RESONANCE`, `RESOLVE`,
`WITNESS`, `ABSORB`, `SCORE`, `TEND`, `REALIZE`, `COMPOSE`, `TRANSMIT`
— 19 arms whose structural identity interns but execution semantics
land later. **These cost nothing today** (the walker returns
`Value::Nid(n)` for them) but they're substrate vocabulary the body
ingests for cross-domain reasoning.

### Verdict

The current dispatch is honestly minimal where it matters. The
passthrough arms are *naming vocabulary*, not unused arms — they
let the substrate intern recipes from BML-richer dialects without
discarding structural identity. Don't compost.

## JIT vector

Once generic recipes are fully typed with hardware-level type
annotations (e.g. `R_Math(op="+", lhs: I64, rhs: I64) → I64`), a
specialized-recipe JIT can generate native assembly for hot paths
without changing the kernel's primitive set. The kernel stays small;
the JIT is a separate optional surface that consults type annotations
and emits machine code for specific Blueprint→Recipe pairs.

The JIT teaching: **the generic recipe is the source of truth**; the
JIT is an optimization that compiles specialized paths. The kernel
walks the generic recipe in the absence of JIT; with JIT, hot specialized
recipes run as native code. Same behavior, faster execution.

This is for after the universal codec is complete and per-language
grammars + tracing are landed. Hardware-type annotations are a
later breath.
