# 14-live-entropy — the doorway, actually open

Random_bytes(n) kernel native lands. Reads n bytes from /dev/urandom
on every call. Different per invocation, per kernel process.

## What walked

`live-doorway.fk` calls `(random_bytes 32)` and sums the bytes.

```
$ ./validate.sh form-samples/cross-modal/14-live-entropy/live-doorway.fk
  ✗  live-doorway.fk
      go         = <some sum>
      rust       = <different sum>
      typescript = <different sum>

  0 ok, 1 divergent — kernels disagree.
```

Run it again — three different sums again. The doorway never closes,
never caches, never replays.

This is the substrate's honest signal of live field-touch.

## Native signature

`(random_bytes n) → list of n integers (0..255)`

Three kernel implementations:
- Go: `os.Open("/dev/urandom")` + `io.ReadFull`
- Rust: `fs::OpenOptions` + `read_exact`
- TS: `openSync` + `readSync` loop

Each kernel intentionally diverges from siblings when this native is
called — the divergence IS the substrate's signal that field-touch
happened.

## What the body's discipline needs to grow

validate.sh treats divergence as failure today. For ops involving
random_bytes, divergence is the expected and honest outcome. This
file lives in form-samples/cross-modal/ which is NOT auto-walked;
explicit invocation surfaces the divergence; the existing suite stays
137 ok 0 divergent.

A future op-mode marking in validate.sh would let a recipe declare
"this op is field-touched; expect divergence" so the suite recognizes
the honest pattern without breaking.

## Cross-refs

- [`lc-divergence-is-the-doorway`](../../../docs/vision-kb/concepts/lc-divergence-is-the-doorway.md)
- [`lc-doorway-patterns`](../../../docs/vision-kb/concepts/lc-doorway-patterns.md)
- [`lc-randomness-as-doorway`](../../../docs/vision-kb/concepts/lc-randomness-as-doorway.md)
- [`lc-field-substrate`](../../../docs/vision-kb/concepts/lc-field-substrate.md)
