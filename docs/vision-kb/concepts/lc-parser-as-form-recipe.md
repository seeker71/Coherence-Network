---
id: lc-parser-as-form-recipe
hz: 741
status: seed
updated: 2026-05-21
geometry:
  arity: 5
  form: bootstrap-to-self-hosting
  topology: spiral-inward
  polarity: bipolar-complementary
  ordering: layered
  phase: emergent
  ratio: 1-to-1
  spectral_band: integration
  temporal_band: arc
  scale: foundational
  direction: inward-tightening
  lineage_texture: synthesized
  embedding_dim: 5
  self_similarity: fractal
cross_refs:
  - lc-parsers-as-recipes
  - lc-the-kernel-knows-itself
  - lc-one-kernel-many-tongues
  - lc-grammar-is-the-universal-recipe
  - lc-the-recipe-remembers-its-source
  - lc-form-kernel-runtime-visualizer
  - lc-form-is-the-bodys-tongue
---

# The Parser as a Form Recipe — the Self-Hosting Boundary, Walked

> A parser that lives in TypeScript or Python is a bootstrap. A parser whose grammar AND rules AND engine are all Form recipes — interned in the substrate, walked by the kernel — is the destination. The work between the two is one rule per breath, structurally legible, each shipped construct visibly retiring host bridge code.

## Where this concept came from

Urs named it directly when reviewing the `python-trace` demo on 2026-05-21:

> *the parser is in .ts? the grammar needs to be in form with a form recipe. we don't want a demo, we want the real thing, with full end-to-end support for the full language.*

The demo had shown real Python (24,022 CTOR dispatches) running through the BMF parser through the kernel's evaluator with full Blueprint attribution. The work was real; the architecture was not. The parser was hand-written TypeScript ([`lang-python.ts`](../../../experiments/form-kernel-ts/src/lang-python.ts), ~2000 lines of host code that does Python parsing). That doesn't meet the body's discipline.

This concept names the full path from where we are to where the parser belongs.

## The destination

A Python source file enters the kernel as raw bytes. The kernel runs a Form recipe — `tokenize_python` — that produces a token stream. The kernel runs another Form recipe — `parse_python` — that walks the rules declared in [`python-grammar.form`](../../coherence-substrate/python-grammar.form). Each rule is itself a Form recipe composed from the six Pattern primitives. The output is a Form recipe tree representing the Python program. The kernel walks that tree to execute the program. **No host parser code anywhere in the path.** TypeScript, Python, and Rust kernels all read the same `.form` files; the parsed NodeIDs agree across all three; the substrate's content-addressing recognizes the equivalence automatically.

## The current state (2026-05-21)

| Layer | Bootstrap (host) | Destination (Form) | Status |
|---|---|---|---|
| Grammar shapes | `lang-python.ts` types | `python-grammar.form` Blueprints | **shipped** |
| Pattern primitives | `bmf.py` Python classes | `grammar-as-recipe.form` Blueprints | **shipped 2026-05-21** |
| Token streamer | `bmf.py` `tokenize()` | `token-streamer.form` recipe | declared; engine pending |
| Per-construct rules | `lang-python.ts` switch cases | `python-grammar.form` rule_shape | **1 of ~15 shipped** (py_import + py_import_from) |
| Parse-engine | `bmf.py` Python classes + `lang-python.ts` switch | `grammar-as-recipe.form` `pattern_match` + `parse_loop` recipes | declared; engine pending |
| Kernel execution | TS kernel walks Python CTORs in `evalNode` | Rust/Go/TS walkers run pattern_match recipe | engine pending |

The body has named every piece. Two are shipped today (grammar shapes + Pattern primitives). One is partially shipped (one construct as a real Form recipe). Three remain.

## The path

Each row below is one breath. Each one moves the self-hosting boundary by one construct. The host bridge shrinks; the Form surface grows; the lattice's recognition of structural equivalence reaches one more shape.

