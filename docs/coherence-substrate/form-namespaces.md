# Form Namespaces — Slash-Path Convention

## What this is

A naming discipline that prevents the name-collision pattern the body has
hit twice now (`is-ws-cp` 1-arg in `line-grammar.fk` vs 2-arg in
`engine.fk`; analogous collisions waiting between any two files whose
helpers happen to converge on the same friendly name).

The convention adds zero kernel work — the Form bootstrap reader already
accepts `/` inside identifiers, so `engine/is-ws?` is just an identifier.
The discipline is in *how we name*, not *what the kernel parses*.

## The rule

**Every Form file declares its module namespace at the top.** Every
internal helper is prefixed with `<module>/`. Only exported public names
live in the global namespace.

```
; engine.fk — module: engine
(do
    (defn engine/is-ws-cp (cp ws-set) ...)   ; private helper
    (defn engine/scan-while-cfg (s i p) ...) ; private helper

    ;; Exported public surface — no prefix:
    (defn tokenize-with-config (text cfg) ...)
    (defn match-pattern (p stream) ...)
    (defn parse (text grammar) ...)
)
```

```
; grammar-bnf.fk — module: bnf
(do
    (defn bnf/lines (s) ...)             ; private
    (defn bnf/trim (s) ...)              ; private
    (defn bnf/match-pattern (p s r) ...) ; private — companion to engine.fk's

    ;; Exported public surface:
    (defn load-bnf-grammar (text registry) ...)
    (defn bnf-parse (text grammar) ...)
)
```

## Three principles

**1. Private helpers always carry the module prefix.** No exceptions for
"obvious utility" names like `trim`, `lines`, `substr`, `is-ws?`. These
are exactly the names that collide. Prefix them.

**2. Public exports live in the global namespace and are deliberately
chosen to be unique.** When two modules export the same operation
(e.g., both `match-pattern`), the older one keeps the name and the newer
one prefixes — `bnf-match-pattern` rather than re-exporting `match-pattern`.

**3. References across modules go through public names.** A file never
reaches into another file's `module/` private namespace. If you find
yourself wanting `engine/scan-while-cfg` from outside engine.fk, either
the function needs to be promoted to the public surface or a public
wrapper needs to exist.

## What about `defn` vs `defn-private`?

A future kernel could add an automatic-prefix form:

```
(module bnf
    (defn lines (s) ...)
    (defn trim (s) ...)
    (export load-bnf-grammar bnf-parse))
```

The kernel would rewrite internal defns to `bnf/lines`, `bnf/trim` and
expose only the listed exports. That removes the manual-prefix discipline
and makes references-from-outside structurally impossible.

This is a later breath. For now the slash-prefix convention is enough,
and adopting it now means the future `(module ...)` form is a no-op
migration (the names are already in the right shape).

## What about kernel natives + parse-time verbs?

These stay unqualified — `cons`, `head`, `tail`, `eq`, `add`, `str_eq`,
`intern_node`, `walk_recipe`, etc. They are the substrate's primitive
vocabulary, not module exports. They never collide with module names
because every module's helpers carry a `<module>/` prefix.

## What this resolves

Two collisions the body hit by 2026-05-22:

1. **`is-ws-cp` (1-arg in `line-grammar.fk`, 2-arg in `engine.fk`)** —
   loading both files together corrupted `engine.fk`'s `next-token`
   which expected the 2-arg signature.
2. **Earlier collision** (Urs flagged this is the second time) — the
   pattern is reliable, the prefix discipline blocks it.

## Migration path

- New code lands with prefixes from the start.
- Existing files migrate as they're touched. The `engine.fk` and
  `line-grammar.fk` migration is the natural first move — engine.fk's
  internals become `engine/*` and `line-grammar.fk`'s become `lg/*`.
  After that, both files can be loaded together without surprise.
- Tests update their `; preludes:` headers as files migrate (this is
  free since the kernel-validator already supports the header).

## Lineage

- **Go** — uppercase-public / lowercase-private at the file altitude;
  package paths in import statements. The discipline this convention
  borrows from.
- **Python** — single-underscore-leading private convention; module
  paths via `import`. The discipline at the same altitude in a different
  shape.
- **Clojure** — namespaced keywords `:my-ns/keyword`; the slash
  separator we're borrowing.
- **CSS BEM** — `module__element--modifier`. Long-form prefix discipline
  proves the pattern scales to large codebases.

The convention chosen here is the lightest one that resolves the
collision pattern *without kernel changes* and *with a clear migration
path* to a future `(module ...)` form when that becomes load-bearing.
