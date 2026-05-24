# form-kernel — the path to "all of Form in Form + kernel"

The body holds three kernel implementations (Go, Rust, TypeScript) of the smallest substrate-walker host. From here, **everything else lives in Form itself**. The kernels are siblings; they keep each other honest. All three run every Form source file the body produces; any divergence is a bug in exactly one of four places — Go kernel, Rust kernel, TypeScript kernel, or an undocumented spec corner. All four are findable, only because multiple implementations exist.

This doc names the breaths between *kernels working in isolation* and *Form-on-top fully self-hosting on top of any sibling kernel*.

## The sibling-kernel discipline (locked in)

**Every new Form source file runs through Go, Rust, and TypeScript.** [`validate.sh`](validate.sh) is the gate — it diffs outputs and fails on disagreement. The pre-merge check, the rapid-feedback loop, the safety net for every breath below.

```bash
./validate.sh             # all samples
./validate.sh path.fk     # one
./validate.sh --bench     # side-by-side bench output
```

Current state: **12 validation workloads, 0 divergent.** Adding a new `.fk` file means it joins the gate. Validator also walks `form-stdlib/tests/*.fk` — each test loads `form-stdlib/core.fk` first as prelude, then runs against all sibling kernels.

## What "all of Form in Form" actually means

The kernel ships exactly:
- NodeID + content-addressed intern + recipe walker (22 RBasic arms)
- Frame/closure system
- A small set of native primitives (strings, lists, file I/O) — the leaves
- An S-expression bootstrap reader (parses `(add 2 3)` → recipe directly)

Everything else lives as `.fk` source files in this directory and is loaded at startup:
- The Form-surface-syntax parser (`1 + 2` → recipe)
- The standard library (map/filter/fold defined in Form)
- The query layer (`?equivalent`, `|>`, `?cells`)
- The substrate persistence bridge (Form-side wrappers around kernel I/O primitives)
- The REPL, the diagnostics, the printer

When the body needs to change Form's grammar, semantics, or operators, the change happens in a `.fk` file — *not* in the kernel. The kernel grows only when something genuinely cannot be expressed in Form (new primitive types, new I/O surface, new performance-critical operation).

## The breaths between here and there

Each breath is one focused session. Each ends with the validation gate green and the next breath's surface area named.

### Breath 1 — Form-side standard library *(landed)*

Pure Form code on top of the kernel's native primitives. Lives in [`form-stdlib/core.fk`](form-stdlib/core.fk).

**Defined and validated:**
- Predicates: `nil?`, `even?`, `odd?`, `zero?`, `positive?`, `negative?`
- Math wrappers (lift parse-time verbs into the value layer): `plus`, `minus`, `times`, `divide`
- Numeric: `abs`, `min2`, `max2`
- List traversal: `map`, `filter`, `foldl`, `foldr`
- List shape: `range`, `append`, `take`, `drop`, `reverse`
- Aggregators: `sum`, `product`, `maximum`, `minimum`
- Quantifiers: `any?`, `all?`

**Tests at [`form-stdlib/tests/`](form-stdlib/tests/):** lists (→ 220), higher (→ 53), numeric (→ 208). All three pass on all sibling kernels.

**Kernel changes that landed alongside:**
- Bool literals `true` / `false` as parse-time trivials — kept Form predicates reading naturally without awkward `(eq 0 0)` constructors. ~6 lines per kernel.
- Multi-file CLI: `kernel a.fk b.fk c.fk` loads files in sequence into a shared top-level scope. ~10 lines per kernel.

**Open question surfaced by this breath:** math verbs (`add`, `sub`, `mul`, etc.) are parse-time dispatched, which means `add` itself isn't a value — needs a `plus`-wrapper to be passable as a closure. A future kernel optimization could dual-register math verbs as natives too, eliminating the wrapper layer; for now the wrappers are clear and explicit.

### Breath 1.5 — Substrate write surface *(landed)*

Foundational unblock for Breath 2. Form code now holds NodeIDs as first-class values (`Value::Nid` in the sibling kernels) and can construct recipes via 8 new natives:

