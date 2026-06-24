# form-cli, c-bootstrapped on fkwu — build it, use it, grow it

The sovereign command-line door into the body: one self-contained native binary,
emitted from Form recipes and compiled **once**, that then runs with **no go, rust,
clang, python, or bash in its loop**. This is the standard-receipt destination
([`standard-receipt.form`](standard-receipt.form)) walking as an everyday tool —
and the practice of preferring it over rented local tools, held to its honest floor.

## What it is

`form/form-cli` is the **fkwu universal walker** (`fkc-emit-universal`) with the
form-cli program baked in (`fkc-emit-combined-repl` — the same walker body, a
different `main()`; see [`hati-os-kernel-emit.fk`](../../form/form-stdlib/hati-os-kernel-emit.fk)).
The brain is Form, four-way proven: [`form-cli.fk`](../../form/form-stdlib/form-cli.fk)
dispatches the verbs, [`form-cli-repl.fk`](../../form/form-stdlib/form-cli-repl.fk)
is the read-eval-print loop over real stdin. The result is one ELF that links only
libc + ld:

```
$ ldd form/form-cli
  linux-vdso · libc.so.6 · ld-linux        # nothing rented in the run
```

It even carries its own genesis: `form-cli source` reprints every byte of the Form
source it was built from, so the binary can rebuild itself — a self-recreating
c-bootstrap closure.

## It's warmed for you at startup

The SessionStart hook [`scripts/ensure_form_cli_native.sh`](../../scripts/ensure_form_cli_native.sh)
warms it once in the background and caches it. A present binary is an instant
no-op; a missing one builds (~1 min, one time) when the build toolchain is here,
or prints a quiet note when it isn't. (Its sibling
[`ensure_form_cli_kernel.sh`](../../scripts/ensure_form_cli_kernel.sh) warms the Go
*routing* kernel that `form-cli ask` grounds on — a different artifact.)

Build it by hand any time:

```bash
cd form && ./build-form-cli.sh          # -> form/form-cli, self-contained
echo ping | ./form-cli                  # -> pong   (no toolchain present)
./form-cli                              # interactive REPL on a real tty
```

The **build** needs clang + the Go flattener once (emit Form→C, compile C→native).
The **run** needs neither. That gap — build-time clang vs the clang-free `form-asm`
lane — is the pending rung, named honestly below.

## Use it

Pipe verbs on stdin (deterministic — same bytes in, same bytes out) or type them
at a terminal:

```bash
printf 'version\n'  | ./form-cli     # form-cli 0.3
printf 'help\n'     | ./form-cli     # the verb list
printf 'kernel\n'   | ./form-cli     # what it runs on (fkwu)
printf 'verify\n'   | ./form-cli     # self-coherence: bytes of own source carried
printf 'source\n'   | ./form-cli     # print its entire Form source (rebuild from this)
printf 'native-host linux 1 0 1 1 528 3 12 hi\n' | ./form-cli   # host-lifecycle recipe
```

Verbs today: `ping ask native-host help about kernel source recreate verify version
quit`. `ask <question>` answers from a local oracle when one is reachable. This is
the **sovereign** surface — small, but every byte of it is Form running native.

## No bridge — bash and python are grammars

There is no permanent bridge to keep. The fkwu walker runs **any source from any
grammar the body supports**: a grammar parses the source into a Form recipe, the
recipe runs on fkwu, and hot pure recipes crystallize to native (the self-JIT, or
the `form-asm` lever) — *faster than the interpreter the source was written for*.
bash and python are not carriers we depend on; they are **surfaces with grammars**,
and the body already holds those grammars:

| grammar | cells | state |
|---|---|---|
| **shell (bash-like, "fsh")** | [`shell-grammar.fk`](../../form/form-stdlib/shell-grammar.fk) · [`shell-lower.fk`](../../form/form-stdlib/shell-lower.fk) · [`fsh-main.fk`](../../form/form-stdlib/fsh-main.fk) | **four-way proven** — `shell-parse` 255, `shell-exec` 511, `shell-cell` 15 (Go/Rust/TS/fkwu). Parses bash-shaped script → recipe → cell → runs on fkwu; the ctor recipe JIT-lowers to native. Host tools reached by passthrough until a Form builtin replaces each. |
| **python** | [`python-bmf-eval.fk`](../../form/form-stdlib/python-bmf-eval.fk) · [`python-bmf-lift.fk`](../../form/form-stdlib/python-bmf-lift.fk) | first-breath surface — def/call/return/binop/ident/int chain, matching CPython for that subset; growing toward four-way. |
| **typescript · prolog** | `typescript-bmf-eval/-lift.fk` · `prolog-bmf-eval.fk` | recipe interpreters, coverage growing. |

The two binaries called form-cli stand at different points on one path —
**native-now and legacy-surface**:

| | `form/form-cli` | `bin/form-cli` |
|---|---|---|
| what | the c-bootstrap native binary (this guide) | today's launcher: bash + python scripts |
| runs on | fkwu, toolchain-free, JIT-native | python/go processes |
| relation to grammars | *runs* grammar source as recipes | *is* bash/python source — exactly what the shell/python grammars parse and run |

