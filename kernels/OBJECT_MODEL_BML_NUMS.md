# The object model — BML single-pointer + NUMS-Go cells (reference synthesis)

> Urs (2026-05-29): "have a deep look at how BML implements class and pointer
> and pointer-to-vtable-and-data in a single pointer so BML supports multiple
> inheritance like no other language" and "nums.go has cells with methods on
> cells as reference implementation."

Two reference implementations, one architecture. This is the spec the kernel's
object primitive must converge to. Companion to
[`KERNEL_PRIMITIVES_STRUCT_AND_EXCEPTIONS.md`](KERNEL_PRIMITIVES_STRUCT_AND_EXCEPTIONS.md).

Sources (read in full):
- BML object system: `docs/field/urs/artifacts/master-thesis-2000/companion/sgb-bml-objects.txt`
- BML VM: `docs/field/urs/artifacts/master-thesis-2000/companion/angelic-assembler.txt`
- NUMS-Go: `docs/field/urs/artifacts/nums-go-2023/` (README, study-notes, mini-nums/core.py)

## BML: identity + behavior in one reference

A BML reference is **one machine word** (64-bit) carrying two indices:

```
Reference = (object_id : 32 bits,  interface_id : 31 bits,  native_flag : 1 bit)
            └── IDENTITY ────────┘ └── BEHAVIOR ──────────────────────────────┘
            OLT[object_id] → data   InterfaceTable[interface_id] → method table
            "which object / its     "what methods, how to find implementations"
             data lives where"      (native_flag in interface_id's MSB; set →
                                     object_id IS the value, e.g. an int — a
                                     "no-object" / native, cannot be aliased)
```

Both indices point into the **Object Look-Up Table (OLT)**. The interface_id is
"like a C++ VMT pointer or Smalltalk message table — but **dynamically
associated**: two references with the *same object_id* can carry *different
interface_ids*, so the same object data is used by different implementations."

### Why this gives multiple inheritance "like no other language"

- **C++** fuses the vtable pointer into object layout; multiple inheritance
  forces pointer-adjustment *thunks* (`±ΔB` offsets) so a base-class pointer
  lands on the right sub-vtable. **BML carries interface_id in the reference**,
  not in the object — *no thunks, no offset math, no layout duplication.*
- **Java/C#** merge a class's methods + its interfaces' methods into one table,
  so a method's index isn't stable → they forbid MI of implementation. **BML
  keeps each interface as its own descriptor**, so method indices are stable
  per-interface and an object can expose *any number* of interfaces. Dispatch
  stays index-based (fast) yet MI-safe.
- **The dual base resolves the diamond.** A method takes **two** receiver args:
  - **behavioral base (`self`)** — always the true object; used to *dispatch*
    (so an override on the most-derived object is always found).
  - **structural base (`this`)** — the object whose fields the running code
    accesses; *moves* as a call delegates down a base chain.
  - Calling `foo()` on E (E→C→A): `self` stays E throughout; `this` walks
    E→C→A. When A.foo internally calls goo(), dispatch uses `self`=E → finds
    E's override. No data duplication (bases are separate objects shared by
    delegation, not flattened into one layout) → no diamond ambiguity.
- **Detached interfaces / casting at runtime.** A new interface can be cast
  onto any object whose *structure* meets its prerequisites; the runtime adds
  it to the object's instantiator's interface list. Behavior attaches to data
  without touching the data or its class.

### The supporting objects (BML)

- **Descriptor** (OLT entry per object): counter (GC), size, fixed-field
  count, binary/dynamic/persistent flags, Data pointer, **Instantiator ref**.
- **Instantiator** — *the* central object: holds the structure description,
  the **list of supported interfaces**, the instance definition (reflection),
  and a ref to the **Common object**. Every instance keeps a ref to its
  instantiator. Instances of the same type may have *different* instantiators
  (localized rifts) while sharing a base common object.
- **Common object** = class-level state + methods (the `COMMON` arm). BML
  "removes the distinction between classes and instances" — a class is just a
  common object shared by instances via delegation.
- **Object layout**: fixed part (fields from all bases, in declaration order,
  grouped) + optional custom part (dynamic field array OR raw binary, resizable
  then freezable).
