# QUOTIENT — Rust kernel arm

Rust port of the QUOTIENT RBasic arm, fourth and final leg of the cross-kernel
quartet (TS, Python, Go, Rust). Mirrors `experiments/form-kernel-ts/src/quotient.ts`
and `api/app/services/substrate/quotient.py` field-for-field; handler names
match exactly so a Form program ingested into any kernel canonicalizes
identically.

## Shape

A recipe whose category is `RBASIC_QUOTIENT` (slot 70) has the shape:

```
QUOTIENT[carrier-recipe, equivalence-recipe]
```

The `equivalence-recipe` is itself a substrate cell (slot 71) describing the
equivalence relation — name + decidability + strategy + handler-name. When a
*value* of the quotient type is interned via `intern_quotient_value`, the
handler runs first; the canonical-children tuple is what the intern table
sees. Two values equivalent under the relation receive the SAME NodeID —
content-addressing IS the quotient.

## Inst layout for QUOTIENT NodeIDs

| `inst` | role |
|--------|------|
| 1 | recipe form — `QUOTIENT[carrier, equivalence]` |
| 2 | canonical value form — `[quotient_recipe, ...canonical_children]` |
| 3 | lazy raw value form — `[quotient_recipe, ...raw_children]` |

The eager path lands directly at inst=2. The lazy path lands at inst=3; once
`canonical_form` forces, it lands at inst=2 too, so cross-strategy equality
holds the moment both sides are canonicalized.

## Decidability + strategy

- `DecidableCheap`  → Eager (canonicalize at intern, fast equality)
- `DecidableHeavy`  → Lazy  (canonicalize on equality query)
- `Undecidable`     → Lazy  (no eager option)

Honest default: eager unless the equivalence declares heavy or undecidable.

## Built-in library

Four handlers registered under the cross-kernel-canonical names:

| name | shape | canonical form |
|------|-------|----------------|
| `integer-from-nat-pair` | `(a, b)` with `a, b ≥ 0` | `(a-b, 0)` |
| `rational-from-int-pair` | `(p, q)` with `q ≠ 0` | `(p/gcd, q/gcd)` sign in numerator |
| `commutative-pair` | `(a, b)` | sorted by NodeID packed key |
| `associative-left-fold` | `[a, b, c, ...]` | identity (proof-of-shape) |

## Surface

```rust
use form_kernel_rust::quotient::{
    build_quotient_library,
    make_quotient_recipe,
    intern_quotient_value,
    canonical_form,
    quotient_equal,
    Decidability,
    register_handler,
    make_equivalence,
};
```

- `build_quotient_library(k)` — bootstrap handlers + intern the four
  built-in equivalence cells.
- `make_quotient_recipe(k, carrier, equiv)` — intern `QUOTIENT[carrier, equiv]`.
- `intern_quotient_value(k, quotient, raw)` — intern a value through the
  quotient's canonicalization.
- `canonical_form(k, value)` — force canonicalize (no-op for inst=2).
- `quotient_equal(k, a, b)` — equality under the quotient.
- `register_handler(name, fn)` + `make_equivalence(k, name, decidability,
  handler_name)` — extend with a new equivalence.

## Handler registry

Module-global, behind a `OnceLock<Mutex<HashMap<String, CanonicalizeFn>>>`.
Handlers are pure functions; the registry lives for the process. The shape
mirrors the TS module-level `Map` and the Python module-level `dict`.

`CanonicalizeFn = Box<dyn Fn(&mut Kernel, &[NodeID]) -> Vec<NodeID> + Send + Sync>`
— takes a mutable Kernel so handlers can intern canonical children
(`intern_trivial_int` etc.) without fighting the borrow checker.

## Tests

11 tests in `src/quotient.rs`, one-for-one mirror of the TS assertions:

- `rbasic_quotient_is_slot_70`
- `integer_from_nat_pair_shares_nodeid` — `(3,1) ≡ (5,3) ≡ (9,7)`, neg
  integers, `quotient_equal`
- `rational_from_int_pair_canonicalizes` — reduce, sign normalization
- `commutative_pair_swaps` — `(7,42) ≡ (42,7)`
- `canonical_round_trip_shape` — children layout + idempotence
- `equivalence_cells_are_content_addressed` — same-bootstrap same-NodeID +
  `resolve_equivalence` round-trip
- `quotient_recipes_are_content_addressed` — `make_quotient_recipe` is
  content-addressed
- `decidability_policy_routes_strategy` — heavy/undecidable → Lazy
- `lazy_strategy_merges_on_demand` — raw NodeIDs differ pre-canon,
  canonical forms merge
- `quotient_parts_inspection`
- `handler_registry_is_queryable`

Run: `cargo test --release`.

## Cross-kernel contract

Handler names (`integer-from-nat-pair`, `rational-from-int-pair`,
`commutative-pair`, `associative-left-fold`), the RBasic slots (QUOTIENT=70,
EQUIVALENCE=71), the equivalence-cell children layout
(`[name, decidability, strategy, handler_name]`), and the value inst markers
(1=recipe, 2=canonical, 3=lazy-raw) all match TS / Python / Go. A Form
program crossing kernels produces the same NodeIDs.
