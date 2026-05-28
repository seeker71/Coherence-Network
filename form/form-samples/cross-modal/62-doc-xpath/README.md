# 62-doc-xpath — addressing content WITHIN one document by path

## What walked

```
$ ./validate.sh form-stdlib/doc-xpath.fk \
                form-samples/cross-modal/62-doc-xpath/doc-xpath.fk
  ✓  doc-xpath.fk+doc-xpath.fk     → title-matches: 1
                                     why-first-matches: 1
                                     headings-count: 3
                                     conclusion-matches: 1
                                     4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each built the same
three-section document, walked the same four path queries, and
landed on the same verdict — using **only** the doc-xpath Form
recipe and the kernel's list + string + node primitives. No
doc-xpath native exists in any kernel; the recipe IS the
implementation.

- 3 sections registered (Intro / Why / Done), each carrying two
  paragraph strings in document order
- `/doc/title` → trivial-string "Test"
- `/doc/section[heading='Why']/paragraph[0]` →
  trivial-string "Because reasons." (predicate addresses section
  by heading equality; positional `[0]` drills into paragraphs)
- `/doc/headings` → flat list of three trivial-string headings
- `/doc/section[2]/paragraph[1]` → trivial-string "The conclusion."
  (purely positional drill into the third section, second paragraph)

**Final verdict: 4** — every query lands correctly in every kernel.

## The shape

```
   DOC ( title         : string
       , SECTION-LIST  : list-node of SECTION recipes )

   SECTION ( heading       : string
           , paragraph-1   : string
           , paragraph-2   : string
           , ... )
```

A section's first child is always its heading; subsequent children
are paragraph strings in document order. The `SECTION-LIST` wrapper
makes the doc's sections positionally addressable — `child[i]` is
the i-th section.

## Path syntax

```
/doc/title                              title trivial-string
/doc/sections                           all sections (list)
/doc/section[i]                         i-th section (0-based)
/doc/section[heading='...']             first section whose heading
                                          equals '...'
/doc/section[i]/heading                 heading of the i-th section
/doc/section[i]/paragraph[j]            j-th paragraph of the i-th
                                          section (0-based)
/doc/section[i]/paragraphs              all paragraphs of the i-th
                                          section (list)
/doc/headings                           all headings, flat list
```

`dxpath` returns a list of matching cells. `dxpath-first` peels the
list and returns the first match — or the `DOC-NOT-FOUND` Blueprint
NodeID when nothing matches. Callers detect with `node_eq`.

## The Form recipe shape

`form-stdlib/doc-xpath.fk` carries:

```
(let DOC           (make_nodeid 1 2 99 1920))
(let SECTION-LIST  (make_nodeid 1 2 99 1921))
(let SECTION       (make_nodeid 1 2 99 1922))
(let DOC-NOT-FOUND (make_nodeid 1 2 99 1923))

(defn make-doc            (title sections))           → DOC
(defn make-section        (heading paragraphs))       → SECTION
(defn doc-title           (doc))                      → string
(defn doc-sections        (doc))                      → list
(defn section-heading     (sec))                      → string
(defn section-paragraphs  (sec))                      → list
(defn section-paragraph-at (sec j))                   → string or
                                                         DOC-NOT-FOUND
(defn dxpath              (path-string doc))          → list
(defn dxpath-first        (path-string doc))          → cell
```

No doc-xpath native opcode; no host parser detour. The recipe
composes directly with the kernel's list + string + node
primitives.

The Blueprint NodeIDs `(make_nodeid 1 2 99 1920..1923)` reserve
the doc-xpath family identity. They sit one decade above
`xpath.fk` and `concept-xpath.fk` (1910..1913) because doc-xpath
is the document-domain sibling lens — the substrate-general
xpath two channels over.

## Why this matters

`xpath.fk` walks the substrate by NodeID. `concept-xpath.fk`
walks the Living Collective KB by concept id and cross-ref edge.
Neither walks WITHIN a document — section by section, paragraph
by paragraph. doc-xpath fills that gap with a path-string lens
the way the other two do for their respective domains:

- **Section by heading.** `/doc/section[heading='Why It Matters']`
  picks the right section without forcing the caller to know its
  position. Useful when the document evolves and ordering drifts
  but headings stay stable.
- **Position fallback.** `/doc/section[2]/paragraph[1]` works
  the same way over any kernel — the recipe handles all
  positional drilling uniformly.
- **Flat heading collection.** `/doc/headings` returns a list of
  every section heading in document order, ready for a table of
  contents, a navigation index, or a structural diff.
- **Cross-channel ready.** Because the document is a Recipe, it
  crosses any channel that carries recipes — wire bytes, registry
  messages, sockets. The same query string evaluates against any
  serialized document.

The recipe is sovereign across all three sibling kernels — once a
kernel runs the core list + string + node primitives,
document-internal addressability comes for free. No new natives,
no new bindings.

## What this is NOT yet

- **No markdown parsing in the recipe.** Sample builds the
  document in memory so sibling-parity stays deterministic. A
  future bridge from `concept-corpus.fk`'s markdown parser to
  doc-xpath's shape is a sibling defn.
- **No nested sections.** A document is title + flat list of
  sections + flat list of paragraphs per section. Section
  hierarchy (h1/h2/h3) is out of scope; the document being
  parsed should flatten its outline before constructing the
  DOC recipe.
- **Predicates limited to `[i]` and `[heading='...']`.**
  Generic xpath supports `@inst`, `text()`, `count()`.
  doc-xpath treats those as out of scope — section position
  and heading equality carry the structural queries this
  domain actually wants.
- **No write surface.** Read-only addressability. Mutating a
  document means rebuilding the recipe; the lens is naive about
  in-place edits.

## Cross-refs

- [`form-stdlib/doc-xpath.fk`](../../../form-stdlib/doc-xpath.fk) — the canonical recipe
- [`form-stdlib/tests/doc-xpath-band.fk`](../../../form-stdlib/tests/doc-xpath-band.fk) — sibling-witness band
- [`form-stdlib/xpath.fk`](../../../form-stdlib/xpath.fk) — generic substrate xpath one decade over
- [`form-stdlib/concept-xpath.fk`](../../../form-stdlib/concept-xpath.fk) — concept-and-edge addressability one decade over
- `60-xpath`, `61-concept-xpath` — sibling samples in the same
  path-as-recipe family
