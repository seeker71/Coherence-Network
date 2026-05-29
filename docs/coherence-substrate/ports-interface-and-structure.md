# Ports — how Form relates interface to structure, and reaches its environment

> Urs (2026-05-30): "Form needs a clean interface to resources, a clean SDK /
> std-lib / interface to its environment. We have not really deeply thought
> about this. Deeply architect that correctly, then build out host integration
> clean like other platforms do — and then see how that affects SQL, since SQL
> is a high-level logical storage abstraction: memory-based, file-based,
> network-based (DB or non-DB). How are we dealing with interface vs structure
> in the Form universe? That is more generic than where the SQL integration
> goes."

This names the one abstraction Form has been building in fragments and never
stated as a whole. The fragments are real and load-bearing; this doc ties them
into a single model so a fresh cell — or a sibling kernel author — can reach the
environment without inventing a new seam each time.

## The core distinction: structure is intrinsic, interface is projected

Form already answers "interface vs structure" — it inherits BML's answer, and
the substrate trinity *is* that answer:

| | Structure | Interface |
|---|---|---|
| Trinity phase | **Blueprint (ice)** — what something IS | **Recipe / View (water)** — how it BEHAVES when seen a certain way |
| BML reference | `object_id` / `this` (structural base) | `interface_id` / `self` (behavioral base) |
| In the body today | a Record's fields; a table-blueprint; a NodeID by shape | `\|>` projection (`@memory(x) \|> @presence`); `form-capability-contract` |
| Identity | content-addressed, unaliasable | attachable to *any* structurally-compatible structure, swappable |

The load-bearing properties, all already present:

- **Structure is content-addressed and intrinsic.** Two things of the same
  shape ARE the same Blueprint, automatically. You don't attach structure; you
  *are* it.
- **Interface is decoupled and many-to-one.** BML's whole "enhance any object
  with a new interface" move is in `form-language.md` as the `|>` operator:
  *"the same data can be viewed through multiple interfaces."* An interface
  attaches to structure; it is not fused into it.
- **Interface attachment is hallucination-bounded.** A View through an
  incompatible Blueprint is *refused* by the substrate (`form-language.md`
  §Views). You cannot claim a behavior the structure can't support.
- **The floor is the `native_flag`.** BML's reference carries a bit
  (`OBJECT_MODEL_BML_NUMS.md`): when set, *there is no separate interface — the
  `object_id` IS the value*, host-native, unaliasable. This is exactly the
  boundary where Form meets its environment: at the edge, structure and value
  collapse into a host primitive that Form does not introspect, only invokes.

So: **structure says what IS; interface says how it's USED; the environment is
reached at the `native_flag` floor where a value is host-native.** A "resource"
is not a new kind of thing — it is structure (a Blueprint describing the
operation's shape) plus an interface (a capability-contract describing its
effect semantics) bound to a host realization at the native floor.

## The missing word: Port

The body has the two halves and the binding *pattern*, but no name unifying
them. Name it **Port**.

```
Port = capability-contract (structure + interface)  ⟗  carrier (host realization)
       └─ WHAT the operation is and what it costs ─┘     └─ WHO actually does it ─┘
```

- **The contract half already exists** — `engine.fk`'s `form-capability-contract`
  carries `(effect, reversibility, lossiness, deterministic, resources)`,
  content-addressed by `intern_node`, and is exercised by three band tests
  (`dynamic-adapter-registry`, `recipe-capsule-abi`,
  `runtime-dynamic-capability-registry`). A capability is *already* a
  first-class structural value describing an interface's semantics.
- **The carrier half already exists for tools** —
  [`lc-tools-as-form-cells`](../vision-kb/concepts/lc-tools-as-form-cells.md)
  defines a tool as `(call_pattern, response_pattern, carrier)` with
  **`carrier ∈ {shell, http, in_process}`**. That IS the resource-binding
  model. It simply stops at tools and was never generalized to storage,
  compute, or any other resource.
- **The swap mechanism already exists** — the `substrate_dispatch` registry
  (used across nine stdlib modules) that swaps `_cosine` for
  `form_native.cosine` is the same registry that
  `lc-tools-as-form-cells` notes "can swap one carrier for another." Binding is
  data, not code.
- **The host seam already exists in all three kernels** — Go's `plugin.Open`,
  Rust's `libloading`, TS's `new Function` are the same physical seam by which
  a host realization is loaded. Effectful natives
  (`read_file`, `write_form_binary`, the `socket_*` family, `fetch`) are all
  attributed `catCall()` — "invoke external effect" — which is precisely the
  *carrier-invocation* category. The kernel already distinguishes
  pure-structural work (`catWitness`, `catMath`, `catAccess`) from
  reach-the-environment work (`catCall`).

A **Port** is the missing noun that says: *this capability-contract is realized
by this carrier.* Tools become one port-family (`carrier: shell|http|in_process`).
Storage becomes another. The kernel grows no per-resource knowledge; a resource
is a contract + a bound carrier, both data.

## What this makes SQL

SQL stops being "a thing to integrate" and becomes **one carrier of the storage
port** — exactly your framing: storage is a logical abstraction; the backing can
be memory, file, or network (DB or non-DB).

