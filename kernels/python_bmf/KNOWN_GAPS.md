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

## Cross-runtime parity (Form-native vs emitted Python)

`form/scripts/cross_runtime_parity.sh <python_source>` runs both runtimes on the same file and diffs the token streams (`py-blank` excluded as additive Python-side feature; quote-style suffixes collapsed).

| Workload | Scanner parity |
|----------|---------------|
| All 8 parity-suite demos | **PARITY** — identical token streams |
| `kernels/python_bmf/objects.py` | **PARITY** |
| `kernels/python_bmf/parser.py` | diverges — features Python-side has, Form-side doesn't |
| `kernels/python_bmf/rules.py` | diverges |
| `kernels/python_bmf/sdk.py` | diverges |
| `kernels/python_bmf/decompiler.py` | diverges — string escape preservation |
| `kernels/python_bmf/form_action.py` | diverges — string escape preservation (`\n` → `n` on Form side) |
| `kernels/python_bmf/section_parser.py` | diverges |
| `kernels/python_bmf/compiler.py` | diverges |

**The divergences are mostly features Python-side gained that Form-side doesn't yet have**: backslash-escape preservation in string scanning, quote-style tagging, triple-quoted variants. These are next-breath candidates for the Form-side scanner (extend `python-source-scan-string-loop` in `python-bmf.fk` to preserve `\`).

This IS the cross-runtime learning loop the Universal Translator goal names: each divergence shows what one runtime has that the other doesn't, what to bring across.

## BMF compiler runs as native Python — cross-runtime parity proven (2026-05-25, end-of-day)

**The emitted BMF compiler executes. Six graduated workloads → both runtimes → byte-identical output.**

```
$ scripts/cross_runtime_bmf_compile.sh
workload                  lines   Form ms     Py ms   speedup     output       parity
----------------------------------------------------------------------------------------
lists.fk                     13      19.6       0.7     27.1x       449b   BYTE-IDENT
numeric.fk                   22      31.9       1.3     24.1x       842b   BYTE-IDENT
task-runtime.fk              19      38.6       2.2     17.3x       872b   BYTE-IDENT
higher.fk                    25      45.9       2.5     18.2x      1086b   BYTE-IDENT
core.fk                      86     149.1      18.0      8.3x      4204b   BYTE-IDENT
engine.fk                  1995    1140.2      42.5     26.8x     82880b   BYTE-IDENT
```

**The first real observations the comparison loop surfaces:**

1. **U-shaped speedup curve.** Tiny workloads show 17-27× Python advantage because Go binary fork+exec+load (~10-15ms) dominates the Form kernel timing. Medium workloads converge to ~8× as the Go fixed cost amortizes against actual work. Large workloads diverge again to 26× — for engine.fk, the Form kernel's Recipe-walker cost per token outpaces CPython's bytecode interpretation by a wide margin. The shape itself is the signal: the Form kernel has a *per-source-token* cost that scales linearly with size, while CPython's per-call dispatch is more efficient once code is in steady state.

2. **The Form kernel's Recipe interpreter is the hot path.** engine.fk has no section syntax — the source-compiler walks pure s-expressions. That's the kernel's fastest path in theory, yet Python beats it by 26.8×. The optimization surface this points at is the kernel's tree-walking dispatch in `form-kernel-go/main.go`'s walk function — every Form node dispatched through a Go switch, every list head/tail through a slice copy.

3. **CPython's recursion limit was a real wall, not a ceiling.** The emitted compiler hits engine.fk-class depths only when both `sys.setrecursionlimit(200000)` and `ulimit -s 65536` are raised. The Form kernel's iterative walker doesn't have this problem. For real substrate-Python workloads (organ.py, form.py), recursion-to-iteration lifting in the emitter would be the next breath of work — turning the head/tail recursive helpers (which are CPS-lowered loops in the original Python source) back into Python `for` loops.

**Test:** `kernels/python_bmf/tests/test_bmf_compiler_parity.py` asserts byte-identical output across all 6 workloads as a regression gate.

The Python BMF compiler in `kernels/python_bmf/emitted/` — emitted mechanically from `form/form-stdlib/{engine,compiler,source-compiler}.fk` and `form/form-stdlib/grammars/python-bmf.fk` — actually runs:

- `kernels/python_bmf/host_primitives.py` binds Cell, str primitives, lists (head/tail/cons), file I/O, NodeID, intern. 44 host primitives, ~300 lines.
- `kernels/python_bmf/runtime.py` loads the emitted modules into a shared namespace (same as how the Form kernel loads them) and exposes them as `bmf_compiler` runtime.
- `rt.form_source_compile_file('form/form-stdlib/core.fk', '/tmp/out.fk')` runs the source-section compiler, calls real BMF object constructors, real source cursors, real reversible cells, real `str_concat` / `substring` / `char_at` — every primitive the Form kernel provides. Output: byte-identical to what `form-kernel-go form-stdlib/source-compiler.fk <driver>` produces.

