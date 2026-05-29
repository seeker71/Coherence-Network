# Kernel primitives: struct/class + exceptions (BML reference)

> Urs (2026-05-29): "we need class / struct with method support in form kernel,
> most languages need this" and "all languages will need exception handling,
> and even more, BML needs exception handling with reverse execution logic —
> you can see BML as reference implementation for any of the kernel primitives."

These are **native kernel primitives** (Go/Rust/TS sibling kernels), not
desugarings in the Python-BMF compiler. Every language target needs them. BML
(Backtracking Model Languages — Bjørg, master thesis 2000,
`docs/field/urs/artifacts/master-thesis-2000/`) is the reference.

The whole Python-BMF compiler is Form-on-kernel already (no Python runtime);
these primitives let `class` and `try/except` (and the equivalent in every
other language grammar) compile to recipes the kernels walk natively.

## Where the kernel is today (2026-05-29 survey)

- **Value** (Rust enum / Go struct / TS union): Null, Int, Float, Str, Bool,
  List, Closure, Nid. **No record/object/struct variant.** Closures capture a
  frame; that's the only compound-with-behavior today.
- **walk dispatch** handles 9 executable arms: MATH(12), COMPARE(13),
  LOGIC(14), COND(11), BLOCK(9), IDENT(33), FNDEF(31), FNCALL(32), LIST(34).
  METHOD(27) and ACCESS(15) exist only as Blueprint *categories* for native
  attribution — **not** executable arms.
- **No exception mechanism.** `walk` returns `Value` directly (not a Result).
  A runtime error (`1/0`, unbound ident, bad arity) is a hard panic (Rust
  panic / Go panic / JS throw) — uncatchable from Form.
- **form-engine.form** already *declares* the target arm vocabulary (the Form
  meta-circular evaluator names them): STATE(22) save/restore/discard,
  EXCEPTION(23) raise/resume, REVERSE(25) undo/inverse, TRY(30) try_catch,
  METHOD(27) define/invoke, DELEGATE(24), COMMON(26). The native kernels
  don't implement these yet — that's the gap.
- **form-ontology.json schema debt:** STATE/EXCEPTION/DELEGATE/REVERSE/COMMON/
  TRY are referenced by form-engine.form but not yet catalogued in
  form-ontology.json. Add them there first (one place; `bp` resolves names).

## BML reference — what the primitives must mean

### Object / struct model (BML Object System, `companion/sgb-bml-objects.txt`)

- **Reference = (object_id, interface_id, native_flag).** Structure and
  behavior are *separated*: object_id indexes the data, interface_id indexes
  the methods (like a VMT but **dynamically** associated — the same data can be
  viewed through different interfaces). native_flag means the value is inline.
- **Dual base on method calls:** a method takes a *behavioral base* (`self` —
  used to dispatch) and a *structural base* (`this` — used for field access).
  Delegation splits them: `self` stays at the delegator (finds the
  implementation), `this` moves to the delegate (provides the fields).
- **Object = structural repository only; behavior is pluggable** (detached
  interfaces can be cast onto any object whose structure meets the prereqs).
- **Instantiator** is the central object: holds structure description, the list
  of supported interfaces, the instance definition (blueprint), and the common
  object (class-level state + methods = `COMMON`/shared-base).

**Kernel implication.** A struct/object is a **mutable record with identity**:
a heap value carrying (a) a blueprint/instantiator NodeID (its type + method
table) and (b) named fields. Method dispatch reads the blueprint's method
table by name. This is the minimum; full BML adds detached interfaces + dual
bases + delegation (DELEGATE/COMMON arms) as later layers.

### Exceptions with reverse execution (BML thesis core)

The thesis's load-bearing claim: **backtracking is not a feature, it is the
architecture of execution.** At the VM level (`companion/angelic-assembler.txt`,
`BMCPU/main.cpp`), `BMVM_STATE.byMode` toggles `DO`/`UNDO` on every step —
**every instruction has forward and reverse semantics.**

- **State stack** primitives: `save` (push n bits), `restore` (pop+restore),
  `discard` (drop). A choice point `save`s; failure `restore`s back to it.
- **fail / throw** flips the VM into UNDO mode; it pops the state stack and
  runs each instruction's inverse, unwinding assignments/field-writes/effects
  back to the last choice (or handler) point.
