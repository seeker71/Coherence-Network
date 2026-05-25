# Known Gaps — surfaced through round-trip testing

These are the missing parts the user predicted ("you will find missing parts in the emitter. you will find issues in the SDK you are building"). Each is signal, not failure — they map what to build next.

Updated each time `python3 -m unittest kernels.python_bmf.tests.test_roundtrip` surfaces something new.

## Round-trip status

Parity-suite demos in `form/form-kernel-ts/seedbank/python-adapter/examples/python_*.py`:

| Demo | Round-trip | Notes |
|------|-----------|-------|
| `python_assign_demo.py` | byte-equivalent | function + assignment + list + subscript |
| `python_builtins_demo.py` | byte-equivalent | aug-assign, builtins (len/sum/etc.) |
| `python_demo.py` | byte-equivalent | recursion, conditional expressions, ackermann |
| `python_imperative_demo.py` | byte-equivalent | while-loop, accumulator |
| `python_lambda_demo.py` | byte-equivalent | trailing + leading comments preserved |
| `python_range_demo.py` | byte-equivalent | `range()` |
| `python_string_demo.py` | byte-equivalent | strings + comments preserved |
| `python_substrate_demo.py` | byte-equivalent | for loop, multi-return def |

**8/8 byte-equivalent** (whitespace-normalized — runs of spaces collapsed). Single-language Universal Translator Step 1 holds on these demos.

## Self-round-trip (the real "full compiler" exercise)

The emitted compiler compiles its own .py files and decompiles back to Python. Semantic equivalence (whitespace + blank-line + bracket-style normalized) is the bar; byte-identical is the deeper destination.

| Module | Self-roundtrip (semantic) | Lines (decompiled) |
|--------|--------------------------|--------------------|
| `sdk.py` | ok | 267 |
| `objects.py` | ok | 181 |
| `parser.py` | ok | 423 |
| `rules.py` | ok | 186 |
| `section_parser.py` | ok | 102 |
| `form_action.py` | ok | 185 |
| `compiler.py` | ok | 181 |
| `decompiler.py` | ok | 266 |

**8/8 emitted modules round-trip semantically through themselves.** The native Python compiler can compile and decompile every file in its own package.

## Categorized gaps

### Scanner-side losses

- ~~trailing `#` comments are stripped~~ — **fixed**: `_skip_trivia` accepts a `comment_sink`.
- ~~string escape sequences (`\n`, `\t`, `\\`) stripped~~ — **fixed**: scanner preserves `\` + the escaped char verbatim in the body.
- ~~string quote-style not preserved~~ — **fixed**: scanner tags strings with `-sq`/`-dq` and triple variants; decompiler restores original quote.
- ~~triple-quoted strings collapse to single-quoted~~ — **fixed**: scanner emits `py-string-triple-sq|dq`; decompiler renders with `"""` / `'''`.
- ~~multi-line bracket-continuation~~ — **fixed**: layout pass tracks `()`/`[]`/`{}` depth; newlines inside brackets don't emit NEWLINE/INDENT/DEDENT.
- ~~blank lines not preserved~~ — **fixed**: scanner emits `py-blank` atoms tracking blank-line gaps.
- **horizontal whitespace runs still collapse** — multiple spaces between tokens collapse to one (acceptable for semantic round-trip; tests normalize spaces).

### Decompiler-side weaknesses

- ~~operator-adjacency naive~~ — **fixed**: `is_op(i, ...)` helpers distinguish py-op vs string-content; kwarg `=` inside parens, unary `-`/`+`/`*`/`**`, decorator `@`, dotted attribute access all bind correctly.
- **multi-line bracketed expressions collapse to one line** — `nodes.append(\n  {\n    ...\n  }\n)` becomes `nodes.append({...})`. Semantically equivalent; lost layout style. Next breath: emit a `py-layout-fmt` atom recording original multi-line shape.
- **slice colon spacing** — `data[pos : pos + n]` and `data[pos:pos + n]` are both Python; my decompiler picks one. Tests normalize colon spacing.
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
