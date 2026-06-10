# seedbank — bootstrap, not destination

> Everything in this directory is **bootstrap**. The body's destination is
> the kernel parsing each host language through its own Form-native BMF
> grammar (`form-stdlib/grammars/python-bmf.fk`, `typescript-bmf.fk`, etc.) —
> not through hand-written TypeScript parsers that know what Python or
> TypeScript look like. The teaching:
> [`lc-the-kernel-knows-itself`](../../../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md).
> The compost sequence:
> [`kernels/BOOTSTRAP_COMPOST_MANIFEST.md`](../../../kernels/BOOTSTRAP_COMPOST_MANIFEST.md).

## What lives here

| Adapter | What it parses | What replaces it Form-native |
|---|---|---|
| `python-adapter/` | Python examples, parity/perf scripts, and Form-native `kernel-bmf-*` wrappers | Mostly arrived: kernel walks `form-stdlib/grammars/python-bmf.fk` against source |
| `ts-adapter/` | TypeScript source → `.fk` recipes (TS parser + emitter) | Kernel walking `form-stdlib/grammars/typescript-bmf.fk` against source |

The remaining TS adapter ships:

- `src/lang-<lang>.ts` — hand-written parser knowing the host language's syntax
- `src/lang-<lang>-fk.ts` — hand-written emitter to `.fk`
- `src/main.ts` — CLI (`<lang>-compile`, `<lang>-run`, `<lang>-eval`, `<lang>-trace`)
- `scripts/parity_suite.sh` — three-way gate (node/tsc + ts-eval + form-kernel-rust)
- `examples/` — demos that exercise the parser+emitter end-to-end

The Python adapter's TS parser/emitter/CLI composted on 2026-06-07. Its parity
and perf scripts remain as gates around the Form-native path: `kernel-bmf-compile`
emits `.fk`, `form-kernel-rust` executes that recipe, and `kernel-bmf-run` walks
the `.py` source end to end.

These files **work**. The three-way parity gate is real. But every Python or TS feature you add (typeann, classes, dicts, inheritance, …) thickens the parser TypeScript by hand, exactly the calcification Form is meant to dissolve. The N×M trap: every (host language) × (source language) pair needs its own hand-maintained parser.

## What's already Form-native (the destination, partly arrived)

- **Grammars exist** as `.fk` files: `form/form-stdlib/grammars/python-bmf.fk` (3000 lines), `typescript-bmf.fk`, `rust-bmf.fk`, `go-bmf.fk`, etc.
- **First Form-native parse landed** ([#2071](https://github.com/seeker71/Coherence-Network/pull/2071)) — four Python arithmetic shapes parse through `python-bmf.fk` driven by the kernel; same recipe NodeID across Rust, TS, Go sibling kernels.
- **The remaining gap** is named in [`kernels/PYTHON_BMF_CONTRACT.md`](../../../kernels/PYTHON_BMF_CONTRACT.md) — five primitives (G1–G5) the kernel needs before `python-bmf.fk` can drive every Python feature this directory's adapter currently covers.
- **The Python parity gate is now Form-native only** (`python-adapter/scripts/parity_suite.sh`) — CPython reference, `kernel-bmf-compile` + Rust execution, and `kernel-bmf-run` all compare the same final value.

## When this directory composts

Per [`BOOTSTRAP_COMPOST_MANIFEST.md`](../../../kernels/BOOTSTRAP_COMPOST_MANIFEST.md) Phase A:

1. Each parity-suite demo proves three-way agreement through the Form-native path
2. The manifest row for each adapter moves `tissue → PROVEN → COMPOST READY → RELEASED`
3. When all rows are `RELEASED`, this directory is residue and gets removed
4. Future host-language support lives as a `.fk` grammar in `form/form-stdlib/grammars/`, not as a sibling adapter here

## When adding to the bootstrap — the discipline

Adding a feature to `lang-python.ts` or `lang-ts.ts`?

1. Add a row (or extend an existing row) in `kernels/PYTHON_BMF_CONTRACT.md` naming what the corresponding `.fk` grammar rule must express to replace your bootstrap addition
2. Run `python3 scripts/wellness_check.py` and confirm `sense_bootstrap_compost` reports the growth honestly
3. Name your PR with the same bootstrap-vs-Form-native framing the recent PRs carry — never claim a bootstrap addition is the destination

## In one sentence

This directory is the kernel **not knowing itself yet**; the kernel-roadmap is the path; the grammars in `form/form-stdlib/grammars/` are where the kernel will look when it learns to.
