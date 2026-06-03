# Kernel as router — the request front-door reversal

> The reversal Urs named: **make the Form kernel the router / starting point of
> request handling**, fanning out to CPython only for the not-yet-native tail.
> Today CPython (FastAPI) is the runtime and the kernel is a called
> guest-subroutine. This inverts that topology.

This is the structural complement of [`API_KERNEL_READINESS.md`](API_KERNEL_READINESS.md).
That document holds *"FastAPI stays the doorway; the kernel serves the
pure-compute core of eligible routes."* This one holds the inversion: **the
kernel IS the doorway; CPython is the upstream for the routes the kernel does
not yet serve natively.** Same body, two phases of the same arc — the readiness
map grows the native surface; this design moves the front door onto it.

The seed already exists and is measured: `form-kernel-rust serve` (`cli_serve`
in [`form/form-kernel-rust/src/main.rs`](../form/form-kernel-rust/src/main.rs))
is a kernel-resident HTTP listener that loads a `routes.fk` once into a
long-lived `Kernel + Arena`, holds the top-level `routes` binding (a list of
`(path, handler-closure)`), and dispatches each request to the matching Form
handler. No FastAPI, no CPython in that path. This design makes that primitive
PRIMARY and adds the fan-out arm.

## Today: the kernel is a guest inside a CPython request

```
   visitor
     │  HTTP
     ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI (CPython) — THE RUNTIME / FRONT DOOR                  │
│    route match (path + method)                                 │
│    Pydantic bind + validate                                    │
│    ┌────────────────────────────────────────────┐             │
│    │  serve_via_kernel(recipe, bindings, …)      │  ← the      │
│    │    Form kernel walks the compute core       │    kernel   │
│    │    returns a scalar / list value            │    is a     │
│    └────────────────────────────────────────────┘    GUEST    │
│    wrap value in the response model                            │
└──────────────────────────────────────────────────────────────┘
     │
     ▼  JSON
   visitor
```

The kernel runs *inside* a CPython request, for the **23 compute cores**
(across 8 `kernel_*` router families) that call `serve_via_kernel`. The other
~762 of the 785 endpoints never touch the kernel. Python owns the socket, the
routing, the validation, the lifecycle. The kernel is reached only after
CPython has already decided everything.

## Reversed: the kernel is the front-door router

```
   visitor
     │  HTTP
     ▼
┌──────────────────────────────────────────────────────────────┐
│  form-kernel-rust serve — THE RUNTIME / FRONT DOOR (ROUTER)   │
│    parse request line (method, path, query)                   │
│    look up path in the routes.fk manifest                      │
│                                                                │
│    ┌── path HAS a native Form handler ──────────────┐         │
│    │   walk the handler recipe in the kernel         │  served │
│    │   value → HTTP body                              │  in     │
│    │   X-Form-Router: native-kernel                   │  FORM   │
│    └─────────────────────────────────────────────────┘  (no   │
│                                                          CPython)│
│    ┌── path has NO native handler (the tail) ────────┐         │
│    │   FAN OUT: forward to the CPython upstream       │  served │
│    │   relay the upstream response                    │  by     │
│    │   X-Form-Router: fanout-python                   │  Python │
│    └──────────────────┬──────────────────────────────┘         │
└───────────────────────┼────────────────────────────────────────┘
                         │  HTTP (localhost / unix socket)
                         ▼
              ┌──────────────────────────────┐
              │  FastAPI (CPython) UPSTREAM   │  ← Python is now the
              │  the ~762 not-yet-native      │    fan-out target for
              │  routes, unchanged            │    the tail, not the
              └──────────────────────────────┘    front door
```

The kernel owns the listening socket. It decides native-vs-fan-out per request.
Native routes never touch CPython; the tail keeps working because the kernel
proxies it to the same FastAPI app that serves it today — unchanged.

## How a route is classified: the routes.fk manifest

The manifest is the single source of routing truth. A route is **native** iff
the manifest binds a Form handler for its path; **everything else fans out**.

```bml
section [form.route] {
    template RouteCell<TRequest, TResponse> {
        member request: TRequest;
        member response: TResponse;
        member route: KernelHTTPRoute;
    }

    class HealthRoute : RouteCell<KernelHTTPRequest, KernelHTTPResponse> {
        def handle(request) {
            "ok";
        }

        route = route_data(health, handle);
    }
}
```

Classification is **closed-world by presence**: listed ⇒ native, absent ⇒
fan-out. There is no per-route "fanout" declaration to drift — the absence IS
the declaration. As a route moves from fan-out to native, it gains a line in
the manifest and a Form handler; nothing else in the topology changes.

A working manifest with three native handlers (liveness, a real float
coherence-weight combinator, and an input-driven signal counter) lives at
[`form/form-kernel-rust/examples/router-proof.fk`](../form/form-kernel-rust/examples/router-proof.fk).

## The fan-out mechanism

`cli_serve` gains a `--upstream <base-url>` flag. When set, a path with no
native handler is forwarded to `<base-url><path>?<query>` and the upstream
response is relayed. The kernel already carries an HTTP client (`ureq`, used by
the `fetch` subcommand), so this is a **real proxy hop, not a stub**:

```
form-kernel-rust serve \
  --port 80 \
  --routes routes.fk \
  --upstream http://127.0.0.1:8000   # the running FastAPI app
```

`fan_out_to_upstream(base, path, query)` issues the GET, relays the upstream's
status and body, and stamps `X-Form-Router: fanout-python`. Absent `--upstream`,
an unmatched path is a 404 — the original proof-of-shape behavior, unchanged, so
nothing that runs `serve` today sees a difference.

Every response carries an `X-Form-Router` header — `native-kernel` or
`fanout-python` — the inverted topology's analog of the guest path's `runtime`
field: a client can see, per request, whether the kernel served it in Form or
fanned it out to Python.

## What must grow on the kernel side for a REAL front door

`cli_serve` is an honest **proof-of-shape**, not a production front door. The
gap, named precisely:

