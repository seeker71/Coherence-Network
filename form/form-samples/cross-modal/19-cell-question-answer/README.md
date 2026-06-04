# 19-cell-question-answer — addressable cells ask and answer by reference

**Discovery**: #18's recipe/payload negotiation is enough to become a small
question/answer capsule. A sender identifies a question, target, and preferred
response recipe through shared numeric catalogs. The receiver resolves the
request, replies with a shared answer reference, an external content reference,
and an opaque commitment to private novel state.

## What walked

```bash
$ ./validate.sh form-samples/cross-modal/19-cell-question-answer/cell-question-answer.fk
  ✓  cell-question-answer.fk    → 24311
  1 ok, 0 divergent — kernels agree on every sample.
```

The output `24311` means:

- `2` — receiver resolved the question blueprint
- `4` — sender resolved the answer meaning
- `3` — sender resolved the external content reference
- `1` — a novel private commitment is present
- `1` — sender verified the response answered its intended request

## Why this cleans bootstrap tissue

The protocol is not a new host native. It is Form code over reusable channel
parts: catalogs, nonce-separated fingerprints, shared references, and a compact
ack. That keeps the kernel surface focused on primitive arithmetic, random
doorways, and list walking while the transport behavior lives as recipe tissue.

## Next pressure

The demo hash is only a structural stand-in. Production wants a real PRF,
content-addressed NodeIDs instead of integers, and a channel that can fetch or
witness the external reference before accepting the novel commitment.
