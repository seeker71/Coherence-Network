# Fourth-arm tables — how the `fkwu` kernel is fed, inspected, and used

The fourth kernel `fkwu` (the emitted universal walker) does not read `.fk`
source. It reads a **pre-flattened integer node-table** — one per band — cached
under `form/form-stdlib/.cache/fourth/t-<stem>-<hash>.txt`. This guide is the
human map of those tables: what they are, how to look inside one, and how to
use them. The byte-exact authority stays the emitter source
([`form-flatten.fk`](form-flatten.fk), [`hati-os-kernel-emit.fk`](hati-os-kernel-emit.fk));
this is the orientation that lets you read those without reverse-engineering the
shell.

## fkwu is not only a walker — it is a native JIT, via Form → asm (no clang)

The tables feed two faces of the fourth kernel, and it is easy to remember only
the first:

1. **Proof-walker.** `build_fourth` emits `fkc-emit-universal` — a generic tree-
   walker that *interprets* the table. `validate.sh` uses this for four-way
   **agreement** (you want pure walking to verify Go/Rust/TS == fkwu).
2. **Self-JIT.** The same emitter family (`fkc-emit-jit2`, `fkc-walk-jit-text`)
   lowers each pure function to a native alternative, counts **heat per
   function**, and **flips dispatch to native** when heat crosses the line
   (`fk_njit` probe); on cool it **melts back** to walking, champion-challenger
   gated. Proven three-way in `crystallization-wire-band` / `melt-hot-swap-band`
   (→ 31) and on the live binary in `scripts/hati_os_kernel_audit.sh` §21/§27.

**The native target is Form → asm bytes, NOT C/clang.** This is the part most
worth not forgetting. The proven, four-way lane emits machine code directly,
every stage a Form recipe:

```
jit-lower (15, full-jit-lower 63)   recipe → lowered cell (one generic engine, per-tag shape is DATA)
  → form-lower (31)                 instruction selection
  → form-asm (31)                   arm64 instruction BYTES (little-endian on-disk image)
  → form-macho (31) / form-elf (31) the .o / executable bytes — "RUNNABLE native binary with ZERO clang"
  → recipe-dylib (787349)           direct, no-ld, dlopen-able dylib
  → codesign (632490)               Form-emitted Mach-O signature (no codesign tool)
  → dylib_call                      dlopen + call
```

clang is **dropped from the native path**, with proof: `form-asm`'s `fa-conviction`
gate is **byte-identity** — the encoder may drop clang only once it byte-verifies
its own output equals the assembler's. `form-macho` then drops clang (`ld` links
the `.o`); `recipe-dylib` drops `ld` too. clang survives ONLY as an **oracle**
(`lowering-conviction.fk`: a teacher for the open optimization question, never the
master) and as the bootstrap C-emit path. So the §27 "drives clang" crystallize
face is the *oracle/bootstrap* lane; the **proven native lane is Form emitting its
own arm64, object format, and signature** — a runtime that compiles its recipes to
native machine code with no external toolchain (the cognitive-sovereignty claim:
a runtime that rents its compiler is not sovereign). Coverage frontier: `fkc-nat-expr`
/ the jit-shape-table cover the pure-compute family (tags 1‑7, 12) today; impure
functions (ports/organs/strings) stay walked, honestly named — the mechanism is
generic, the op coverage is what grows.

## What a table is

A table is one Form band — its prelude modules **plus** the band expression —
flattened from the recipe tree into the program `fkwu` executes. It is the band
as *program-as-cells*:

- every `defn` becomes a **function-table row**, called by index. **Function 0
  is the band's verdict expression** (the value the band returns).
- the body lowers onto the walker's **arena op tags**: list ops `18..23`
  (`cons/list/head/tail/len/nth`), string ops `24..28`
  (`str_eq/str_len/str_concat/substring/...`), bitwise/figure ops `34..42`
  (`band/bor/bxor/shl_u32/shr_u32/rotr_u32/add_u32/bnot_u32/mul/...`). Children
  are referenced **by position** in the node array — content-addressed.
- multi-arg calls right-fold their arguments into a CONS chain (packed args),
  the callee binds params as `NTH(ARG, i)`; negative integers and `true/false`
  (→ `1/0`) lower as ordinary rows.

