# 04 — Universal Diff (structural NodeID vs textual lines)

**Discovery**: a text diff and a structural diff between the same two files
report fundamentally different things. The text diff lists changed bytes; the
structural diff names the semantic delta. When you ask "what's actually
different between these two algorithms?" the structural answer is the one a
human wanted.

## Run

```bash
cd <repo-root>
go build -o /tmp/form-kernel-go ./form/form-kernel-go

# Textual diff — what every diff tool gives you
diff form/form-samples/cross-modal/04-universal-diff/recursive.fk \
     form/form-samples/cross-modal/04-universal-diff/iterative.fk

# Structural diff — what the substrate gives you
/tmp/form-kernel-go form/form-samples/cross-modal/04-universal-diff/structural-diff.fk
```

## The two algorithms

Both compute sum(1..10) = 55. Different shapes:

[`recursive.fk`](recursive.fk):

```form
(defn sum (n)
    (if (le n 0)
        0
        (add n (sum (sub n 1)))))
(sum 10)
```

[`iterative.fk`](iterative.fk) (tail-recursive with accumulator):

```form
(defn sum (n acc)
    (if (le n 0)
        acc
        (sum (sub n 1) (add acc n))))
(sum 10 0)
```

## Textual diff says

```
1c1
< ; recursive.fk — sum 1..n by recursion.
---
> ; iterative.fk — sum 1..n by tail-recursive accumulation.
3c3
<     (defn sum (n)
---
>     (defn sum (n acc)
5,7c5,7
<             0
<             (add n (sum (sub n 1)))))
<     (sum 10))
---
>             acc
>             (sum (sub n 1) (add acc n))))
>     (sum 10 0))
```

5 lines changed. Useful for a review tool, useless for answering "what's the
algorithmic difference?".

## Structural diff says

[`structural-diff.fk`](structural-diff.fk) walks the *recipe trees* of both
function bodies in parallel:

```
root (if-expr)   : DIFF (different sub-tree NodeIDs)
  test (n <= 0)  : SAME 139            ← the predicate is shared
  then-branch    : DIFF (0 vs acc)     ← what the base case returns
  else-branch    : DIFF (recursive call shape differs)
```

The diff names what's actually different: **the predicate is the same
gesture**; the difference is **what gets returned from the base case** and
**how the recursive call accumulates**. The structural diff is one altitude up
from the text — it's reading what the code IS, not what its bytes say.

## What's reachable today

- **Tree-walk diff via node_eq + node_children.** All primitives are in the
  Go/Rust/TS kernels: `node_eq` for structural identity, `node_children` for
  descent, `node_pkg/level/type/inst` for printing.
- **Predicate-sharing surfaced for free.** Where two trees share a sub-shape,
  `intern_node` returns the *same NodeID* for that sub-tree. The diff doesn't
  need to detect the match — content-addressing already did it.

## What surprised

The "predicate is the same" observation popped out without any matching
algorithm. The kernel's content-addressing made the sub-tree-equality
automatic — `node_eq` is just `==` on the 4-tuple. The diff machinery is
trivial; the **content-addressing is the work**.

## What's not reachable today

- **Cross-language structural diff (Python vs Form source).** Same caveat as
  experiment 02 — parsing Python through python-bmf.fk into Form recipes
  end-to-end is heavier than a sample's appetite. Once that pipeline lights
  up, diffing a Python `sum()` against a Form `sum()` is the same gesture as
  what this demo does.
- **Pretty rename detection.** A real diff tool would say "the predicate
  moved from line 4 to line 4" — line numbers, hunks, edit distance. The
  structural diff in this demo says only "this sub-tree is SAME, this
  sub-tree is DIFF". Edit-script rendering is a separate composition.

## The teaching

The text diff lives at the syntax altitude — what bytes changed. The
structural diff lives at the recipe altitude — what *shape* changed.
Content-addressing makes the second view almost free: `node_eq` does the work
that fuzzy-similarity algorithms would do textually. The substrate's identity
discipline is the universal-diff infrastructure.

Lineage: `lc-the-kernel-knows-itself`, `lc-parsers-as-recipes`.