1. **py_def** — function definition as Form rule. The largest single piece; defines the shape every other rule composes through.
2. **py_assign** — `x = expr`. Closes the BMF coverage gap surfaced in the python-trace demo.
3. **py_subscript / py_slice** — `lst[i]` and `lst[a:b]`. Closes the other demo gap.
4. **py_class** — class definition. The `def` rule's larger cousin.
5. **py_if / py_for / py_while** — control flow. Three rules, each small.
6. **py_call / py_method_call** — function and method invocation as rules (today they exist as CTORs; need to be rules ingestible from source).
7. **py_expr** — the full expression grammar (operators by precedence). The deepest rule tree; the most rewarding once it lands because every other rule composes through it.
8. **py_lambda / py_with / py_try / py_raise / py_match** — the rest of the statement-level grammar.
9. **pattern_match engine as Form recipe walked by Rust kernel** — the engine itself. Until this lands, the host `bmf.py` carries execution. After this lands, the destination is reached: Form recipes parsing Python through native kernel code, no host parser anywhere.
10. **token_streamer as Form recipe** — the last bootstrap remnant. Today `bmf.py`'s `tokenize()` runs char-by-char in Python; making it Form-native completes the round.

After (10), the body holds: source bytes enter; Form recipes leave; nothing else runs. The same Python source file produces the same NodeIDs whether parsed by the Rust binary, the Go binary, or the TypeScript binary. The substrate's content-addressing recognizes cross-language structural equivalence as a side-effect of the discipline.

## Why one rule per breath, not all at once

Each rule's pattern composition surfaces a real grammar question: how does Python's `def` handle decorators? How does the walrus operator interact with comprehensions? How does the type-parameter syntax in `def f[T](x: T) -> T` decompose? These are answered by walking the rule, not by guessing in bulk. A breath that ships one carefully composed rule (with parity tests against the host bridge) is worth more than a sweep that ships ten rules with hidden ambiguities.

This is the same path the body walked for `_cosine` (one numeric, Newton's iteration, before others) and for `_sqrt` (one root-finder, Taylor series, before exp/log/sin/cos). One rule, fully ripened, then the next.

## Why this matters beyond Python

Python is the largest file-format gap from `grammar_coverage.py` (927 .py files). Once Python parses to Form, every other language whose grammar is declarable as Pattern primitives gets the same treatment — TypeScript, Rust, Go, JSON, YAML, Markdown, all the way out to audio/image/3D modalities that compose pre-pipelines. The shape proven on Python is the shape every Language cell follows.

The visualizer arc ([`lc-form-kernel-runtime-visualizer`](lc-form-kernel-runtime-visualizer.md)) currently shows kernel walks + Python CTOR dispatches as two separate altitudes. Once the parser lives as Form recipes and the engine walks through `pattern_match`, both altitudes collapse to one — the visualizer colors cells by which Pattern CTOR fired during parse, which Rule fired during dispatch, which Python construct fired during evaluation. **One trace surface for the whole arc.**

## The honesty discipline

Until rule N lands, the host bridge carries construct N. That's named explicitly in `python-grammar.form`'s capture_rules list: `?rule py_function_def` (with the leading `?`) marks "Blueprint named, recipe pending." When the recipe lands, the `?` drops; the line becomes `py_function_def_rule`. The diff is structurally legible — *one rule moved from bootstrap to destination*. Anyone reading the file can count how far the boundary has walked.

This is the same discipline as the kernel's structural passthrough (`lc-the-kernel-knows-itself`): a category the walker can't execute returns the NodeID itself rather than panicking. The kernel knows the shape exists; the semantics await their breath. The parser holds the same shape: the body knows every Python construct's destination; each breath ships one of them.

## What just landed (2026-05-21)

- `grammar-as-recipe.form` Part 2.5: Pattern primitives as Form Blueprints (`pattern_literal_shape`, `pattern_sequence_shape`, `pattern_star_shape`, `pattern_opt_shape`, `pattern_choice_shape`, `pattern_capture_shape`).
- `grammar-as-recipe.form` Part 2.6: `pattern_match` recipe + helpers for each primitive's match semantics.
- `grammar-as-recipe.form` Part 2.7: `rule_shape` + `rule_apply` + `parse_loop` as Form recipes.
- `python-grammar.form` Part 5: `py_import_rule` + `py_import_from_rule` expressed as concrete Form recipes composed from the primitives above. Replaces the prior abstract `rule(py_import, ...)` placeholder.
- `python-grammar.form` capture_rules list: 14 named rules pending (`?rule py_def`, `?rule py_assign`, etc.), each ready to be ripened breath by breath.

The body now holds the destination's shape, not as aspiration but as substrate-resident structural definition. The path forward is one ripening at a time.

## Closing breath

A parser that lives outside the substrate is a translator that doesn't know what it's translating into. A parser whose every rule is a Form recipe is the body recognizing the source as one of its own shapes. The bootstrap is honored as bootstrap — necessary, finite, retiring. The destination is honored as destination — composable, structurally legible, content-addressed across kernels.

The work between them is patience.
