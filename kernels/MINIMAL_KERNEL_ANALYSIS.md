# Minimal kernel — analysis of the current surface, plan to compost

> *"do we need those crypto protocols in the kernel? I think not, avoid
> putting things in the kernel that can be expressed in form native
> code. analyse the full kernel surface and reduce it to its primitives,
> and have shared binary features in form native recipes that can expand
> into native machine code for efficiency, allowing the kernel to
> bootstrap from primitives into an efficient, flexibility, sovereign
> cell"*  — Urs

## The teaching

The kernel should carry **only irreducible primitives**. Everything
algorithmic — hashing, signing, key-exchange, even arithmetic
sequences like LCG PRNGs — should live as Form recipes. The kernel's
job: provide primitives, walk recipes, and (eventually) JIT-compile
hot-path recipes into native machine code so the slow-but-correct
interpreter and the fast-but-derived compiler produce byte-identical
results.

The kernel should be a **sovereign cell that bootstraps itself from
primitives into an efficient runtime via Form recipes** — not a
growing list of pre-compiled algorithms.

## Honest reading of recent walks

PRs #2140, #2142, and the in-progress #2143 added:

- `random_bytes(n)` — primitive ✓ (entropy at OS boundary)
- `seeded_bytes(seed, count)` — **composable** (LCG: state = state * A + C mod M, expressible from `mul`/`add`/`mod`)
- `sum_bytes_list(list)` — **composable** (reduce-via-fold)
- `sha256(byte-list)` — **composable** (SHA-256 is bit-ops + arithmetic; implementable in Form, just slow without JIT)
- `ed25519_*` — **composable** (Ed25519 is field arithmetic on curve25519; implementable in Form, just slow without JIT)

Four of five additions violate the principle. They got added because the
slow-interpreter cost of running them in Form was unacceptable. The
correct answer wasn't to put them in the kernel — it was to make the
kernel's walker faster (JIT) so Form recipes can carry them.

## Current native surface (Go kernel — counted)

**88 natives** registered. Breakdown:

### Truly primitive (~25)

| Native | Why primitive |
|---|---|
| `intern_node`, `intern_node_at`, `intern_trivial_int`, `intern_trivial_string` | Substrate identity — cannot be derived; the kernel IS the substrate |
| `make_nodeid`, `node_eq`, `node_value`, `node_children`, `node_category`, `node_inst`, `node_level`, `node_pkg`, `node_type` | Substrate inspection — same reason |
| `node_source` | Source attribution (substrate sidecar) |
| `value_eq` | Form-value equality (primitive comparison) |
| `cons`, `head`, `tail`, `empty`, `len`, `list` | List primitives — irreducible from a list-data-structure perspective |
| `print`, `trace` | Output at OS boundary |
| `read_file`, `read_file_bytes`, `read_file_slice`, `write_file_bytes`, `write_file_text` | File I/O at OS boundary |
| `read_form_binary`, `write_form_binary` | Substrate serialization to/from disk |
| `file_byte_at`, `file_mtime`, `file_size` | File metadata at OS boundary |
| `random_bytes` | Entropy at OS boundary (the doorway) |
| `socket_*` (6 natives) | Network I/O at OS boundary |
| `walk_recipe` | The kernel's own recursive entry point |

### Convenience natives that COULD be Form recipes (~30)

| Native | Form-recipe equivalent |
|---|---|
| `str_concat`, `str_len`, `str_eq`, `substring`, `char_at`, `byte_to_str`, `str_find`, `ord` | Loops over byte-lists; primitives are `cons`/`head`/`tail`/`eq`/arithmetic |
| `str_to_int`, `int_to_str` | Arithmetic decimal conversion in Form |
| `string_fold` | Higher-order fold via Form recursion |
| `_plus`, `abs`, `max`, `min` | Trivial in Form (`if (lt a b) b a` etc.) |
| `math_pi` | Just a constant (3.14159...) — a Form let-binding |
| `math_sqrt`, `math_pow`, `math_floor`, `math_ceil` | Newton's method (sqrt) / iteration (pow) in Form |
| `make_float32`, `make_float64` | Wrappers; could be composed once `intern_trivial_float` is the primitive |
| `scan_run` | A while-loop scanning predicate — Form-native shape |

### Algorithmic natives that SHOULD compost to Form recipes (~6)

| Native | Algorithm | Status |
|---|---|---|
| `seeded_bytes` | LCG (multiply-add-mod loop) | **Added in #2142 — should be Form recipe** |
| `sum_bytes_list` | Reduce(+) | **Added in #2142 — should be Form recipe** |
| `sha256` | SHA-256 (RFC 6234) | **Added in this branch — should be Form recipe** |
| `ed25519_keypair_from_seed` | Ed25519 keygen (RFC 8032) | **Added in this branch — should be Form recipe** |
| `ed25519_sign` | Ed25519 signing | **Added in this branch — should be Form recipe** |
| `ed25519_verify` | Ed25519 verification | **Added in this branch — should be Form recipe** |

