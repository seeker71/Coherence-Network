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

```lisp
; routes.fk — the front-door manifest (S-expression Form, the kernel's
; native surface). Native handlers are Form recipes; the tail is implicit.
(defn route_coherence_weight (q) ...)   ; a native compute core, in Form
(defn route_health () "ok")

(let routes
  (list
    (list "/health"           route_health)            ; native
    (list "/coherence_weight" route_coherence_weight)  ; native
    ; /api/ideas, /api/contributors, … — NOT listed → fan out to CPython
    ))
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
| **HTTP version** | serves HTTP/1.1 with keep-alive on BOTH hops — on the client hop a worker holds the accepted connection and serves multiple requests on it (one TCP handshake amortized across the connection), and on the fan-out hop each worker reuses a per-worker keep-alive connection to the upstream (the router→upstream handshake amortized across requests, the symmetric saving); every response is Content-Length-framed so the reader knows exactly where one ends and the next begins; the client's intent is honored (HTTP/1.1 default-keep-alive unless `Connection: close`, HTTP/1.0 close-unless-`keep-alive`); a 5s idle read-timeout closes a quiet client connection so it cannot pin a worker; over-read bytes (pipelining) are carried into the next request on both hops, never dropped | chunked transfer encoding (today every response is Content-Length-framed; a streamed/unknown-length body would need chunked — and an upstream chunked response is read-to-close and not pooled), HTTP/2 behind Traefik |
| **Concurrency** | the accept loop dispatches each accepted stream to a POOL of kernel workers (`--workers`, default the host's available parallelism), each owning its own `Kernel + Arena` (the `!Sync` constraint) with `routes.fk` loaded once per worker; concurrent requests run lock-free on isolated kernels — measured ~3–5x throughput over a single worker under 50-way concurrent CPU-bearing load, with no cross-request state bleed | an async/work-stealing accept loop (the thread-per-request-blocked model caps at the worker count); shared read-only routing structure to drop the per-worker re-parse |
| **Request parsing** | reads the full request honoring Content-Length (a body larger than the initial 8 KiB read is captured across as many socket reads as it needs); parses `application/x-www-form-urlencoded` bodies into the same `(key value)` alist the query string uses, captures `application/json` (and any other body) raw under the reserved key `__body__`; 1 MiB body cap rejected with 413; any method (POST/PUT/PATCH/GET) | full header map exposed to handlers; a structural JSON→Form-value parse (today JSON is raw-captured, not parsed); larger/streamed/chunked bodies |
| **Fan-out proxy** | reuses a per-worker keep-alive connection to the upstream, framing each response by Content-Length, reconnecting transparently on a stale pooled connection — repeated fan-outs amortize the upstream TCP handshake instead of opening a fresh connection per request. Bounds each fan-out with a connect timeout (~5s) and a read/write timeout (~30s) so a hung upstream returns a 504 and frees the worker rather than pinning it; a read-timeout is not retried (the upstream is hung — a retry would only re-hang and double the latency), a connect-timeout may retry once (in case a pooled-addr was bad), distinct from the stale-close path which reconnects+retries once on an idle-closed pooled connection. Forwards the original method, the request body, and the client's end-to-end request headers (Authorization, Cookie, Accept\*, User-Agent, Content-Type, X-\*, …) — hop-by-hop headers (Connection, Keep-Alive, Transfer-Encoding, Upgrade, Proxy-\*, Proxy-Connection, TE, Trailer) stripped, Host rewritten to the upstream, Content-Length re-derived from the captured body, the router writing its OWN `Connection: keep-alive` to the upstream — and relays the upstream's response headers back (Content-Type so a JSON/HTML route survives the proxy, Set-Cookie, Cache-Control, Location, ETag, X-\*, …), with the router owning the client-hop framing (its own Content-Length + Connection; the upstream's hop-by-hop/framing headers are not relayed) | chunked/streaming response bodies (an upstream chunked response is read-to-close and its connection not pooled), per-route timeout config and circuit-breaking, retries beyond the single stale-connection / connect-timeout retry |
| **Handler inputs** | 0 or 1 arg — the request alist, carrying query params AND parsed body fields uniformly (form-urlencoded merged in; JSON/other body under `__body__`), so a handler reads a field the same way regardless of how it arrived | path params and headers marshalled into the handler frame; a richer body shape than a flat alist (e.g. structural JSON) |
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
read-to-close worked), so it reads exactly one Content-Length-framed response and
carries any over-read bytes forward for the next response on the connection (the
classic keep-alive proxy bug — a mis-framed read corrupts the next request — held
off by the same carry discipline the client hop uses). A pooled connection may
have been idle-closed by the upstream since it was returned; on a reuse whose
write or read fails, the router transparently reconnects once and retries the
same request, never surfacing a stale-pool error to the client. The honest scope:
reuse applies to Content-Length-framed responses; an upstream chunked or
unframed response is read-to-close and its connection is dropped, not pooled
(chunked-body reuse is a named-later breath). The ONE `fanout_request` shape is
preserved — the pool only changes the connection lifecycle (reused vs fresh); the
request build and response framing are identical either way.
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
becomes an infinite (or even doubled) retry loop. The timeout values are sane
defaults (overridable via `COH_FANOUT_CONNECT_TIMEOUT_MS` / `COH_FANOUT_READ_TIMEOUT_MS`
so a test proves the path in seconds); production tuning of the exact values and
per-route timeouts is a named-later breath. The ONE `fanout_request` shape is
preserved — the timeouts are deadlines set on the stream plus the error
classification, not a second fan-out path.
The remaining rows (chunked transfer, a structural JSON→Form parse, streaming,
per-route timeout config + circuit-breaking, TLS/lifecycle, observability) are
still open breaths.

## The BML preference

Native handlers and the routes manifest are **Form-native tissue, not
Python-cross-compiled**. BML surface syntax (`def name(args) = expr;`) is the
preferred authoring tongue because it exposes Form features directly — Python
reaches Form only through the bolted-on adapter SDK — and the router serves a
BML-authored manifest today.

The BML surface parser is not a Rust build — it already lives in Form-stdlib.
`form-stdlib/source-compiler.fk`'s `form.bml` dialect lowers a `section [form.bml]
{ ... }` block into ordinary Form, the same `form-source-compile-file` lowering
`form/validate.sh prepare_sources` runs to source-compile any section file. The
router reuses that compiler directly: `serve --routes <manifest> --stdlib
form-stdlib` SOURCE-COMPILES a BML manifest **at load** (the manifest is BML iff
it opens a `section [...]` block), in the main thread before any worker spawns,
through the four form-stdlib preludes (`json.fk` + `cache.fk` +
`form-ontology-loader.fk` + `source-compiler.fk`) — then loads the lowered
S-expression with the SAME `read_root_from_source` an S-expression manifest uses.
The lowering writes a `.fkb` Recipe sidecar the lowered manifest reads via
`walk_recipe_here`; both live in a temp dir held for the server's lifetime. The
cost is paid once at startup, not per-worker and not per-request: a worker loads
the lowered `.fk` exactly as it loads a raw S-expression one.
[`examples/router-bml-proof.bml`](../form/form-kernel-rust/examples/router-bml-proof.bml)
is a working BML-authored manifest;
[`router_bml_proof_harness.py`](../form/form-kernel-rust/router_bml_proof_harness.py)
proves each BML route serves the correct value in Form (`X-Form-Router:
native-kernel`, no CPython) and EQUAL to the same handler authored in
S-expression — the BML surface lowered to the same Form shape. A raw
S-expression manifest is unchanged: it has no `section [...]`, so it never
touches the source-compiler and `read_root_from_source` reads it directly.

Honest scope of the BML authoring path: the `form.bml` dialect lowers `def
name(args) = expr;` (single-line), the block form `def name(args) { ... }`,
nested `if c then a else b`, `f(a, b)` calls, and integer, string, AND float
literals. The proof's handlers — a multi-step integer aggregator, an
input-driven counter, liveness, and a **float** route (`route_coherence_weight`,
`0.5*0.25 + 1.0*0.75 = 0.875`) — are authored in it, and their values cross the
source-compiler's `.fkb` artifact intact. A float trivial node carries its
IEEE-754 value in the wire format (a dedicated `FORM_BINARY_FLOAT64` node tag
followed by 8 little-endian bytes), so the value travels in the bytes and each
kernel re-interns it into its own overflow table on read — the per-kernel table
index never crosses the wire. The float-literal route therefore serves the
correct value end-to-end (`router_bml_proof_harness.py` checks `/coherence_weight
-> 0.875`, `native-kernel`), and the artifact round-trip is bit-identical across
Rust, Go, and TS (`form-samples/float-artifact-roundtrip.fk`). An S-expression
manifest serves floats the same way — the kernel's `.fk` source reader reads
float tokens directly (the existing `router-proof.fk`'s 0.8125 coherence-weight
is one).

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
[over-cap 413     ] declared CL=1053576    -> 413 Payload Too Large  OK
```

