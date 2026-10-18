# Form language

Form is a content-addressed language of blueprints, recipes, cells, choices,
effects, and observations. BML and domain grammars are its authored surfaces.
`fkwu` is its sole live kernel.

## For agents arriving fresh read before the long story

The production direction is:

```text
domain grammar or BML
  -> Form recipes and cells
  -> fkwu realization
  -> page JIT for hot compatible functions
  -> observed value/effect receipt
```

Rust, Go, TypeScript, and Python kernel implementations are bootstrap history
and prior validation evidence. They are not implementation targets, runtime
fallbacks, or routine validation gates. A missing fkwu or page-JIT capability
is work in fkwu/JIT; it is never permission to restore a sibling carrier or a
lowering detour.

Start with:

1. [`../shared/agent-start-packet.md`](../shared/agent-start-packet.md)
2. [`../../form/form/apps/coherence-network/api.bml`](../../form/form/apps/coherence-network/api.bml)
3. [`../../form/form/form-stdlib/bml/jit-page.bml`](../../form/form/form-stdlib/bml/jit-page.bml)
4. [`../system_audit/form_kernel_floor_2026-10-18.md`](../system_audit/form_kernel_floor_2026-10-18.md)

## The three structural kinds

- A **Blueprint** names a shape.
- A **Recipe** names a transformation or relation over shapes.
- A **NamedCell** gives a stable local name to an observed composition.

Content-addressing makes equal compositions share identity. Names may move;
the compositions they recognize remain available, attributable, and
reversible.

## Surface notation

Direct Form recipes use S-expression syntax:

```form
(do
  (defn twice (x) (mul x 2))
  (twice 21))
```

BML is the preferred high grammar for typed programs, classes, interfaces,
route catalogs, and larger application cells:

```bml
section [form.bml] {
    def twice(x) = x * 2;
    twice(21);
}
```

Use a domain grammar above BML when the domain has repeated language of its
own. Use direct recipes when they are already the clearest complete shape.

## How to write software default for every agent

1. Find the live BML/domain grammar or application cell that owns the behavior.
2. Add the behavior at the highest existing grammar.
3. Realize it on fkwu.
4. Let the page JIT own hot compatible functions.
5. When the JIT cannot carry a needed shape, repair that JIT shape directly.
6. Observe the smallest result or effect that proves the change.
7. Move callers to the replacement and remove obsolete host code, adapters,
   fallback routes, documentation, and duplicate authority.

The current Coherence Network application catalog is
[`api.bml`](../../form/form/apps/coherence-network/api.bml). The Python API is
the compatibility HTTP/persistence host for routes not yet owned end to end by
the native application host. It is location, not destination authority.

## Choice and care

Branching belongs in Form choice semantics: `choose`, `fail`, `stop`, and the
save/restore/discard boundary. A failed choice carries its inputs, owner,
effects, and observation into the next choice. Repeating an unchanged failure
is not progress.

External effects travel through explicit resource interfaces and host doors.
The recipe names the capability it needs; the carrier provides only that
bounded capability. File, process, HTTP, socket, persistence, and platform
resources already have native fkwu surfaces. New host wrappers are not the
default implementation language.

## The page JIT

The fkwu page JIT is the optimization authority. Heat from real execution
selects compatible functions, binds their page, and records misses and
dispatch observations. A miss is an implementation finding. Extend the page,
op table, calling convention, or value shape that caused it, then run only the
focused band that demonstrates the repaired shape.

Do not introduce an alternate evaluator, pre-translated copy, hand-lowered
route, or sibling-kernel fallback. Those hide the gap and split authority.

## Source realization

High-grammar source keeps its imports and prelude declarations. fkwu owns
their realization. Callers pass the source unit as a unit; host code does not
concatenate high-grammar bodies into direct Form, strip prelude directives, or
generate shadow source trees.

Native images (`.fkb`), symbols (`.sym`), attestations, and source identities
are one carrier bundle. `gate/form-cli-build-run.bml` builds and proves the
native `form-cli` bundle. Its `.source.id` is the source authority used by
cache selection and deployment observation.

## Reading and shell work

- `form-cli ask` is the grounded native reasoning/read door.
- `fsh-main.fk` is the Form shell surface.
- The substrate read door carries NodeID, equivalence, and annotation lookups.

A sufficient grounded native answer ends the lookup. A miss permits remote
reasoning, which must remain labeled as rented rather than body-generated.

## Application hosting

The native application host already has BML route catalogs, JSON composition,
HTTP primitives, sockets, crypto, host I/O, and Postgres primitives. The
current direct work is to join those capabilities into complete ownership:

- template-parameter dispatch;
- file-backed configuration;
- Postgres and persistence lifecycle;
- process startup and public HTTP ownership;
- migration of one complete route family at a time;
- deletion of each Python owner after its native replacement is observed.

## Validation

Validation follows the changed surface:

- fkwu source change: the smallest focused compile/runtime/JIT observation;
- BML or recipe change: its focused application result;
- host compatibility change: its exact boundary contract;
- documentation-only change: structural/source checks.

There is no routine sibling-kernel suite. The presence of historical carriers
does not create a validation obligation.

## Trust and sovereignty

Native lookup and verification do not imply native prose generation. Report
each reasoning step with its path, grounding, frequency, sufficiency, and
observation status. Report rented model/provider use honestly. The body earns
more sovereignty by owning more of the route, effect, evidence, and response —
not by relabeling remote reasoning as native.
