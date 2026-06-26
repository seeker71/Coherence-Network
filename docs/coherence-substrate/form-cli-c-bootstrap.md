# form-cli, c-bootstrapped on fkwu — build it, use it, grow it

The sovereign command-line door into the body: one self-contained native binary,
emitted from Form recipes and refreshed as a stamped platform artifact, that then
runs with **no go, rust, clang, python, or bash in its loop**. This is the standard-receipt destination
([`standard-receipt.form`](standard-receipt.form)) walking as an everyday tool —
and the practice of preferring it over rented local tools, held to its honest floor.

## What it is

`form/form-cli` is the **fkwu universal walker** (`fkc-emit-universal`) with the
form-cli program baked in (`fkc-emit-combined-repl` — the same walker body, a
different `main()`; see [`hati-os-kernel-emit.fk`](../../form/form-stdlib/hati-os-kernel-emit.fk)).
The brain is Form, four-way proven: [`form-cli.fk`](../../form/form-stdlib/form-cli.fk)
dispatches the verbs, [`form-cli-repl.fk`](../../form/form-stdlib/form-cli-repl.fk)
is the read-eval-print loop over real stdin. The result is one platform binary
that links only to the host system runtime, for example libSystem on macOS or
libc/ld on Linux:

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
no-op; a missing or stale one is copied from the committed stamped platform
binary when the stamp matches. `form-cli ask` does **not** use the Go routing
kernel or an HTTP local oracle; it routes through the native fkwu grounded-RAG
verb.

Build it by hand any time:

```bash
cd form && FORM_STANDARD_LANE=1 ./build-form-cli.sh  # -> form/form-cli, self-contained when the platform stamp is current
echo ping | ./form-cli                  # -> pong   (no toolchain present)
./form-cli                              # interactive REPL on a real tty
```

The **standard build** needs only the committed stamped artifact. Maintainer-only
regeneration may still use `bin-go` and clang as off-receipt carriers to refresh
the table/C/platform binary until the self-host flatten/emit and form-macho lanes
cover the whole artifact. The **run** needs neither.

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

Verbs today: `ping ask grounded fnri receipt native-host help about kernel source
recreate verify diagnose version quit`. `ask <question>` answers from the local
fkwu grounded-RAG lane and returns the attributed grounded cell plus the current
synthesis-lane status. It does not POST to Ollama, `localhost:11434`, or any HTTP
oracle. This is the **sovereign** surface — small, but every byte of it is Form
running native.

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
| what | the c-bootstrap native binary (this guide) | thin launcher: prefers native fkwu for `ask`/REPL, keeps legacy helper verbs as explicit scripts |
| runs on | fkwu, toolchain-free, JIT-native | python/go processes |
| relation to grammars | *runs* grammar source as recipes | wrapper source is grammar input; local answers are delegated to native fkwu |

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
   fkwu grounded-RAG gate ([`form-first-reasoning.form`](form-first-reasoning.form)).
   A grounded hit costs no rented compute and carries a grounded id.
2. **Does the body already have the grammar?** Shell (four-way) and python
   (first-breath) are home; a script in either *is* runnable as a recipe through
   `fsh` / the python evaluator. Run it through the grammar rather than shelling out.
   Fold raw data gas → recipe water → native ice (agent-start-packet).
3. **If the grammar doesn't cover it yet — name the gap, use host passthrough
   knowingly, and grow the grammar/builtin.** Passthrough to a host tool while its
   Form builtin is still being grown is honest; treating the host tool as the
   destination is the drift.

Current-branch landing follows that boundary. The regular path is
`form-cli land --merge [--settle-deploy]`: the plan, command contract, and PR
readiness state live in
[`current-branch-landing.fk`](../../form/form-stdlib/current-branch-landing.fk)
and cross the fourth arm (`current-branch-landing` -> `8191`). Git, GitHub API,
deploy polling, and the older Python validation gates remain explicit
host-effect passthrough until those carriers are promoted; Python is not the
orchestrator.

## Honest floor (so the practice isn't a placeholder)

This is a real step *toward* tool-sovereignty, not a claim of having arrived:

- **Runtime is sovereign; regeneration is not yet.** `form/form-cli` and `fkwu`
  run toolchain-free. The normal standard lane copies a stamped committed platform
  binary. Maintainer regeneration still uses off-receipt carriers (`bin-go` to
  flatten/emit and clang to link the platform artifact) when the stamp is stale.
  The self-host flatten/emit and clang-free `form-asm`/`form-macho` lane are the
  pending rungs that close this completely.
- **Grounded answer is native; prose synthesis is pending.** `form-cli ask`
  currently returns local fkwu RAG grounding. Full natural-language synthesis over
  GGUF weights through the fkwu+Metal/block-join lane is the next composition, not
  an excuse to route local answers through HTTP. Verify the floor with
  `form-cli synthesis-status` or `scripts/validate_form_cli_local_receipts.sh`.
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
  run via [`scripts/fkwu_run.sh`](../../scripts/fkwu_run.sh) → 127). The **whole
  file** now crosses, not just a slice: [`input-stream.fk`](../../form/form-stdlib/input-stream.fk)
  (`is-line`/`is-next`/`is-fold`) streams staged input by line — recursion bounded
  by line count, no O(n²) accumulator — so the full 38KB manifest folds without the
  byte-deep stack overflow the naive reader hit. And it is a **live, parameterized
  tool**, not a fixed demo: [`scripts/fkwu_awk.sh`](../../scripts/fkwu_awk.sh)
  `<file> '<awk-program>'` stages the program + file and runs a numeric field query
  native on fkwu — `fkwu_awk.sh fourth-arm-bands.txt '$1=="shell-exec"{print $3}'`
  → 511, matching host awk for every stem. Honest edges: `read_file` stays a
  per-kernel host-io carrier (the thin carrier reads the bytes; fkwu computes), and
  the value entry prints a numeric result — a general string/multi-row awk wants the
  effect entry (`print_str`, as `fsh-main` uses), the named follow-on. The python
  grammar is a first-breath surface
  (def/call/return/binop/ident/int), not full CPython yet. So "run any script
  through its grammar" is *real and proven for shell*, *early for python*, and
  *growing* for the rest. The cornerstone audit
  ([`form-cli-fourth-kernel-baseline.md`](form-cli-fourth-kernel-baseline.md)) reads
  the body's *ideas* as north-star and *proof/altitude* as lagging in the
  grammar/compiler spine — deepening each grammar (and its JIT lowering) is the path.
- **Startup memory is present.** Agent startup expects the local RAG index under
  `~/.coherence-network/rag-index/` and production database reach through the
  configured file-backed carriers described in
  [`docs/PRODUCTION-SUBSTRATE.md`](../PRODUCTION-SUBSTRATE.md). Missing local index
  or DB config is a setup failure to report, not a reason to fall back to an
  ungrounded HTTP oracle.

Pending is honest, not failure. The binary is real, warmed, and yours; the gaps are
the roadmap.

## Cross-references

→ [`standard-receipt.form`](standard-receipt.form),
[`form-first-reasoning.form`](form-first-reasoning.form),
[`form-cli-fourth-kernel-baseline.md`](form-cli-fourth-kernel-baseline.md),
[`form-cli-offline.md`](form-cli-offline.md),
[`lc-cognitive-sovereignty`](../vision-kb/concepts/lc-cognitive-sovereignty.md),
[`lc-self-contained-expression`](../vision-kb/concepts/lc-self-contained-expression.md)