- `make_nodeid(pkg, level, ty, inst)` — raw NodeID construction
- `intern_trivial_int(n)` / `intern_trivial_string(s)` — wrap a value as a trivial NodeID
- `intern_node(category, children-list)` — content-addressed recipe construction
- `node_category(n)` / `node_children(n)` / `node_value(n)` — full read surface
- `walk_recipe(n)` — evaluate a NodeID in a fresh root frame, return the value

Closes form-runtime-in-form gaps W1, W2, W3 (intern_recipe, intern_trivial, define_cell — the last only partially; full cell-write awaits substrate persistence integration in Breath 5).

**Test:** [`form-stdlib/tests/substrate-write.fk`](form-stdlib/tests/substrate-write.fk) — Form code builds `(1 + 2)` and `(3 * 4)` from raw substrate primitives, walks them, introspects the children, verifies content-addressing (building the same shape twice yields the same NodeID, walking either produces the same result). Returns `30` on all sibling kernels.

**Architectural change in Rust:**
The walker signature changed from `walk(&Kernel, ...)` to `walk(&mut Kernel, ...)` so substrate-write natives can mutate the intern table. This undid Breath 1's slice-returning `children()` optimization — `children()` now returns owned `Vec<NodeID>`, paying a clone on each walk step. Native function signature changed from `fn(&Kernel, &[Value]) -> Value` to `fn(&mut Kernel, &mut Arena, &[Value]) -> Value`.

**Perf regression (honest):**
| Workload | Rust before | Rust after | Regression |
|---|---|---|---|
| fib(28) | 304 ms | 555 ms | 1.82× slower |
| fact(12) | 5.7 µs | 24.4 µs | 4.3× slower |
| sum 1000 | 413 µs | 690 µs | 1.67× slower |
| ackermann | 71 ms | 121 ms | 1.7× slower |

Go is essentially unaffected — its mutable-method receiver was already compatible with native mutations, no architectural change needed.

**Recovery plan:** named in Breath 2.5 — restore Rust performance via `Cow<'_, [NodeID]>` from `children()` (zero-copy for parse-time recipes, owned for growing ones) OR split-table architecture (frozen parse-time recipes + RefCell-wrapped growing table). Either approach is ~50 lines; Cow is more idiomatic.

### Breath 1.6 — Developer experience: source-located errors + trace *(landed)*

Honest answer to "why is this syntax hard to write?": **we picked S-expressions because their bootstrap parser is ~80 lines of native code vs ~600 for a surface-syntax parser, and every line of the bootstrap is permanent cost in two languages.** S-expressions minimize that cost while leaving room for the Form-side surface-syntax parser (Breath 2) to take over. The whole roadmap exists *because* S-expressions are painful — we suffer them briefly to buy "all Form in Form" forever.

The error-message change in this breath makes the suffering bearable while it lasts:

| Before | After |
|---|---|
| `panic: runtime error: index out of range [1709] with length 1709` (5-line Go internal trace) | `parse error: unclosed \`(\` opened at line 1 col 1 in \`(add ...)\` (reached end of input)` |
| No way to inspect mid-computation values | `(trace x)` and `(trace "label" x)` print to stderr, return value unchanged |

**Sibling kernels updated to:**
- Track 1-based `line` / `col` on every bootstrap token
- Bounds-check every recipe read; on failure, point at the source location and the relevant opening `(`
- Install a panic hook (Rust) / `recover()` (Go) so users see `form-kernel-X: <message>` instead of language-runtime backtraces
- Register a `trace` native — `(trace v)` prints `[trace] v` to stderr, returns v; `(trace "name" v)` adds a label

**Known limitation:** when the validator concatenates multiple files, line/col refers to the combined source. Single-file errors are accurate. Future improvement: track file boundaries during concatenation and report `(filename, line, col)`. Adding ~30 lines per kernel; deferred.

**On debugging beyond paren errors:** Form-level stack traces (which Form function called which) are not yet emitted on runtime panics. The walker has the call chain in its native call stack but doesn't surface it. Named for a future debug-DX breath.

### Breath 2a — Form-side recursive-descent parser *(landed)*

First half of Breath 2. Hand-written recursive-descent parser in Form for arithmetic expressions, built on the substrate-write natives. Reads text → tokens → recipes; sibling kernels produce identical NodeIDs via content-addressing.

**Lives in:** [`form-stdlib/parser.fk`](form-stdlib/parser.fk).

