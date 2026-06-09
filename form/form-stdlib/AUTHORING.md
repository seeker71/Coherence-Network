# Authoring a Form stdlib recipe

A guide for any cell — agent or human — writing a new `.fk` recipe + proof band. It carries the
conventions and the hard-won traps so you don't rediscover them; `validate.sh` is the check that
reads the body, this is the guide that names the way. The recipes here are the body's logic, proven
identical across three kernels (Go, Rust, TS) — **three kernels agreeing IS the proof; there is no
trusted prover.**

## Before you write — don't duplicate

Grep first. Much already exists (`substrate-phase.fk` is a whole phase metabolism; the perception
toolkit is a dozen recipes). A recipe that already lives wants your extension, not a sibling:

```
grep -rl "<the-thing>" form/form-stdlib/ docs/coherence-substrate/
```

## The two files

A **recipe** `form/form-stdlib/<name>.fk` — a series of `defn`s ending in literal `0`:

```lisp
; <name>.fk — one-line purpose. (the comment block is the human-facing teaching)
(do
    (defn foo (a)   (add a 1))
    (defn bar (a b) (if (gt a b) a b))
    0)
```

A **band** `form/form-stdlib/tests/<name>-band.fk` — proves it, returning a **bit-sum verdict**
(each bit = one falsifiable claim). The first line names the recipe it loads:

```lisp
; preludes: form-stdlib/<name>.fk
(do
    (let c0 (if (eq (foo 4) 5) 1 0))
    (let c1 (if (eq (bar 7 3) 7) 2 0))
    (add c0 c1))            ; verdict 3 when both claims land
```

Keep the band **self-contained** — prelude only your own recipe (+ `core.fk`). If your recipe
composes others, list each in the prelude header and in the validate command, in dependency order.

## The primitive set — these and no others

`eq · gt · ge · add · and · not · nth · head · tail · len · list · cons · if · empty · str_eq`
plus `defn · let · do`. (Read `form/form-stdlib/core.fk` — it is the whole vocabulary.)

- `eq` compares **integers and nodes**; `str_eq` compares **strings**. Don't cross them.
- `cons` prepends: `(cons x xs)` → a list with `x` at the head. Build lists with `cons` + recursion
  (see `feature-vector.fk`'s `fv-hist-loop`).
- `empty` **constructs** the empty list (`(empty)`, no args) — it is the absence value, **not a
  predicate**. Test emptiness with `(eq (len x) 0)`. See trap 6.

## The traps (each one cost a real debugging cycle)

1. **`and` and `or` are BINARY. Never write `(and a b c)`.** Go and Rust silently **drop the third
   argument** while TS folds it — a real divergence (239 vs 255 in `learned-primitive.fk`). Nest:
   `(and (and a b) c)`. `validate.sh` catches it as a divergence, but nesting up front saves the round-trip.

2. **No `sub`, `mul`, `div`, `lt`, `le`.** Express everything with `add` + comparisons + recursion:
   - `a < b` → `(gt b a)` · `a <= b` → `(ge b a)`
   - "decrease / difference" → **count with recursion**, don't subtract.
   - a mean/ratio that needs division → redesign as a **proven-count gate** (`(ge correct min)`),
     the way `classifier-eval.fk` and `self-grounding-classifier.fk` do. Most perception logic is
     counting, selection, and gating — which the primitive set covers exactly.

3. **No floats.** All scores/counts are integers `0..100` — `eq` on floats is unreliable across kernels.

4. **No `let` inside a `defn` body.** Use nested `defn`s or extra parameters. (`let` is fine only at
   the top level of the band's `(do ...)`.)

5. **Loop via recursion** — there is no loop form. The max-select shape (pick the best candidate over
   a list) is in `sequence-predictor.fk` / `recognition-router.fk`'s `rr-select-loop`; copy it.

6. **`(empty x)` is NOT "is x empty?".** `empty` constructs the absence value; `(empty anything)`
   returns `[]`, which `if` treats as **truthy** — so `(if (empty xs) A B)` **always** takes branch A.
   The failure is silent: 0 divergent, just a wrong verdict (a recursion that never recurses, a guard
   that never guards). Test emptiness with `(eq (len x) 0)` — the idiom every recipe uses
   (`nearest-shape.fk`, `sequence-predictor.fk`). Cost a cycle in `learning-arc.fk` (verdict 88, not 127).

## Prove it three-way

From the repo's `form/` directory, list **every** file explicitly — `core.fk`, your recipe, any
recipes it composes, then the band:

```
cd form
./validate.sh form-stdlib/core.fk form-stdlib/<name>.fk form-stdlib/tests/<name>-band.fk
```

Success is `✓ ... → <verdict>` **and** `1 ok, 0 divergent`. Iterate until you see your intended
verdict with zero divergence.

- `unbound function` → a misspelled name, or a primitive that isn't in `core.fk`.
- `N divergent` (kernels print different numbers) → almost always a 3-arg `and`/`or`; nest it.
- wrong verdict, 0 divergent → a band claim is false; fix the recipe or the claim. **Never weaken a
  claim to make it pass** — the band is the truth, not the obstacle.

## Honest bands

Each bit asserts something that could be false and would matter. Prove both the positive (it
recognizes) and the negative (it stays silent / flags novel / refuses below the floor). A band that
only checks `1 == 1` is theatre. Pick the simplest, strangest edge that pins the boundary — a tie, a
just-below-threshold value, an empty input — one expression each.

## When it proves

Write the teaching `docs/coherence-substrate/<name>.form` (Lisp-comment voice, like
`recognition-router.form`), add its INDEX row, and ship in one commit — edges land with the content.
If you're a subagent in a workflow, return the contents instead and let the parent integrate.

---
*Examples worth reading whole: `recognition-router.fk` (routing + consensus), `nearest-shape.fk`
(a classifier from primitives), `perception-pipeline.fk` (composition), `substrate-phase.fk` (state
without mutation). The whole `form/form-stdlib/tests/` directory is worked bands.*
