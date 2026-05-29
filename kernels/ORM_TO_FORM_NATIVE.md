# ORM → Form-native: the gating dependency for "API code runs Form-native"

> Urs: "we need ORM support, no?" — Yes. It is THE gate. The substrate's core
> files (`kernel.py`, `orm.py`, `agent_relationship.py`, `substrate_strings.py`)
> exist to do content-addressed persistence; compiling them to `.fkb` is
> useless until the Form kernel can read/write the same store.

## The two groups (from the substrate scan, 2026-05-30)

- **Pure-computation (orm=0):** `form_eval`, `form_render`, `form_lexer`,
  `form_atoms`, `category`, `numeric_formats`, … → compile + run Form-native
  *today* (gated only on compiler syntax coverage). No ORM needed.
- **ORM-bound (orm≥10):** `kernel.py` (30), `orm.py` (20),
  `agent_relationship.py` (16), `substrate_strings.py` (11) → the substrate's
  *heart*. These `session.query(...)` / `Column(...)` against SQLAlchemy. They
  cannot run Form-native until the store is reachable from the kernel.

## The ORM surface is tiny — it is content-addressed interning

`intern_node` (the central op) is: `serialize_tree(category, children)` → a
string key → `SELECT by (package, level, domain, serialized)` → return the
existing NodeID, else allocate the next instance and INSERT. Plus:
`lookup_node(NodeID)`, `lookup_cell(domain, name)`, `make_cell(...)`. That's
the whole hot surface — four operations, all **content-addressed get-or-insert**.

The Form kernel **already does exactly this**:
- The native `intern_node` (Rust/Go/TS) content-addresses in-memory.
- `form-stdlib/persistence.fk` (Breath 5) does it file-backed: `cell-put` /
  `lookup-cell` / `store-cells`, same `(domain, name)` identity and the same
  `UNIQUE(domain, name)` semantics `orm.py` enforces.
- Records + methods (this session) give the mutable row/handle shape.

So "ORM support" = **bind those four operations to the Form-native store**, not
reimplement SQLAlchemy.

## The reshape (we own the code; functionality preserved)

Introduce a thin **`SubstrateStore` interface** that the substrate code calls
instead of `session.query` directly. Two backends, identical behavior:

```
SubstrateStore (protocol)
  intern(domain, category, children) -> NodeID      # get-or-insert by content
  lookup_node(node_id) -> row | None
  lookup_cell(domain, name) -> cell | None
  put_cell(name, domain, blueprint, ctor, ...) -> cell
  next_instance(package, level, type_) -> int

  SqlAlchemyStore   — wraps today's session.query/ORM (current behavior, default)
  FormNativeStore   — wraps persistence.fk via the kernel (the dogfood target)
```

Migration is mechanical and safe:
1. Extract the ~4 query patterns in `kernel.py`/`orm.py` behind
   `SubstrateStore`. `SqlAlchemyStore` IS the current code, moved — zero
   behavior change, all existing tests stay green.
2. Now `kernel.py`'s logic (level computation, serialize_tree, the get-or-
   insert control flow) is **pure** — it calls `store.intern(...)`. *That*
   logic compiles to `.fkb` and runs Form-native, with `store` = a small set
   of kernel natives over `persistence.fk`.
3. `FormNativeStore` routes the same ops to the kernel's `intern_node` +
   `persistence.fk` cell store. The `.fkb`↔SQLAlchemy reconciliation (Breath
   5's open item) is the one real bridge: one shared lattice on disk, or the
   Form store as a cache over the SQL backend.

## Why this unlocks the whole goal

Once the store is an interface:
- The substrate's **control logic** (the interesting part — interning,
  leveling, equivalence) runs Form-native via `.fkb`. Dogfooding lands on the
  core, not just the leaves.
- The **persistence** stays correct (SqlAlchemyStore) until FormNativeStore is
  proven at parity, then flips per the same swappable-backend discipline
  Breath 5 named.
- Every advantage you listed — traceability (recipe provenance on every
  intern), perf tuning (kernel-native hot path), feature-priority signal
  (what the kernel can't yet express is the next breath) — accrues to the
  substrate's center.

## Order

1. **Compiler coverage for the pure files first** (no ORM) — proves the
   end-to-end `.py → .fkb → run` arc on real substrate code now. (`form_eval`,
   `form_atoms`, `form_lexer` are the leanest; they need: classes/decorators
   per their feature scan, then they compile.)
2. **Extract `SubstrateStore`** (Python reshape, SqlAlchemyStore = current
   behavior, all tests green). Pure, behavior-preserving.
3. **FormNativeStore over persistence.fk** + the `.fkb`↔SQL reconciliation.
4. **Compile the now-store-abstracted `kernel.py` logic** to `.fkb`, run it
   Form-native against FormNativeStore. The core dogfoods.

This doc is the spec for steps 2–4; the COMPILER_GAP_QUEUE drives step 1.
