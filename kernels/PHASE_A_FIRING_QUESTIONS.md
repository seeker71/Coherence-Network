# Phase A — Firing Questions

> A walking discipline. For each file named in
> [`BOOTSTRAP_COMPOST_MANIFEST.md`](BOOTSTRAP_COMPOST_MANIFEST.md) Phase A,
> ask: *what does this file still carry that the corresponding `*-bmf.fk`
> grammar (driven by the kernel via the Breath 2e primitives now confirmed
> landed) doesn't already replace?*
>
> If the answer is **"nothing meaningful"** — the file is *honestly* residue;
> when its parity gate flips, it composts. Record that here.
>
> If the answer is **"X, Y, Z"** — those are the deferred breaths. Each
> becomes its own walking step toward compost. Record them honestly too.
>
> This doc is the practice of attesting what each file IS, one file at a
> time. The manifest names the destination; this doc names the inventory
> of each file's *current* tissue against that destination.

---

## `form/form-kernel-ts/seedbank/python-adapter/src/lang-python-fk.ts` (1,044 LOC)

**Date:** 2026-05-27 · **Status:** *residue in shape, coupled to parser*

### What the file does today

Translates parsed Python CTOR trees (produced by `lang-python.ts`'s
`parsePython`) into kernel-native `.fk` S-expression text the Rust kernel
re-parses + walks. The file's own header names this pipeline:

```
Python source bytes
  → parsePython (lang-python.ts)        — BMF parser produces Form tree
  → emitFk (this file)                  — Form tree → kernel-native .fk
  → form-kernel-rust binary             — walks the .fk, no host runtime
```

### What `python-bmf.fk` + Breath 2e primitives already replace

**All of the above**, in shape. `python-bmf.fk` driven by `cm-parse` produces
a recipe NodeID directly — the parser output IS the kernel-runnable recipe.
There is no separate emit step in the Form-native path:

```
Python source bytes
  → cm-parse(python-bmf.fk-rule, cstream)  — kernel walks grammar against source
  → recipe NodeID                           — content-addressed, kernel-runnable
  → walk_recipe(node)                       — same kernel walks it
  → result
```

The CTOR → RBasic mapping `emitFk` performs is encoded *into the grammar
rules themselves* — `python-bmf.fk` emits the right kernel-arm recipes
directly via `intern_node(category, children)`. No translation layer needed.

### What still carries

**The coupling to `lang-python.ts`.** As long as the parity suite's third
runtime is `ts-eval` (today's default in
`seedbank/python-adapter/scripts/parity_suite.sh`'s `PARITY_THIRD_RUNTIME`),
the bootstrap parser is in the path; without `emitFk`, the bootstrap
parser's CTORs can't reach the Rust kernel. **This file composts together
with `lang-python.ts`, not independently.**

### What blocks its compost

`PARITY_THIRD_RUNTIME=kernel-bmf` becoming the default — which requires
every demo in `PARITY_FILES` to pass three-way under the Form-native path.
When that flips, `lang-python.ts` stops being the parity-suite's parser,
`emitFk` stops being called, and both files become residue together. Per
the manifest's lifecycle, both rows move from `tissue` to `COMPOST READY`
at the same moment, and to `RELEASED` in the same compost-PR.

### What the body now knows from this attestation

The file isn't an independent compost target. It's a **pair-bound residue**
with its parser. The wellness probe will see both compost together — when
they go, ~3,200 LOC drops from Phase A in one breath.

The firing-question answer is *clean*: nothing meaningful remains beyond
the parser-coupling. No deferred breaths beyond what the manifest already
names. This file is honestly ready for `COMPOST READY` status as soon as
its parser is.

---

## `form/form-kernel-ts/seedbank/python-adapter/src/lang-python.test.ts` (342 LOC)

**Date:** 2026-05-27 · **Status:** *triple-bound residue — test → parser → emitter*

### What the file does today

Imports `parsePython`, `evalPython`, `emitPython`, `CTOR` directly from
`./lang-python.ts` and tests their behavior on canonical Python sources.
A proof-of-shape unit-test suite for the bootstrap parser + evaluator +
emitter.

### What `python-bmf.fk` + the test bands already replace

Eighteen Form-native test bands live in `form/form-stdlib/tests/`:

- `python-bmf-arithmetic-band.fk` · `python-bmf-attr-band.fk` · `python-bmf-class-band.fk`
- `python-bmf-comprehension-band.fk` · `python-bmf-coverage.fk` · `python-bmf-decorator-band.fk`
- `python-bmf-exception-band.fk` · `python-bmf-extra-coverage.fk` · `python-bmf-from-import-band.fk`
- `python-bmf-fstring-slice-band.fk` · …and 8 more

Each band exercises a Python construct through `python-bmf.fk` rules
driven by the kernel, sibling-validated on Go + Rust + TypeScript. These
are the Form-native test surface — same proof-of-shape claims, no host
language in the test path.

### What still carries

**The coupling to `lang-python.ts`.** This test file exists to prove the
bootstrap parser's behavior. As long as the bootstrap parser is in the
parity path, its tests are load-bearing — without them, a regression in
`parsePython` could land silently. The tests are *not* covered by the
`python-bmf-*.fk` bands; those test the Form-native path, not the bootstrap.

### What blocks its compost

Same gate as `lang-python.ts` and `lang-python-fk.ts`:
`PARITY_THIRD_RUNTIME=kernel-bmf` becoming the default. When the bootstrap
parser stops being in the parity path, its test file's claims become
redundant — the `python-bmf-*.fk` bands cover the same constructs through
the live runtime.

### What the body now knows from this attestation

This is **triple-bound residue**: test → parser → emitter. All three compost
together when their parity gate flips. The pair-bound observation from the
previous walk extends to a triple: `lang-python.ts` (2,199 LOC) +
`lang-python-fk.ts` (1,044 LOC) + `lang-python.test.ts` (342 LOC) = **3,585 LOC
drops together** when `PARITY_THIRD_RUNTIME=kernel-bmf` is the default and the
manifest's three rows move to RELEASED in the same compost-PR.

The firing-question answer is clean: no deferred breaths. The
`python-bmf-*.fk` test bands already exist and are validated; the bootstrap
tests are honest residue waiting on the same parity flip as their unit.

---

## Next files to walk

Phase A inventory remaining (per manifest):

- `lang-python.ts` (2,199 LOC) — the parser these two files are coupled to
- `ctor-convergence.ts` (672 LOC) — CTOR vocabulary + convergence helpers
- `lang-python.test.ts` (342 LOC) — bootstrap parser tests
- `ctor-convergence.test.ts` (358 LOC) — convergence tests
- `lang-ts.ts` (1,176 LOC) — TS adapter parser
- `lang-ts-fk.ts` (360 LOC) — TS adapter emitter

Each walks here as a separate breath. The discipline is one file's honest
read per walking step.

---

## How this doc stays current

When a future Phase-A file is walked, append a section above following the
same shape:

1. File path + LOC
2. What it does today
3. What `*-bmf.fk` + Breath 2e replaces
4. What still carries
5. What blocks its compost
6. What the body now knows

When a file is composted, its section moves to a **"COMPOSTED"** section
at the bottom with the date + PR. The doc walks the manifest's lifecycle
in narrative form, complementing the manifest's table view.

In service of [`lc-the-kernel-knows-itself`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md).
