# 53-now-unix-ms — the clock as a sibling native

A `(now_unix_ms)` native in all three kernels, returning the current
millisecond unix timestamp as an int. Same name, same arity, same
return shape — but the VALUE diverges between kernels by definition.
Sibling parity holds on SHAPE, not on value.

## What walked

```
$ ./validate.sh form-samples/cross-modal/53-now-unix-ms/now.fk
  ✓  now.fk                          → t1-positive: 1
                                       t2-positive: 1
                                       t1-after-epoch: 1
                                       t2-after-epoch: 1
                                       4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran the walk
end-to-end:

1. **`t1-positive: 1`** — first clock read is a positive int. Any
   sane unix-ms timestamp must be positive; this catches a kernel
   that silently returns 0 or a negative.
2. **`t2-positive: 1`** — second clock read is a positive int. Two
   reads in a row, same shape.
3. **`t1-after-epoch: 1`** — first read is greater than
   `1700000000000` (2023-11-14 UTC). Any clock that matters today is
   comfortably past this; a host with a broken RTC reset to 1970
   would fail this while passing the positivity check.
4. **`t2-after-epoch: 1`** — second read, same epoch check.

**Verdict: 4** — all four shape attestations hold across all three
kernels.

## The shape-vs-value discipline

This sample is the first cross-modal walk where the native's VALUE
**must** differ between siblings. Every prior native — sha256, hmac,
adler32, base64 — was a pure function on byte input, so a sibling
parity check on the exact bytes was the canonical attestation. The
clock is not pure: it reads the host's wall-clock at the moment of
invocation, and even on the same host the three kernel processes run
sequentially with microseconds of drift between them.

So the sample prints only **booleans** derived from the timestamps,
never the timestamps themselves. The booleans are deterministic
under any reasonable host clock; the underlying ints aren't. The
verdict is the sum of the booleans, which IS sibling-stable.

If a future sibling kernel returns `0` (uninitialized stub) or a
negative (signed-overflow bug), the positivity check fails on that
kernel only, sibling parity diverges, and the band reports which
kernel is the outlier. If a host has a broken RTC, all three
kernels fail the epoch check together and the verdict drops to 2 —
but parity holds (all three see 2), so the sample still passes
validate.sh; the verdict number itself is the freshness signal.

## The native

In each kernel, `now_unix_ms` is registered as a `catCall` native
(external effect — reads the host clock — so it's outside `catPure`):

```rust
// form-kernel-rust/src/main.rs
self.register_native("now_unix_ms", cat_call(), |_, _, _| {
    use std::time::{SystemTime, UNIX_EPOCH};
    let ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0);
    Value::Int(ms)
});
```

```go
// form-kernel-go/main.go
k.registerNative("now_unix_ms", catCall(), func(_ *Kernel, _ []Value) Value {
    return Value{Kind: VInt, Int: time.Now().UnixMilli()}
})
```

```typescript
// form-kernel-ts/src/kernel.ts
this.registerNative("now_unix_ms", catCall(), (_k, _args) => ({
    kind: "int",
    int: Date.now(),
}));
```

The host APIs (`SystemTime::now`, `time.Now().UnixMilli()`,
`Date.now()`) all return milliseconds since the unix epoch in
contemporary 64-bit ranges (well under 2^53, comfortable in i64 and
JS number alike), so the integer travels across all three kernels
without rebuild.

## What this unblocks

Six existing walks have been carrying placeholder `0` stamps or
host-side time injection where the recipe wanted a real clock:

- **`42-ping`** — `ping.fk` notes explicitly that the stamp is `0`
  because no `(now)` native exists yet; one line changes once this
  lands.
- **`form-stdlib/token.fk`** — capability token mint/validate
  carries an `expires-at` value; today every call site passes a
  literal. Real freshness needs `(now_unix_ms)` as the validation
  clock.
- **`form-stdlib/heartbeat.fk`** — observer-clock freshness checks
  take `now-time` as a parameter; until this native existed, every
  caller had to thread a synthetic clock through.
- **`async-correlation`** — windows that expire on the originator's
  clock.
- **`audit-log`** — entry timestamps.
- **`autoresearch-loop`** — iteration deadlines.

Each of those becomes a one-line update from `0` (or
host-injected) to `(now_unix_ms)` once they want real wall-clock
freshness instead of synthetic-clock parity.

## Cross-refs

- [`form-stdlib/tests/now-unix-ms-band.fk`](../../../form-stdlib/tests/now-unix-ms-band.fk) — sibling-witness band (verdict 4)
- 42-ping — documents the gap this sample closes
- 49-token — capability token that wants a real expiry clock
- 52-heartbeat — liveness table that wants observer-clock freshness