```
storage port (capability-contract: get-or-insert by content, lookup, put, scan)
  ├─ carrier: memory        — an in-process map (test/dev, the leanest)
  ├─ carrier: file          — persistence.fk over .fkb (already built, Breath 5)
  ├─ carrier: sql/sqlite    — db-schema.fk renders DDL; emits/sql.fk renders DML;
  │                            a host carrier executes the strings (dev/test)
  ├─ carrier: sql/postgres  — SAME contract, SAME rendered strings, prod carrier
  └─ carrier: network/non-db — an HTTP/socket store, same contract
```

Three pieces the body *already* has for the SQL carrier, none of which are the
kernel learning SQL:

1. **The schema (structure)** — `db-schema.fk`: a table is a Blueprint;
   `create-ddl` / `migration-ddls` project it to DDL per dialect (dialect is
   data). Three-way proven.
2. **The query/DML (interface)** — `emits/sql.fk`: the universal codec already
   renders comparisons → WHERE, pairs → `col = val`, objects → SELECT. SQL is
   one emit-target beside Python/Go/Rust/HTML.
3. **The carrier (host realization)** — the *only* genuinely new piece: a thing
   that takes a rendered string and runs it against a real store. This is the
   `native_flag` floor — Form hands a string to a host primitive and gets rows
   back; it does not introspect the driver.

The relational shape (tables, rows, WHERE) is **one interface over the storage
port**, not the port itself. A key-value carrier, a graph carrier (Neo4j is
already in the stack), and a document carrier are other interfaces over the same
port. This is why "where does SQL go" was the wrong question: SQL is an
interface+carrier pair plugged into a port the body needs to name first.

## The carrier-binding seam — settled on evidence

The fork was "Form-level registry vs new kernel host-binding natives." A direct
probe of the kernel's dispatch settles it:

- `(f 3 4)` where `f` is a let-bound **function value** → works (returns 7). Form
  passes functions as first-class values through variables.
- `((nth ops 1) 3 4)` — a *computed* head position — **does not parse**. Native
  dispatch requires a static symbol in head position; there is no `apply`.

So a carrier **cannot** be selected by a data-driven head (`(carrier-op args)`
where `carrier-op` is looked up at runtime). But it **can** be a function value
bound to a name and then called:

```form
(let op (storage-intern-fn carrier))   ; pull the operation (a function value)
(op store key recipe)                  ; call it — static head, value from data
```

This is exactly the `substrate_dispatch` pattern (swap `_cosine` for
`form_native.cosine`), and it means:

**The binding seam lives at the Form level, not in new kernel natives.** A
carrier is a record of named function-values (its operations); selecting a
carrier is choosing which record; invoking is let-binding the operation and
calling it with a static head. The kernel needs *no* `port_bind`/`port_invoke`
surface — first-class function values + the existing effectful `catCall` natives
(which each carrier's functions wrap) are sufficient. This keeps the kernels
small (no effectful path that can't be value-diffed three ways) and puts carrier
selection where it belongs: in data the Form layer reads.

The `native_flag` floor is respected: the *effect* still happens in a `catCall`
native (file write, socket send, SQL exec) — the carrier's function value is a
thin Form wrapper choosing *which* native to reach. Selection is Form-level;
execution is kernel-floor. The probe confirmed the hypothesis the trinity
predicted.

## Why this is the right shape for the platform

- **It's the substrate's own grammar applied to the environment.** Structure /
  interface / native-floor is the same ice/water/gas trinity the whole body
  runs on. Reaching the environment is not a foreign concern bolted on; it's the
  trinity at its edge.
- **One model, many resources as data.** Tools, storage, compute, network all
  become contract + carrier. New resources are rows, not new kernel code —
  core-abstraction-first.
- **Traceability for free.** A capability-contract is content-addressed and
  carries `(effect, reversibility, resources)`; every environment reach has a
  recipe provenance and a declared cost. The witness already records `catCall`
  firings.
- **No second source of truth.** Carriers are swappable *under one contract*;
  there is no file-lattice-vs-SQL reconciliation to keep honest, because the
  contract is the single truth and a carrier is just where it lands today.

## Status and next breath

This doc is the architecture (decision: architect-first). The next breath is the
**storage-port prototype** as its first proof: the storage capability-contract
with a **memory carrier** and the **file carrier** (`persistence.fk`) behind one
Form interface, with the relational view (`db-schema.fk` + `emits/sql.fk`) as one
interface over it. The prototype settles the binding-seam fork on evidence, and
SQL/sqlite lands as the third carrier once the seam is proven on the leanest two.

## See also

- [`form-language.md`](form-language.md) §Views — the `|>` projection operator;
  interface-as-detached-from-structure, BML lineage.
- [`OBJECT_MODEL_BML_NUMS.md`](../../kernels/OBJECT_MODEL_BML_NUMS.md) — the
  single-pointer reference; `(object_id, interface_id, native_flag)`.
- [`lc-tools-as-form-cells`](../vision-kb/concepts/lc-tools-as-form-cells.md) —
  the carrier model (`shell|http|in_process`), here generalized from tools to
  all resources.
- [`engine.fk`](../../form/form-stdlib/engine.fk) §capability — the
  `form-capability-contract` structure (the contract half of a Port).
- [`ORM_TO_FORM_NATIVE.md`](../../kernels/ORM_TO_FORM_NATIVE.md) — the storage
  port's concrete schema/migration engine and the open carrier leaves.
- [`emits/sql.fk`](../../form/form-stdlib/emits/sql.fk) — SQL as one emit-target
  in the universal codec (the DML/interface half of the SQL carrier).
