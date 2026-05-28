# 36-channel-query-json — Form ↔ JSON wire bridge

> *Form cells talk to each other through the channel-query vocabulary
> directly — the Recipe shape IS the wire. But a Slack webhook can't
> read a Form Recipe; it speaks JSON. This walk encodes a query and
> response into JSON a non-Form service can consume.*

## What walked

```
$ ./validate.sh form-stdlib/json.fk form-stdlib/sha256.fk \
                form-stdlib/channel-query.fk \
                form-stdlib/channel-query-json.fk \
                form-samples/cross-modal/36-channel-query-json/channel-query-json.fk
  ✓  json.fk+sha256.fk+channel-query.fk+channel-query-json.fk+channel-query-json.fk
       → query-json-match: 1
         response-json-match: 1
         2
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each produced the same
canonical JSON for a QUERY and a RESPONSE built from the channel-query
vocabulary. **Verdict: 2** — both messages match their expected wire
form byte-for-byte across all three kernels.

## The wire schema

The bridge is `form-stdlib/channel-query-json.fk`. JSON shape:

```jsonc
// QUERY
{"verb": "about",
 "address": {"pkg": 1, "level": 2, "type": 99, "inst": 7},
 "body": null}

// RESPONSE
{"correlation": 1,
 "status": "ok",
 "items": [
   {"type": "substrate-ref",
    "value": {"pkg": 0, "level": 0, "type": 0, "inst": 1}}
 ]}
```

Item types the encoder handles, in increasing wire cost:

| Item type        | JSON value shape                                                  |
|------------------|-------------------------------------------------------------------|
| `substrate-ref`  | `{"pkg":…,"level":…,"type":…,"inst":…}`                           |
| `cell-ref`       | same as substrate-ref                                             |
| `external-uri`   | `{"url":"…","sha256_len":32}`                                     |
| `novel-blueprint`| `{"category":<nid-obj>,"arity":N}` — shape only, see below        |
| `recipe-content` | `{"category":<nid-obj>,"arity":N}` — shape only, see below        |

## Why some items carry shape-only

`substrate-ref`, `cell-ref`, and `external-uri` are flat: a 4-int NodeID
or a (URL, sha256) pair. They round-trip cleanly through JSON.

`novel-blueprint` and `recipe-content` carry arbitrary sub-trees built
from substrate Blueprints the sender uses. Faithfully serializing those
into JSON would require a schema for every Form Blueprint the sender
might use — schema that lives in the substrate, not on the JSON wire.

So the bridge emits a *shape attestation* — category NodeID + child
count — and lets the foreign receiver dispatch on that. The full
sub-tree rides the Form-native wire (`form-stdlib/channel.fk`'s .fkb
serialization) when both ends speak Form; the JSON view is for the
non-Form half of the federation.

## Round-trip status

| Direction          | Status |
|--------------------|--------|
| `query-to-json`    | canonical |
| `json-to-query`    | inverse (verb + address; body field reads back as empty trivial-string) |
| `response-to-json` | canonical (substrate-refs and cell-refs round-trip fully; novel/recipe shape-only as documented) |
| `json-to-response` | deferred — next walk |

`json-to-query` is implemented because non-Form callers are most often
the *originators* of queries (a Slack slash-command, an inbound webhook
request). The Form cell is most often the *originator* of responses.
Round-tripping a full response — including novel-blueprint sub-trees —
is a richer walk that needs base64 (for sha256 bytes) and a Blueprint
registry the receiver can index by NodeID; deferred so this breath
ships one clean shape.

## What this enables

A Form cell can now:

1. Receive an HTTP POST whose body is JSON `{"verb": "about", …}`.
2. Decode via `json-to-query` into a substrate-resident QUERY Recipe.
3. Dispatch through the existing channel-query handler.
4. Encode the RESPONSE via `response-to-json`.
5. Return the JSON in the HTTP response body.

The Form cell stays substrate-native end to end; the foreign service
sees only JSON. The bridge is the membrane.

## Cross-refs

- [`form-stdlib/channel-query.fk`](../../../form-stdlib/channel-query.fk) — the vocabulary
- [`form-stdlib/channel-query-json.fk`](../../../form-stdlib/channel-query-json.fk) — this bridge
- [`form-stdlib/json.fk`](../../../form-stdlib/json.fk) — JSON parser the decoder leans on
- 21-cell-query-protocol — the Form-native side of the same vocabulary
- 27-external-uri-verify — sha256-backed external content; the bridge surfaces sha256_len so a foreign receiver can audit
- 30-base64 — the base64 codec a future walk will pull in to inline sha256 bytes into JSON