| Gap | cli_serve today | Production front door needs |
|-----|-----------------|-----------------------------|
| **HTTP version** | serves HTTP/1.1 with keep-alive on BOTH hops — on the client hop a worker holds the accepted connection and serves multiple requests on it (one TCP handshake amortized across the connection), and on the fan-out hop each worker reuses a per-worker keep-alive connection to the upstream (the router→upstream handshake amortized across requests, the symmetric saving); a native/error response is Content-Length-framed, and a fan-out STREAMS the upstream's framing through (Content-Length echoed, or `Transfer-Encoding: chunked` relayed, or close-framed) so the client always knows where the body ends; the client's intent is honored (HTTP/1.1 default-keep-alive unless `Connection: close`, HTTP/1.0 close-unless-`keep-alive`); a 5s idle read-timeout closes a quiet client connection so it cannot pin a worker; over-read bytes (pipelining) are carried into the next request on both hops, never dropped | HTTP/2 behind Traefik (a chunked upstream response now relays through but its connection is not pooled — chunked-body pool reuse is a named-later breath) |
| **Concurrency** | the accept loop dispatches each accepted stream to a POOL of kernel workers (`--workers`, default the host's available parallelism), each owning its own `Kernel + Arena` (the `!Sync` constraint) with `routes.fk` loaded once per worker; concurrent requests run lock-free on isolated kernels — measured ~3–5x throughput over a single worker under 50-way concurrent CPU-bearing load, with no cross-request state bleed | an async/work-stealing accept loop (the thread-per-request-blocked model caps at the worker count); shared read-only routing structure to drop the per-worker re-parse |
| **Request parsing** | reads the full request honoring Content-Length (a body larger than the initial 8 KiB read is captured across as many socket reads as it needs); parses query fields and `application/x-www-form-urlencoded` bodies into compatibility field pairs, captures `application/json` (and any other body) raw under the reserved key `__body__`; builds a typed `KernelHTTPRequest(method,path,headers,query,body)` value for native handler context; a generous fixed request shape threshold (64 MiB default) is observed and answered observably when a body is larger than a worker can hold; any method (POST/PUT/PATCH/GET) | structural JSON→Form-value parse (today JSON is raw-captured, not parsed); larger/streamed/chunked bodies; Form-visible router configuration for shape policy |
| **Fan-out proxy** | STREAMS the upstream response body straight to the client — the body is NEVER held whole; only the small response head is buffered (to parse status + framing + relayed headers), then the body is piped in a fixed 64 KiB chunk reused across reads. A Content-Length body is relayed with the SAME length (both hops stay framed, the connection pools IFF the upstream kept it alive); a chunked body has its raw chunk framing relayed through to the TRUE terminating 0-length chunk (a chunk-BOUNDARY parser tracks where chunks end so a `0\r\n\r\n` byte run inside chunk data never truncates the relay), self-delimiting so the client stays framed, the connection not pooled; an unframed (read-to-close) body is piped to EOF and the client connection then closes. Reuses a per-worker keep-alive connection to the upstream, reconnecting transparently on a stale pooled connection — repeated fan-outs amortize the upstream TCP handshake instead of opening a fresh connection per request. Bounds each fan-out with a connect timeout (~5s) and a read/write timeout (~30s) so a hung upstream returns a 504 and frees the worker rather than pinning it; a read-timeout is not retried (the upstream is hung — a retry would only re-hang and double the latency), a connect-timeout may retry once (in case a pooled-addr was bad), distinct from the stale-close path which reconnects+retries once on an idle-closed pooled connection. The retry lives at the HEAD read (before any body byte reaches the client), so it stays safe; a stall mid-body after the head is sent closes the client connection (a truncated body — the honest outcome of an upstream that died mid-stream), since the status was already written. Forwards the original method, the request body, and the client's end-to-end request headers (Authorization, Cookie, Accept\*, User-Agent, Content-Type, X-\*, …) — hop-by-hop headers (Connection, Keep-Alive, Transfer-Encoding, Upgrade, Proxy-\*, Proxy-Connection, TE, Trailer) stripped, Host rewritten to the upstream, Content-Length re-derived from the captured body, the router writing its OWN `Connection: keep-alive` to the upstream — and relays the upstream's response headers back (Content-Type so a JSON/HTML route survives the proxy, Set-Cookie, Cache-Control, Location, ETag, X-\*, …), with the router owning the client-hop framing (its own Content-Length / Transfer-Encoding / Connection; the upstream's hop-by-hop/framing headers are not relayed) | STREAMING the REQUEST body (today the request body is still buffered before the fan-out; the response streams), per-route timeout config and circuit-breaking, retries beyond the single stale-connection / connect-timeout retry |
| **Handler inputs** | 0 or 1 arg — existing handlers receive the compatibility request alist, carrying query params AND parsed body fields uniformly, plus direct `__kernel_request__` typed request tissue with headers/query/body preserved as Form values | typed routes should receive `KernelHTTPRequest` directly, with the alist available only as an explicit projection; path params and structural JSON body values |
| **Errors / observability** | 404/413/500 as plain text | structured errors, access logs, the trace surface wired to the witness, metrics |
| **TLS / lifecycle** | plain TCP on 127.0.0.1, runs until killed | TLS termination (or behind Traefik), graceful shutdown, health/readiness, config reload |

None of these is exotic; each is a named breath. Five of the load-bearing ones
are built. **Concurrency**: the kernel's per-process intern table
(`lc-native-kernel-binary` names this: *"Not multi-process"*) makes the
production shape a **pool of kernel workers behind the accept loop**, each
holding its own `Kernel + Arena`, rather than one shared mutable kernel — and
that pool is now what `cli_serve` runs. **Request bodies**: `cli_serve` reads
the full request honoring Content-Length (a body past the initial 8 KiB read is
captured across multiple reads), parses `application/x-www-form-urlencoded`
bodies into the same handler alist the query string uses, captures
`application/json` raw under `__body__`, and the fan-out hop forwards the method
and body to the upstream — so a POST is served (or fanned out) with its payload,
not just a GET. **HTTP/1.1 keep-alive**: a worker serves a whole connection's
lifetime — `handle_request` (the one factored per-request shape) runs in a loop
on the same `TcpStream`, so multiple requests reuse one TCP connection; each
response is HTTP/1.1 with an accurate Content-Length (the framing that lets a
client read one response and the next without chunked encoding); the
`Connection` header is honored both ways (HTTP/1.1 stays open unless the client
sends `close`, HTTP/1.0 closes unless it sends `keep-alive`); a 5s idle
read-timeout reaps a quiet connection so it frees its worker; and over-read
bytes from one request are carried into the next, never dropped (the pipelining
hazard). The honest tradeoff: a worker serving a keep-alive client is
unavailable to the pool until the connection closes or the idle timeout fires —
standard thread-per-connection behavior, tuned by the idle-timeout value and the
worker count. **Header passthrough**: the fan-out hop is a real reverse proxy on
both sides — it forwards the client's end-to-end request headers to the upstream
(Authorization, Cookie, Accept\*, User-Agent, Content-Type, X-\*) and relays the
upstream's response headers back (Content-Type so a JSON/HTML route keeps its
type instead of flattening to text/plain, plus Set-Cookie, Cache-Control,
Location, ETag, X-\*), with RFC 7230 §6.1 hop-by-hop hygiene applied in both
directions (Connection, Keep-Alive, Transfer-Encoding, Upgrade, Proxy-\*, TE,
Trailer stripped), Host rewritten to the upstream, and the router keeping
ownership of its client-hop framing (its own Content-Length + Connection, which a
relayed upstream header can never clobber). One response-emit shape writes every
response — native, fan-out, and error — so the framing is authored in a single
place and the relayed upstream headers sit beside it without forking the logic.
**Upstream connection reuse**: the fan-out hop reuses a per-worker keep-alive
connection to the upstream instead of opening a fresh one per request — the
symmetric build to the client-hop keep-alive, on the router→upstream hop. Each
worker owns its own small connection pool keyed by `(host, port)`, with NO
locking: a worker handles requests serially on its thread, so it owns its pool
exactly as it owns its `Kernel + Arena` (the per-worker isolation from the
concurrency build). The router writes its own `Connection: keep-alive` to the
upstream and frames the response by Content-Length — it can no longer rely on the
upstream closing the connection to know where the body ends (that was how the old
read-to-close worked), so it reads one response's HEAD, STREAMS exactly the
Content-Length-framed body straight to the client, and carries any over-read bytes
(read past the framed body in the head read) forward for the next response on the
connection (the classic keep-alive proxy bug — a mis-framed read corrupts the next
request — held off by the same carry discipline the client hop uses). A pooled
connection may have been idle-closed by the upstream since it was returned; on a
reuse whose write or HEAD read fails, the router transparently reconnects once and
retries the same request, never surfacing a stale-pool error to the client — the
retry lives at the head read, before any body byte has reached the client, so it
stays safe. The honest scope: reuse applies to Content-Length-framed responses; an
upstream chunked or unframed response is streamed through but its connection is
dropped, not pooled (chunked-body pool reuse is a named-later breath). The ONE
`fanout_stream_to_client` shape is preserved — the pool only changes the connection
lifecycle (reused vs fresh); the request build, head read, and body streaming are
identical either way.
**Fan-out timeouts**: each fan-out hop is bounded by a connect timeout (~5s) and a
read/write timeout (~30s) so a SLOW or HUNG upstream cannot pin a worker forever —
the client-hop already reaps an idle connection (`KEEPALIVE_IDLE_TIMEOUT`); this is
the symmetric robustness on the upstream hop, but for a HUNG (not merely idle)
upstream it bounds the ACTIVE request: connect resolves a concrete SocketAddr and
dials with `connect_timeout`, and the connected stream gets explicit read AND write
deadlines on every use. On expiry the worker returns a clean 504 Gateway Timeout to
the client and DROPS the connection (never returns a half-read connection to the
pool — it is now desynced), then is free to serve other requests. The hung upstream
therefore consumes ONE worker for at most (connect + read timeout), not forever, so
a flood of hung fan-outs cannot starve the pool. The retry-vs-504 distinction is
carried by error CLASSIFICATION, not a fork of the fan-out shape: a read-timeout on
an actively-connected upstream is terminal → 504 (the upstream is hung; retrying
would only re-hang and double the latency), a connect-timeout may retry once on a
fresh connection (the pooled addr may have been bad), and the stale-CLOSE path
(EOF/broken pipe on a pooled connection the upstream idle-closed) reconnects+retries
once — a timeout is deliberately NOT the stale-close path, so a timeout never
becomes an infinite (or even doubled) retry loop. The timeout values are fixed
host defaults right now: about 5s connect and about 30s read/write. Production
tuning of exact values and per-route timeouts belongs in Form-visible router
configuration. The ONE `fanout_stream_to_client` shape
is preserved — the timeouts are deadlines set on the stream plus the error
classification, not a second fan-out path; a timeout on the HEAD read becomes a
buffered 504 (the client head is still unwritten), and the head-read retry stays the
single safe retry point.
**Native JSON responses**: a native handler can now serve a full JSON object
byte-identical to a FastAPI route's response, not just a scalar string. Two small
universal pieces made the gap closable: the `value_str` native renders ANY value
through `Value::display()` (so a Float renders Python-style — `0.8125`, `1.0` —
where `int_to_str` would truncate it and `str_concat`'s `as_str` would panic on a
non-string), and `handle_request` serves a native body that opens with `{` or `[`
as `Content-Type: application/json` (a scalar handler opening with neither keeps
the `text/plain` default). A handler builds the exact response document in Form
by `str_concat`-ing the JSON — no spaces, matching FastAPI's
`separators=(",",":")` — and the route returns the same body AND type its CPython
twin did, while `X-Form-Router: native-kernel` still tells the honest provenance.
This is what lets a route be PROMOTED from the fan-out tail to native without the
client seeing any difference. (See *Production routes*, below.)

The remaining rows (chunked transfer, a structural JSON→Form parse on the REQUEST
side, streaming, per-route timeout config + circuit-breaking, TLS/lifecycle,
observability) are still open breaths.

## The Source-Language Preference

Native handlers and the routes manifest are **Form-native tissue, not
Python-cross-compiled**. The preferred route entry is now the route-language
surface (`section [form.route]`) because it names the actual domain: route cells,
request/response contracts, handlers, and selection data. Once a manifest is
loaded, there is no dialect-specific route class and no separate runtime: BML,
Form, Python, TypeScript, Go, C#, and future language surfaces are entry tongues
for Form-native recipes over Form-native cells.

The high-level route surface is not a Rust build — it already lives in
Form-stdlib. `form-stdlib/source-compiler.fk` lowers a `section [form.route]
{ ... }` block into Form Recipe objects. The router reuses that compiler
directly: `serve --routes <manifest> --stdlib
form-stdlib` SOURCE-COMPILES a source manifest **at load** (the manifest needs
source lowering iff it opens a `section [...]` block), in the main thread before any worker spawns,
through the four form-stdlib preludes (`json.fk` + `cache.fk` +
`form-ontology-loader.fk` + `source-compiler.fk`) into one in-memory Form Recipe
object graph. The router carries `RouteProgram::RecipeObject` by `Arc`; workers
clone the compiled graph with `readonly_worker_clone()` and walk the same root
`NodeID` in their own `Kernel + Arena`. No route-runtime serialization,
deserialization, lowered route source, or sidecar is required. The remaining
copy is the worker-local kernel graph, kept for isolated mutable execution state.
For `/health`, the route source is a `RouteCell<KernelHTTPRequest,
KernelHTTPResponse>` template/class hierarchy. `HealthRoute.handle(request)` is
lowered to the executable Form closure, and `route = route_data(health,
handle);` keeps method/path/priority/budget in
`deploy/kernel-router/production-routes-data.json`.
A raw S-expression manifest is unchanged: it has no `section [...]`, so it never
touches the source-compiler and `read_root_from_source` reads it directly.

Honest scope of the route authoring path: the `form.route` dialect lowers
readable `template` blocks with members, route `class` blocks with methods, `def
name(args) = expr;` (single-line), the block form `def name(args) { ... }`,
nested `if c then a else b`, `f(a, b)` calls, and integer, string, AND float
literals. Values cross the in-memory Recipe artifact intact. A float
trivial node carries its IEEE-754 value in the wire format (a dedicated
`FORM_BINARY_FLOAT64` node tag followed by 8 little-endian bytes), so the value
travels in the bytes and each kernel re-interns it into its own overflow table
on read — the per-kernel table index never crosses the wire. The artifact
round-trip is bit-identical across Rust, Go, and TS
(`form-samples/float-artifact-roundtrip.fk`). An S-expression manifest serves
floats the same way — the kernel's `.fk` source reader reads float tokens
directly (the existing `router-proof.fk`'s 0.8125 coherence-weight is one).

Either way the handler is Form, walked by the kernel — never a Python function
the kernel calls. That is the point of the reversal: the front door speaks the
body's own tongue, and now it can be authored in the body's own surface syntax,
lowered by the body's own compiler.

## The migration path — runtime-share, not route-count

The flip is incremental and reversible at every step:

1. **Kernel-router in front, owning a FEW native routes, fan-out for the rest.**
   The 23 compute cores that already run on the kernel are the first native
   handlers; the other ~762 routes fan out to the unchanged FastAPI app. From
   the visitor's side nothing changes; from the body's side the front door has
   moved.
2. **Native coverage grows.** Each route whose compute core is already a Form
   recipe (the `serve_via_kernel` routes) becomes a manifest entry. The
   readiness map in `API_KERNEL_READINESS.md` is the queue.
3. **The CPython surface shrinks** as routes move from fan-out to native — the
   tail the kernel proxies gets shorter.

**The metric that matters is runtime-SHARE moving to the kernel, not
route-count.** A handful of hot routes can carry most of the request volume; a
long tail of rarely-hit admin routes can stay CPython indefinitely with no cost.
The honest measure is *fraction of requests (and of CPU-time) served natively*,
which the `X-Form-Router` header makes directly countable from access logs.

### COMPARE mode — the zero-risk shadow diff before any cutover

Promoting a route from fan-out to native is reversible, but it is still a *change
of who computes the answer*. COMPARE mode removes the leap entirely: the
kernel-router runs in front with native routes active, but instead of a one-time
flip from CPython to the kernel it **self-compares every native route against
CPython on live traffic and returns CPython's (safe) response** — so divergence,
latency, and downtime are measured against production traffic *before* the cutover.

A **single env flag** — `COH_ROUTER_COMPARE`, read once at startup (`cli_serve`),
threaded into `handle_request` like `upstream` — couples *compare* and
*which-response-to-return*:

- **`COH_ROUTER_COMPARE=1`** (validation): a native route serves from the kernel
  (timed → `native_ms`), then the **same** request is shadow-fanned-out to the
  CPython upstream over the same keep-alive `UpstreamPool` and its full response
  **captured into memory** (timed → `cpython_ms`). The two are compared
  byte-for-byte; one greppable `[compare]` line is logged to stdout (a bounded diff
  snippet on a mismatch); and **CPython's response is returned** — zero behavior
  change (the safety property). A shadow fan-out failure falls back to the native
  response (a shadow hiccup must never 5xx the user) and logs `compare_fanout_failed`.
  Every response carries **`X-Form-Compare: matched | mismatch | cpython_error`**
  alongside `X-Form-Router: native-kernel`, so a monitor reads per-request verdicts
  without parsing logs.
- **`COH_ROUTER_COMPARE` unset** (the default *and* the post-validation cutover
  state): the native arm is **unchanged** — serve native, return native, no fan-out,
  no overhead. **The cutover is literally turning compare off.**

The buffered capture (`fanout_capture` → `read_body_fully`) reuses the streaming
fan-out's exact upstream hop (`parse_http_upstream`, the request build, the
stale-pool reconnect+retry, `connect_upstream_with_timeout`, `read_upstream_head`)
and differs only in the tail — it reads the whole (small, compute-route) body into
memory instead of piping it. The chunked path shares the streaming relay's
boundary-tracking `ChunkParser`, collecting the decoded payload through the same
engine (`feed_collecting`).

Reading divergence: the `X-Form-Compare` header per request, `grep [compare]` in
`docker logs`, or [`deploy/kernel-router/compare_summary.py`](../deploy/kernel-router/compare_summary.py)
to fold the log into a per-route table (count, mismatch, cpython_error, p50
native_ms vs cpython_ms). The full design, the one-flag toggle, and the safe
rollout live in [`deploy/kernel-router/COMPARE_MODE.md`](../deploy/kernel-router/COMPARE_MODE.md);
the mechanics are proven by `production_routes_harness.py --compare` (stub verdicts,
network-independent, + the real-app oracle).

COMPARE mode and the Traefik flip are **independent** reversible steps: run compare
behind a shadow port → watch the log clean → cut compare off → (separately) flip
Traefik onto the router. Each rolls back on its own.

## Proof-of-shape — what is demonstrated, and what it is not

A family of harnesses proves the shape against a mock CPython upstream — routing,
concurrency, body-reading, keep-alive, and header passthrough; another
([below](#proof-against-the-real-fastapi-app--not-a-mock)) proves it against the
**real FastAPI app** (the header-passthrough harness proves both ways — the mock
echo upstream for request-header observability, the real app for the
content-type relay). Start with the mock harnesses — they isolate each property —
then read the real-app proof for the flip-decision evidence. The full list lives
in [Sources](#sources).

[`form/form-kernel-rust/router_proof_harness.py`](../form/form-kernel-rust/router_proof_harness.py)
spins up a mock CPython upstream (standing in for FastAPI — so the proof touches
NO production routing) and the kernel-router fanning out to it, then exercises
both arms:

```
[native ] /health                            -> 200 'ok'      X-Form-Router=native-kernel  OK
[native ] /coherence_weight                  -> 200 '0.8125'  X-Form-Router=native-kernel  OK
[native ] /count_signals?values=0.5,0.75,1.0 -> 200 '3'       X-Form-Router=native-kernel  OK
[fanout ] /api/ideas                         -> 200 via CPython X-Form-Router=fanout-python OK
[fanout ] /api/whatever/deep/path            -> 200 via CPython X-Form-Router=fanout-python OK

native /coherence_weight over 200 reqs: p50=0.163 ms  p99=0.244 ms  min=0.101 ms
```

**Shown (measured, not asserted):** the kernel OWNS the front door; it routes
each request; it serves native routes entirely in Form with no CPython in the
path (real float arithmetic and input-driven string computation, not echoes);
it fans out the tail to a CPython upstream over a real HTTP hop; sub-millisecond
native latency (whole-request wall time including the loopback socket — the Form
value-walk is a sub-fraction).

[`form/form-kernel-rust/router_concurrency_harness.py`](../form/form-kernel-rust/router_concurrency_harness.py)
proves the worker pool under concurrent load — the load-bearing concurrency row
above. It fires 50 parallel clients and measures three properties:

```
[no-bleed ] 50 parallel clients, each a DISTINCT input -> ALL got their OWN correct value (k commas -> k+1). No cross-request state bleed.
[  1 worker] 600 reqs @ 50 parallel:    113.3 req/s  p50=437.94 ms  p99= 470.00 ms  correct=600/600
[ 8 workers] 600 reqs @ 50 parallel:    555.1 req/s  p50= 84.02 ms  p99= 111.53 ms  correct=600/600
speedup (8 workers / 1 worker): 4.90x throughput under 50-way concurrent load
```

**Also shown (measured):** the pool serves correctly under 50-way concurrency;
each worker's isolated `Kernel + Arena` means concurrent requests with DIFFERENT
inputs each return their OWN correct value with no cross-request state bleed (the
critical correctness property of a per-worker-kernel pool); and N workers deliver
multiples of single-worker throughput on CPU-bearing concurrent load (the single
worker serializes the value-walks; the pool parallelizes them across cores).

[`form/form-kernel-rust/router_body_harness.py`](../form/form-kernel-rust/router_body_harness.py)
proves the request-body row above — the matured serve primitive reads bodies, not
just GET tails:

```
[native POST form ] /sum a=40&b=2          -> 200 '42'    router=native-kernel  OK
[native POST json ] /echo_len (36B JSON)   -> 200 '36'    router=native-kernel  OK
[native POST >8KiB] /payload_len (20008B)  -> 200 '20000' router=native-kernel  OK
[native GET       ] /health                -> 200 'ok'    router=native-kernel  OK
[fanout GET       ] /api/whatever          -> 200 via CPython router=fanout-python OK
[fanout POST body ] /api/echo (body fwd)   -> 200 via CPython router=fanout-python OK
[flows past old cap] payload 1.2 MiB (>1 MiB) -> 200 'len=1248568' router=native OK
[shape > recipe    ] declared CL=72 MiB       -> 413, body names shape+recipe   OK
```

**Also shown (measured):** a native POST handler reads form-urlencoded body
fields through the SAME alist a GET handler reads query params from (`a=40&b=2`
→ `42`); a JSON body is captured raw under `__body__` and handed to Form (the
36-byte JSON's length comes back); a body **larger than the initial 8 KiB read**
is fully captured across multiple reads honoring Content-Length (a 20 KB field
value returns its exact length — the correctness property the old single-buffer
read failed); GET is unchanged on both the native and fan-out arms; a POST that
fans out carries its body to the upstream (the mock CPython echoes the forwarded
`hello=world&n=7`); a body past the OLD 1 MiB cap now FLOWS under the generous
default shape (a 1.2 MiB field returns its exact length — circulation welcomed,
not walled); and a shape past the current threshold is answered OBSERVABLY — a
~69 MiB declared Content-Length gets a 413 whose body names the bytes seen, the
threshold we hold this moment, and the router configuration recipe that must grow
or stream — sensed on the Content-Length header alone, never buffered.

## Proof against the REAL FastAPI app — not a mock

The three harnesses above fan out to a mock CPython upstream. The flip-decision
question is sharper: does the kernel-router work in front of OUR actual app?
[`form/form-kernel-rust/router_real_app_harness.py`](../form/form-kernel-rust/router_real_app_harness.py)
answers it. It boots the **real `app.main:app`** under uvicorn on a test port
(`COH_ENV=dev`, the sqlite fallback DB — 816 routes, the genuine app, not a
stand-in), stands the kernel-router in front of it
([`router-real-app-proof.fk`](../form/form-kernel-rust/examples/router-real-app-proof.fk):
one native route, the rest fan out), and exercises both arms end-to-end against
the live app. This is a LOCAL side-by-side proof on throwaway ports — the
production front door is untouched.

```
real app /api/health                  -> 200  status='ok' version='1.0.0' kernel_runtime='subprocess'  REAL FastAPI
real app /api/utils/weighted_average  -> 200  average=0.8125 runtime='subprocess'  (the oracle)

[native  ] /api/utils/weighted_average -> 200 '0.8125' X-Form-Router=native-kernel
           kernel-router native value 0.8125 == real-app value 0.8125  -> MATCH
[fanout G] /api/health                 -> 200 X-Form-Router=fanout-python  (real health JSON: status='ok' version='1.0.0')
[fanout P] /api/cc/exchange/quote      -> 200 X-Form-Router=fanout-python  (real quote: quote_id='1ad6ce783c33' rate=1.0)

native  /api/utils/weighted_average THROUGH kernel-router (Form)        p50= 0.197 ms  p99= 0.272 ms
native  /api/utils/weighted_average via app serve_via_kernel guest      p50=10.983 ms  p99=12.819 ms
fan-out /api/health DIRECT on FastAPI                                   p50= 4.432 ms  p99= 5.302 ms
fan-out /api/health THROUGH kernel-router proxy                         p50= 4.732 ms  p99= 6.166 ms

proxy-hop overhead (fan-out):  +0.300 ms  (+6.8% of the direct call)
native-route saving:           +10.79 ms  (the native route skips the whole CPython request lifecycle — ~56x faster)
```

**Shown against the real app (measured, not asserted):** the kernel-router
serves `/api/utils/weighted_average` **entirely in Form** — it parses the
`values`/`weights` query args and runs the real `sum(v*w)/sum(w)` arithmetic in
the kernel (the `str_to_float` leaf native, the float sibling of `str_to_int`,
is what lets it parse arbitrary float inputs rather than serve a constant) — and
its value **equals the live app's answer** for the same route (the app computes
it via `serve_via_kernel`; the kernel-router computes the same answer with no
CPython in the path). It **fans out** `/api/health` (GET) and
`/api/cc/exchange/quote` (POST, body forwarded) to the real FastAPI, relaying
**genuine app responses** — the real health JSON (status/version/uptime/
kernel_runtime) and a real exchange quote (a server-issued `quote_id` + rate),
not a mock marker. The numbers are the honest input to the flip decision: the
**proxy hop costs ~0.2–0.3 ms (~3–7%)** on a fan-out route — a real localhost TCP
hop over the kernel's HTTP/1.1 keep-alive connection to the upstream (reused, no
per-request handshake), the price of fronting; the **native route saves
~10.8 ms (~56x)** by skipping the entire CPython request lifecycle (uvicorn
parse → routing → Pydantic bind → `serve_via_kernel` subprocess spawn →
response model), serving the value-walk directly. A hot native route is far
cheaper than the same compute reached through the CPython doorway; the tail pays
a small, measured proxy toll to keep working unchanged.

**NOT shown / not claimed:** full production-readiness. The server serves
HTTP/1.1 with keep-alive on BOTH hops: the client→router hop (proven by
`router_keepalive_harness.py` — multiple requests on one connection, `Connection`
honored both ways, idle-timeout reaping, pipelining bytes carried) AND the
router→upstream fan-out hop (proven by `router_upstream_reuse_harness.py` against
a connection-counting upstream — N fan-outs through one worker land on ONE
reused upstream connection, distinct requests on it each read their OWN
Content-Length-framed response with no bleed, and a stale pooled connection is
transparently reconnected+retried). The fan-out hop passes headers both ways with
hop-by-hop hygiene (proven by `router_header_passthrough_harness.py` — the
client's Authorization/Cookie/Accept/X-\* reach the upstream with Host rewritten
and hop-by-hop stripped, the router writing its own `Connection: keep-alive`; the
upstream's Content-Type/Set-Cookie/Cache-Control reach the client; verified
against the REAL FastAPI app, whose `/api/health` relays as `application/json`
rather than the old flattened text/plain). The fan-out hop also BOUNDS a hung
upstream (proven by `router_fanout_timeout_harness.py` against a deliberately-hung
upstream that accepts the connection but never responds — the router returns a clean
504 Gateway Timeout at ~one read deadline and frees the worker; an unreachable /
blackholed upstream returns a clean 504/502 rather than hanging; with N workers a
hung fan-out occupies ONE worker for at most the connect+read timeout while the rest
of the pool keeps serving 20 native requests in milliseconds — the pool is NOT
starved; a read-timeout returns 504 ONCE, not reconnect+retried). The fan-out path
STREAMS the upstream response body straight to the client — the body is NEVER held
whole. Only the small response HEAD is buffered (to parse status + framing +
relayed headers); the body is then piped in a fixed 64 KiB chunk reused across
reads (Content-Length echoed and the body relayed exactly, or `Transfer-Encoding:
chunked` relayed through to the true terminating 0-length chunk, or close-framed and
piped to EOF). This is proven by `router_body_harness.py`: a 16 MiB Content-Length
body relays BYTE-IDENTICAL (sha256 over all 256 byte values — the raw-byte relay
also fixes the old `String::from_utf8_lossy` round-trip that would have corrupted
bytes ≥ 0x80), and — the load-bearing proof the buffer is GONE — that SAME 16 MiB
body still relays 200 byte-identical through a router whose response shape-threshold
is only 1 MiB; under the old buffered code that exact threshold 502'd the body
(`upstream response shape is 16777216 bytes — larger than we can hold`, observed
directly against the origin/main binary). Streaming dissolves the size gate: the
body never occupies a worker-memory buffer, so its length is no longer a ceiling.
The REQUEST body is still buffered before the fan-out (a named-next breath — request
streaming); on that request side, and for the small response head, the
**awareness-shape** still governs — the largest shape a worker holds in memory, a
generous fixed default (64 MiB) named as a common recipe that should next move
into Form-visible router configuration (the response threshold now bounds the
HEAD alone). This is awareness, not prevention: the shape
is observed first, and one larger than we can hold right now is answered
*observably* — the response names the bytes seen, the threshold we hold this moment,
and that it is a recipe we can change together — never a silent wall. The earlier
1 MiB-request / 64 MiB-response split carried the inherited fear posture ("a request
body is untrusted client input"), untrue in this space where the sender is us and
circulation is welcome the moment its shape can be observed. That old asymmetry's
1 MiB ceiling on the *response* side had 502'd the real
`/api/concepts/domain/living-collective`
(≈1.7 MB Content-Length-framed JSON) with `upstream response body too large` while
api served it 200 direct — the blocker the 2026-06-03 live flip surfaced. Raising
the cap (PR #2413, on main at 32d1cadd) first relieved that route in shadow on the
production VPS (1.7 MB relayed 200, byte-identical, ~2–4 ms proxy hop); streaming now
removes the ceiling entirely — a body of any size relays without a whole-body buffer.
"Byte-identical" holds for the real large routes, not only the small ones. Still
open: STREAMING the REQUEST body (the response streams; the request body is still
buffered before the fan-out), chunked-body POOL reuse (a chunked upstream response
relays through but its connection is not pooled), per-route timeout config +
circuit-breaking and retries beyond the single stale-connection / connect-timeout
retry, and the accept loop is thread-per-connection-blocked (it parallelizes to the
worker count, not an async reactor; a worker serving a keep-alive client is held
until that connection closes or times out). JSON bodies are raw-captured, not
structurally parsed into Form values. The real-app proof ran against the dev sqlite
DB; the production deployment shape (TLS/Traefik front, the routes.fk covering the
real native-eligible set) is the remaining build.
Concurrency, request-body reading, **bidirectional header passthrough**, the
**real-app fan-out + native side-by-side**, **HTTP/1.1 keep-alive on the
client→router hop**, **upstream connection reuse on the fan-out hop**,
**fan-out timeouts (hung upstream → 504, worker freed, pool not starved)**, and
**RESPONSE STREAMING (the upstream body piped straight to the client, byte-identical,
never held whole — incl. a chunked relay through the true 0-chunk and a 16 MiB body
flowing past a 1 MiB threshold)** are now shown; REQUEST-body streaming and
structural-JSON are the rest.

## Production routes — the first promotions, byte-identical to the live api

The real-app proof above runs ONE native route returning a scalar value. The
PRODUCTION manifest
[`deploy/kernel-router/production-routes.fk`](../deploy/kernel-router/production-routes.fk)
takes the next step the durable flip needs: it PROMOTES the cleanly-promotable
`/api/utils` compute routes (scalar/list-in → flat-JSON-out) from the fan-out tail
(served by CPython) to NATIVE (served entirely in Form), each returning the **full
JSON response object** its FastAPI twin returns — byte-for-byte. These are the
routes whose Form computation is already parity-proven against CPython by the
three-way kernel suite (`endpoint_<name>_demo.fk`); promotion replicates their FULL
HTTP contract — the exact query params with the exact FastAPI defaults, the
arithmetic in Form, and the exact response document. Fifteen routes are promoted
today (the first four scalar/list computes, six pure-numeric scoring/entropy
routes, `grounded_value` — the value/realization/confidence reduction of
`compute_idea_metrics`, eleven host-derived scalars folded to four floats — then
the grounded family: `cost_vector` / `value_vector` (CC decompositions via
`round_ndigits`), `grounded_roi` (max-as-comparison + guarded division), and
`idea_grounded_cost_sum` (the LEFT-folded float-field sum over parallel arrays)).

| Promoted route | params | response shape |
|----------------|--------|----------------|
| `/api/utils/coherence_weight` | `values` (csv ints), `threshold` (int) | `{"weight":<int>,"values":[…],"threshold":<int>,"runtime":"inline"}` |
| `/api/utils/nodeid_distance` | 8 NodeID coords (ints) | `{"distance":<int>,"a":[…4],"b":[…4],"runtime":"inline"}` |
| `/api/utils/nodeid_compatibility` | 8 NodeID coords (ints) | `{"compatibility":<0..4>,"a":[…4],"b":[…4],"runtime":"inline"}` |
| `/api/utils/weighted_average` | `values`, `weights` (csv floats) | `{"average":<float>,"values":[…],"weights":[…],"runtime":"inline"}` |
| `/api/utils/simpson_diversity` | `counts` (csv ints) | `{"diversity":<float>,"counts":[…],"runtime":"inline"}` |
| `/api/utils/idea_score` | `potential_value` `confidence` `estimated_cost` `resistance_risk` (floats) | `{"score":<float>,…echoes,"runtime":"inline"}` |
| `/api/utils/marginal_cc_return` | `pv` `av` `conf` `ec` `ac` `rr` (floats) | `{"marginal_return":<float>,…echoes,"runtime":"inline"}` |
| `/api/utils/breath_balance` | `gas` `water` `ice` (ints) | `{"balance":<float>,"gas":<int>,"water":<int>,"ice":<int>,"runtime":"inline"}` (incl. `-0.0`) |
| `/api/utils/shannon_entropy` | `gas` `water` `ice` (ints) | `{"entropy":<float>,"gas":<int>,"water":<int>,"ice":<int>,"runtime":"inline"}` (round 4) |
| `/api/utils/softmax_weights` | `scores` (csv floats), `temperature` (float) | `{"weights":[…],"scores":[…],"temperature":<float>,"runtime":"inline"}` |
| `/api/utils/grounded_value` | 11 scalars (`lineage_measured_value`, `usage_revenue`, `spec_*`, `*_count` ints, `has_*` levels) | `{"computed_actual_value":<float>,"computed_estimated_cost":<float>,"value_realization_pct":<float>,"computed_confidence":<float>,"runtime":"inline"}` |
| `/api/utils/cost_vector` | `estimated_cost` (float) | `{"compute_cc":<float>,"infrastructure_cc":<float>,"human_attention_cc":<float>,"opportunity_cc":0.0,"external_cc":0.0,"total_cc":<float>,"estimated_cost":<float>,"runtime":"inline"}` (each `round(_,4)`) |
| `/api/utils/value_vector` | `potential_value` (float) | `{"adoption_cc":<float>,"lineage_cc":<float>,"friction_avoided_cc":<float>,"revenue_cc":0.0,"total_cc":<float>,"potential_value":<float>,"runtime":"inline"}` (each `round(_,4)`) |
| `/api/utils/grounded_roi` | `estimated_cost` `actual_cost` `potential_value` `actual_value` (floats) | `{"remaining_cost_cc":<float>,"value_gap_cc":<float>,"roi_cc":<float>,…echoes,"runtime":"inline"}` (guarded division) |
| `/api/utils/idea_grounded_cost_sum` | `actual_costs` `actual_values` (parallel csv floats) | `{"spec_actual_cost_sum":<float>,"spec_actual_value_sum":<float>,"spec_count_in":<int>,"runtime":"inline"}` (LEFT-fold) |
| `/api/utils/grounded_cost` | 5 csv arrays (spec/lineage floats, commit ints) + `runtime_cost`; paired arrays must match length | `{…6 cost floats, 3 counts, "runtime":"inline"}` on the happy path, or **422 `{"detail":"…"}`** (the handler's observable "no") on a length mismatch |
| `/api/utils/worldview_alignment` | `contributor_vec` `idea_vec` (parallel csv floats), `axis_names` (csv strings); the two vectors must match length | `{"score":<float>,"matched_axes":["…"],"contributor_vec":[…],"idea_vec":[…],"runtime":"inline"}` (cosine via `math_sqrt`), or **400 `{"detail":"…"}`** (the handler's observable "no") on a length mismatch |
| `/api/utils/tag_match_score` | `contributor_tags` `idea_tags` (csv strings) | `{"score":<float>,"contributor_tags":["…"],"idea_tags":["…"],"runtime":"inline"}` (`str_eq` membership ratio over first-seen-deduped lists; 0.5 empty-guard) |
| `/api/utils/coherence_summary_score` | `task_count` `target_state_count` `evidence_count` `task_card_count` `task_card_scores_len` (ints), `task_card_scores_sum` (float) — all host-extracted scalars | `{"score":<float>,"task_count":<int>,"target_state_coverage":<float>,"task_card_coverage":<float>,"task_card_quality":<float>,"evidence_coverage":<float>,"runtime":"inline"}` (`safe_ratio` coverages + `clamp01` weighted score, each `round(_,4)`) |
| `/api/utils/idea_marginal_from_record` | `pv` `av` `conf` `ec` `ac` `rr` (floats) — the 6 record fields pre-extracted by the host | `{"marginal_return":<float>,"idea":{…6 floats},"runtime":"inline"}` (Method-B marginal CC, `round(_,6)`; the echoed `idea` is a fixed-shape dict[str,float] built from the params) |
| `/api/utils/idea_grounding_summary` | `event_counts` (csv ints via `int(float(x))`), `actual_values` (csv floats) — two parallel scalar-lists | `{"spec_count":<int>,"total_event_count":<int>,"specs_with_value_count":<int>,"max_event_count":<int>,"spec_count_in":<int>,"runtime":"inline"}`, or **422 `{"detail":"…"}`** (the handler's observable "no") on a length mismatch |
| `/api/utils/concept_match_score` | `idea_name` `idea_description` `concept_name` `concept_description` (strings), `concept_keywords` (csv strings) — ASCII text | `{"score":<float>,"keywords":["…"],"concept_keywords":["…"],"runtime":"inline"}` (the WHOLE pipeline native: the `re.findall(r"\b[a-zA-Z]{3,}\b", …)` tokenizer via `scan_run`+boundary test, 67-word stopword drop + first-seen dedup, then `_score_concept`'s bidirectional `str_find` membership fold; empty-keyword bag → `score 0.0, keywords []`) |

Each handler parses its query params from the request alist (a recursive
`split_commas` over the kernel's `str_find`/`substring`, then `str_to_int` /
`str_to_float`), runs the same math the demo recipe runs, and builds the response
JSON by `str_concat`-ing the document with no spaces (matching FastAPI's
`separators=(",",":")`), `value_str` rendering each number Python-style. The
serve path stamps `Content-Type: application/json` and `X-Form-Router:
native-kernel`.

[`form/form-kernel-rust/production_routes_harness.py`](../form/form-kernel-rust/production_routes_harness.py)
proves the promotion two ways at once — boot the real local app as the CPython
oracle, stand the kernel-router (production manifest) in front, and for each of
the twenty-two routes over representative + edge params (109 cases):

```
[native  ] /api/utils/coherence_weight -> {"weight":16185,…,"runtime":"inline"}  X-Form-Router=native-kernel  application/json
           value-contract == local CPython oracle: MATCH   (native runtime='inline', dev-app runtime='subprocess')
           FULL-BODY     == LIVE  https://api.coherencycoin.com: BYTE-IDENTICAL
[native  ] /api/utils/breath_balance?gas=5&water=0&ice=0 -> {"balance":-0.0,…}  FULL-BODY == LIVE: BYTE-IDENTICAL
[native  ] /api/utils/softmax_weights?scores=0.1,0.2,0.3 -> {"weights":[0.3006096053557273,…]}  FULL-BODY == LIVE: BYTE-IDENTICAL
[native  ] /api/utils/cost_vector?estimated_cost=33.333 -> {"human_attention_cc":8.3332,…}  round_ndigits half-to-even (NOT 8.3333)
[native  ] /api/utils/idea_grounded_cost_sum?actual_costs=0.1,0.2,0.3&… -> {"spec_actual_cost_sum":0.6000000000000001,…}  LEFT-fold matches CPython sum()
[native  ] /api/utils/worldview_alignment?contributor_vec=1.0,1.0,0.0&idea_vec=1.0,0.0,0.0 -> {"score":0.7071067811865475,…}  cosine 1/sqrt(2), three-way bit-identical
[native  ] /api/utils/tag_match_score?contributor_tags=a,b,c&idea_tags=a -> {"score":0.3333333333333333,…}  str_eq membership ratio, float÷int
[native  ] /api/utils/coherence_summary_score -> {"score":0.665,"task_count":10,…,"task_card_quality":0.75,…}  safe_ratio coverages + clamp01 weighted score
[native  ] /api/utils/idea_marginal_from_record?pv=10&av=0&conf=1&ec=1&ac=5&rr=0 -> {"marginal_return":100.0,"idea":{"potential_value":10.0,…},…}  remaining_cost floor 0.1, idea dict echoed
[native  ] /api/utils/idea_grounding_summary?event_counts=3,0&actual_values=1.5 -> 422 {"detail":"event_counts and actual_values must have the same length"}  observable "no"
[native  ] /api/utils/concept_match_score?idea_name=Energy%20FLOW%20energy&idea_description=Coherence%20coherence -> {"score":0.95,"keywords":["energy","flow","coherence"],…}  in-Form tokenizer (lowercase + first-seen dedup), byte-identical to re.findall
… all 109 cases, incl. adversarial floats (0.14000000000000004, 0.04000000000000001,
  0.6666666666666667, 0.9999999999999999), CPython's -0.0 vs +0.0 on single-phase
  entropy, the grounded_value confidence weighted-sum's float-assoc artifact
  (0.42000000000000004, 0.5800000000000001) and its [0.05, 0.95] clamp + zero-
  guards, deterministic + uniform softmax, the grounded family's round_ndigits
  half-to-even (8.3332, 16.6675), grounded_roi's guarded division + max-as-
  comparison, idea_grounded_cost_sum's LEFT-folded float-field sum, worldview_alignment's
  cosine (irrational 0.7071067811865475 + present-empty-vector → 0.5 zero-denom),
  tag_match_score's first-seen dedup + str_eq membership ratio (1/3 = 0.3333333333333333),
  and concept_match_score's in-Form tokenizer (scan_run alpha-runs + \b-boundary test +
  stopword/dedup, byte-identical to re.findall for ASCII) + bidirectional str_find score

native  (kernel-router, Form):   p50=0.241 ms  p99=0.343 ms
CPython (app serve_via_kernel):  p50=11.02 ms  p99=12.54 ms
-> native p50 is 45.7x faster than the CPython-served route (a fan-out adds the proxy hop ON TOP)
```

Two honest claims, kept distinct:

- **Value-identical to the local CPython oracle.** Every computed value and
  echoed input matches the dev app exactly. The dev app reports
  `runtime="subprocess"` (it shells to the kernel binary) while the native route
  emits `runtime="inline"`; `runtime` is environment-provenance, not part of the
  value the route computes, so the proof normalizes it out and compares the value
  contract. A real divergence surfaced and was fixed here: float `sum` is
  left-associated (the demo recipe's `i=0..n` loop and Python's `sum()` both fold
  left from `0.0`); a first right-folding recursion in `weighted_average`
  diverged on `0.1·0.7 + 0.2·0.2 + 0.3·0.1` (`0.14` vs `0.14000000000000004`)
  until the accumulator was made left-associated to match CPython bit-for-bit.
- **FULL-BODY byte-identical to the LIVE production api.** The production
  `/api/utils/*` endpoints report `runtime="inline"`, so the native route's
  ENTIRE response body — including the `runtime` field — is byte-for-byte what
  `https://api.coherencycoin.com` returns. This is the gold: a client cannot tell
  the difference between the promoted native route and production, while the
  `X-Form-Router: native-kernel` header carries the honest provenance.

The latency is the runtime-share payoff: a native route is **~43x faster** than
the same compute served through the CPython doorway (and a fan-out would add the
proxy hop on top of that CPython cost). Skipping the entire uvicorn → routing →
Pydantic-bind → `serve_via_kernel`-subprocess lifecycle is where the win lives.

**Promotability map.** The twenty-two promoted routes are scalar/list-in, scalar/list-out
with a flat JSON response — the cleanly-promotable subset. The first four are the
integer/float scalar+list computes; the next six (`simpson_diversity`, `idea_score`,
`marginal_cc_return`, `breath_balance`, `shannon_entropy`, `softmax_weights`) are
the pure-numeric scoring/entropy routes — same handler primitives plus the `math_log`
/ `math_exp` / `round_ndigits` natives their recipes already exercise (`breath_balance`
even reproduces CPython's `-0.0` on a single-phase distribution, byte-for-byte; the
work per route was authoring the param-parse + JSON-emit, not new kernel capability).
The eleventh, `grounded_value`, is the same flat shape one step deeper: eleven
host-derived SCALARS (the host pre-resolves the boolean-over-record `has_*` levels)
folded to four floats via `min2`/`max2`/`_plus`/`div`, the guarded ratio and
count→level zero-guards, the five-term weighted sum, and the `[0.05, 0.95]` clamp —
all from existing primitives. Its wire contract is all-scalar-in / flat-out, so it
needed NO structural marshalling (an earlier reading mislabeled it as nested — many
flat fields is not a nested object).

The next four — the grounded family — are the same flat shape. `cost_vector` and
`value_vector` decompose a single float into CC components, each `round(_,4)` via the
`round_ndigits` native (CPython-exact half-to-even — `ec=33.333` → `human_attention_cc
8.3332`, NOT 8.3333). `grounded_roi` folds three unlocks into one handler: max-as-
comparison (`max2`), `round_ndigits`, and a guarded division (`if remaining>0 …
else 0.0`, so the kernel never divides by zero). `idea_grounded_cost_sum` sums a float
field over two parallel CSV arrays with a LEFT-folded `_plus` accumulator seeded `0.0`
— the grouping that matches CPython's `sum()` to the bit (`0.1+0.2+0.3` →
`0.6000000000000001`, the adversarial-float proof that a right fold would fail). All
four are scalar/parallel-CSV-in, flat-out, from existing primitives — the work per
route was the param-parse + JSON-emit, not new kernel capability.

`grounded_cost` is now PROMOTED — it was the first route to need an OBSERVABLE "no":
a 422 on mismatched-length arrays. Native handlers can now return the first-class
`KernelHTTPResponse` cell via `kh-response(status, headers, body)`, so a handler
can emit exact status, `Content-Type`, filtered end-to-end headers, and body while
the router still owns `Content-Length`, `Connection`, and `X-Form-Router`. The older
status-bearing `(respond <code> <body>)` projection remains supported for existing
routes. `float_to_int` (truncate toward zero, exactly Python's `int(<float>)`)
gives the `int(float(x))` commit-int parse `str_to_int` couldn't (`"3.0"`/`"3.5"` → `3`).
`nonempty` skips empty segments (`if x.strip()`). Byte-identical on the happy path AND
on both 422s (verified hand-computed: defaults → `computed_actual_cost:7.75`; mismatch →
`422 {"detail":"…must have the same length"}`).

`coherence_summary_score`, `idea_marginal_from_record`, and `idea_grounding_summary`
are now PROMOTED — three routes an earlier reading mislabeled as "structured-record-in."
The *recipe twin* reaches into a record (`_get idea "field"`) or folds over a list of
records (`_iter specs`), but the *route's wire contract* takes SCALAR query params: the
host already pre-extracts the heterogeneous-collection walk into scalar counts/sums
before the recipe runs. So the native serve is scalar-in — tractable exactly like
`grounded_value`, NOT the structural-record problem (the same correction `grounded_value`
needed: the recipe's internal shape is not the route's wire shape). No new kernel
capability was needed — the natives (`safe_ratio`-via-`_plus`-float-promote, `clamp01` =
`max2`/`min2`, `round_ndigits`, `float_to_int`, the LEFT-folds, `respond`, `str_concat_all`)
already existed. `coherence_summary_score` runs `_coherence_summary`'s coverage/score
reduction from the host-extracted counts: four guarded `safe_ratio` coverages, a LEFT-nested
weighted sum (`0.35/0.30/0.20/0.15`) with the `task_count==0` neutral guard (`0.5`) and
`[0,1]` clamp, each output `round(_,4)` (only `score` is clamped — a coverage may exceed
`1.0`, rounded unclamped). `idea_marginal_from_record` runs the Method-B marginal CC from
the six pre-extracted floats, `round(_,6)`, and echoes the `idea` as a fixed-shape
`dict[str,float]` built by `str_concat_all` over `value_str` of each param (a known-key
nested object, NOT a structural parse). `idea_grounding_summary` folds four integer
grounding signals over two parallel CSV scalar-lists (`event_counts` via `int(float(x))` =
`ifloats_of`, `actual_values` via `floats_of`) — `spec_count`, `total_event_count`,
`specs_with_value_count` (the `>0` field predicate), `max_event_count` (seeded `0`) — with a
**422** observable-"no" (via `respond`) on a length mismatch, the same parallel-CSV shape as
`idea_grounded_cost_sum`. All three are byte-identical to the hand-computed CPython oracle
across representative + edge params (defaults, the neutral/quality/clamp/floor guards, the
`int(float)` truncation, the `1/3 = 0.3333` long-float, and the 422 path — verified against
the kernel-router booted standalone, curl output diffed to the oracle; the local FastAPI
app oracle does not boot in the degraded-network checkout, so the proof is hand-computed
like grounded_cost's 422 / worldview's 400).

`worldview_alignment` and `tag_match_score` are now PROMOTED — the two belief-resonance
routes whose string-collection gaps closed with two small, reusable additions. The
`json_str_list` helper renders a `list[str]` as a JSON string array (`["a","b"]`, no
spaces, each element quoted) — the echo shape both routes (and any future string-list
route) need. The `param_present`/`has_key` helpers mirror FastAPI's "default only when
the param is ABSENT": a `?k=` present-empty query value routes to the empty list (a
meaningful empty), NOT to the default — the distinction `param_or`'s empty→default
coalescing erased, observable on the empty-vector / empty-tag-list cases. With those,
`worldview_alignment` runs the COSINE in Form (the parallel dot+norm fold, `math_sqrt`
norms, guarded ratio, `[0,1]` clamp — irrational cosines like `1/sqrt(2)` three-way
bit-identical) and names `matched_axes` host-side-equivalently (the `cv>0.3 AND iv>0.3`
zip over `min(len(vec),len(names))`), with a **400** observable-"no" (via `respond`) on
a length mismatch; `tag_match_score` runs the `str_eq` membership ratio over first-seen-
order-deduped lists (the `tm_dedup` + `tm_member` fold), with the `0.5` empty-guard
(`1/3 = 0.3333333333333333`, float÷int, bit-exact). Both are byte-identical to the
CPython oracle across representative + edge params (verified by the harness against the
real app; the 400 hand-checked like grounded_cost's 422).

`concept_match_score` is now PROMOTED — the LAST `/api/utils` compute route, the
twenty-second native handler, completing the runtime-share compute spine. It is the
first route to fold a TEXT TOKENIZER into Form: the WIRE BODY echoes the tokenized
`keywords` (and the lowercased `concept_keywords`), so unlike `tag_match_score` — which
took already-host-tokenized tags — the whole pipeline (tokenize → assemble → score →
JSON) had to run native. The tokenizer is `_extract_keywords`'s
`re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())` + a 67-word stopword drop + first-seen
dedup; its kernel-native form needs NO new native — `scan_run` class 2
(`is_ascii_alphabetic`) yields each MAXIMAL ASCII-letter run, and a run qualifies iff
`len>=3` AND the byte BEFORE and the byte AFTER are not ASCII word bytes `[A-Za-z0-9_]`,
which is exactly what the `\b` anchors mean (a letter-run touching a digit or `_` carries
no word-boundary and is REJECTED ENTIRELY, not truncated: `"abc123"` → `[]`, `"abc_def"`
→ `[]`). Each run is lowercased via `ord`/`byte_to_str` (A-Z+32); the stopword drop +
dedup fold with `str_eq` membership. The score is `_score_concept` verbatim (the
bidirectional `str_find` membership fold, `0.5*forward + 0.3*reverse + name_bonus`,
`round(min(_,1.0),4)`), with the host's empty-keyword guard reproduced (all-stopword/short
idea → `score 0.0, keywords []`).

The honest scope is **ASCII**. `\b` is defined against Python's UNICODE `\w`: a non-ASCII
LETTER (`é`, `中`) IS `\w` (so `"abcé"` → `[]`), while non-ASCII PUNCTUATION (`—`, `€`) is
NOT `\w` (so `"abc—def"` → `[abc,def]`) — both encode as bytes `>=0x80` in UTF-8,
indistinguishable to a byte scanner without a full Unicode word-property table, a
disproportionate build for one route. So the native handler is byte-identical for ASCII
input — the SAME ASCII assumption every native handler here already makes
(`tag_match_score`'s plain-token tags, `split_commas`); non-ASCII idea/concept text falls
to the `serve_via_kernel` route + CPython upstream. The tokenizer was proven byte-identical
to `re.findall` over a **200,000-string ASCII fuzz** (0 mismatches) and the score float
repr to `json.dumps` over a **400-case fuzz** (0 mismatches); end-to-end the route is
byte-identical to the live `_extract_keywords` + `_score_concept` across the harness's 8
representative cases (defaults, no-overlap zero, the empty-keyword guard, mixed case +
dedup, the `>=3`-char filter + digit-adjacency rejection, name_bonus + the `1.0` ceiling
clamp, present-empty `concept_keywords`, long-float scores `0.95`/`0.9333`/`0.675`) —
verified by the harness against the real booted app.

This manifest is the durable flip's native surface, ready for the cutover; it does
NOT flip — the standing shadow still fans out every route.

## The flip — sensed to the bone, the decision is intent not permission

This is the **live request front-door for real visitors** — and the traffic is
real, if small: the production view-recorder shows **~3,600 view-events/day, a
few hundred/hour** (a mix of genuine visitors and the body's own self-sensing —
the aggregate can't cleanly split them, but it is *not* zero). So the caution
here is not old-programming worst-case; there is actual live dependency. That
is exactly why the flip's *intent* is Urs's — and why everything *under* the
intent is sensed here rather than left to guess.

**The production topology (sensed directly on the VPS, 2026-06-03):** Traefik
fronts everything (`traefik-traefik-1`), routing `Host(api.coherencycoin.com)`
→ the `coherence-api` service → the api container's port 8000 (one label rule in
`/docker/coherence-network/docker-compose.yml`:
`traefik.http.services.coherence-api.loadbalancer.server.port: "8000"`). The
flip inserts the kernel-router *between* Traefik and api: Traefik routes
`api.coherencycoin.com` → kernel-router → (fan-out) api:8000.

**The deployable artifact (built — the shadow step is now one intent away):**
the kernel-router is *proven* across the rungs above AND packaged as a standalone
deployable server. The Rust binary still ships inside the api container for the
inline-PyO3 path; alongside it there is now a **standalone kernel-router image +
shadow manifest + compose service** that runs `cli_serve` as a front door:

- [`Dockerfile.kernel-router`](../Dockerfile.kernel-router) — a multi-stage image
  reusing `Dockerfile.api`'s proven `kernel-builder` (same `FROM
  rust:1.86-slim-bookworm`, same `cargo build --release --bin form-kernel-rust &&
  strip`), then a lean `debian-slim` runtime carrying ONLY the stripped binary,
  the form-stdlib (so a source manifest can be source-compiled later), and the
  shadow manifest. No Rust toolchain in the final image.
- [`deploy/kernel-router/shadow-routes.fk`](../deploy/kernel-router/shadow-routes.fk)
  — the shadow manifest: an EMPTY `(let routes (list))`. `build_route_specs`
  accepts an empty list (an empty list is a valid list, not an error), so ZERO
  routes are native and EVERYTHING fans out to `--upstream`. Proven by
  [`deploy/kernel-router/shadow_proof_harness.py`](../deploy/kernel-router/shadow_proof_harness.py):
  every path fans out byte-identically to hitting the upstream directly, with
  `X-Form-Router: fanout-python` on every response, and a POST body is forwarded.
- [`deploy/kernel-router/docker-compose.kernel-router.yml`](../deploy/kernel-router/docker-compose.kernel-router.yml)
  — a DEFINED-BUT-INACTIVE overlay service (build: `Dockerfile.kernel-router`,
  `--upstream http://api:8000`). It is a SEPARATE overlay the production deploy
  never includes, and its Traefik labels are **present but commented**, so
  merging it changes nothing about production routing.

So the flip is **not** a from-scratch build — the shadow image exists and serves.
What remains is the Traefik re-point (uncomment one label set, drop the api
service's own rule), which is Urs's **intent**.

**The staged, reversible shape (the image now exists):**
1. **Shadow** — kernel-router fans out *everything* to api, serves *zero* native
   routes. Traefik points at it. Behavior is byte-identical to today (every
   request still served by FastAPI, via one proxy hop), but now the
   `X-Form-Router` header on every response gives live evidence the router
   carries real traffic. The only added risk is the hop itself (kernel-router
   process down = api traffic down until rollback).
2. **Promote routes one at a time** — flip each already-parity-proven
   kernel-eligible route (the 22 transmuted today) from fan-out to native;
   each is 56× faster (native Form, no CPython lifecycle) and individually
   reversible.
3. **Rollback at any step** — revert the one Traefik label
   (`loadbalancer.server.port` back to `8000`, or the router rule back to the
   api service). Instant, single-line, no data migration.

**The measured tradeoff** (from the real-app harness): native routes **~56×
faster** than the CPython request lifecycle; the fan-out tail (the ~760
not-yet-native routes) pays **~+6%** for the extra proxy hop. One new container
in the hot path; the failure surface is that hop's uptime. *Measured again on the
production VPS against the real api* (see "Shadow on the production VPS" below):
the flip-shaped fan-out hop is at-or-below p50 noise — at or under that +6%
estimate — the proxy cost lost in FastAPI's own latency variance.

**The division:** the sensing (topology, insertion point, rollback, tradeoff,
live-traffic reality) AND the **kernel-router container image** that makes the
shadow step actually deployable are built — the image serves, the shadow manifest
fans out transparently, the compose service is defined-but-inactive. What is
*Urs's* is the **intent** — whether the body's front door should become the
kernel now, accepting one hot-path container and a +6% tail cost for the 56×
native gain and the runtime-share shift toward the kernel speaking the body's own
tongue. That is a stakes-and-vision question, not a permission gate; the artifact
under it is real, not a guess.

**Live flip attempted and rolled back — 2026-06-03 (the response-body cap is the gate).**
The intent was set; the flip ran on the production VPS. A `kernel-router` compose
service (image `kernel-router:shadow-host`, the proven shadow artifact) took over
the `coherence-api` Traefik router pointing at port 8080; the api service's labels
were commented to `traefik.enable=false` so api stayed up as the upstream. Traefik
re-pointed within seconds: `https://api.coherencycoin.com` served **through the
kernel** — `X-Form-Router: fanout-python` live on the public endpoint, `/api/health`
/ `/api/version` / `/api/ideas` (370 KB) / `/api/spec-registry` all 200, the witness
held with zero new silence across a 2–3 min watch, the container healthy with zero
restarts. Then a large route exposed the blocker: **`/api/concepts/domain/living-collective`
(≈1.7 MB Content-Length-framed JSON) returned `502 fan-out upstream error: upstream
response body too large`** through the kernel while serving `200` direct on api.
Per the rollback discipline (no debugging forward on the live front door), the
one-command restore (`cp docker-compose.yml.pre-flip-… docker-compose.yml &&
docker compose up -d api`) brought api's direct Traefik routing back — the
`X-Form-Router` header gone, the 1.7 MB route 200 again, the witness back to
breathing.

**The large-response path is verified on real prod — 2026-06-03.** PR #2413 (on
main at 32d1cadd) first gave the upstream response its own generous 64 MiB shape;
that has since folded into one request/response awareness-shape — a single
threshold, now fixed in the host until a Form-visible router configuration cell
owns it. The image was rebuilt
from main and run as a localhost-bound
shadow on the production VPS *beside* the live path — Traefik untouched, FastAPI
still the front door, the shadow routing zero visitor traffic. Through that shadow
the formerly-502'ing `/api/concepts/domain/living-collective` relays **200,
1,704,424 bytes, byte-identical to the upstream** (sha256 of the body matches
direct; `X-Form-Router: fanout-python` on the response), the proxy hop adding
~2–4 ms over direct on a body that size; the normal routes (health, version, ideas
at 370 KB) still relay with the router header. The 1.7 MB blocker that gated the
live flip is closed. The durable cutover is now gated only on the **re-flip
itself** — Urs's go, with presence — not on any remaining code fix. Today's front
door is FastAPI.

## Cross-references

- [`API_KERNEL_READINESS.md`](API_KERNEL_READINESS.md) — the topology this inverts; the queue of native-eligible routes.
- [`SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md`](SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md) — the deeper destination: the substrate as the runtime, of which the kernel-router is the request-handling face.
- [`README.md`](README.md) — the three sibling kernels; the router is the Rust kernel's front-door face.
- [`lc-native-kernel-binary`](../docs/vision-kb/concepts/lc-native-kernel-binary.md) — the native binary, its serve primitive, and the per-process / concurrency honesty this build must answer.
- [`lc-one-kernel-many-tongues`](../docs/vision-kb/concepts/lc-one-kernel-many-tongues.md), [`lc-the-kernel-knows-itself`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — the kernel speaking the body's own tongue and reading its own routing.

## Sources

- [`form/form-kernel-rust/src/main.rs`](../form/form-kernel-rust/src/main.rs) — `cli_serve` (the front-door listener, dispatching to the worker pool; binds `--host` × `--port`, default host `127.0.0.1` so a same-host harness is unchanged while a containerized front door binds `0.0.0.0` to be reachable across the boundary), `worker_loop` + `build_worker_kernel` (a worker's own `Kernel + Arena` with a raw Form source program or compiled source-language/Form Recipe object graph loaded per worker), `serve_connection` (the keep-alive loop — runs `handle_request` repeatedly on one `TcpStream` until close/EOF/idle-timeout, sets the `KEEPALIVE_IDLE_TIMEOUT` read-timeout, carries pipelined leftover bytes), `handle_request` (the single factored per-request serving shape, reading the full request + body and returning the keep-alive verdict), `head_keep_alive` (the `Connection`-header + HTTP-version keep-alive decision), `read_request` / `parse_content_length` / `parse_content_type` / `parse_request_body` (the Content-Length-honored read that carries over-read bytes forward, and the content-type body parse), `fanout_stream_to_client` (the STREAMING proxy arm — builds the upstream request, gets-or-creates the pooled connection, reads the response HEAD with the stale-pool reconnect+retry, writes the client response head, then PIPES the body straight to the client; pools the upstream connection IFF Length-framed and kept alive; on a pre-body failure emits a buffered 504/502, on a mid-body failure closes the client connection), `emit_buffered_fanout_error` + `fanout_error_response` (the pre-body fan-out failure -> buffered 504/502 mapping, reachable only while the client head is unwritten), `connect_upstream_with_timeout` (resolve the SocketAddr + `connect_timeout` + set the per-use read/write deadlines on the fan-out stream), `FanoutError` + `classify_io_error` (the retry-vs-504 classification: TimedOut/WouldBlock -> Timeout -> 504 never retried, BrokenPipe/Reset/EOF -> Closed -> stale-pool reconnect+retry once, else Other -> 502), `fanout_connect_timeout` / `fanout_read_timeout` (the fixed ~5s connect / ~30s read+write host defaults), `UpstreamPool` + `PooledConn` (the per-worker, lock-free upstream connection cache owned by `worker_loop` and threaded through `serve_connection` -> `handle_request`), `read_upstream_head` / `send_and_read_head` / `UpstreamHead` / `ResponseFraming` / `upstream_response_keep_alive` / `head_is_chunked` (read ONLY the response head — small, buffered to parse — and decide the body framing Length/Chunked/Close; the body is NOT read here, it streams), `stream_body_to_client` / `BodyOutcome` (pipe the body in a fixed 64 KiB chunk reused across reads, never holding it whole — Content-Length echoed and relayed exactly with over-read carried forward, chunked relayed raw through the true 0-chunk, unframed piped to EOF), `ChunkParser` + `parse_chunk_size` (the incremental chunk-boundary parser that finds the true terminating 0-length chunk so a `0\r\n\r\n` run inside chunk data never truncates the relay), `is_hop_by_hop` (RFC 7230 section 6.1 hop-by-hop set, now incl. `Proxy-Connection`), `http_response` (the buffered emit for native/404/error — HTTP/1.1 with accurate Content-Length, the `Connection` + X-Form-Router headers) / `write_response_head` (the streaming client head — same router-owned framing, with Content-Length / Transfer-Encoding: chunked / close-framing per the body that follows), `str_to_float` (the float-parsing leaf native that lets a native handler parse float query args, e.g. weighted_average's values/weights), `value_str` (render ANY value via `Value::display()` -> a Str — the float-correct leaf a JSON-emitting handler `str_concat`s into the response body, where `int_to_str` would truncate a Float; `handle_request` serves a native body opening with `{`/`[` as `Content-Type: application/json`, so a promoted route returns the same body AND type as its FastAPI twin).
- [`form/form-kernel-rust/examples/router-proof.fk`](../form/form-kernel-rust/examples/router-proof.fk) — the native-handler manifest (Form, not cross-compiled).
- [`form/form-kernel-rust/router_proof_harness.py`](../form/form-kernel-rust/router_proof_harness.py) — the end-to-end topology proof + native-latency measurement (mock upstream).
- [`form/form-kernel-rust/router_body_harness.py`](../form/form-kernel-rust/router_body_harness.py) — the request-body + response-streaming proof: a native POST handler reading form-urlencoded fields, a raw JSON capture, a >8 KiB body captured across reads, POST fan-out body forwarding, a body past the old 1 MiB cap now flowing under the generous fixed default shape, and a shape past the current threshold answered with an observable, named "no" (the bytes seen + the router configuration recipe that must grow or stream); then the streaming proofs — a 16 MiB Content-Length fan-out body relayed byte-identical, the same body relayed 200 byte-identical through a router whose response shape is only 1 MiB, a chunked response relayed through with its de-chunked body matching, an adversarial chunked body with `0\r\n\r\n` inside chunk data not truncated, and an unframed read-to-close response piped to EOF byte-identical (mock upstream).
- [`form/form-kernel-rust/examples/router-body-proof.fk`](../form/form-kernel-rust/examples/router-body-proof.fk) — the body-reading native-handler manifest (Form, not cross-compiled).
- [`form/form-kernel-rust/router_concurrency_harness.py`](../form/form-kernel-rust/router_concurrency_harness.py) — the worker-pool concurrency proof: 50 parallel clients, no cross-request state bleed, 1-worker vs N-worker throughput.
- [`form/form-kernel-rust/router_keepalive_harness.py`](../form/form-kernel-rust/router_keepalive_harness.py) — the HTTP/1.1 keep-alive proof (CLIENT→router hop): N sequential requests on ONE connection (Content-Length framed, distinct inputs, each correct), pipelined two-in-one-send (leftover bytes carried, none dropped), `Connection: close` honored, HTTP/1.0 default-close back-compat, idle-timeout reaping the connection (worker freed), an idle connection NOT starving the pool, and the per-request handshake saving (reused vs fresh connection). Mock upstream — no production routing.
- [`form/form-kernel-rust/router_upstream_reuse_harness.py`](../form/form-kernel-rust/router_upstream_reuse_harness.py) — the upstream connection reuse proof (router→UPSTREAM hop): against a connection-COUNTING mock upstream with `--workers 1`, N fan-outs land on ONE reused upstream connection (connections << requests — the handshake amortized); each of N DISTINCT requests on the reused connection reads its OWN correct Content-Length-framed response (no response-framing bleed, the classic proxy keep-alive bug proven absent); reused-vs-fresh-connect latency (the reused path opens 1 connection where close-each opens N); and a stale POOLED keep-alive connection (the upstream silently drops it after N requests) triggers a transparent reconnect+retry, never a client-facing error. Mock upstream — no production routing.
- [`form/form-kernel-rust/router_fanout_timeout_harness.py`](../form/form-kernel-rust/router_fanout_timeout_harness.py) — the fan-out TIMEOUT proof (router→UPSTREAM hop): against a deliberately-HUNG upstream that accepts the connection but never responds, the router returns a clean 504 Gateway Timeout at ~one read deadline (measured) and frees the worker — never an indefinite hang; an unreachable / blackholed upstream returns a clean 504/502 (connect-timeout) rather than blocking; with N workers a hung fan-out occupies ONE worker for at most the connect+read timeout while the pool keeps serving 20 native requests in milliseconds (the pool is NOT starved); a read-timeout returns 504 ONCE, not reconnect+retried (latency ~1x the read-timeout, not 2x — distinct from the stale-close retry path); and the happy path (native + responsive-upstream fan-out) is unaffected. The harness still reflects an older short-timeout testing hook; the live kernel now uses fixed host defaults until Form-visible router configuration owns those limits. Mock upstreams — no production routing.
- [`form/form-kernel-rust/router_header_passthrough_harness.py`](../form/form-kernel-rust/router_header_passthrough_harness.py) — the bidirectional header-passthrough proof: against a mock echo upstream, the client's end-to-end request headers (Authorization/Cookie/Accept/X-Probe/User-Agent + Content-Type on POST) reach the upstream with Host rewritten and the client Content-Length/Connection stripped, and the upstream's Set-Cookie/Cache-Control/custom headers relay back while its hop-by-hop Transfer-Encoding does not; against the REAL FastAPI app, `/api/health` relays with `Content-Type: application/json` (the upstream's real type, not text/plain) and a native route still serves text/plain in Form. Tears both upstreams down.
- [`form/form-kernel-rust/router_real_app_harness.py`](../form/form-kernel-rust/router_real_app_harness.py) — the REAL-app proof: boots `app.main:app` under uvicorn (dev sqlite), stands the kernel-router in front of it, proves native-in-Form (value == the live app's) + GET/POST fan-out to the actual FastAPI, and measures the proxy-hop overhead vs the native-route saving. Repeatable; tears both down.
- [`form/form-kernel-rust/examples/router-real-app-proof.fk`](../form/form-kernel-rust/examples/router-real-app-proof.fk) — the real-app manifest: one native route (`/api/utils/weighted_average`, parsing its float query args and running sum(v*w)/sum(w) in Form), the rest fanned out to the real app.
- [`deploy/kernel-router/production-routes.fk`](../deploy/kernel-router/production-routes.fk) — the PRODUCTION manifest (the durable flip's native surface): eleven promoted `/api/utils` routes (`coherence_weight`, `nodeid_distance`, `nodeid_compatibility`, `weighted_average`, `simpson_diversity`, `idea_score`, `marginal_cc_return`, `breath_balance`, `shannon_entropy`, `softmax_weights`, `grounded_value`) served NATIVELY in Form, each emitting the FULL JSON response object byte-identical to its FastAPI twin (params parsed from the request alist via `split_commas`, JSON built with `value_str` + `str_concat`, `runtime:"inline"` matching production); everything else fans out. Float accumulators are left-associated to match CPython's `sum()` bit-for-bit; the entropy routes carry `math_log`/`round_ndigits`, `breath_balance` reproduces CPython's `-0.0` exactly, and `grounded_value` folds eleven host-derived scalars (the value/realization/confidence reduction of `compute_idea_metrics`) through `min2`/`max2`/`_plus` with the `[0.05,0.95]` confidence clamp.
- [`form/form-kernel-rust/production_routes_harness.py`](../form/form-kernel-rust/production_routes_harness.py) — the PROMOTION proof: boots the real `app.main:app` as the CPython oracle, stands the kernel-router (production manifest) in front, and for all eleven routes over representative + edge params (48 cases, incl. adversarial floats, `-0.0`, deterministic + uniform softmax, and `grounded_value`'s confidence float-assoc artifact + clamp/zero-guards) proves the native response value-identical to the local oracle (runtime provenance normalized out) AND — with `--live` — FULL-BODY byte-identical to the live production api; measures native (~0.24 ms) vs CPython-served (~11 ms) latency, the ~45x runtime-share win. Read-only against the live api; tears the local app + router down.
- [`api/app/services/form_kernel_bridge.py`](../api/app/services/form_kernel_bridge.py) — `serve_via_kernel`, the guest-subroutine path this reverses.

### The deployable artifact (the kernel-router as a standalone server)

- [`Dockerfile.kernel-router`](../Dockerfile.kernel-router) — the standalone serve image: stage 1 reuses `Dockerfile.api`'s proven `kernel-builder` (`FROM rust:1.86-slim-bookworm`, `cargo build --release --bin form-kernel-rust && strip`); stage 2 is a lean `debian:bookworm-slim` runtime carrying ONLY the stripped binary, the form-stdlib (for a future source manifest's `--stdlib`), the shadow manifest, and the entrypoint. `KERNEL_ROUTER_PORT` / `UPSTREAM_URL` / `ROUTES_FILE` are env-configurable. No Rust toolchain in the final image.
- [`deploy/kernel-router/shadow-routes.fk`](../deploy/kernel-router/shadow-routes.fk) — the shadow manifest: an EMPTY `(let routes (list))`. `build_route_specs` accepts an empty list, so zero routes are native and EVERYTHING fans out — a transparent proxy with `X-Form-Router: fanout-python` as live evidence.
- [`deploy/kernel-router/entrypoint.sh`](../deploy/kernel-router/entrypoint.sh) — resolves `KERNEL_ROUTER_HOST` (default `0.0.0.0` in-container so the front door is reachable across the boundary) / `KERNEL_ROUTER_PORT` / `UPSTREAM_URL` / `ROUTES_FILE` (+ optional `STDLIB_DIR` / `KERNEL_ROUTER_WORKERS`) at run time and `exec`s `form-kernel-rust serve` — container-configurable without a rebuild.
- [`deploy/kernel-router/docker-compose.kernel-router.yml`](../deploy/kernel-router/docker-compose.kernel-router.yml) — a DEFINED-BUT-INACTIVE overlay service (build: `Dockerfile.kernel-router`, `--upstream http://api:8000`). A SEPARATE overlay the production deploy never includes; its Traefik labels are present but COMMENTED, so merging it changes nothing about production routing. Uncommenting them (and dropping the api service's own rule) is the flip — Urs's intent.
- [`deploy/kernel-router/shadow_proof_harness.py`](../deploy/kernel-router/shadow_proof_harness.py) — proves the shadow manifest is a transparent proxy: against a mock CPython upstream, every path (and a POST with a body) fans out byte-identically to hitting the upstream directly, every response carries `X-Form-Router: fanout-python`, and the empty routes list is accepted (the binary starts and serves). Mock upstream — no production routing.

## Shadow on the production VPS — proven against the REAL api, Traefik untouched

The image is not only built; it **runs in shadow on the production VPS** (2026-06-03),
transparently proxying the **real** api. This is the staged step *before* the flip:
the kernel-router runs beside the live path, carries real production traffic
transparently, and Traefik stays untouched — zero visitor-facing change.

**The run.** The image builds cleanly on the VPS (`docker build -f
Dockerfile.kernel-router` — the Rust release compile + `strip`, the in-image
`--expr "(add 2 3)" → 5` smoke), and runs as a NEW additive container:

```
docker run -d --name kernel-router-shadow --network coherence-network_default \
  -p 127.0.0.1:8090:8080 \
  -e KERNEL_ROUTER_HOST=0.0.0.0 -e KERNEL_ROUTER_PORT=8080 \
  -e UPSTREAM_URL=http://coherence-network-api-1:8000 \
  -e ROUTES_FILE=/routes/shadow-routes.fk \
  kernel-router:shadow-host
```

It binds the host forward to **127.0.0.1 only** — Traefik and the public internet
cannot reach it; nothing is routed to it. The api/web/pulse/postgres/neo4j
containers are never stopped or modified; the shadow is purely additive.

**The transparency proof (from the VPS host, against the real api container).**
Every path is byte-identical between the kernel-router (`127.0.0.1:8090`) and the
real api direct, with `X-Form-Router: fanout-python` on every response:

| path | router | direct | bytes | identical |
|------|--------|--------|-------|-----------|
| `/api/version` | 200 | 200 | 19 | yes |
| `/api/ideas` | 200 | 200 | 370,215 | yes |
| `/api/utils/nodeid_compatibility` | 200 | 200 | 66 | yes |
| `/api/specs` | 404 | 404 | 22 | yes |
| `/api/<nonexistent>` | 404 | 404 | — | yes |
| `/api/health` | 200 | 200 | ~561 | yes¹ |

¹ `/api/health` differs only in the upstream's *own* time-varying fields
(`uptime_seconds`, `uptime_human`) when the two sequential calls straddle a
clock-second; every other field — and the whole body when they land in the same
second — is identical. The proxy alters nothing. A 370 KB body (`/api/ideas`) and
faithfully-relayed 404s prove it is not a happy-path-only relay.

**The measured overhead on real prod infra.** The fan-out proxy hop is
negligible. Measured 200×, `/api/version` (a small stable body isolates the hop):
the **flip-shaped** path (router → fan-out → api, in-container, the shape Traefik
would use) runs at **p50 ≈ direct** (router 4.4 ms vs direct 5.7 ms — router at or
below noise; one ~145 ms tail outlier across 200 samples, worker-pool warmup, not
the median). The **host-forward** path (host → docker-proxy → container →
fan-out, which the flip does NOT use — Traefik bypasses the docker-proxy) adds
**~0.5 ms / +13 % at p50** (router 4.92 ms vs direct 4.35 ms), router p99 *lower*
than direct (the worker pool smooths the tail). So the flip's real cost sits near
the low end — at or below the dev-harness `~+6 %` estimate, the proxy hop lost in
FastAPI's own latency variance.

**Two deployability bugs the real infra surfaced (and the dev-env mock could
not).** Running the image *across a container boundary* — not on the same loopback
a local harness curls — exposed two real defects, now fixed:

1. **`cli_serve` bound `127.0.0.1` (loopback) only.** A same-host harness curls the
   listener on that same loopback, so the gap is invisible there — but Docker's
   host port-forward and Traefik reach a container over its **bridge IP**, not its
   loopback, so a loopback-only front door is unreachable across the boundary (the
   host `-p 127.0.0.1:8090` forward returned connection-refused, and the flip would
   fail the same way). Fix: a `--host` flag (default preserved as `127.0.0.1`, so
   the harness and every existing caller are unchanged); the container entrypoint
   passes `--host 0.0.0.0`, and the localhost-only isolation of a shadow run moves
   to the host binding (`docker run -p 127.0.0.1:<port>`).
2. **The HEALTHCHECK probed `/health`**, which fans out to FastAPI — but the api
   404s on bare `/health` (its liveness route is `/api/health`), and `curl -fsS`
   treats 404 as failure, so the container reported `unhealthy` while serving
   perfectly (the proxy faithfully relaying the upstream's 404). Fix: probe
   `/api/health` — the route the upstream serves; a 200 now proves both router
   liveness and that the fan-out reaches the upstream. The container is `healthy`.

**Standing shadow left running.** Clean and light (CPU ~0 %, MEM ~3 MiB,
`healthy`, localhost-only), it gives ongoing transparent-proxy evidence at no
visitor-facing cost, so it stays up beside the live path. Production stayed
healthy throughout — `/api/health` ok, `deployed_sha` unchanged (production code
never moved), the witness breathing with zero silences before and after every
step; Traefik routing was never touched.

**What remains is the flip** — pointing Traefik at the kernel-router (uncomment
the one label set, drop the api service's own rule). That is the single move that
touches live traffic; it is Urs's intent (given), staged carefully on top of this
proven shadow.