- **VM ops** (angelic-assembler): `new`, `getfield`/`putfield` (via `this`),
  `getstatic`/`putstatic` (common object), `cast` (change interface_id),
  `invokevirtual`/`invokeinterface` (dispatch via `self`'s interface),
  `invokespecial` (non-virtual), `invokestate` (on common object).

## NUMS-Go: methods on the blueprint, cells as named slots

NUMS-Go (`recipe.go:497`, validated in `mini-nums/core.py:276`):

```
NamedCell = { Recipe (embedded = ACCESS recipe), Base (parent Blueprint),
              Name (string handle), CTOR (RecipeNodeID — interned seed) }
```

The load-bearing design choices:

- **Methods live on the Blueprint, not on instances.** A Blueprint carries a
  `NamedRecipes` collection (methods) + `NamedCells` (fields). All instances of
  a type share one Blueprint → share its methods. Dispatch is **name-based**:
  `obj.m()` → `obj.Base` (its blueprint) → `NamedRecipes["m"]` → invoke with
  obj as receiver.
- **Methods are part of the type identity.** A Blueprint's NodeID =
  `serialize(category + ordered child blueprint IDs)`, and methods are children
  — so adding a method *changes the Blueprint NodeID*. "Cells are part of what
  the struct IS, not something it HAS." Two structs with the same field+method
  shape content-address to the *same* Blueprint → cross-language structural
  equivalence for free.
- **CTOR is an interned Recipe, not a stored value.** `var g = 5` stores
  `(name "g", blueprint string, access RID_global(inst), ctor <Recipe of the
  init expr>)`. Two globals with the same init share one CTOR NodeID.
- **Dual pointer = BML's, already in the substrate.** A cell's `Base`
  (structural pointer — which blueprint owns the data) and its access `Recipe`
  (behavioral pointer — how to read it) ARE BML's (object_id, interface_id).
  The substrate's `NamedCell` (`api/app/services/substrate/kernel.py`) and its
  view-through-blueprint already implement this split at the Python layer.

## Convergence — what the kernel object primitive must become

The kernel's current `Record` (#2195) = `{ blueprint: NodeID, fields:
name→value }`. That is the **structural half only** (BML's object_id/data,
NUMS's NamedCells). It is a correct first rung but NOT the full model. The gaps,
in BML/NUMS terms:

| Aspect | Record today | BML/NUMS target |
|---|---|---|
| Field data | ✓ name→value, mutable, shared identity | ✓ (this is right) |
| Type tag | ✓ blueprint NodeID | ✓ but blueprint should *own the methods* |
| **Methods** | ✗ none | **on the Blueprint** (NamedRecipes), name-dispatched, shared by all instances |
| **Behavior pointer** | ✗ fused (blueprint = type only) | **separate interface_id** so the same data is viewable through different interfaces (BML's decoupling) |
| **Dual base dispatch** | ✗ | `self` (behavioral, dispatch) + `this` (structural, fields) passed to every method |
| **Multiple inheritance** | ✗ | falls out of multiple interfaces + dual base + delegation; no thunks |
| **Detached interface / cast** | ✗ | attach an interface to any structurally-compatible object at runtime |
| **Content-addressed identity** | ✗ records are distinct objects | blueprint interns by shape (methods included) → cross-language equivalence |

### Build order to the full model (revises rung 2 of the primitives plan)

2a. **Record value + natives** — DONE (#2195). Structural half: mutable fields,
    shared identity, blueprint tag.

2b. **Methods on the blueprint.** A blueprint NodeID gains an associated
    method table: `(blueprint, method-name) → recipe/closure NodeID`, stored in
    the kernel (a `Map<(NodeID,NameID), NodeID>`) or — truer to NUMS — as
    children of the blueprint recipe. Natives: `method_define(blueprint, name,
    body)` and `method_invoke(record, name, args...)` which dispatches by the
    record's blueprint and binds `self`=record. This is what makes a Record a
    real object. Python `class` compiles here: methods → blueprint table.

2c. **Dual pointer / interface_id (BML decoupling).** Let a record carry a
    *behavioral* blueprint distinct from its *structural* one — `record_view`/
    `cast` produces a new handle to the same data with a different method table.
    This is the substrate's view-through-blueprint at the kernel level, and the
    foundation of MI.

2d. **Dual base in dispatch + delegation (DELEGATE/COMMON arms).** Method
    invoke passes `self` (behavioral) and `this` (structural); `delegate` moves
    `this` while keeping `self`. Multiple inheritance + diamond resolution
    emerge here, matching BML exactly.

2e. **Content-addressed blueprints with methods as children** → cross-language
    structural equivalence (a Python class and a Go struct of the same shape
    share a blueprint), closing the loop back to the substrate's promise.

The single-pointer encoding is BML's *machine* optimization (packing two 32-bit
indices in a 64-bit word). At the Form-kernel level the equivalent is a record
value carrying two NodeIDs (structural blueprint + behavioral blueprint); the
bit-packing is an implementation detail we can adopt later for a native
distribution but is not needed for semantic correctness first.

## Discipline

Sibling parity (Go/Rust/TS) on every rung; band-test three-way before the next;
kernels stay small (methods/dispatch are a handful of natives + at most the
METHOD/DELEGATE/COMMON walk arms form-engine.form already names). BML is the
reference for *semantics*; NUMS-Go is the reference for *how it sits on the
NodeID lattice*.