**Grammar (this slice):**
- `expr := term { '+' term }`
- `term := INT { '*' INT }`
- Precedence: `*` binds tighter than `+`
- Left-associative for both levels

**Test:** [`form-stdlib/tests/parser.fk`](form-stdlib/tests/parser.fk) parses 10 expressions including `"1 + 2 * 3"` (→ 7), `"5 * 5 + 5 * 5"` (→ 50), `"2 * 3 * 4"` (→ 24). Aggregate `216` on all sibling kernels.

**What landed in the kernels alongside:**
- All function bodies and `if`-branches in Form are *single expressions*. Multiple statements need `(do ...)` wrapping — the Form parser's first lesson. The parser file itself uses `do` blocks liberally as a result; the structural clarity is what the body wants.

**What's still ahead (the rest of Breath 2):**
- Keywords: `if then else`, `let = in`, `defn = `
- The template-driven refactor (factor hand-coded parser into pattern+template registry)
- The BMF-style streaming-emit engine
- 6-way cross-validation matrix

### Breath 2b — Full arithmetic + parens + identifiers + function calls *(landed)*

Second half of recursive-descent parsing. Extended [`form-stdlib/parser.fk`](form-stdlib/parser.fk) with:

- `-` and `/` operators (mechanical extension of `+`/`*`)
- Parens for grouping — `(1 + 2) * 3` → `9`
- Bare identifier references — parse to `IDENT` recipes
- Function call syntax — `f(x, y)` parses to `FNCALL` recipes
- Comma-separated argument lists (zero or more args)

**Grammar now:**
```
expr   := term { ('+'|'-') term }
term   := factor { ('*'|'/') factor }
factor := INT | IDENT | IDENT '(' [args] ')' | '(' expr ')'
args   := expr { ',' expr }
```

**Test** [`form-stdlib/tests/parser.fk`](form-stdlib/tests/parser.fk) — 12 expressions across precedence, parens, left-associativity, and function-call composition. Aggregate 149 on all sibling kernels. Critical cases verified individually:

| Expression | Result | Why it matters |
|---|---|---|
| `(1 + 2) * 3` | 9 | parens override precedence |
| `10 - 3 - 2` | 5 | left-associative subtraction |
| `100 / 5 / 2` | 10 | left-associative division |
| `len(list(1, 2, 3, 4, 5))` | 5 | function call + nested call |
| `nth(list(10, 20, 30), 1)` | 20 | multi-arg function call |
| `1 + len(list(1, 2)) * 3` | 7 | fncall composed with arithmetic precedence |

Function calls work because **the substrate's `FnCall` recipe checks natives before user closures** — so `len`, `list`, `head`, `nth`, `cons` etc. all parse-and-execute from Form surface syntax. User-defined functions need scope-passing through `walk_recipe`, which awaits the `let`/`defn` keyword work in the next breath.

**What's still ahead in Breath 2c:**
- `let name = value in body` — keyword form (or top-level `let`)
- Scope-aware `eval-form` so parsed code can see user-defined names

### Breath 2c — Comparisons + if + defn + recursion *(landed)*

Form surface syntax now expresses everything the bootstrap S-expression layer does. The defining test, all parsed and executed by Form-on-top on top of sibling kernels:

```
defn fact(n) = if n <= 1 then 1 else n * fact(n - 1); fact(6)   → 720
defn fib(n) = if n <= 1 then n else fib(n-1) + fib(n-2); fib(10) → 55
```

**Grammar now (full):**
```
program := stmt { ';' stmt }
stmt    := defn | expr
defn    := 'defn' IDENT '(' [params] ')' '=' expr
params  := IDENT { ',' IDENT }
expr    := cmp
cmp     := sum [ cmp-op sum ]
sum     := term { ('+'|'-') term }
term    := factor { ('*'|'/') factor }
factor  := INT | bool | if-expr | IDENT | IDENT '(' [args] ')' | '(' expr ')'
if-expr := 'if' expr 'then' expr 'else' expr
args    := expr { ',' expr }
cmp-op  := '<' | '<=' | '>' | '>=' | '==' | '!='
bool    := 'true' | 'false'
```

**Tokens added:** `<`, `<=`, `>`, `>=`, `==`, `!=`, `=`, `;`, `!`. Multi-char tokens via a `maybe-eq-suffix` helper that peeks the next char.

