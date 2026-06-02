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
| **HTTP version** | HTTP/1.0, `Connection: close` per request | HTTP/1.1 + keep-alive (and ideally HTTP/2 behind Traefik), chunked transfer |
| **Concurrency** | single-threaded `for incoming in listener.incoming()` — one request at a time | a thread pool or async accept loop; the `Kernel + Arena` is `!Sync` today, so either a kernel-per-worker pool or an arena-sharding pass |
| **Request parsing** | request line + flat string query alist; 8 KiB cap; GET only | full header map, request bodies (POST/PUT/PATCH), content-type aware parsing, larger/streamed bodies |
| **Fan-out proxy** | GET only, status+body relayed as text/plain, no header passthrough | method + header + body passthrough, response content-type/headers relayed, streaming, connection reuse, timeouts, retries |
| **Handler inputs** | 0 or 1 arg (the query alist) | path params, headers, parsed bodies marshalled into the handler frame |
| **Errors / observability** | 404/405/500 as plain text | structured errors, access logs, the trace surface wired to the witness, metrics |
| **TLS / lifecycle** | plain TCP on 127.0.0.1, runs until killed | TLS termination (or behind Traefik), graceful shutdown, health/readiness, config reload |

None of these is exotic; each is a named breath. The concurrency item is the
load-bearing one — the kernel's per-process intern table (`lc-native-kernel-binary`
names this: *"Not multi-process"*) means a production router is a **pool of
kernel workers behind the accept loop**, not one shared mutable kernel.

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

**NOT shown / not claimed:** production-readiness. The proof is HTTP/1.0,
single-threaded, GET-only, with a mock upstream. The production build is the
table above.

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

- [`form/form-kernel-rust/src/main.rs`](../form/form-kernel-rust/src/main.rs) — `cli_serve` (the front-door listener), `fan_out_to_upstream` (the proxy arm), `http_response_routed` (the X-Form-Router header).
- [`form/form-kernel-rust/examples/router-proof.fk`](../form/form-kernel-rust/examples/router-proof.fk) — the native-handler manifest (Form, not cross-compiled).
- [`form/form-kernel-rust/router_proof_harness.py`](../form/form-kernel-rust/router_proof_harness.py) — the end-to-end proof + measurement.
- [`api/app/services/form_kernel_bridge.py`](../api/app/services/form_kernel_bridge.py) — `serve_via_kernel`, the guest-subroutine path this reverses.
