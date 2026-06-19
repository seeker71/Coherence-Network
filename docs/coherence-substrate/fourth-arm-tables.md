# Fourth-arm tables — how the `fkwu` kernel is fed, inspected, and used

The fourth kernel `fkwu` (the emitted universal walker) does not read `.fk`
source. It reads a **pre-flattened integer node-table** — one per band — cached
under `form/form-stdlib/.cache/fourth/t-<stem>-<hash>.txt`. This guide is the
human map of those tables: what they are, how to look inside one, and how to
use them. The byte-exact authority stays the emitter source
([`form-flatten.fk`](form-flatten.fk), [`hati-os-kernel-emit.fk`](hati-os-kernel-emit.fk));
this is the orientation that lets you read those without reverse-engineering the
shell.

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

`value-ledger-port` (the CC ledger as a storage-port layer) is the canonical
small example: band [`tests/value-ledger-port-band.fk`](tests/value-ledger-port-band.fk)
over recipe [`value-ledger-port.fk`](value-ledger-port.fk), manifest row
`value-ledger-port fks 111111`. Its table is `fks` (it interns the
`value-cc/entry/…` keys into the pool), 166 functions deep once the
storage-port + cell-log-store + file-carrier preludes flatten in, and `fkwu`
walking it returns `111111` — the same value Go, Rust, and TypeScript compute.
