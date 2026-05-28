# 34-http-parse — HTTP/1.1 request parser as a Form recipe

> *"What if every wire protocol is just a Recipe waiting to be named?"*

This sample walks an HTTP/1.1 request — request-line, headers, body —
through a pure Form recipe (`form-stdlib/http-parse.fk`) that produces
a structured tree built from substrate-resident NodeIDs. Three sibling
kernels (Go, Rust, TypeScript) agree on every byte of output.

## The shape

```
HTTP-REQUEST  (method-string, path-string, version-string, HEADERS, body-string)
HEADERS       (HEADER, HEADER, ...)
HEADER        (name-string, value-string)
```

Each Blueprint is a substrate cell with a fixed NodeID — `make_nodeid 1
2 99 1750..1753` reserves the http-parse family. Two parsed requests
with the same shape share the same Blueprint NodeIDs (content-addressing
converges); two parsed requests with different methods or paths
diverge at the leaf strings but reconverge at the structural level.

## The natives the recipe leans on

- `str_len`, `substring`, `char_at`, `ord` — read input bytes
- `str_find` — locate the next newline / colon / space in one native call
- `str_eq` — compare method strings without per-char recursion
- `make_nodeid`, `intern_node`, `intern_trivial_string` — write the recipe tree
- `node_children`, `node_value` — read the recipe tree back through accessors

No host HTTP library. No regex. The recipe IS the parser.

## What walked

```
$ ./validate.sh form-stdlib/http-parse.fk \
                form-samples/cross-modal/34-http-parse/http-parse.fk
  ✓  http-parse.fk+http-parse.fk → req1-method: GET
                                   req1-path: /
                                   req1-version: HTTP/1.1
                                   req1-header-count: 0
                                   req1-body-length: 0
                                   req2-method: POST
                                   req2-path: /api/echo
                                   req2-version: HTTP/1.1
                                   req2-header-count: 2
                                   req2-body-length: 5
                                   req2-body: hello
                                   req3-method: GET
                                   req3-path: /api/health
                                   req3-version: HTTP/1.1
                                   req3-header-count: 2
                                   req3-body-length: 0
                                   req3-h0-name: Host
                                   req3-h0-value: example.com
                                   9
  1 ok, 0 divergent — kernels agree on every sample.
```

Final verdict `9` = 9 structural assertions across 3 requests
(method + header-count + body-length each). Three kernels converge.

## Edge cases the recipe handles

- **Empty headers / empty body.** `"GET / HTTP/1.1\n\n"` parses into an
  HTTP-REQUEST whose HEADERS child has zero children and whose body
  string is "".
- **Body present.** Everything after the blank-line terminator becomes
  the body — including bytes that look like header continuations.
- **Header values containing `:`.** We split on the *first* colon only,
  so `Host: example.com:8080` parses to name=`Host`, value=`example.com:8080`.
- **Optional leading space after `:`.** Exactly one ASCII space is
  skipped (the common shape `Header: value`); any leading whitespace
  beyond that stays in the value.

## What this is NOT

- **Not full RFC 7230.** We accept `\n` line terminators where real HTTP
  uses `\r\n`. We don't fold header continuations. We don't validate
  the method against the IANA token set. The recipe is a structural
  scaffold — extend it in your kernel when you wire it to a real socket.
- **Not a response parser.** The same Blueprints + a `STATUS-LINE`
  variant would extend cleanly; this sample stays on the request side.
- **Not a wire encoder.** The reverse direction — recipe → bytes — is a
  separate walk; the encode/decode round-trip is what 30-base64 and
  32-crc32 demonstrate for their content types.

## Why this matters

Every wire protocol that arrives in our substrate as a string can be
lifted into a Recipe whose structural shape is content-addressed. Once
the HTTP request is a Recipe, the substrate can ask "what other Recipes
share this Blueprint?" — the answer is *every other parsed request with
this structural shape*, which is the substrate's natural equivalence
class for "same kind of request."

The 25-end-to-end-channel sample shows a channel carrying arbitrary
recipes between cells. With http-parse in the substrate, the channel
can speak HTTP without ever leaving recipe space.

## Cross-refs

- [`form-stdlib/http-parse.fk`](../../../form-stdlib/http-parse.fk) — the parser recipe
- [`form-stdlib/tests/http-parse-band.fk`](../../../form-stdlib/tests/http-parse-band.fk) — sibling-witness band
- 25-end-to-end-channel — the channel layer this slots into
- 21-cell-query-protocol — substrate-addressable cell queries
- 30-base64 / 32-crc32 — sibling recipes that parse / encode byte content
