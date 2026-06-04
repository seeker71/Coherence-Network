# 18-channel-negotiation — recipe and payload agree without crossing the wire

**Discovery**: the private-channel proof scales from one referent to a useful
transport opening. A sender can select both an encoding recipe and a payload
blueprint; the receiver identifies both through shared substrate catalogs; the
receiver acknowledges the pair; neither referent crosses the channel.

## What walked

```bash
$ ./validate.sh form-samples/cross-modal/18-channel-negotiation/channel-negotiation.fk
  ✓  channel-negotiation.fk       → 341
  1 ok, 0 divergent — kernels agree on every sample.
```

The byte-layer diverges because each kernel opens `random_bytes` three times.
The meaning-layer converges because all kernels share the same recipe and
payload catalogs.

## The protocol

```
sender private state:
  recipe index 3  -> recipe value 440
  payload index 4 -> payload value 1005

sender -> receiver:
  (recipe_nonce, fingerprint(recipe_nonce, 440))
  (payload_nonce, fingerprint(payload_nonce, 1005))

receiver:
  resolves index 3 from its recipe catalog
  resolves index 4 from its payload catalog

receiver -> sender:
  (ack_nonce, fingerprint(ack_nonce, pair(3, 4)))

sender:
  verifies the ack against its intended pair
```

The stable output `341` means:

- `3` — receiver found the selected recipe
- `4` — receiver found the selected payload
- `1` — sender verified the receiver's acknowledgement

## What this adds beyond 15-private-channel and 16-megabyte-channel

- **Media and recipe negotiation**: cells can agree on the channel recipe
  before sending any novel payload reference.
- **Payload privacy**: cells can reference a blueprint, file hash, external URL,
  model weight table, image, audio clip, or recipe without sending it.
- **Pair acknowledgement**: the response confirms the combination, not just one
  referent. This is the smallest useful handshake for universal transport.

## Production gaps

- The fingerprint is still a demo hash. Production wants a kernel-native PRF
  such as HMAC or BLAKE3.
- The catalogs are integer lists in the sample. Production catalogs are
  substrate NodeIDs, external content addresses, and recipe capsules.
- Both cells run in one invocation. Production needs socket, pipe, queue, or
  shared-substrate channel I/O with nonce replay protection.

In service of private meaning transport: less payload on the wire, more shared
substrate doing the work.