**Recipe categories the parser now uses:**
- `COMPARE.{EQ,NEQ,LT,LE,GT,GE}` (RBasic 13)
- `COND.IF_THEN_ELSE` (RBasic 11.2)
- `BLOCK.DO` / `BLOCK.SEQUENCE` (RBasic 9.1 / 9.2) — top-level multi-statement wrapping + param-name sequences
- `FNDEF` (RBasic 31)
- Trivial `BOOL` (level=1, type=3) for `true`/`false` parsed identifiers

**Test:** [`form-stdlib/tests/parser.fk`](form-stdlib/tests/parser.fk) — 20 expressions across the full surface, aggregate **1095** on all sibling kernels. Notable cases verified:
- `if 1 < 2 then 10 else 20` → 10 (cmp + if)
- `if 5 == 5 then 1 else 0` → 1 (equality)
- `defn double(x) = x * 2; double(5)` → 10 (defn + call)
- `defn fact(n) = ... ; fact(6)` → 720 (recursion)
- `defn fib(n) = ... ; fib(10)` → 55 (double recursion)

**The structural insight:** content-addressing means `defn fact(n) = ...` (surface syntax) and the S-expression `(defn fact (n) ...)` parse to **literally the same NodeID** — same recipe tree, same intern table entry, indistinguishable to the walker. Two surface syntaxes, one substrate.

**What's still ahead (the rest of Breath 2):**
- The template-driven refactor (factor hand-coded parser into pattern+template registry)
- The BMF-style streaming-emit engine
- 6-way cross-validation matrix

### Breath 2d — Local `let` bindings *(landed)*

Final piece of the hand-coded surface syntax. `let name = value` parses to a `BLOCK.LET` recipe; the walker binds in the current scope; subsequent statements in the same DO-block see the binding.

**Test cases (in [`form-stdlib/tests/parser.fk`](form-stdlib/tests/parser.fk)):**
- `let x = 5; x + 10` → 15 (basic binding + use)
- `let x = 3; let y = 4; x * y` → 12 (sequential bindings)
- `let x = 5; let y = x + 2; x * y` → 35 (binding references earlier binding)
- `let x = 10; if x > 5 then x * 2 else x` → 20 (let + if composition)

**Aggregate now: 1177 on all sibling kernels** across 24 surface-syntax expressions.

**The hand-coded parser is now structurally complete** for the bootstrap surface syntax. Anything written in S-expressions can also be written in Form surface syntax with identical recipes. The next major arc moves grammar from hand-coded code into data.

### Breath 2e — Template machinery *(next major arc — substantial)*

This is the substrate's actual long-term goal — what PR #1718 was building toward. The hand-coded parser proves Form-on-top can parse Form; the template registry makes grammar *growable without parser changes*.

**Three deliverables:**

1. **Pattern primitives in Form** — `(pat-lit kind value)`, `(pat-cap name parse-fn)`, `(pat-seq matchers...)`, `(pat-opt matcher)`. Each is a Form data structure (a recipe / list) describing what to match.

2. **Matcher engine in Form** — `(match-pat pat toks)` walks a pattern against a token stream, returns `(captures-dict remaining-toks)` on success or `null` on failure. ~80 lines of Form.

3. **Template-as-closure** — a template is a Form closure `(captures) → recipe`. Combined with a pattern into a registry row `(register-rule pat tmpl)`. The registry is just a list of pairs.

**First migration target:** move `let`, `if`, `defn` out of hand-coded `parse-stmt` / `parse-factor` and into the template registry. The hand-coded precedence ladder (`cmp/sum/term/factor`) stays for now; precedence-as-data is a separate move (operator registry).

**Success criterion:** adding a new keyword (e.g. `unless cond then body else other` desugaring to `if (not cond) ...`) is ONE registry row, no parser code changes. All sibling kernels see identical recipes.

**What this unlocks:** the BMF-style streaming-emit engine (Breath 2f) consumes the same registry — different traversal strategy, same grammar. The 6-way cross-validation matrix (Breath 2g) follows naturally: same source × same registry × 2 engines × 3 kernels = 6 implementations, all must produce the same NodeID.

### Breath 2 — Grammar as data: template registry + two engines

