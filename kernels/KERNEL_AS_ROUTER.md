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
| **HTTP version** | serves HTTP/1.1 with keep-alive — a worker holds the accepted connection and serves multiple requests on it (one TCP handshake amortized across the connection), each response Content-Length-framed so the client knows exactly where one ends and the next begins; the client's intent is honored (HTTP/1.1 default-keep-alive unless `Connection: close`, HTTP/1.0 close-unless-`keep-alive`); a 5s idle read-timeout closes a quiet connection so it cannot pin a worker; over-read bytes (pipelining) are carried into the next request, never dropped | chunked transfer encoding (today every response is Content-Length-framed; a streamed/unknown-length body would need chunked), upstream connection reuse on the fan-out hop (the fan-out still opens a fresh upstream connection per request), HTTP/2 behind Traefik |
| **Concurrency** | the accept loop dispatches each accepted stream to a POOL of kernel workers (`--workers`, default the host's available parallelism), each owning its own `Kernel + Arena` (the `!Sync` constraint) with `routes.fk` loaded once per worker; concurrent requests run lock-free on isolated kernels — measured ~3–5x throughput over a single worker under 50-way concurrent CPU-bearing load, with no cross-request state bleed | an async/work-stealing accept loop (the thread-per-request-blocked model caps at the worker count); shared read-only routing structure to drop the per-worker re-parse |
| **Request parsing** | reads the full request honoring Content-Length (a body larger than the initial 8 KiB read is captured across as many socket reads as it needs); parses `application/x-www-form-urlencoded` bodies into the same `(key value)` alist the query string uses, captures `application/json` (and any other body) raw under the reserved key `__body__`; 1 MiB body cap rejected with 413; any method (POST/PUT/PATCH/GET) | full header map exposed to handlers; a structural JSON→Form-value parse (today JSON is raw-captured, not parsed); larger/streamed/chunked bodies |
| **Fan-out proxy** | forwards the original method, the request body, and the client's end-to-end request headers (Authorization, Cookie, Accept\*, User-Agent, Content-Type, X-\*, …) — hop-by-hop headers (Connection, Keep-Alive, Transfer-Encoding, Upgrade, Proxy-\*, TE, Trailer) stripped, Host rewritten to the upstream, Content-Length re-derived from the captured body — and relays the upstream's response headers back (Content-Type so a JSON/HTML route survives the proxy, Set-Cookie, Cache-Control, Location, ETag, X-\*, …), with the router owning the client-hop framing (its own Content-Length + Connection; the upstream's hop-by-hop/framing headers are not relayed) | chunked/streaming response bodies, upstream connection reuse, timeouts, retries |
| **Handler inputs** | 0 or 1 arg — the request alist, carrying query params AND parsed body fields uniformly (form-urlencoded merged in; JSON/other body under `__body__`), so a handler reads a field the same way regardless of how it arrived | path params and headers marshalled into the handler frame; a richer body shape than a flat alist (e.g. structural JSON) |
| **Errors / observability** | 404/413/500 as plain text | structured errors, access logs, the trace surface wired to the witness, metrics |
| **TLS / lifecycle** | plain TCP on 127.0.0.1, runs until killed | TLS termination (or behind Traefik), graceful shutdown, health/readiness, config reload |

None of these is exotic; each is a named breath. Four of the load-bearing ones
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
The remaining rows (chunked transfer, upstream connection reuse on the fan-out
hop, a structural JSON→Form parse, streaming, TLS/lifecycle, observability) are
still open breaths.

## The BML preference

Native handlers and the routes manifest are **Form-native tissue, not
Python-cross-compiled**. The proof manifest is authored as `.fk` S-expression
Form — the kernel's native surface that `read_root_from_source` reads directly.
BML surface syntax (`defn name(a, b) = do { ... };`) is the preferred authoring
tongue because it exposes Form features directly (Python reaches Form only via
the bolted-on adapter SDK); serving a BML-authored manifest needs the Form
surface parser in Rust (the `.recipelib.json` tongue_caches → S-expression
converter named in [`lc-native-kernel-binary`](../docs/vision-kb/concepts/lc-native-kernel-binary.md)).
Either way the handler is Form, walked by the kernel — never a Python function
the kernel calls. That is the point of the reversal: the front door speaks the
body's own tongue.

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
**proxy hop costs ~0.2–0.3 ms (~5–7%)** on a fan-out route — a real localhost TCP
hop over the kernel's HTTP/1.0, the price of fronting; the **native route saves
~10.8 ms (~56x)** by skipping the entire CPython request lifecycle (uvicorn
parse → routing → Pydantic bind → `serve_via_kernel` subprocess spawn →
response model), serving the value-walk directly. A hot native route is far
cheaper than the same compute reached through the CPython doorway; the tail pays
a small, measured proxy toll to keep working unchanged.

**NOT shown / not claimed:** full production-readiness. The server serves
HTTP/1.1 with keep-alive (proven by `router_keepalive_harness.py` — multiple
requests on one connection, `Connection` honored both ways, idle-timeout reaping,
pipelining bytes carried) and the fan-out hop passes headers both ways with
hop-by-hop hygiene (proven by `router_header_passthrough_harness.py` — the
client's Authorization/Cookie/Accept/X-\* reach the upstream with Host rewritten
and hop-by-hop stripped; the upstream's Content-Type/Set-Cookie/Cache-Control
reach the client; verified against the REAL FastAPI app, whose `/api/health`
relays as `application/json` rather than the old flattened text/plain). What
stays open: the **upstream fan-out hop still opens a fresh connection per
request** (the client→router hop reuses connections; the router→upstream hop does
not yet — so the proxy-hop latency above is measured on a non-reused upstream
connection), and the accept loop is thread-per-connection-blocked (it
parallelizes to the worker count, not an async reactor; a worker serving a
keep-alive client is held until that connection closes or times out). Responses
are Content-Length-framed, not chunked; JSON bodies are raw-captured, not
structurally parsed into Form values. The real-app proof ran against the dev
sqlite DB; the production deployment shape (TLS/Traefik front, the routes.fk
covering the real native-eligible set) is the remaining build. Concurrency,
request-body reading, **bidirectional header passthrough**, the **real-app
fan-out + native side-by-side**, and **HTTP/1.1 keep-alive on the client→router
hop** are now shown; chunked transfer, upstream connection reuse, and
structural-JSON are the rest.

## The flip is Urs's decision

This is the **live request front-door for real visitors** — high-stakes. This
design and proof establish that the inverted topology *works* and name the build
precisely. **The production flip — putting the kernel-router in front of the
real FastAPI app — is Urs's explicit decision, not shipped here.** Today's
front door (FastAPI) is untouched; this is the design plus a side proof on a
test port so the reversal can be weighed with evidence rather than assertion.

## Cross-references

- [`API_KERNEL_READINESS.md`](API_KERNEL_READINESS.md) — the topology this inverts; the queue of native-eligible routes.
- [`SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md`](SUBSTRATE_AS_DEPLOYMENT_RUNTIME.md) — the deeper destination: the substrate as the runtime, of which the kernel-router is the request-handling face.
- [`README.md`](README.md) — the three sibling kernels; the router is the Rust kernel's front-door face.
- [`lc-native-kernel-binary`](../docs/vision-kb/concepts/lc-native-kernel-binary.md) — the native binary, its serve primitive, and the per-process / concurrency honesty this build must answer.
- [`lc-one-kernel-many-tongues`](../docs/vision-kb/concepts/lc-one-kernel-many-tongues.md), [`lc-the-kernel-knows-itself`](../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md) — the kernel speaking the body's own tongue and reading its own routing.

## Sources

- [`form/form-kernel-rust/src/main.rs`](../form/form-kernel-rust/src/main.rs) — `cli_serve` (the front-door listener, dispatching to the worker pool), `worker_loop` + `build_worker_kernel` (a worker's own `Kernel + Arena` with `routes.fk` loaded per worker), `serve_connection` (the keep-alive loop — runs `handle_request` repeatedly on one `TcpStream` until close/EOF/idle-timeout, sets the `KEEPALIVE_IDLE_TIMEOUT` read-timeout, carries pipelined leftover bytes), `handle_request` (the single factored per-request serving shape, reading the full request + body and returning the keep-alive verdict), `head_keep_alive` (the `Connection`-header + HTTP-version keep-alive decision), `read_request` / `parse_content_length` / `parse_content_type` / `parse_request_body` (the Content-Length-honored read that carries over-read bytes forward, and the content-type body parse), `fanout_request` (the proxy arm, forwarding method + body), `http_response` (HTTP/1.1 with accurate Content-Length, the `Connection` + X-Form-Router headers), `str_to_float` (the float-parsing leaf native that lets a native handler parse float query args, e.g. weighted_average's values/weights).
- [`form/form-kernel-rust/examples/router-proof.fk`](../form/form-kernel-rust/examples/router-proof.fk) — the native-handler manifest (Form, not cross-compiled).
- [`form/form-kernel-rust/router_proof_harness.py`](../form/form-kernel-rust/router_proof_harness.py) — the end-to-end topology proof + native-latency measurement (mock upstream).
- [`form/form-kernel-rust/router_body_harness.py`](../form/form-kernel-rust/router_body_harness.py) — the request-body proof: a native POST handler reading form-urlencoded fields, a raw JSON capture, a >8 KiB body captured across reads, POST fan-out body forwarding, and over-cap 413 (mock upstream).
- [`form/form-kernel-rust/examples/router-body-proof.fk`](../form/form-kernel-rust/examples/router-body-proof.fk) — the body-reading native-handler manifest (Form, not cross-compiled).
- [`form/form-kernel-rust/router_concurrency_harness.py`](../form/form-kernel-rust/router_concurrency_harness.py) — the worker-pool concurrency proof: 50 parallel clients, no cross-request state bleed, 1-worker vs N-worker throughput.
- [`form/form-kernel-rust/router_keepalive_harness.py`](../form/form-kernel-rust/router_keepalive_harness.py) — the HTTP/1.1 keep-alive proof: N sequential requests on ONE connection (Content-Length framed, distinct inputs, each correct), pipelined two-in-one-send (leftover bytes carried, none dropped), `Connection: close` honored, HTTP/1.0 default-close back-compat, idle-timeout reaping the connection (worker freed), an idle connection NOT starving the pool, and the per-request handshake saving (reused vs fresh connection). Mock upstream — no production routing.
- [`form/form-kernel-rust/router_header_passthrough_harness.py`](../form/form-kernel-rust/router_header_passthrough_harness.py) — the bidirectional header-passthrough proof: against a mock echo upstream, the client's end-to-end request headers (Authorization/Cookie/Accept/X-Probe/User-Agent + Content-Type on POST) reach the upstream with Host rewritten and the client Content-Length/Connection stripped, and the upstream's Set-Cookie/Cache-Control/custom headers relay back while its hop-by-hop Transfer-Encoding does not; against the REAL FastAPI app, `/api/health` relays with `Content-Type: application/json` (the upstream's real type, not text/plain) and a native route still serves text/plain in Form. Tears both upstreams down.
- [`form/form-kernel-rust/router_real_app_harness.py`](../form/form-kernel-rust/router_real_app_harness.py) — the REAL-app proof: boots `app.main:app` under uvicorn (dev sqlite), stands the kernel-router in front of it, proves native-in-Form (value == the live app's) + GET/POST fan-out to the actual FastAPI, and measures the proxy-hop overhead vs the native-route saving. Repeatable; tears both down.
- [`form/form-kernel-rust/examples/router-real-app-proof.fk`](../form/form-kernel-rust/examples/router-real-app-proof.fk) — the real-app manifest: one native route (`/api/utils/weighted_average`, parsing its float query args and running sum(v*w)/sum(w) in Form), the rest fanned out to the real app.
- [`api/app/services/form_kernel_bridge.py`](../api/app/services/form_kernel_bridge.py) — `serve_via_kernel`, the guest-subroutine path this reverses.
