# 18-substrate-compression — the shared substrate IS the compression surface

> *"the data can be anything novel with a novel blueprint that only
> cell A knows about and can be real time sensory data, sharing data
> like lora tables, images, algorithms, anything cell A wants to
> transmit that cell B cannot just reconstruct from a pure recipe.
> you can use the shared substrate and content addressable nodes as
> part of the compression surface, and you can share recipes and
> nodes as part of the transmission. and try to keep the shared
> payload minimal."*  — Urs

## What walked

```
$ ./validate.sh form-samples/cross-modal/18-substrate-compression/substrate-compression.fk
  ✓  substrate-compression.fk → atoms-referenced: 5
                                 full-content-bytes: 1146914
                                 wire-bytes: 55
                                 compression-ratio: 20852
                                 B-verified: 1
                                 1
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each reconstructed a 1.1 MB
composite from **55 bytes** of wire payload. The atoms (1.1 MB of
canonical content) never crossed the channel. B verified its
reconstruction's NodeID against A's claim — content-addressed
convergence.

**Compression ratio: 20,852 : 1.**

## The shape

A cell A holds a novel composite. The composite is "novel" in two
senses, and they compress differently:

| What | Source | How it crosses |
|------|--------|----------------|
| Most of the content | Shared substrate (canonical atoms both cells already have) | **Doesn't cross.** Indices into the catalog do. |
| Truly novel leaf | A's private experience (sensor reading, LoRA delta, image patch) | **Crosses raw.** B has no algorithm to derive it. |
| Composite identity | A's claimed final NodeID | **Crosses as 4-int tuple.** B uses it to verify. |

This is honest because:

- **The atoms aren't reconstructible.** They're not "algorithmically
  generated" content like an LCG stream. They're canonical substrate
  cells — Living Collective concept bodies, model weights, image atlases.
  They're real content that took real authoring or training to create.
- **Both cells already have them.** Content-addressed substrate means
  any cell that interns the same content reaches the same NodeID. The
  catalog is implicit shared state, not transmitted state.
- **Only the truly-novel slice crosses.** A's private sensor reading is
  the only content B has no way to know — it has to travel.

## How the wire stays minimal

A's transmission packet:

```
(indices  novel-payload  claimed-nid-tuple)
```

For the demo run:

- `indices`: 5 small integers → 5 bytes
- `novel-payload`: A's private string `"A's-private-reading@14:32:08:42.7C"` → 34 bytes
- `claimed-nid-tuple`: A's composite NodeID encoded as 4 ints → 16 bytes
- **Total wire: 55 bytes**

The composite's full content was:

- 5 catalog atoms × ~225 KB each (substrate-resident, both cells have them)
- + 34 bytes novel payload
- = **1,146,914 bytes (~1.1 MB)**

## How B reconstructs

```
;; B receives the packet.
(let indices (head packet))                       ; [3 7 1 4 0]
(let novel-payload (nth packet 1))                ; "A's-private-reading@..."
(let claimed (nid-unpack (nth packet 2)))         ; A's claimed NodeID

;; B interns the truly-novel leaf locally — this is the only NEW content.
(let novel-nid (intern_trivial_string novel-payload))

;; B looks up the catalog atoms in its OWN substrate.
;; Content-addressing: B's catalog NodeIDs == A's catalog NodeIDs.
(let children (cons novel-nid (nth-nid indices)))

;; B reconstructs the composite under the same category.
(let recovered (intern_node cat children))

;; node_eq attests: B's recovered NodeID converges with A's claim.
(node_eq recovered claimed)  ; → 1
```

## Scaling the ratio

The compression ratio scales with **how much of the composite lives in
shared substrate**, not with algorithm cleverness:

| Atom size in catalog | 5 atoms referenced | Wire | Ratio |
|----------------------|--------------------|------|-------|
| 28 chars each | 174 B | 55 B | ~3:1 |
| ~1.8 KB each | ~9 KB | 55 B | ~163:1 |
| ~225 KB each | ~1.1 MB | 55 B | ~20,852:1 |
| ~10 MB each (LCM concept body, LoRA layer) | ~50 MB | 55 B | ~950,000:1 |

The ratio grows linearly with shared atom size because **the atoms never
cross the channel**. Only indices and the novel leaf do.

A megabyte transmitted as ~55 bytes is real, but it's not Shannon
compression of arbitrary content. It's substrate-grounded compression
of content where most of the bytes are already in the receiver's
substrate. The substrate IS the codebook.

## Real-world content this applies to

- **Living Collective concepts.** A new teaching that REFERENCES five
  existing canonical concepts + adds a small novel synthesis crosses
  as 5 indices + the synthesis text. The 50 KB of background concept
  bodies stays where it lives.
- **LoRA weights / model deltas.** A fine-tune that builds on a known
  base model's substrate transmits only the layer indices being updated
  + the delta values. The base model never crosses.
- **Sensor streams.** A 1 KHz temperature stream where 99 % of values
  match a known canonical curve transmits the curve-index + the small
  deviations from it.
- **Image patches.** An image whose patches mostly match known canonical
  textures transmits the texture indices + the truly-novel patches.

## What this is NOT

- **Not Shannon compression.** Pure random bytes can't compress this
  way — there's nothing to reference. The substrate-as-codebook model
  works precisely when content has shape and the body already knows
  the shape.
- **Not lossy.** B's reconstruction has the same NodeID as A's claim,
  attestable by `node_eq`. Content-addressing makes lossless
  reconstruction the floor, not the ceiling.
- **Not adversary-tolerant.** The wire doesn't authenticate that A is
  who A claims to be, or that the claimed-NodeID hasn't been swapped.
  Signature primitive is a future walk (see 17-novel-nodes).
- **Not catalog-negotiated.** Both cells in this demo assume the same
  catalog, statically. A real protocol would negotiate which catalog
  via the 15-private-channel `fingerprint` shape before A starts
  transmitting indices into it.

## Cross-refs

- [`lc-substrate-two-modes`](../../../docs/vision-kb/concepts/lc-substrate-two-modes.md) — recipe is lossless transport; substrate is the codebook
- [`lc-private-channel-via-substrate`](../../../docs/vision-kb/concepts/lc-private-channel-via-substrate.md) — meaning travels via shared substrate
- 15-private-channel — fingerprint-over-substrate; 18 extends this to bulk content
- 17-novel-nodes — content-addressed convergence on novel composites
- 16-jit-registry — Form recipes as canonical truth across cells