It is a **content-addressed, regenerable cache** — a `.o` file, not a source.
The `<hash>` is `shasum(band sources + the emitter chain)`: change any source and
the hash changes, so a stale table is never reused. The whole directory is safe
to delete; `validate.sh` rebuilds it (cold) on the next run.

## The table format

`fkc-table-file` (pool-free) serializes as space-separated integers:

```
<num-roots>  <root-index …>   <num-rows>  <node-row …>
```

- **roots** — one entry index per function; `root[0]` is the band's verdict.
- **rows** — each node is a **4-int record `[tag, child0, child1, child2]`**
  (`fk_node[N][4]` in the walker). Unused children are `0`.

`fks-table-file` (the `fks` emitter) appends a **string pool** after the rows:

```
… <num-rows> <node-row …>   <pool-count>  <per-string: len, byte …>
```

Every distinct string literal is interned once; a literal in the program is a
`SLIT` row carrying its **pool index**. That pool is the *only* difference
between the manifest's `fkc` (no pool) and `fks` (with pool) emitters — neither
names an arm count. (The walker's loader is a plain digit cursor that handles a
leading `-` for negatives and treats a missing pool as empty.)

## How to know what's in one

Read the **source it was flattened from**, never the integers:

```bash
# the stem names the band; its header names the full source chain
head -1 form/form-stdlib/tests/<stem>-band.fk      # ; preludes: core … <port>
grep '^<stem> ' form/fourth-arm-bands.txt           # emitter (fkc/fks) + expected verdict
```

- what it **means** → the `.fk` sources in that `; preludes:` chain.
- what the **tags** mean → [`form-flatten.fk`](form-flatten.fk) header (the full
  vocabulary) and [`hati-os-kernel-emit.fk`](hati-os-kernel-emit.fk) (the walker).
- what it **computes** → run it (below); `fkwu`'s value is the fourth-leg verdict.

## How to use them

You never hand-write a table. You author the `.fk` band; `validate.sh` flattens
it → table → runs `fkwu` on it as the **fourth leg**, requiring `fkwu`'s value to
byte-equal the Go/Rust/TS walkers'. That equality is the whole "four-way" gate.
A band crosses the fourth arm only when its stem is a row in
`fourth-arm-bands.txt`.

Programmatically (from `form/`):

```bash
source scripts/fourth-arm.sh
build_fourth                            # build the fkwu binary (cached by emitter content)
tbl="$(fourth_table <stem>)"            # build/return the cached table path
"$FKWU" "$tbl" 0                        # run it -> the verdict
```

To force a rebuild of one band's table: `rm form-stdlib/.cache/fourth/t-<stem>-*.txt`
then re-run `validate.sh` (or `fourth_table <stem>`).

### Two traps (learned the hard way)

- **Generation match.** The `fkwu` binary and the tables must come from the same
  emitter generation (matching `<hash>`/stamp). Run a table built by one
  generation on a binary from another and you get a diagnostic line (e.g.
  `melt …`) instead of a verdict. Let `validate.sh`/`fourth-arm.sh` build both —
  do not hand-roll the flatten+run, or a *harness* mismatch will masquerade as a
  kernel divergence.
- **Noexec scratch.** The `fkwu` binary lives in `.cache/fourth` because it must
  be executable; a sandboxed `/tmp` is often `noexec`, so a binary copied there
  fails with "permission denied". Read tables from anywhere; run the binary from
  `.cache/fourth`.

## Worked example

A genuinely four-way band makes the cleanest example: `graph-node-port`
(manifest row `graph-node-port fks 11111`) — its cached table runs on `fkwu` and
returns `11111`, byte-equal to Go/Rust/TypeScript.

`value-ledger-port` (the CC ledger as a storage-port layer, band
[`tests/value-ledger-port-band.fk`](tests/value-ledger-port-band.fk)) is the
honest in-progress example: **3-way proven** (go=rust=ts=`111111`) but **held out
of the manifest** because the local fresh-flatten path is currently broken — on a
clean single-generation rebuild even the `graph-node-port` *control* returns
`fkwu=0`, so the break is the toolchain (the cached tables ride an older working
generation), not the recipe. This is the standing "trust a working fourth arm
over a red local one" situation: the row is registered only once the fourth arm
can actually verify it. The failure shape itself — `fkwu=0` while the three
walkers agree — is the textbook *diagnose-don't-assume* trap: confirm against a
known-four-way control before calling it a recipe divergence.