**Also shown (measured):** a native POST handler reads form-urlencoded body
fields through the SAME alist a GET handler reads query params from (`a=40&b=2`
→ `42`); a JSON body is captured raw under `__body__` and handed to Form (the
36-byte JSON's length comes back); a body **larger than the initial 8 KiB read**
is fully captured across multiple reads honoring Content-Length (a 20 KB field
value returns its exact length — the correctness property the old single-buffer
read failed); GET is unchanged on both the native and fan-out arms; a POST that
fans out carries its body to the upstream (the mock CPython echoes the forwarded
`hello=world&n=7`); and an over-cap body is rejected with 413 on the
Content-Length header alone, never buffered.

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
starved; a read-timeout returns 504 ONCE, not reconnect+retried). The fan-out
response-body cap is now decoupled from the request cap: the router buffers each
upstream response whole and bounds it at `MAX_UPSTREAM_RESPONSE_BYTES` = 64 MiB —
distinct from the 1 MiB `MAX_BODY_BYTES` that rejects oversized *request* bodies
with 413. A request body is untrusted client input; the upstream is the body's own
FastAPI, a trusted peer that legitimately returns large JSON. The 1 MiB symmetry
was wrong: it 502'd the real `/api/concepts/domain/living-collective`
(≈1.7 MB Content-Length-framed JSON) with `upstream response body too large` while
api served it 200 direct — the blocker the 2026-06-03 live flip surfaced. The fix
(PR #2413, on main at 32d1cadd) is verified on the production VPS: the cap-fixed
kernel-router in shadow relays that 1.7 MB route at `200`, byte-identical to the
upstream (sha256 of the 1,704,424-byte body matches direct, X-Form-Router:
fanout-python on the response), the proxy hop adding ~2–4 ms over direct on a body
that size. "Byte-identical" now holds for the real large routes, not only the
small ones. Still open:
chunked/streaming upstream response bodies (an upstream chunked response is
read-to-close and not pooled), per-route timeout config + circuit-breaking and
retries beyond the single stale-connection / connect-timeout retry, and the accept
loop is thread-per-connection-blocked (it parallelizes to the worker count, not an
async reactor; a worker serving a keep-alive client is held until that connection
closes or times out). Responses are Content-Length-framed, not chunked; JSON bodies
are raw-captured, not structurally parsed into Form values. The real-app proof ran
against the dev sqlite DB; the production deployment shape (TLS/Traefik front, the
routes.fk covering the real native-eligible set) is the remaining build.
Concurrency, request-body reading, **bidirectional header passthrough**, the
**real-app fan-out + native side-by-side**, **HTTP/1.1 keep-alive on the
client→router hop**, **upstream connection reuse on the fan-out hop**, and
**fan-out timeouts (hung upstream → 504, worker freed, pool not starved)** are now
shown; chunked transfer and structural-JSON are the rest.

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
  the form-stdlib (so a BML manifest can be source-compiled later), and the
  shadow manifest. No Rust toolchain in the final image.
- [`deploy/kernel-router/shadow-routes.fk`](../deploy/kernel-router/shadow-routes.fk)
  — the shadow manifest: an EMPTY `(let routes (list))`. `build_route_pairs`
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

**The cap fix is verified on real prod — 2026-06-03.** PR #2413 (on main at
32d1cadd) decoupled `MAX_UPSTREAM_RESPONSE_BYTES` (64 MiB) from `MAX_BODY_BYTES`
(1 MiB). The cap-fixed image was rebuilt from main and run as a localhost-bound
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

