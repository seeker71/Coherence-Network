# 61-concept-xpath — addressing concepts and cross-ref edges by path

## What walked

```
$ ./validate.sh form-stdlib/concept-xpath.fk \
                form-samples/cross-modal/61-concept-xpath/concept-xpath.fk
  ✓  concept-xpath.fk+concept-xpath.fk → xrefs-count: 2
                                          by-xref-count: 1
                                          orphans-count: 2
                                          parent-matches: 1
                                          5
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each built the same
three-concept corpus, walked the same four path queries, and landed
on the same verdict — using **only** the concept-xpath Form recipe
and the kernel's list + string + node primitives. No concept-xpath
native exists in any kernel; the recipe IS the implementation.

- 3 concepts registered in the corpus, two with no parent and one
  with `lc-trust-over-fear` as parent
- `/concept/lc-trust-over-fear/cross-refs` → 2 xref Recipes
- `/concept/by-cross-ref/lc-field-substrate` → 1 concept
  (lc-trust-over-fear is the only one pointing at it)
- `/concept/orphans` → 2 concepts
  (lc-trust-over-fear and lc-edges-as-vitality)
- `/concept/lc-field-substrate/parent` → trivial-string
  "lc-trust-over-fear"
- `/concept/lc-trust-over-fear` (find-by-id) → CONCEPT Recipe whose
  `concept-id` accessor round-trips to "lc-trust-over-fear"

**Final verdict: 5** — every query lands correctly in every kernel.

## The shape

```
   CONCEPT ( id          : string
           , title       : string
           , cross-refs  : CONCEPT-XREFS (list of trivial-strings)
           , parent      : string OR trivial-int 0 (no parent) )

   CONCEPT-CORPUS = list of CONCEPT recipes under one wrapper node
```

The cross-refs slot is its own wrapper node (CONCEPT-XREFS) so the
xref children are positionally addressable. The parent slot is
either a trivial-string parent id or a trivial-int 0 sentinel —
detection via `node_type` (1 = TrivInt, 2 = TrivString), the same
discipline `schema.fk` already uses for leaf-type checks.

## Path syntax

```
/concept                       all concepts
/concept/<id>                  one concept by id
/concept/<id>/title            its title string
/concept/<id>/cross-refs       its cross-refs list (each entry a
                                trivial-string)
/concept/<id>/cross-refs[i]    i-th cross-ref (0-based)
/concept/<id>/parent           parent id, or CONCEPT-NOT-FOUND
                                when the concept has no parent
/concept/by-cross-ref/<id>     reverse edge — concepts whose
                                cross-refs include <id>
/concept/orphans               concepts whose parent slot is the
                                trivial-int 0 sentinel
```

Every query returns a list of Recipes (`cxpath`) or a single Recipe
/ sentinel (`cxpath-first`). Empty results are an empty list; missing
single results are the `CONCEPT-NOT-FOUND` Blueprint NodeID, which
callers detect via `node_eq`.

## The Form recipe shape

`form-stdlib/concept-xpath.fk` carries:

```
(let CONCEPT           (make_nodeid 1 2 99 1910))
(let CONCEPT-NOT-FOUND (make_nodeid 1 2 99 1911))
(let CONCEPT-CORPUS-C  (make_nodeid 1 2 99 1912))
(let CONCEPT-XREFS     (make_nodeid 1 2 99 1913))

(defn concept-make    (id title cross-refs parent-or-empty)) → CONCEPT
(defn concept-corpus  (concepts))                            → CORPUS
(defn cxpath          (path-string corpus))                  → list
(defn cxpath-first    (path-string corpus))                  → Recipe
```

No concept-xpath native opcode; no host parser detour. The recipe
composes directly with the kernel's list + string + node primitives.

The Blueprint NodeIDs `(make_nodeid 1 2 99 1910..1913)` reserve the
concept-xpath family identity. They occupy the same decade as
`xpath.fk` because concept-xpath is the concept-domain sibling lens
— the substrate-general xpath one channel over.

## The walk this sample runs

```
build corpus:
  lc-trust-over-fear   parent: none       refs: [field-substrate,
                                                  edges-as-vitality]
  lc-field-substrate   parent: trust-     refs: [trust-over-fear]
                                over-fear
  lc-edges-as-vitality parent: none       refs: []