- **Native methods carry three pointers: do / redo / undo.** A side-effecting
  native must provide its inverse so the journal can reverse it.
- **try/catch** (thesis §"Try Catch Translation", assembly `jerr`/`throw`):
  `jerr handler` installs a handler frame; `throw` puts the exception in a
  register and jumps to the handler; the handler does `IsInstance` type-filter
  per catch, binds the matched exception, runs that catch; no match → re-throw
  to the next outer handler.
  - **Caught** → unwinding *stops* at the handler; partial state before the
    throw is **kept** (try/catch is control-flow, not auto-rollback).
  - **Uncaught** → the angelic UNDO unwinds effects as it propagates.
  - Explicit rollback-to-try-point is `save` at try-entry + `restore` on catch
    — composed from the state-stack primitives, not built into try.

**Kernel implication.** This needs `walk` to be able to **signal** rather than
only return a `Value`. Minimum viable shape: a thread-local / kernel-field
"pending signal" (exception value + mode) that arms check after each child
walk, plus a try arm that installs a catch boundary. Full BML adds the
DO/UNDO journal + per-native undo for true reverse execution. The journal is
the deeper layer; a catchable-signal try/catch (no auto-undo) is the first
rung and already matches BML's "caught → keep partial state" semantics.

## Build order (core abstraction first, each its own breath)

1. **Ontology + arm numbers.** Add STATE(22), EXCEPTION(23), DELEGATE(24),
   REVERSE(25), COMMON(26), TRY(30), and a STRUCT/object family to
   form-ontology.json with the form-engine.form instance numbers. One source
   of truth; `bp "raise"` etc. resolve everywhere.

2. **Struct/class primitive (no new control flow — start here).**
   - Add a `Record` Value variant (Go/Rust/TS): `{ blueprint: NodeID, fields:
     map<name,Value> }` — mutable identity (Rc/RefCell in Rust, pointer in Go,
     object in TS).
   - Executable **METHOD(27)** arm: define (register a method NodeID under a
     blueprint+name) and invoke (dispatch by reading the blueprint's table,
     binding `self` to the record).
   - Field read via **ACCESS(15)** arm; field write via a new STATE-ish set or
     a `record_set` native (mutates in place — the first genuinely mutable
     kernel value, which BML requires for `self.x = v`).
   - Every language's `class`/`struct` compiles onto this. Python `class`:
     constructor builds a Record with blueprint = the class; methods are
     NodeIDs in the blueprint table; `obj.m()` is METHOD-invoke; `self.x`
     is ACCESS; `self.x = v` is record_set.

3. **Catchable signal + try/catch (control-flow rung).**
   - Kernel gains a pending-signal channel (exception Value + active mode).
   - **EXCEPTION(23)** arm: `raise` sets the signal; arms short-circuit while a
     signal is pending. **TRY(30)** arm: walk the body; if a signal is pending
     after, run the catch handler (BML `IsInstance` filter) and clear it.
   - Turn the hard panics (divide-by-zero, unbound, bad arity) into raised
     signals so they're catchable — matching the thesis's uniform model.

4. **Reverse execution (the deep BML layer).**
   - STATE(22) save/restore/discard backed by a journal; REVERSE(25)
     undo/inverse. Mutating natives register undo functions (do/redo/undo
     triple). Uncaught throw unwinds the journal in UNDO mode.
   - This is the largest arc; it's what makes BML *BML* rather than ordinary
     try/catch. Build it after 1–3 prove the value/dispatch shapes.

5. **DELEGATE(24) / COMMON(26) / detached interfaces** — the full BML object
   system (dual bases, delegation, shared-base, casting). Latest layer.

## Discipline

- **Sibling parity is non-negotiable.** Every arm/native lands in Go, Rust,
  AND TS together; `./validate.sh` must stay 0-divergent. A primitive in one
  kernel and not the others is a divergence bug.
- **Prove each rung with a band test** in `form-stdlib/tests/` exercised
  three-way, before the next rung.
- **The native kernels stay small** (the README's <1000-line discipline) — add
  exactly the arms/variants the primitive needs; everything above lives in
  Form.
- Reference the thesis sections when implementing: object system in
  `companion/sgb-bml-objects.txt`, VM/backtracking in
  `companion/angelic-assembler.txt` + `backtracking-model-languages.txt`.
