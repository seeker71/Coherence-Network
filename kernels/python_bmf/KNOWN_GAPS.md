# Known Gaps — surfaced through round-trip testing

These are the missing parts the user predicted ("you will find missing parts in the emitter. you will find issues in the SDK you are building"). Each is signal, not failure — they map what to build next.

Updated each time `python3 -m unittest kernels.python_bmf.tests.test_roundtrip` surfaces something new.

## Round-trip status

Parity-suite demos in `form/form-kernel-ts/seedbank/python-adapter/examples/python_*.py`:

| Demo | Round-trip (semantic) | Notes |
|------|----------------------|-------|
| `python_assign_demo.py` | ok | function + assignment + list + subscript |
| `python_builtins_demo.py` | ok | aug-assign, builtins (len/sum/etc.) |
| `python_demo.py` | ok | recursion, conditional expressions, ackermann |
| `python_imperative_demo.py` | ok | while-loop, accumulator |
| `python_lambda_demo.py` | ok semantic / trailing-comments lost | trailing `#` comments stripped |
| `python_range_demo.py` | ok | `range()` |
| `python_string_demo.py` | ok semantic / trailing-comments lost | trailing `#` comments stripped |
| `python_substrate_demo.py` | ok | for loop, multi-return def |

**Semantic round-trip: 8/8.** Byte-identical round-trip blocked on the gaps below.

## Categorized gaps

### Scanner-side losses

- **trailing `#` comments are stripped** — `_skip_trivia` in `parser.py` discards `#...\n`. Next breath: emit a `py-comment` atom alongside the `\n`, preserve as layout-adjacent metadata. Affects: `python_lambda_demo`, `python_string_demo`.
- **horizontal whitespace runs collapse** — multiple spaces between tokens collapse to one in decompiler. Original alignment (e.g. `xs = [1, 2, 3, 4, 5]` vs `xs=[1,2,3,4,5]`) lost. Next breath: preserve span-derived spacing in decompiler.
- **string quote-style not preserved** — single-quoted and double-quoted strings both serialize as `"..."`. Next breath: tag `py-string` with quote variant.

### Decompiler-side weaknesses

- **operator-adjacency rules naive** — `_render_tokens` uses simple `isidentifier` checks; misses cases like `not x` (looks like `notx`). Next breath: longest-prefix Python operator table + grammar-aware spacing.
- **block headers detected by position, not category** — `_walk` assumes the first child of a `statement-block` is the head, the rest are body. Correct for `def`/`while`/`for` but wrong for try/except/else/finally chains. Next breath: tag the relationship explicitly.

### Compiler-side weaknesses (BMF rule coverage)

- **rule registry covers ~12 patterns; python-bmf.fk lists ~50.** Statements that don't match a rule fall back to the generic `"statement"` interning shape — works for round-trip but doesn't carry semantic shape. Next breath: extend `python_bmf_rules` list to mirror more of python-bmf.fk's rule book.
- **no inverse actions yet** — `Rule.reverse` is always `None`. Forward emits a Recipe; the inverse should regenerate the source tokens. Next breath: define reverse for the common rules so the decompiler can use the rule's own reverse instead of recovering from stored tokens.
- **multi-line statements collapse to one statement** — the parser groups by NEWLINE; continuation via `\` or unclosed brackets isn't handled. Next breath: extend layout pass to recognize bracket-depth continuation.

### SDK-side

- **`intern` keys serialize all values to JSON** — large nested structures rebuild the hash from scratch each time. Performance concern, not correctness. Next breath: structural hash that walks once.
- **`write_fkb` doesn't preserve a header for the lens** — the lens lives in a sibling `.fkl` file. Combine to single artifact? Trade-off pending.
- **`Lens.load` returns empty silently on missing file** — useful for tolerance, harmful for debugging. Add a `Lens.must_load` variant.

### Interning collapse on identical structural content

- **fixed in compiler.py via `statement-occurrence`** — wraps each rule emit with a span-bearing parent so two occurrences of `return n` at different lines stay distinct. The fix is one indirection layer; a cleaner shape would have `intern` accept an explicit occurrence/span axis. Next breath: SDK addition.

## Larger gaps to face

- **Bidirectional rule definition** — Form's `python-bmf.fk` rules carry both `=>` (emit) and `<=` (source) — the inverse. The Python rules only have `forward`. Next breath: add `reverse` to every rule; check round-trip uses reverse path.
- **`form.action` is a placeholder** — `recipe_to_action` covers int/string/ident leaves only. Most action recipes route through `unhandled`. Next breath: lower COND, CALL, MATH, COMPARE, LOGIC arms.
- **`section_parser` doesn't read real `.fk` source-of-truth** — it has the dispatcher shape and registers `python`, but won't successfully parse a real `form-stdlib/*.fk` file because dialect handlers beyond `python` aren't registered. Next breath: register `form.bml`, `form.recipe`, `form.action` handlers.
- **Universal Translator: step 2 (different languages)** — `emits/python-native.fk` is one target. Sibling `emits/<lang>-native.fk` for Go, Rust, TypeScript, C++ should reuse `semantic-lowerer.fk`. Next breath after the Python loop stabilizes.
- **Universal Translator: step 3 (different domains)** — beyond programming languages. The substrate's promise. Next breath after step 2 has at least one paired proof.
