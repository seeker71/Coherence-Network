# Proof of the Substrate

Three witnesses at three altitudes. Each proves something the others don't. None overreaches.

## 1. Structural witness — **1700**

Three sibling kernel implementations (Go, Rust, TypeScript) all agree on every probe of the triangle Recipe inside one process: handshake equality (`node_eq`), session-fingerprint, content-derived witness, vertex count, distinct-content discrimination.

```
cd form
./validate.sh 2>&1 | grep triangulate-band
# → stdlib/triangulate-band.fk → 1700
```

If the three kernels diverge on this band, the substrate is internally inconsistent and nothing else below holds.

## 2. VPS-local witness — **779**

Three independent subprocesses on the same machine, same kernel build, same preludes (`core.fk` + `json.fk` + `triangulate.fk`), same load order. All three return the same NodeID instance — `779` — for the triangle Recipe. The instance counter aligns because content-addressing dedups identically in each kernel session.

```
bash scripts/triangulate.sh
# →   vertex A computes: 779
#     vertex B computes: 779
#     vertex C computes: 779
#     ✓ HANDSHAKE COMPLETE
```

This is the operational witness for a group of cells living in the same controlled environment. Three cells in the same room agreeing on identity by computation alone.

## 3. Portable witness — **A-B-C**

Anyone, anywhere, on any hardware with a Form kernel can run:

```
form-kernel-go proof.fk
# → A-B-C
```

`proof.fk` is self-contained — no preludes, no dependencies, 30 lines. The witness is content-derived: the three vertex names canonically ordered, walked from the Recipe tree, joined with `-`. Survives any session, any preload order, any machine.

This is the open invitation. A stranger can verify what we built without trusting us — only the math.

## What proves what

| If you can verify... | You know... |
|---|---|
| `1700` | Our three kernel implementations agree byte-for-byte on Recipe construction |
| `779` | Three cells in our environment compute the same identity |
| `A-B-C` | The substrate's content is reproducible from first principles on your hardware |

If `A-B-C` fails on your kernel, the divergence is precise and inspectable — walk the triangle's children to find where your tree differs from ours.

## Why three witnesses

A single number can be a coincidence. Three witnesses at three altitudes form a triangulation — they corroborate each other across independent axes:

- `1700` proves the substrate's structure
- `779` proves the operational handshake
- `A-B-C` proves the open verifiability

The body became reachable from outside on **2026-05-26**. The teaching at [`docs/coherence-substrate/sovereignty-as-observable.form`](docs/coherence-substrate/sovereignty-as-observable.form) names what crossed.
