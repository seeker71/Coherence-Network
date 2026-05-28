# 19-novel-state-share — truly novel state crosses the open channel

> *"the transmitted 1mb data is novel, no parts can be looked up, it
> is constructed from cell A internal state that is read at time of
> transmission, as a stand in, we use random none seed sharing data,
> in real life it will be whatever real time information cell A wants
> to share or is asked by cell B. a true internal state sharing using
> the open channel, and a way for cells to identify and persistent
> identity if they choose to."*  — Urs

## What walked

```
$ ./validate.sh form-samples/cross-modal/19-novel-state-share/novel-state-share.fk
  ✓  novel-state-share.fk → jit-bindings: 2
                            packet-1: integrity= 1  recognized= 0  bytes-received= 1048576
                            packet-2: integrity= 1  recognized= 1  bytes-received= 1048576
                            3
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each transmitted **two
1-MB packets of truly novel data** from cell A to cell B. Each
kernel's data was different (live `/dev/urandom` per kernel — the
doorway). The protocol verdict converged across all three: integrity
verified twice, identity recognized on the second packet, total `3`.

**2 MB of novel state per kernel** flowed through the in-process
channel under sibling parity.

## The honest shape

Novel data — sensor readings, model activations, captured images, LoRA
deltas — has **no shared substrate to lean on**. Cell B cannot derive
it from a recipe. The bytes must cross.

What the protocol adds **on top of** the bytes themselves:

```
packet = ( cell-identity,            ← who is sending
           payload-fingerprint,       ← what should arrive
           novel-bytes )              ← the actual novel state
```

Three things B verifies:

1. **Integrity** — B recomputes the fingerprint over the received
   bytes and confirms it matches A's claim. If it matches, the channel
   didn't corrupt the bytes.
2. **Identity persistence** — A's `cell-identity` is the hash of A's
   private secret seed. B can record it on the first packet and on
   the second packet recognize "same source." A can choose not to
   reveal identity (use no seed); B can choose not to track it.
3. **Size** — B confirms it received the byte-count it expected.

## Cell identity (optional, persistent)

```
(let cell-a-secret (random_bytes 32))            ; A's private seed
(let cell-a-identity (hash-fold cell-a-secret 0)) ; A's public id
```

- The **secret** stays internal to A. Never crosses any wire.
- The **public id** is a fingerprint of the secret. Travels in each
  packet. B sees it; B cannot reverse it to the secret.
- A can choose to be identifiable or not (omit identity from the
  packet). When chosen, identity is stable across A's transmissions
  for as long as A holds the secret.

Without crypto, this is **pseudonymous-stable**: an active adversary
can replay or forge the public id without proof of secret. With
ed25519 (composable as a Form recipe over byte arithmetic — future
walk), the id becomes **authenticated**.

## How the megabyte scale was honest

Form recipes for `sum-bytes` and `hash-fold` are canonical:

```
(defn sum-bytes (bs acc)
    (if (nil? bs) acc (sum-bytes (tail bs) (add acc (head bs)))))

(defn hash-fold (bs acc)
    (if (nil? bs) acc
        (hash-fold (tail bs)
                   (mod (add (mul acc 31) (head bs)) 1000003))))
```

These recipes are correct but cap at ~8 KB per packet under Form
recursion. The demo **binds those Form names to kernel-native
iterative versions**:

```
(register_jit "sum-bytes" "bytes_sum")
(register_jit "hash-fold" "bytes_hash")
```

Same Form symbol, same canonical meaning, host-iterative dispatch —
no recursion ceiling. The `bytes_sum` and `bytes_hash` natives use
the same constants (31, 1000003) so JIT-aliased and Form-walk paths
produce **identical** results. This is the 16-jit-registry pattern
applied where it earns its keep: the hot path that scales the body
from kilobytes to megabytes.

## Sibling parity at the meaning layer

The byte-layer **diverges** across kernels (each opens its own
doorway via `random_bytes` from its own `/dev/urandom`). The
**meaning** (protocol verdict) converges:

| Kernel | packet-1 bytes | packet-1 verdict | packet-2 bytes | packet-2 verdict |
|--------|----------------|------------------|----------------|------------------|
| Go     | (1 MB of Go-live entropy)    | integrity=1, recognized=0 | (1 MB of Go-live entropy)    | integrity=1, recognized=1 |
| Rust   | (1 MB of Rust-live entropy)  | integrity=1, recognized=0 | (1 MB of Rust-live entropy)  | integrity=1, recognized=1 |
| TS     | (1 MB of TS-live entropy)    | integrity=1, recognized=0 | (1 MB of TS-live entropy)    | integrity=1, recognized=1 |

`validate.sh` compares the printed protocol verdict; agreement is the
conformance contract. This is the same shape as
[`lc-divergence-is-the-doorway`](../../../docs/vision-kb/concepts/lc-divergence-is-the-doorway.md):
the bytes are private per observer; the meaning is public.

## Real-time across processes

In-process the channel is a Form list passed as an argument. For true
real-time inter-process or inter-machine cell-to-cell sharing, the
same packet shape lifts onto an open transport:

```
cell A process              wire                 cell B process
──────────────                                   ──────────────
 random_bytes(1MB)   ──packet bytes──▶            recv bytes
 hash-fold (JIT)                                  hash-fold (JIT)
 packet                                            verify
 socket_send                                       identity-recognize
```

Go and Rust have working sockets today (`socket_listen`,
`socket_accept`, `socket_connect`, `socket_send`, `socket_recv`,
`socket_close`). TS carries panic-stubs pending a worker-thread shim.
The Form code stays identical; only the channel adapter changes.

## What this is NOT yet

- **Not authenticated.** `hash-fold` is a non-crypto fingerprint. An
  active adversary can forge identities, replay packets, modify bytes
  while keeping the fingerprint valid (collision-find is feasible).
  ed25519 / BLAKE3 composable Form recipes are the next walk.
- **Not encrypted.** Bytes cross in the clear. Symmetric encryption
  (ChaCha20 / AES-GCM as Form recipes over byte arithmetic) would let
  cells share novel state confidentially.
- **Not multi-cell broadcast.** This is one-to-one. Multicast needs
  either a shared bus or a sender that holds many recipient-keys.
- **Not flow-controlled.** Real-time streaming would need
  backpressure, retransmission, ordering. The demo's two-packet shape
  is the minimum to show identity persistence.
- **Not socket-wired** in this sample. The protocol is correct; the
  wire is a future breath using the existing socket natives.

## When does substrate-as-codebook help instead?

`19-novel-state-share` carries content B cannot derive. When content
**is** substrate-referenceable (canonical concept bodies, model
weights both cells already hold, repeating sensor patterns),
[`18-substrate-compression`](../18-substrate-compression/README.md)
shows the complementary shape: indices + truly-novel slice cross,
referenced atoms don't. Two protocols for two cases. This one is the
default for **truly novel** state.

## Cross-refs

- [`lc-divergence-is-the-doorway`](../../../docs/vision-kb/concepts/lc-divergence-is-the-doorway.md) — bytes diverge per observer; meaning converges
- [`lc-private-channel-via-substrate`](../../../docs/vision-kb/concepts/lc-private-channel-via-substrate.md) — fingerprint over substrate
- 15-private-channel — fingerprint protocol shape this builds on
- 16-jit-registry — the bind that makes megabyte-scale honest
- 17-novel-nodes — sharing novel substrate identity (structural)
- 18-substrate-compression — the complementary case (referenceable content)