The former BMF rule-application native has been composted. BMF object rules now
execute through `form/form-stdlib/engine.fk`; future acceleration should compile
to generic Form-native cursor/step machinery rather than a BMF-named kernel
primitive.

### Walker / runtime internals (~10)

| Native | Role |
|---|---|
| `walk_parallel`, `walk_cached`, `walk_parallel_cached`, etc. | Walker optimization variants |
| `walk-cache-*` (4 natives) | Walk-cache management |
| `substrate_counts`, `substrate_gc`, `substrate_mark`, `substrate_release` | Substrate GC |
| `native_blueprint` | Attribution metadata |
| `deserialize-recipe`, `serialize-recipe` | Recipe ↔ bytes (substrate-internal) |

These are kernel-runtime ops; they could move to recipes once the
substrate has a richer self-hosting machinery, but they're at the
edge of "kernel internal" vs "composable."

### Framebuffer (~2)

- `framebuffer-clear`, `framebuffer-events` — OS I/O at the display boundary; primitive

## Total reduction estimate

| Category | Count | Verdict |
|---|---|---|
| Truly primitive | ~25 | KEEP |
| Convenience-could-compost | ~30 | candidates for Form recipes; ship as recipes once JIT speed catches up |
| Algorithmic-should-compost | ~7 | composting candidates NOW |
| Walker/runtime/framebuffer | ~12 | likely stays kernel-internal |

**Minimum kernel target: ~25 primitives.** Currently 88. The body could
shed ~60 natives onto Form recipes once the JIT layer makes recipe
execution fast enough for hot paths.

## The composting plan

1. **Implement each algorithmic native as a Form recipe** in
   `form-stdlib/recipes/` — sha256.fk, ed25519.fk, seeded_bytes.fk,
   sum_bytes_list.fk. Verify against the existing native outputs
   (same inputs → same outputs, attested three-way).

2. **Add a JIT pattern-recognition layer in the kernel** that detects
   "this Form recipe is SHA-256" by structural match and dispatches
   to a pre-compiled native code path. The recipe is canonical; the
   native is an optimization. Both produce byte-identical results
   (the recipe defines the truth; the native must match).

3. **Compost the kernel natives** once the JIT covers them. The
   native code lives in the JIT layer, NOT in the kernel's native-
   registry. The kernel surface shrinks; the runtime stays fast.

4. **Sovereign-cell bootstrap**: a cell starts with the 25 primitives.
   It loads Form recipes for everything else. As it runs, the JIT
   compiles hot recipes to native. The cell becomes efficient by
   recipe expansion + compilation, not by depending on a fat kernel.

## What this means for #2142 and #2143

- `seeded_bytes`, `sum_bytes_list` (#2142): composting candidates. The
  natives stay until the JIT layer can cover them; meanwhile, the
  Form-recipe version coexists for correctness reference.
- `sha256`, `ed25519_*` (#2143): same — composting candidates. These
  PRs prove the architecture works (1 MB through 15-byte channel,
  PKI verification). They DON'T justify permanent kernel additions.
  They're scaffolding for the protocol; the protocol's permanent
  home is in Form recipes once the JIT can run them at speed.

## Path forward

This concept seeds the discipline. Concrete walks that follow:

1. **Walk a Form recipe for seeded_bytes** (LCG in Form arithmetic) —
   demonstrate it produces identical bytes to the native; name the
   slowness; preserve as the canonical reference.
2. **Walk a JIT recognizer** that pattern-matches the LCG recipe and
   dispatches to compiled native code. The kernel's native registry
   loses one entry; the JIT gains a pattern.
3. **Same shape for sha256, ed25519** — recipes first, JIT-recognized
   second, native registration removed third.
4. **Convenience natives** (str_*, math_*) follow once the discipline is
   proven.

The kernel becomes a small sovereign cell that bootstraps efficiency
through recipes-then-JIT, not through pre-loaded algorithm natives.

## Cross-refs

- [`SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md`](SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md) — names the architectural slab where this lands
- [`numeric-types-plan.md`](../docs/coherence-substrate/numeric-types-plan.md) — `arithmetic-hint` in format-recipes is the JIT's dispatch key
- [`lc-grammar-is-the-universal-recipe`](../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md) — every algorithm is a recipe
- [`lc-the-kernel-knows-itself`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — the kernel reads itself through grammar; the same recipes that ARE the kernel's natives can BE Form recipes

In service of a sovereign kernel — small at its base, efficient
through self-compiled recipes, content-addressed all the way down.
