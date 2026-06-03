# Kernel-Router COMPARE Mode — live native-vs-CPython shadow diff

COMPARE mode is the **zero-risk shadow step** before the kernel-router becomes the
real front door. Instead of a risky one-time flip from CPython to the kernel, the
kernel-router runs **in front** of the CPython app and, for every native route,
**self-compares its answer against CPython on live traffic** while still returning
CPython's (safe) response. Divergence, latency, and downtime are measured against
production traffic *before* any cutover. The cutover then becomes a **single env
toggle**, not a leap.

This is the read-time companion to the deploy overlay in
[`docker-compose.kernel-router.yml`](docker-compose.kernel-router.yml) and the flip
described in [`kernels/KERNEL_AS_ROUTER.md`](../../kernels/KERNEL_AS_ROUTER.md).

## The design (one flag couples *compare* and *which-response-to-return*)

`COH_ROUTER_COMPARE` — read **once at startup** (never per request) by the
kernel-router (`cli_serve` in `form/form-kernel-rust/src/main.rs`).

When it is set (`1`/`true`) **AND** an upstream is configured, every NATIVE route:

1. **Serves natively** from the kernel (timed → `native_ms`).
2. **Shadow-fans-out the same request** (method, target, headers, body) to the
   CPython upstream over the same keep-alive `UpstreamPool` the fan-out tail uses,
   and **captures the full response into memory** (timed → `cpython_ms`).
3. **Compares** byte-for-byte: `status_match = native_status == cpython_status`,
   `body_match = native_body == cpython_body` (exact bytes), `matched = both`.
4. **Logs** one structured `[compare]` line to stdout (captured by `docker logs`);
   on a mismatch a bounded diff snippet (~200 bytes each side) follows.
5. **Returns CPython's response** — the user gets exactly what direct-CPython would
   serve. This is the safety property: **zero behavior change**. If the shadow
   fan-out errors, it falls back to returning the **native** response (a shadow
   hiccup must never 5xx the user) and logs `compare_fanout_failed`.

Every response also carries the header **`X-Form-Compare: matched | mismatch |
cpython_error`** (alongside the existing `X-Form-Router: native-kernel`), so an
external monitor reads per-request verdicts without parsing logs.

When `COH_ROUTER_COMPARE` is **unset** (the default **and** the post-validation
cutover state), the native arm is **unchanged**: serve native, return native, no
fan-out, no overhead. **The cutover is literally turning compare off.**

Only the NATIVE arm is touched. Non-native paths already fan out to CPython — there
is nothing to compare.

## The one-flag toggle

| `COH_ROUTER_COMPARE` | Native route behavior | Use |
|----------------------|-----------------------|-----|
| `1` / `true`         | Serve native, compare vs CPython, **return CPython** | **Validation** — watch divergence on live traffic |
| unset / `""`         | Serve native, **return native**, no fan-out | **Cutover** — the native kernel is the answer |

The toggle lives in [`docker-compose.kernel-router.yml`](docker-compose.kernel-router.yml)
(`environment: COH_ROUTER_COMPARE: "1"`). Cutover = set it to `""` (or remove it)
and `docker compose up -d kernel-router`. Rollback = set it back. Instant, no data
migration.

## Reading divergence

**Per-request** (no log access needed): read the `X-Form-Compare` response header.

```bash
curl -sI http://localhost:8088/api/utils/coherence_weight?values=10,20,30 \
  | grep -i x-form-compare
# X-Form-Compare: matched
```

**In the logs** — every comparison is one greppable line on stdout:

```
[compare] route=/api/utils/coherence_weight matched=true status_native="200 OK" \
  status_cpython="200 OK" status_match=true body_match=true native_ms=0.31 \
  cpython_ms=12.74 nbytes=91 cbytes=91
```

A mismatch adds bounded snippets:

```
[compare] route=/api/utils/foo matched=false ... body_match=false ...
[compare] route=/api/utils/foo mismatch_native_snippet="0.80"
[compare] route=/api/utils/foo mismatch_cpython_snippet="0.81"
```

A shadow-upstream failure (the user still got the native answer, 200):

```
[compare] route=/api/utils/foo compare_fanout_failed error="..." native_ms=0.2 returning=native
```

**Aggregate** with [`compare_summary.py`](compare_summary.py) — folds `[compare]`
lines from stdin into a per-route table (count, mismatch, cpython_error, p50
native_ms vs cpython_ms):

```bash
docker logs coherence-network-kernel-router 2>&1 \
  | python3 deploy/kernel-router/compare_summary.py
```

```
route                                          count  mismatch  cpy_err  p50_native_ms  p50_cpython_ms
------------------------------------------------------------------------------------------------------
/api/utils/coherence_weight                     1843         0        0          0.310          12.740
...
totals: compared=… mismatch=0 cpython_error=0  =>  CLEAN — safe to cut over (unset COH_ROUTER_COMPARE)
```

## Safe rollout

1. **Insert the compare-mode front door.** Bring up the kernel-router overlay with
   `COH_ROUTER_COMPARE=1` and `UPSTREAM_URL=http://api:8000`, pointed at a manifest
   with native routes (`production-routes.fk`). Traefik/prod is **untouched** — the
   overlay only adds the service; the flip (re-pointing Traefik) is a separate,
   intent-level step documented in `docker-compose.kernel-router.yml`.
2. **Watch the log clean.** Run real traffic (or replay) through the router and run
   `compare_summary.py`. Watch until `mismatch=0` and `cpython_error≈0` across every
   route over a representative window. Any mismatch row names a route whose native
   handler diverges from CPython — fix the handler (or its manifest), redeploy, keep
   watching. The user is never affected: they got CPython the whole time.
3. **Cut over.** Once the window is clean, set `COH_ROUTER_COMPARE=""` and
   `docker compose up -d kernel-router`. Native routes now serve+return native, with
   the proxy hop skipped entirely. Rollback is setting it back to `"1"`.

The flip of Traefik onto the kernel-router (making it the real front door for
`api.coherencycoin.com`) is the **separate** stakes-and-intent step in
`docker-compose.kernel-router.yml` — the commented `traefik.*` labels. Compare mode
and the Traefik flip are independent: you can run compare mode behind a shadow port
first, then flip Traefik, then cut compare off — each reversible on its own.

## Proof

The compare-mode mechanics are proven by
[`form/form-kernel-rust/production_routes_harness.py --compare`](../../form/form-kernel-rust/production_routes_harness.py):

- **Stub mechanics** (network-independent): a trivial native route against a tiny
  stub upstream drives all three verdicts — `matched` (returns the body,
  `X-Form-Compare: matched`), `mismatch` (returns the *CPython* body, logs the diff
  snippets), `cpython_error` (dead upstream → returns *native*, 200, never a 5xx),
  plus normal-mode-unchanged (compare unset → native served+returned, no header, no
  `[compare]` logs).
- **Real-app oracle**: a promoted native route compared against the live CPython app
  returns the CPython body, carries `X-Form-Compare: matched`, and logs `[compare]
  ... matched=true` with both latencies.

Latency: in compare mode the user waits for CPython anyway, so response latency ≈
CPython's; the native serve + the byte compare add ~nothing (`native_ms` is a
fraction of a millisecond against CPython's tens). The summary's `p50_native_ms` vs
`p50_cpython_ms` columns make the post-cutover speedup visible *before* cutting over.
