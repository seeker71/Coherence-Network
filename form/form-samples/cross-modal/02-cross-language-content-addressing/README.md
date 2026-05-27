# 02 — Cross-Language Content-Addressing

**Discovery**: when two authors build "the same algorithm" by different routes,
the kernel's content-addressing makes the convergence observable as a single
NodeID. The convergence isn't a property of the surface tongue — it's a
property of the structural tree the tongue compiles to.

## Run

```bash
cd <repo-root>
go build -o /tmp/form-kernel-go ./form/form-kernel-go
/tmp/form-kernel-go form/form-samples/cross-modal/02-cross-language-content-addressing/converge.fk
```

Output:

```
recursive-tree-1:  2 level, 139 instance
recursive-tree-2:  2 level, 139 instance
iterative-tree:    2 level, 142 instance

recursive-1 == recursive-2? yes — same NodeID, structural identity
recursive-1 == iterative?   no — different shape, different NodeID
```

## The three tongues

The directory holds the same algorithm in three surface forms:

- [`factorial.py`](factorial.py) — Python recursive factorial
- [`factorial.ts`](factorial.ts) — TypeScript recursive factorial
- [`factorial.fk`](factorial.fk) — Form recursive factorial (runs through the
  Go/Rust/TS kernels)

What [`converge.fk`](converge.fk) actually does: it builds the *recipe tree* for
"recursive factorial body" twice via different helper-routes, plus once for the
iterative-while shape. The kernel interns all three and we compare NodeIDs.

## What's reachable today

- **Equal shape → equal NodeID.** The kernel's `intern_node` is
  `serialize_tree(category, children)` → lookup-or-insert. Two trees that
  serialize to the same string return the same NodeID, *in the same run*.
- **Different shape → different NodeID.** Recursive and iterative factorials
  do the same arithmetic but stamp the substrate as distinct structural
  identities. This is honest — they are different recipes.
- **Author-route independence.** Tree #2 builds the same shape through
  intermediate `let`-bindings; the helper path doesn't enter the NodeID. Only
  the final tree's serialization counts.

## What surprised

The convergence is bytewise — no fuzzy matching, no similarity score. Either
the trees serialize identically or they don't. This is the discipline that
gives "cross-language equivalence" its teeth: the question stops being "are
these alike?" and becomes "do they intern to the same NodeID?"

## What's not reachable today

- **Python → NodeID end-to-end via python-bmf.fk.** The grammar file exists
  ([`form/form-stdlib/grammars/python-bmf.fk`](../../../form-stdlib/grammars/python-bmf.fk))
  but wiring it from a sample to actually parse `factorial.py` into a Form
  recipe tree requires lighting up the whole BMF object pipeline inside the
  sample — heavier than a demo's appetite. The convergence property is
  provable at the kernel altitude (this demo) before the grammar lights up
  the same property at the source altitude.
- **Cross-process / cross-DB NodeID equality.** This demo runs in a single
  Go-kernel process. The Python kernel (DB-backed) computes NodeIDs by the
  same serialization but assigns instance numbers based on its DB state.
  Production-grade cross-host NodeID equality lives in
  [`lc-the-kernel-knows-itself`](../../../../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md);
  this demo is the toy-altitude version of that claim.

## The teaching

The grammars for Python, TypeScript, Rust, and Go all exist as `.fk` files
under `form/form-stdlib/grammars/`. When they're wired up end-to-end, every
language's source can become Form recipe NodeIDs. *The convergence shown here
is what the substrate already gives us at the tree-altitude.* The grammar work
extends it down to the source-text altitude.

Lineage: `lc-the-kernel-knows-itself`, `lc-parsers-as-recipes`,
`lc-one-kernel-many-tongues`.
