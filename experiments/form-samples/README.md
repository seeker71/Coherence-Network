# form-samples

Real `.fk` source files in Form's S-expression bootstrap syntax. The Go, Rust, and TypeScript kernels ([`../form-kernel-go/`](../form-kernel-go/), [`../form-kernel-rust/`](../form-kernel-rust/), and [`../form-kernel-ts/`](../form-kernel-ts/)) read these files end-to-end and produce identical results.

| Sample | What it exercises | Expected output |
|---|---|---|
| [`fact.fk`](fact.fk) | Recursive factorial — `defn`, `if/else`, recursion | `3628800` |
| [`fib.fk`](fib.fk) | Naive Fibonacci — double-recursion, the tree-walker's worst case | `6765` |
| [`closure.fk`](closure.fk) | Closure captures defining frame, called later with different arg | `15` |
| [`list-sum.fk`](list-sum.fk) | Native `list`/`head`/`tail`/`len` + recursion over a list | `15` |
| [`string-walk.fk`](string-walk.fk) | Char-by-char string scan (`char_at`, `ord`) — shape Form-on-top's lexer will use | `5` |
| [`native-kernel-dogfood.fk`](native-kernel-dogfood.fk) | Form-level contract that grammar/parser proof uses Go, Rust, or TypeScript kernels, not Python bridges | `1` |

```bash
# Run any sample through a sibling kernel
./form-kernel-go      form-samples/fact.fk   # → 3628800
./form-kernel-rust    form-samples/fact.fk   # → 3628800
npx --yes tsx form-kernel-ts/src/main.ts form-samples/fact.fk
```

## S-expression verb vocabulary (bootstrap)

The kernels read S-expression syntax that maps directly onto substrate recipes:

| Verb | Recipe category | Notes |
|---|---|---|
| `(do <stmt>...)` | BLOCK.DO | last value |
| `(seq <stmt>...)` | BLOCK.SEQUENCE | last value |
| `(let <name> <expr>)` | BLOCK.LET | binding |
| `(if <c> <t>)` / `(if <c> <t> <e>)` | COND.IF_THEN / IF_THEN_ELSE | |
| `(add/sub/mul/div/mod <a> <b>)` | MATH.* | |
| `(eq/ne/lt/le/gt/ge <a> <b>)` | COMPARE.* | |
| `(and/or <a> <b>)` / `(not <a>)` | LOGIC.* | |
| `(defn <name> (params...) <body>)` | FNDEF | |
| `(<name> <args>...)` | FNCALL | shorthand for both user fns and natives |

Natives (called via `(<name> ...)` when no user binding shadows): `print`, `list`, `cons`, `head`, `tail`, `len`, `nth`, `empty`, `str_len`, `substring`, `char_at`, `str_concat`, `str_eq`, `int_to_str`, `str_to_int`, `ord`, `read_file`.

The Form-surface-syntax parser written in Form (next turn) will sugar these into the `1 + 2` / `if x then a else b` / `defn f(x) = ...` syntax the Python kernel currently accepts. The recipes produced are identical either way.