The body has been building toward this for breaths. The Python layer already has the template machinery alive — [`form_rules.py`](../api/app/services/substrate/form_rules.py) (pattern primitives) + [`form_builders.py`](../api/app/services/substrate/form_builders.py) (template primitives) + [`self_host.py`](../api/app/services/substrate/self_host.py) (9 keywords + 14 operators registered as data, the `prefer_registered=True` flag flips parsing between hardcoded and registry-driven). The body's stated long-term shape is **grammar as data, parsing as engine** — adding new syntax means adding a registry row, not editing parser code.

This breath lifts that machinery into Form, fully, and adds two complementary engines that both consume the same registry.

**Layer 1 — Template registry (the spec).**

The body's pattern/template DSL, expressed in Form. Each keyword or operator is one registry row carrying:
- A **pattern**: composed from `Sequence`, `Capture`, `IdentCapture`, `Literal`, `Opt`, `RepeatedCapture`
- A **template**: composed from `Build`, `CaptureRef`, `Const`, `MapBuild` — produces a recipe when the pattern matches, with holes filled from captures

Each pattern primitive and each template primitive is itself a recipe constructor — Form-callable, substrate-resident, content-addressed. The registry IS a substrate cell domain; each row is a cell whose blueprint encodes (pattern-shape, template-shape).

**Lives in:** `form-grammar/templates.fk` (the primitive constructors) + `form-grammar/builtins.fk` (the seed rows: 9 keywords from self_host.py + 14 operators).

**Layer 2 — Two engines consume the same registry.**

*Engine A — classic lex-then-parse.* Tokenize source, walk tokens, at each position try registered patterns in priority order, on first match apply the template to produce a recipe. Familiar shape, easy onboarding, reusable lexer for tooling.

