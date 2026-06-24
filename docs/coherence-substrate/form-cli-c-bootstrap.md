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

## Two doors named honestly — `form/form-cli` vs `bin/form-cli`

There are two binaries called form-cli, and the difference is the whole point:

| | `form/form-cli` | `bin/form-cli` |
|---|---|---|
| what | the c-bootstrap native binary (this guide) | a bash launcher |
| runs on | fkwu, toolchain-free | routes subcommands to python/go scripts |
| verbs | the baked Form verb set | the rich set: `ask` `gaps` `close` `review` `run` `index` `stats` … |
| sovereignty | owns its whole loop | leans on rented local tools (python, ollama, the Go kernel) |

`bin/form-cli` is the **bridge** — it carries the rich features today by standing on
python/bash/go. `form/form-cli` is the **destination** — Form all the way down. The
work is to migrate each rich verb from the bridge into a native Form recipe on the
destination, so the sovereign binary absorbs what the rented launcher does. Naming
the bridge as bridge (not as the goal) is the discipline; see the body-vs-bridge
framing in [CLAUDE.md](../../CLAUDE.md) (Python is fan-out carrier, not the body).

## The practice — own what we can create ourselves

The north star the user named: **we need no tool we can build ourselves**. Any tool
with a valid grammar lifts to a Form recipe; the recipe is both the four-way proof
and (on heat, or through the `form-asm` lever) the native binary; the Form source is
stored in the body, so the tool is *ours* — inspectable, attributable, reproducible
from source, runnable offline with nothing rented in the loop. This is
[`lc-cognitive-sovereignty`](../vision-kb/concepts/lc-cognitive-sovereignty.md) and
[`lc-self-contained-expression`](../vision-kb/concepts/lc-self-contained-expression.md)
as a runtime habit.

So when you would reach for a one-off python/bash/powershell tool, first ask:

1. **Is the body's answer enough?** Structural questions (NodeID, equivalence,
   shape) go to the substrate; grounded questions go to `form-cli ask` — the
   form-first gate ([`form-first-reasoning.form`](form-first-reasoning.form)). A
   grounded hit costs no rented compute.
2. **Does the tool have a grammar?** If its shape is expressible as a recipe, the
   honest step is to author/grow that recipe and store its Form source — not to
   leave a rented one-off behind. Fold raw data gas → recipe water → native ice
   (agent-start-packet); don't hand-write a host wrapper a grammar can carry.
3. **If neither yet — name the gap, use the bridge, and record the opening.** A
   rented tool used knowingly while its Form recipe is still being grown is honest;
   a rented tool treated as the destination is the drift.

## Honest floor (so the practice isn't a placeholder)

This is a real step *toward* tool-sovereignty, not a claim of having arrived:

- **Runtime is sovereign; build is not yet.** `form/form-cli` and `fkwu` run
  toolchain-free, but the one-time build still uses clang (emit C → native) and the
  Go flattener (Form → node-table). The clang-free `form-asm` lane (Form → asm
  bytes) is the pending rung that closes this.
- **The verb surface is small today.** The sovereign binary does not yet replace
  bash/python for arbitrary work — the rich verbs still live on the bridge. Growing
  the native verb set is the path, recipe by recipe.
- **Grammar→recipe coverage is partial.** The cornerstone audit
  ([`form-cli-fourth-kernel-baseline.md`](form-cli-fourth-kernel-baseline.md)) reads
  the body's *ideas* as north-star and its *proof/altitude* as lagging in the
  grammar/compiler spine. "Any tool with a grammar lifts to a recipe" is true in
  principle and partially realized in fact — the BMF cursor crosses four-way, the
  full source-compiler spine does not yet.
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