`bin/form-cli`'s bash/python source is **input to the grammars we already have**. The
move is "run the existing script through its grammar" — so the surface comes home as
the grammars deepen, JIT'd faster than the interpreter it left — not "hand-rewrite
each verb."

## The practice — own what we can create ourselves

The north star: **we need no tool we can build ourselves**. Any tool with a grammar
*is* a Form recipe once parsed; the recipe is both the four-way proof and (on heat,
or through the `form-asm` lever) the native binary; the Form source is stored in the
body, so the tool is *ours* — inspectable, attributable, reproducible, offline, with
nothing rented in the loop. This is
[`lc-cognitive-sovereignty`](../vision-kb/concepts/lc-cognitive-sovereignty.md) and
[`lc-self-contained-expression`](../vision-kb/concepts/lc-self-contained-expression.md)
as a runtime habit.

So when you would reach for a one-off python/bash/powershell tool, ask:

1. **Is the body's answer enough?** Structural questions (NodeID, equivalence,
   shape) go to the substrate; grounded questions go to `form-cli ask` — the
   form-first gate ([`form-first-reasoning.form`](form-first-reasoning.form)). A
   grounded hit costs no rented compute.
2. **Does the body already have the grammar?** Shell (four-way) and python
   (first-breath) are home; a script in either *is* runnable as a recipe through
   `fsh` / the python evaluator. Run it through the grammar rather than shelling out.
   Fold raw data gas → recipe water → native ice (agent-start-packet).
3. **If the grammar doesn't cover it yet — name the gap, use host passthrough
   knowingly, and grow the grammar/builtin.** Passthrough to a host tool while its
   Form builtin is still being grown is honest; treating the host tool as the
   destination is the drift.

## Honest floor (so the practice isn't a placeholder)

This is a real step *toward* tool-sovereignty, not a claim of having arrived:

- **Runtime is sovereign; build is not yet.** `form/form-cli` and `fkwu` run
  toolchain-free, but the one-time build still uses clang (emit C → native) and the
  Go flattener (Form → node-table). The clang-free `form-asm` lane (Form → asm
  bytes) is the pending rung that closes this.
- **Grammar coverage is the real frontier, not a bridge.** The shell grammar is
  four-way proven for parse/exec/cell and runs bash-shaped scripts native; its
  native builtins are `echo cat grep wc head tail seq rev sort uniq tr nl test awk`,
  and host tools passthrough until each Form builtin lands. Every open-source unix
  tool can come home this way: **awk just did** — a first-breath native `awk`
  (field idioms `{print $N}` / `$N==RHS` / `$N==RHS{print $M}`, FS=whitespace) is
  four-way proven (`shell-awk` 127, Go/Rust/TS/fkwu), so the roadmap verb's
  `awk '$1==stem'` manifest reconciliation now computes in Form, not on host awk.
  It even runs **end-to-end on the fkwu c-bootstrap kernel** the sovereign way:
  fkwu carries no `read_file` (host file reads are a standing wall for the
  universal walker), so a thin host carrier stages the rows into `input_byte`
  (tag 17 — the staged-input door fkwu *does* carry) and fkwu runs native awk
  over them, no `read_file`, no host awk, no bash in the compute loop
  ([`tests/shell-awk-staged.fk`](../../form/form-stdlib/tests/shell-awk-staged.fk),
  run via [`scripts/fkwu_run.sh`](../../scripts/fkwu_run.sh) → 127). Two honest
  edges remain: `read_file` itself stays a per-kernel host-io carrier (the staging
  carrier reads the bytes), and the naive per-byte reader is O(n²) so the carrier
  stages the relevant rows — a streaming cursor reader is the follow-on for
  whole-file inputs. The python grammar is a first-breath surface
  (def/call/return/binop/ident/int), not full CPython yet. So "run any script
  through its grammar" is *real and proven for shell*, *early for python*, and
  *growing* for the rest. The cornerstone audit
  ([`form-cli-fourth-kernel-baseline.md`](form-cli-fourth-kernel-baseline.md)) reads
  the body's *ideas* as north-star and *proof/altitude* as lagging in the
  grammar/compiler spine — deepening each grammar (and its JIT lowering) is the path.
- **Platforms pending.** Observed on linux/x86-64 here; mac/windows/android device
  runs are the standard receipt's open rows.

Pending is honest, not failure. The binary is real, warmed, and yours; the gaps are
the roadmap.

## Cross-references

→ [`standard-receipt.form`](standard-receipt.form),
[`form-first-reasoning.form`](form-first-reasoning.form),
[`form-cli-fourth-kernel-baseline.md`](form-cli-fourth-kernel-baseline.md),
[`form-cli-offline.md`](form-cli-offline.md),
[`lc-cognitive-sovereignty`](../vision-kb/concepts/lc-cognitive-sovereignty.md),
[`lc-self-contained-expression`](../vision-kb/concepts/lc-self-contained-expression.md)