- [`form/form-kernel-rust/src/main.rs`](../form/form-kernel-rust/src/main.rs) — `cli_serve` (the front-door listener, dispatching to the worker pool; binds `--host` × `--port`, default host `127.0.0.1` so a same-host harness is unchanged while a containerized front door binds `0.0.0.0` to be reachable across the boundary), `worker_loop` + `build_worker_kernel` (a worker's own `Kernel + Arena` with `routes.fk` loaded per worker), `serve_connection` (the keep-alive loop — runs `handle_request` repeatedly on one `TcpStream` until close/EOF/idle-timeout, sets the `KEEPALIVE_IDLE_TIMEOUT` read-timeout, carries pipelined leftover bytes), `handle_request` (the single factored per-request serving shape, reading the full request + body and returning the keep-alive verdict), `head_keep_alive` (the `Connection`-header + HTTP-version keep-alive decision), `read_request` / `parse_content_length` / `parse_content_type` / `parse_request_body` (the Content-Length-honored read that carries over-read bytes forward, and the content-type body parse), `fanout_request` / `fanout_request_result` (the proxy arm, forwarding method + body over a pooled keep-alive upstream connection, mapping a `FanoutError::Timeout` → 504 and `Closed`/`Other` → 502), `connect_upstream_with_timeout` (resolve the SocketAddr + `connect_timeout` + set the per-use read/write deadlines on the fan-out stream), `FanoutError` + `classify_io_error` (the retry-vs-504 classification: TimedOut/WouldBlock → Timeout → 504 never retried, BrokenPipe/Reset/EOF → Closed → stale-pool reconnect+retry once, else Other → 502), `fanout_connect_timeout` / `fanout_read_timeout` (the ~5s connect / ~30s read+write deadlines, env-overridable via `COH_FANOUT_CONNECT_TIMEOUT_MS` / `COH_FANOUT_READ_TIMEOUT_MS`), `UpstreamPool` + `PooledConn` (the per-worker, lock-free upstream connection cache owned by `worker_loop` and threaded through `serve_connection` → `handle_request`), `read_upstream_response` / `send_and_read_one` / `upstream_response_keep_alive` / `head_is_chunked` (the Content-Length-framed one-response read that no longer relies on connection-close, with read/write deadlines classified as timeouts, the stale-connection reconnect+retry, and the reuse-vs-drop verdict), `is_hop_by_hop` (RFC 7230 §6.1 hop-by-hop set, now incl. `Proxy-Connection`), `http_response` (HTTP/1.1 with accurate Content-Length, the `Connection` + X-Form-Router headers), `str_to_float` (the float-parsing leaf native that lets a native handler parse float query args, e.g. weighted_average's values/weights).
- [`form/form-kernel-rust/examples/router-proof.fk`](../form/form-kernel-rust/examples/router-proof.fk) — the native-handler manifest (Form, not cross-compiled).
- [`form/form-kernel-rust/router_proof_harness.py`](../form/form-kernel-rust/router_proof_harness.py) — the end-to-end topology proof + native-latency measurement (mock upstream).
- [`form/form-kernel-rust/router_body_harness.py`](../form/form-kernel-rust/router_body_harness.py) — the request-body proof: a native POST handler reading form-urlencoded fields, a raw JSON capture, a >8 KiB body captured across reads, POST fan-out body forwarding, and over-cap 413 (mock upstream).
- [`form/form-kernel-rust/examples/router-body-proof.fk`](../form/form-kernel-rust/examples/router-body-proof.fk) — the body-reading native-handler manifest (Form, not cross-compiled).
- [`form/form-kernel-rust/router_concurrency_harness.py`](../form/form-kernel-rust/router_concurrency_harness.py) — the worker-pool concurrency proof: 50 parallel clients, no cross-request state bleed, 1-worker vs N-worker throughput.
- [`form/form-kernel-rust/router_keepalive_harness.py`](../form/form-kernel-rust/router_keepalive_harness.py) — the HTTP/1.1 keep-alive proof (CLIENT→router hop): N sequential requests on ONE connection (Content-Length framed, distinct inputs, each correct), pipelined two-in-one-send (leftover bytes carried, none dropped), `Connection: close` honored, HTTP/1.0 default-close back-compat, idle-timeout reaping the connection (worker freed), an idle connection NOT starving the pool, and the per-request handshake saving (reused vs fresh connection). Mock upstream — no production routing.
- [`form/form-kernel-rust/router_upstream_reuse_harness.py`](../form/form-kernel-rust/router_upstream_reuse_harness.py) — the upstream connection reuse proof (router→UPSTREAM hop): against a connection-COUNTING mock upstream with `--workers 1`, N fan-outs land on ONE reused upstream connection (connections << requests — the handshake amortized); each of N DISTINCT requests on the reused connection reads its OWN correct Content-Length-framed response (no response-framing bleed, the classic proxy keep-alive bug proven absent); reused-vs-fresh-connect latency (the reused path opens 1 connection where close-each opens N); and a stale POOLED keep-alive connection (the upstream silently drops it after N requests) triggers a transparent reconnect+retry, never a client-facing error. Mock upstream — no production routing.
- [`form/form-kernel-rust/router_fanout_timeout_harness.py`](../form/form-kernel-rust/router_fanout_timeout_harness.py) — the fan-out TIMEOUT proof (router→UPSTREAM hop): against a deliberately-HUNG upstream that accepts the connection but never responds, the router returns a clean 504 Gateway Timeout at ~one read deadline (measured) and frees the worker — never an indefinite hang; an unreachable / blackholed upstream returns a clean 504/502 (connect-timeout) rather than blocking; with N workers a hung fan-out occupies ONE worker for at most the connect+read timeout while the pool keeps serving 20 native requests in milliseconds (the pool is NOT starved); a read-timeout returns 504 ONCE, not reconnect+retried (latency ~1x the read-timeout, not 2x — distinct from the stale-close retry path); and the happy path (native + responsive-upstream fan-out) is unaffected. Uses short env-set timeouts (`COH_FANOUT_READ_TIMEOUT_MS`/`COH_FANOUT_CONNECT_TIMEOUT_MS`) for a seconds-fast proof. Mock upstreams — no production routing.
- [`form/form-kernel-rust/router_header_passthrough_harness.py`](../form/form-kernel-rust/router_header_passthrough_harness.py) — the bidirectional header-passthrough proof: against a mock echo upstream, the client's end-to-end request headers (Authorization/Cookie/Accept/X-Probe/User-Agent + Content-Type on POST) reach the upstream with Host rewritten and the client Content-Length/Connection stripped, and the upstream's Set-Cookie/Cache-Control/custom headers relay back while its hop-by-hop Transfer-Encoding does not; against the REAL FastAPI app, `/api/health` relays with `Content-Type: application/json` (the upstream's real type, not text/plain) and a native route still serves text/plain in Form. Tears both upstreams down.
- [`form/form-kernel-rust/router_real_app_harness.py`](../form/form-kernel-rust/router_real_app_harness.py) — the REAL-app proof: boots `app.main:app` under uvicorn (dev sqlite), stands the kernel-router in front of it, proves native-in-Form (value == the live app's) + GET/POST fan-out to the actual FastAPI, and measures the proxy-hop overhead vs the native-route saving. Repeatable; tears both down.
- [`form/form-kernel-rust/examples/router-real-app-proof.fk`](../form/form-kernel-rust/examples/router-real-app-proof.fk) — the real-app manifest: one native route (`/api/utils/weighted_average`, parsing its float query args and running sum(v*w)/sum(w) in Form), the rest fanned out to the real app.
- [`api/app/services/form_kernel_bridge.py`](../api/app/services/form_kernel_bridge.py) — `serve_via_kernel`, the guest-subroutine path this reverses.

### The deployable artifact (the kernel-router as a standalone server)

- [`Dockerfile.kernel-router`](../Dockerfile.kernel-router) — the standalone serve image: stage 1 reuses `Dockerfile.api`'s proven `kernel-builder` (`FROM rust:1.86-slim-bookworm`, `cargo build --release --bin form-kernel-rust && strip`); stage 2 is a lean `debian:bookworm-slim` runtime carrying ONLY the stripped binary, the form-stdlib (for a future BML manifest's `--stdlib`), the shadow manifest, and the entrypoint. `KERNEL_ROUTER_PORT` / `UPSTREAM_URL` / `ROUTES_FILE` are env-configurable. No Rust toolchain in the final image.
- [`deploy/kernel-router/shadow-routes.fk`](../deploy/kernel-router/shadow-routes.fk) — the shadow manifest: an EMPTY `(let routes (list))`. `build_route_pairs` accepts an empty list, so zero routes are native and EVERYTHING fans out — a transparent proxy with `X-Form-Router: fanout-python` as live evidence.
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