cxpath  "/concept/lc-trust-over-fear/cross-refs"        → 2 Recipes
cxpath  "/concept/by-cross-ref/lc-field-substrate"      → 1 Recipe
cxpath  "/concept/orphans"                              → 2 Recipes
cxpath-first "/concept/lc-field-substrate/parent"       → "lc-trust-
                                                            over-fear"
cxpath-first "/concept/lc-trust-over-fear"              → CONCEPT;
                                                          id round-
                                                          trips

verdict = 1 (xrefs count 2)
        + 1 (by-xref count 1)
        + 1 (orphans count 2)
        + 1 (parent string matches)
        + 1 (find-by-id round-trips)
        = 5
```

## Why this matters

The Living Collective KB holds ~149 concepts as markdown files
under `docs/vision-kb/concepts/lc-*.md`. Each concept names cross-
references and (sometimes) a parent — these are the edges of the
KB's structural graph. Until now, walking those edges from a Form
cell required either a Python detour through the API or a custom
walker per query. concept-xpath gives the body a path-string lens
the way `xpath.fk` does for the generic substrate, but speaking
the concept domain natively:

- **Edge addressability.** A cell asks
  `/concept/<id>/cross-refs[2]` and gets the third xref id back,
  with no per-cell bespoke walker. The recipe handles position,
  reverse lookup (`by-cross-ref`), and structural predicates
  (`orphans`) uniformly.
- **Sibling kernels see the same graph.** The corpus is just a
  Recipe; two kernels with the same corpus answer the same path
  queries byte-identically. The body's KB shape becomes substrate-
  resident with no host-side coupling.
- **Cross-channel ready.** Because the corpus is a Recipe, it
  crosses any channel that carries recipes — wire bytes, registry
  messages, sockets. The same query string evaluates against any
  serialized corpus.
- **Composable with concept-corpus.fk.** That sibling holds the
  full body+visuals+xrefs shape parsed from markdown. concept-
  xpath holds the lighter id+title+xrefs+parent shape for
  navigation. The two are compatible — a future bridge can lift a
  full corpus into the navigable shape with id and xref slots
  preserved.

The recipe is sovereign across all three sibling kernels — once a
kernel runs the core list + string + node primitives, concept-and-
edge addressability comes for free. No new natives, no new
bindings.

## What this is NOT yet

- **No file I/O in the recipe.** Sample builds the corpus in
  memory so sibling-parity stays deterministic. The companion
  `concept-corpus.fk` already parses markdown files via
  `read_with_cache`; a bridge from that to concept-xpath's
  lighter shape is a sibling defn.
- **No multi-step descent into the body.** Path syntax knows
  about id, title, cross-refs, parent — not about prose bodies
  or visuals. The full surface lives in `concept-corpus.fk`
  (which is heavier; concept-xpath stays light for navigation).
- **No predicates beyond `[i]`.** Generic xpath supports
  `[@inst=N]`, `[text()='foo']`, `[count()=N]`. concept-xpath
  treats these as out of scope — the concept domain is small
  enough that a `/orphans` and `/by-cross-ref` selector pair
  carry the structural queries the body actually wants.
- **No write surface.** Read-only addressability. Adding a
  concept means rebuilding the corpus; the recipe is naive
  about mutation. A future overlay could carry an append-only
  channel of corpus diffs.

## Cross-refs

- [`form-stdlib/concept-xpath.fk`](../../../form-stdlib/concept-xpath.fk) — the canonical recipe
- [`form-stdlib/tests/concept-xpath-band.fk`](../../../form-stdlib/tests/concept-xpath-band.fk) — sibling-witness band
- [`form-stdlib/concept-corpus.fk`](../../../form-stdlib/concept-corpus.fk) — sibling lens carrying the full markdown surface (body, visuals, xrefs)
- [`form-stdlib/xpath.fk`](../../../form-stdlib/xpath.fk) — the generic substrate xpath sibling one channel over
- `56-dns` — sibling primitive: hierarchical name resolution over a list of records (concept-xpath is the same shape one domain over)