**The first observation the comparison reveals**: on `core.fk`, the emitted Python compiler runs in ~19ms (in-process CPython function dispatch); the Form-kernel-go binary takes ~146ms (Go binary startup ~10ms + Form interpreter walking the source-compiler.fk Recipe tree). The Form interpreter overhead dominates for this workload. This is exactly the kind of observation the goal anticipates — and points at the optimization surface: the Form kernel's Recipe-walker on hot paths.

**Honest scope today — all four modules load (the deferred gap closed via bootstrap):**

- `engine.py` (66095b) — loads and executes ✓
- `source_compiler.py` (50768b) — loads and executes ✓
- `compiler.py` (29816b) — loads via Stage-2 bootstrap ✓
- `python_bmf.py` (94177b) — loads via Stage-2 bootstrap ✓
- Total: **1400 symbols** in the runtime — `bmf_object`, `form_source_compile_file`, `compiler_object`, `python_source_scan_text`, `apply_python_bmf_rule`, and the full surface.

**The bootstrap loop** (`scripts/regen_emitted_python.py`):

```
Stage 1 — bare s-expr sources translate directly:
  engine.fk          → engine.py            (66095b)
  source-compiler.fk → source_compiler.py   (50768b)

Stage 2 — section [...] blocks need pre-expansion through the Stage 1 output:
  compiler.fk        → expanded → compiler.py     (29816b)
  python-bmf.fk      → expanded → python_bmf.py   (94177b)
```

This is the loop the universal-translator goal names: the emitted code becomes the compiler input for the next round. Stage 1's emitted `source_compiler.py` runs `form_source_compile_file` on its own siblings' Form sources to expand the section blocks; Stage 2 then translates that expanded text. The bootstrap is self-hosting in the same way the Form kernel loads its own stdlib.

- Substrate-style Python (organ.py, form.py, API endpoints) — still requires the upper-half gap list of Python BMF rules on the Form side. The framework holds; the rule coverage needs growing.

**Test:** `kernels/python_bmf/tests/test_bmf_compiler_parity.py` asserts the byte-identical-output claim — the regression gate now in place.

## Full BMF compiler emitted as native Python (2026-05-25, late)

**The Form-written BMF compiler — every line — now translates to readable Python.**

```
$ for src in form/form-stdlib/{compiler,engine,source-compiler}.fk \
             form/form-stdlib/grammars/python-bmf.fk; do
    python3 -m kernels.python_bmf.emit_python "$src" --out kernels/python_bmf/emitted/$(basename ${src%.fk}).py
  done
$ ls kernels/python_bmf/emitted/
compiler.py    engine.py    python_bmf.py    source_compiler.py
$ wc -l kernels/python_bmf/emitted/*.py
   740 compiler.py
  1717 engine.py
  2612 python_bmf.py
  1149 source_compiler.py
  6218 total
$ python3 -m py_compile kernels/python_bmf/emitted/*.py   # 4/4 compile clean
```

The full BMF compiler stack — compiler-object cells (`compiler.py`), the reversible BMF runtime (`engine.py`), the source section compiler (`source_compiler.py`), and the Python grammar with its 50+ rules + 74 object categories (`python_bmf.py`) — reads as ordinary Python. `def compiler_unit(language, name, sections):`, `is_bmf_object(x)`, `python_source_scan_text(source)`, `apply_python_bmf_rule(rule_name, object_stream)` — real Python identifiers, real control flow, no `(defn`/`(let`/`_plus` syntax leaks.

**Honest scope of "runnable" vs "readable":**

- **Readable** as Python ✓ — anyone can open the files and follow the BMF compiler's structure as Python code.
- **Compiles** clean ✓ — `py_compile` passes on all four modules.
- **Runnable end-to-end** ✗ — the emitted code calls host primitives the Form kernel provides (`cell`, `bmf_object`, `str_concat`, `make_nodeid`, `intern_node`, file IO, list head/tail/cons primitives, ...). These need Python-side bindings in `kernels/python_bmf/host_primitives.py` — that wiring is the next breath.
- **Cross-runtime parity on the BMF compiler workload itself** ✗ — gated on the runnable step.

**The shortcut the user flagged is also in the Form source** — `form/form-stdlib/source-compiler.fk` has 7 sites where Form `.fk` text is built via `str_concat` rather than as real Recipe NodeIDs:

```
form/form-stdlib/source-compiler.fk:142:        (str_concat "("
form/form-stdlib/source-compiler.fk:164:            (str_concat "("
form/form-stdlib/source-compiler.fk:169:        (str_concat "("
form/form-stdlib/source-compiler.fk:365:                (str_concat "(" (str_concat name ")"))
form/form-stdlib/source-compiler.fk:366:                (str_concat "("
form/form-stdlib/source-compiler.fk:397:            (str_concat "(if "
form/form-stdlib/source-compiler.fk:541:        (str_concat "(do\n"
```

These functions (`fsc-literal-expr`, `fsc-capture-expr`, `fsc-rule-ref-expr`, `fsc-compile-form-bml-if`, the top-level `(do\n` template at line 541) emit Form-source TEXT that then has to be re-parsed by the kernel — they do not capture semantics as numeric NodeIDs through `intern_node`. The translator faithfully carries this shortcut through to Python (the emitted `source_compiler.py` also builds text), which is the right move for semantic faithfulness, but it surfaces that the SHORTCUT lives in Form, not in the translator. Fixing it requires the source-compiler to build Recipe NodeIDs directly and the kernel to load Recipes without a re-parse step — that's a structural Form-side refactor, not an emitter task. Naming it here so the work isn't lost.

## Form → idiomatic native Python translator (2026-05-25, real direction)