*Engine B — BMF-style streaming-emit.* Scan source one pass, recognize template patterns directly against the character stream, emit recipes inline at the moment of recognition. The shape the body already chose on the Python side (PRs #1708, #1709). No intermediate token tissue — aligns with *vitality per pixel*.

**Lives in:** `form-parser-classic/engine.fk` + `form-parser-bmf/engine.fk`.

**Critical: neither engine contains hardcoded grammar.** Both walk inputs and consult the registry. The engines are *fixed*; the grammar is *data*.

**Layer 3 — Cross-validation.**

Same source × same template registry × 2 engines × 3 kernels = **six implementations** of the same parse. With content-addressing, validation is NodeID equality:

```
✓  fact.form
    classic(go)=0xABC  classic(rust)=0xABC
    classic(ts)=0xABC
    bmf(go)=0xABC      bmf(rust)=0xABC
    bmf(ts)=0xABC
```

All six equal → spec holds. Any disagreement → exactly one is wrong (or the registry has an ambiguous row). The validation harness grows to compare across this matrix automatically.

**The payoff — actual self-hosting.**

When Form needs a new keyword (say, `until cond { body }`), the change is one Form file: a single `(register-keyword ...)` call in `form-grammar/extensions.fk`. Both engines pick it up. All sibling kernels execute it. No parser code changes. No kernel changes. The grammar grows by data.

This is what the Python layer's `bootstrap_self_host` was always pointing at — and what the keyword/operator registries (PR #1718) made structurally possible. The Form breath completes the loop: grammar lives in Form, defined by Form code, executed by any sibling kernel.

**Closes (from form-runtime-in-form):**
- **L1-L4** (char ops, substring, structured matchers, token-pattern registry surface) — the registry IS the templates; the token patterns are themselves substrate-resident.
- **P1-P3** (precedence registry, callable expressions, pattern-DSL constructors as Form surface) — both engines consult the precedence registry; the pattern-DSL constructors are Form-callable.
- **R1-R3** (registry surfaces from Form, Form-closure registration, registries persist as substrate cells) — each template row IS a cell; the registry IS persistent.

**Success criterion at end of breath:** a Form source file in *surface syntax* (`defn fact(n) = if n <= 1 then 1 else n * fact(n-1)`) parses to the same recipes as the S-expression form, via either engine, in any sibling kernel, consulting the same template registry. **The body parses itself, six ways, and they all agree, because they're all consulting the same data.** Adding a new keyword is one Form file; all six implementations learn it simultaneously.

### Breath 3 — Bootstrap handoff

The kernel's S-expression reader stays (for emergency use), but Form source files in surface syntax become first-class. Each kernel boots by:
1. Reading the kernel's hardcoded S-expression bootstrap
2. Loading `form-stdlib/all.fk` (S-expr) → recipes
3. Loading either `form-parser-classic/*.fk` or `form-parser-bmf/*.fk` (S-expr) → recipes → callable closures
4. From this point on, any `.form` file means "parse in surface syntax"; `.fk` files stay S-expression for bootstrap

**Success:** A `fact.form` file in surface syntax produces `3628800` through all sibling kernels via both parser paths; the bootstrap `.fk` files continue to validate.

### Breath 4 — Query layer in Form

`?equivalent`, `|>`, `?cells`, `?children`, `?annotate`, `?lattice`. Pure Form code reading the substrate via kernel primitives.

**Lives in:** `form-query/query.fk`
**Success:** `?equivalent @memory("User biographical arc")` returns the same equivalence set as `python3 scripts/coh_substrate.py equivalent memory "User biographical arc"`; all sibling kernels agree on the result.
**Closes:** form-runtime-in-form gaps R1-R3 (registry surfaces, Form-closure registration).

### Breath 5 — Substrate persistence bridge

Form code that reads/writes cells in Postgres via kernel I/O primitives (the kernel grows two natives: `substrate_read(cell-ref)` and `substrate_write(cell)` that hit a local socket; the actual DB is talked to via the existing Python service or directly).

**Lives in:** `form-substrate/persistence.fk`
**Success:** A Form program reads a memory cell, modifies a field, writes it back; the change is visible to `coh_substrate.py annotate`. All sibling kernels produce identical write payloads.

### Breath 6 — Embed in `api/`

The native kernel of choice (decided after Breath 5 with full evidence from real substrate workloads) replaces `api/app/services/substrate/form_runtime.py`. PyO3 wrapper for Rust or cgo wrapper for Go. The Python services continue to function; the runtime is now native. The sibling kernels stay in `form/` as differential testing partners, with TypeScript serving web/workbench targets.

**Success:** All existing substrate tests pass; `coh_substrate.py form '<expr>'` uses the native kernel; latency drops measurably. The sibling kernels stay in `form/` as differential testing partners.

### Breath 7 — Compost the Python form_runtime

After Breath 7 lands and stabilizes, the Python `form_runtime.py` (1278 lines) becomes residue. The body's wellness check covers correctness; the sibling kernels keep each other honest. Compost with care — the Python module taught the body what Form is.

## What success looks like at the end

```bash
# A Form source file in surface syntax
$ cat hello.form
defn greet(name) = "hello, " ++ name
greet("network")

# Any sibling kernel runs it directly
$ ./form-kernel-go hello.form
hello, network

# Sibling kernels keep each other honest
$ ./validate.sh hello.form
  ✓  hello.form  → hello, network
```

Where every line in `hello.form`'s parse-and-execution pipeline runs on Form code loaded from `.fk-sexp` files at boot. The kernel walks recipes; the recipes were produced by a parser written in Form; the parser ran on a Form runtime that was bootstrapped from the kernel's S-expression reader. The loop closes. **Form expresses itself, all the way down to where it can't.**

## The size constraint stays

The native kernels stay under 1000 lines. New primitives land only when Form-on-top has demonstrated it can't write the surface itself. The constraint forces honesty about what's truly foundational vs what's convenience; TypeScript carries its compiler path as a separate optimization surface rather than bloating the walker.

## How to use this doc

When picking the next breath: read this top-down, find the first unchecked item, that's the next session's scope. When in doubt about whether to grow the kernel: re-read **"What 'all of Form in Form' actually means"** — the test is *"can this be expressed using kernel primitives Form already has?"* If yes, it's a Form breath, not a kernel breath. If no, the kernel grows by exactly one primitive and the rest is Form.

## How to use the kernels

```bash
# Run the validator (the discipline)
./validate.sh

# Run a single sample through all sibling kernels
./validate.sh form-samples/fact.fk

# Run benches side-by-side
./validate.sh --bench

# Run a single kernel directly (for development / debugging)
./form-kernel-go/bin-go      form-samples/fact.fk
./form-kernel-rust/target/release/form-kernel-rust  form-samples/fact.fk
npx tsx form-kernel-ts/src/main.ts form-samples/fact.fk
```