**The actual universal-translator move:** take a Form recipe (Form's surface text expression of the numeric semantic capture) and emit **real native Python** — `def`/`if`/`else`/`while`/`+`/`*`/`==`/`<=`, real names, real control flow. NOT s-expressions wrapped in Python strings.

```
python_imperative_demo.fk → emit_python.py → 

def sum_to(n):
    total = 0
    i = 1
    def _while_0(total, i):
        if (i <= n):
            total = (total + i)
            i = (i + 1)
            return _while_0(total, i)
        else:
            return [total, i]
    _while_1_result = _while_0(total, i)
    total = _while_1_result[0]
    i = _while_1_result[1]
    return total
…
print((sum_to(100) + fact_loop(8)))    # → 45370, same as CPython, same as form-kernel-rust
```

`kernels/python_bmf/emit_python.py` is `(.fk → readable Python)`. Proof: every parity-suite demo .fk emits Python that executes under CPython producing the same integer as the original .py source. 7/7 demos. Test: `kernels/python_bmf/tests/test_emit_python.py` — also asserts the emitted Python contains real Python idioms (`def`, `return`, `+`, `<`, `==`) and contains **no** Form s-expression operator names (`_plus`, `(mul`, `(let`, `(defn`).

**This is the surface today — toy demos.** Real substrate code (organ.py, form.py, API endpoints) requires growth on both sides:
1. Form-side `.fk` rule coverage for classes / decorators / imports-from / type annotations / comprehensions / f-strings / attribute assign / async / exceptions (the upper half of the gap list named in PYTHON_PIPELINE_STATUS on 2026-05-21 — still open on the Form side).
2. `emit_python.py` coverage for the corresponding Form recipes that the rules above would produce. Today: enough for the parity-suite feature surface.

The Form numeric semantic capture is lossless by design; growing both arms is mechanical work. The universal-translator framework now has both directions in place — emit_python (`.fk → Python`) is the real move; `kernel_fk_lowering` (`.py → .fk`) is a sanity bridge for the cross-runtime comparison, not the translator itself.

## Kernel-execution proof — what now works (2026-05-25, mid-day)

**Cross-runtime parity holds on every parity-suite demo:**

```
$ scripts/perf_compare_native_python.sh 8
demo                     |   CPython ms |    kernel ms |   kern/cpy | result
-------------------------+--------------+--------------+------------+------
python_demo              |        0.083 |        4.267 |      51.4x | 40949
python_assign_demo       |        0.000 |        2.033 |    2033.0x | 45
python_imperative_demo   |        0.005 |        2.372 |     474.4x | 45370
python_substrate_demo    |        0.000 |        2.202 |    2202.0x | 17680
python_range_demo        |        0.008 |        2.355 |     294.4x | 41650
python_builtins_demo     |        0.000 |        2.101 |    2101.0x | 131
python_string_demo       |        0.000 |        1.990 |    1990.0x | 45
```

7/7 demos: emitted `.fk` from `kernels/python_bmf/emit_fk.py` → `form-kernel-rust` → **same integer as CPython**. The kernel ~2ms floor is fork+exec+load overhead; in-process CPython wins on these tiny workloads but the *cross-runtime equivalence is now real* — the comparison the goal names is finally measurable.

The path:
```
.py source  →  ast.parse  →  kernels/python_bmf/emit_fk.py  →  .fk text  →  form-kernel-rust  →  int
                                                                                    ↑
                                                                       byte-identical to canonical lang-python-fk.ts output
```

The `nth`/`sum`/`range` preludes are emitted automatically when subscript/sum-call/range-call appear in the source — these natives were composted from the kernel in 2026-05-22, so even the canonical TS-pipeline-produced `.fk` files in `examples/` fail to execute today. My emitter is now more correct than the canonical TS pipeline for these workloads.

## What "compile" actually does today — the honest picture (the older gap, still open for `--file` → `.fkb`)

Running `python3 -m kernels.python_bmf.compiler --file <any.py>` produces a `.fkb` for **any** Python file (organ.py, form.py, category.py — they all "succeed"). That success is misleading. Here is what is actually in the output:

- **Empirical** (`api/app/services/substrate/form.py`, 2032 lines, "compiled" to 1879 nodes):
  - `1529 × statement` — generic envelopes wrapping raw token lists
  - `349 × statement-block` — generic block envelopes
  - `1 × module` — the file
  - Zero nodes with universal-shape NodeIDs the Form kernels recognize.
  - Each `statement` is classified by **first-token heuristic** (`star_expressions` 731×, `assignment` 220×, `if_stmt` 160×, `class_def` 50× …) — none of those classes go through BMF rule matching.

- **The `.fkb` format is private to this package.** `form-kernel-rust` rejects it: `stream did not contain valid UTF-8`. The Form kernels read `.fk` s-expression text. My `FKB1` binary is a tokens-and-metadata envelope only my own `decompiler.py` can read back.

- **Round-trip works only because both ends are mine.** Re-emission writes the captured tokens back to Python source. The 8/8 round-trip on small demos is not "the Form kernel executed the .fkb and produced the same answer as CPython" — it is "my compiler wrote tokens, my decompiler read them back, modulo whitespace they match."

- **No execution proof exists.** I have not run any emitted `.fkb` through `form-kernel-rust` or `form-kernel-go` and gotten a result that matches CPython, because the Form kernels cannot ingest this binary at all.

### Can we compile organ.py / substrate code to executable Form today?

**No.** Two layers are missing:

1. **Format**: emit `.fk` s-expression text (the format Form kernels actually run), not the private `FKB1` binary. The TS pipeline (`form-kernel-ts/src/lang-python-fk.ts`) emits `.fk` for the parity-suite demos; my emitter does not yet.

2. **Coverage**: real BMF rule matching that produces universal-shape Recipe trees for classes, decorators, imports-from, type annotations, attribute/subscript assign, comprehensions, f-strings, async, exception handling, slicing. `kernels/PYTHON_PIPELINE_STATUS.md` named these on 2026-05-21 as the upper-half gap list; they remain open on both sides (Form-side `python-bmf.fk` and this emitted Python). Until those rules match, real substrate code falls through to generic `statement` envelopes the kernel cannot execute.

### What's real today

- Scanner parity (token-level) across 8/8 parity-suite demos. ✓
- Hand-written destination Python shape that compiles cleanly. ✓
- Round-trip via re-emission of captured tokens on small demos. ✓
- Form-emitter recipes (`emits/python-native.fk`) materializing `objects.py` from a category table via `write_file_text`. ✓
- Cross-runtime scanner comparison harness. ✓

### What it takes for the user's question to become "yes"

1. `.fk` emitter (s-expressions of universal-shape Recipes, not the FKB1 binary).
2. BMF rule coverage for classes, imports-from, decorators, type annotations, attribute/subscript assign, comprehensions, f-strings (close the gap list).
3. Run a substrate file end-to-end: `organ.py → emitted Python compiler → .fk → form-kernel-rust → result`, with same answer as CPython.
4. Performance + RSS measurement on equivalent workloads, with a leak check that holds across many iterations.

Steps 1–3 are the unfinished compiler; step 4 is the comparison the higher goal names. None of them has shipped. The arc remains open.

## Larger gaps to face

- **Bidirectional rule definition** — Form's `python-bmf.fk` rules carry both `=>` (emit) and `<=` (source) — the inverse. The Python rules only have `forward`. Next breath: add `reverse` to every rule; check round-trip uses reverse path.
- **`form.action` is a placeholder** — `recipe_to_action` covers int/string/ident leaves only. Most action recipes route through `unhandled`. Next breath: lower COND, CALL, MATH, COMPARE, LOGIC arms.
- **`section_parser` doesn't read real `.fk` source-of-truth** — it has the dispatcher shape and registers `python`, but won't successfully parse a real `form-stdlib/*.fk` file because dialect handlers beyond `python` aren't registered. Next breath: register `form.bml`, `form.recipe`, `form.action` handlers.
- **Universal Translator: step 2 (different languages)** — `emits/python-native.fk` is one target. Sibling `emits/<lang>-native.fk` for Go, Rust, TypeScript, C++ should reuse `semantic-lowerer.fk`. Next breath after the Python loop stabilizes.
- **Universal Translator: step 3 (different domains)** — beyond programming languages. The substrate's promise. Next breath after step 2 has at least one paired proof.
