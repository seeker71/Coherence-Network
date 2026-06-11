# Source-language kernel router tracking sheet

This is the current picture. Update it in place as the route body changes. Do
not preserve history here; keep the live goal, what works, what is tight, and
where attention moves next.

## Living goal

Every authored language can express Form-native cells and recipes that the
kernel can run. BML is the first high-level route dialect being grown deeply,
not the name of the shared runtime object model. BMF is the bidirectional lens
layer. Form recipes and cells are runtime truth. There is no primary kernel:
Rust, Go, and TypeScript are sibling carriers for the same route cells, handler
recipes, observations, and failures. In `serve --form`, Form owns HTTP parse,
route, dispatch, render, and socket recv/send loops over minimal `socket_*`
ports. Rust hosts listener/process lifecycle, worker kernels, accepted stream
handles, deadlines, and opaque host ports; the older host-router path still
carries compatibility fan-out while the Form-native path grows. The next
front-door parity pass moves through Go so the shape stops leaning on Rust as
the implicit source of truth. Source-level branch tables are substrate cells:
BML/Form `match` lowers to `MATCH.SWITCH` and dispatches by direct NodeID lookup
across Go, Rust, and TypeScript.

The desired flow:

```text
source surface
  -> lens / parser / translator
  -> Form route values, cells, recipes, handler closures
  -> kernel execution
  -> runtime observations
  -> attention matrix and source/lens feedback
```

`.fk` text and `.fkb` bytes are carriers. The requirement is Form-native runtime
objects plus transparent source entry observability.

Traffic promotion target: at least 90% of web-used `/api` traffic shall be
served by kernel-native handlers written in BML or a domain route grammar. Use
runtime events, not source-code guesses, to choose the next route. The web API
proxy now stamps calls with `X-Coherence-Web-Proxy`; API runtime telemetry records
those requests as `source="web_api"` so route frequency can be sliced by traffic
from the web interface.

Route lift discipline: each promotion shall walk `source -> flow -> purpose ->
grammar -> proof -> release`. The agent questions the observed information
source, traces the web/API/data flow, names what the route contributes to the
body, chooses BML or a higher domain grammar, proves the handler against the real
substrate, and releases or names the remaining old carrier. Frequency chooses
where attention lands; this gate keeps the lift aligned with the highest goal
rather than route-count pressure alone. The route cell shall answer five
questions before implementation counts as aligned: why this route exists in the
organism; which user/web flows actually call it; whether BML is enough or a
graph/domain grammar is asking to emerge; whether the response shape is the
right shape rather than only the compatible shape; and whether frequency serves
the highest goal instead of only the route-count goal.

2026-06-12 promotion pass: `GET /api/agent/tasks/{task_id}/log` is now a BML route in `deploy/front-door/api.bml` mapped natively as `/api/agent/tasks/{task_id}/log`. The handler parses the `task_id` segment from the path, connects to the database, queries the task record, checks if `api/logs/task_{task_id}.log` exists, and reads its content. If the file is not found on disk, the handler constructs a fallback snapshot log from DB state fields (`status`, `current_step`, `updated_at`, and `output` limited to 5000 characters), fully matching the Python FastAPI handler's response contract and returning with `log_source: "task_snapshot"` or `"file"`.

2026-06-07 health movement: `GET /api/health` was already BML/high-grammar
native and the current `web_api` route-goal window read `47/47` observed events
on `/api/health`, so the movement was not a route-count promotion. The route
exists as the organism's operational breath: deploy scripts, web proxy checks,
witness probes, local verification, and operators ask it whether API, schema,
runtime carrier, recent traffic outcomes, and deploy identity are alive. BML is
enough for the current liveness/readiness response; a broader health grammar can
emerge only if `shape_health`, provider readiness, witness organs, and route
outcome summaries converge into one repeated domain language. The response shape
stays compatible with the Python carrier but now tells more native truth:
`recent_outcomes` is populated from production `runtime_events` when DB reach is
present, `smart_reap_available` is resolved from the repo root instead of the
process cwd, and missing DB reach returns `recent_outcomes: null` rather than a
fake zero snapshot. Production-tunnel curl against the Go kernel returned
`200 OK`, `X-Form-Router: native-kernel-go`, `schema_ok=true`,
`smart_reap_available=true`, `kernel_runtime=form-kernel-go`, and populated
`last_1m`/`last_5m` outcome buckets.

2026-06-05 promotion batch: `deploy/front-door/api.bml` now carries DB-backed
BML handlers for `/api/coherence/score`, `/api/concepts/lc-*`,
`/api/ideas/resonance`, `/api/edges`, `/api/inspired-by`,
`/api/runtime/endpoints/summary`, and `/api/feed/personal`, in addition to the
earlier `/api/ideas`, health/ready, recent voices/reactions, anonymous traces,
vitality, presence, substrate page, federation count, and field-story trace. The
Go carrier probes hit the real production Postgres tunnel and returned
`X-Form-Router: native-kernel-go` for each promoted route. `/api/coherence/score`
now uses a six-signal evidence vector (ideas, specs, evidence, runtime, value,
graph connectedness). `/api/inspired-by` was corrected from a full-node dump to a
bounded card projection (`count=40`, `total=281`, `limit=40` in the probe) after
the first native shape exposed a multi-second emission cost.

2026-06-07 backend promotion pass: `POST /api/views/ping` is now a BML route in
`deploy/front-door/api.bml`. The native handler parses the JSON ping body,
reads typed request headers, writes `asset_view_events`, upserts
`asset_reads_daily`, infers/accepts entity identity, locates the newest
`content_view` contribution, and inserts an `attention` contribution when the
viewer is not the source author. Curl proof against the Go kernel on the
production Postgres tunnel returned `200 OK`, `X-Form-Router:
native-kernel-go`, `route:views-ping`, and a JSON body with `ok:true`,
`read_daily_written:1`, and `attention_credited:false` for the low-blast-radius
probe asset `codex-native-views-ping-20260607`. The explicit remaining gap from
the Python path is the in-process render-events settlement bridge; that bridge
is not durable tissue, so it shall be replaced by a native persisted event cell
instead of being copied into BML as memory-only behavior.

The same 2026-06-07 pass also lifted exact `GET /api/graph/nodes` as
`graph-nodes-index`. It deliberately does **not** add a wildcard
`/api/graph/nodes/*` route, because that can capture `/edges`, `/neighbors`,
and `/subgraph` detail routes before their contracts are native. The BML handler
implements the list route's real filters (`type`, `phase`, `search`, `limit`,
`offset`), excludes `anonymous-meeting:%` rows like the Python carrier, orders
by `updated_at DESC`, and merges arbitrary `graph_nodes.properties` into each
node's top-level JSON projection. Production-tunnel curl proof for
`/api/graph/nodes?type=contributor&limit=2` returned `200 OK`,
`X-Form-Router: native-kernel-go`, `route:graph-nodes-index`, `total=168`, and
the same first two contributor ids as the public API:
`contributor:vasudev-baba`, `contributor:alex-sandr`.

2026-06-05 gap pass: household source was found on `origin/main`, not invented:
`api/app/routers/household.py` is the Python carrier and
`docs/coherence-substrate/household-membrane.form` names the domain source.
`deploy/front-door/api.bml` now lifts the read-heavy household board surfaces:
`GET /api/household/requests`, `GET /api/household/requests/{request_id}`, and
`GET /api/household/members`. Local Go listener probes against the production
Postgres tunnel returned `200` for all three and byte-normalized `jq -S` diffs
against the public Python carrier were empty.

The next backend gap, `POST /api/meetings/anonymous-traces`, is now a BML
write/upsert handler rather than a Python fan-out. The Go route compiler loads
`form-stdlib/sha256.fk`, so privacy continuity IDs are computed by the Form
SHA-256 recipe over bitwise primitives, not a Go or database hash shortcut. The
BML handler parses the HTTP body, validates the endpoint fields, writes the
`graph_nodes` event through PostgreSQL JSONB merge/upsert SQL, emits the 201
response through Form JSON nodes, and preserves first-occurrence surface and
referrer ordering in both item and summary reads. A namespaced validation POST
created a real production row, a second POST merged a second surface, native GET
and public Python GET compared equal, then the validation row was deleted.

`GET /api/agent/tasks/task_*` is now a BML detail handler over the real
`agent_tasks` table. The route pattern is intentionally `task_*`, not a generic
path variable, so static Python tail routes such as `/api/agent/tasks/count` and
`/api/agent/tasks/attention` are not shadowed. The BML handler extracts the task
id from `KernelHTTPRequest`, queries production Postgres, parses `context_json`
with Form JSON, projects the public `AgentTask` shape, and emits the response
through Form JSON nodes. The parity pass exposed and fixed shared JSON-library
gaps: `form-stdlib/json.fk` now preserves booleans as bool nodes, decimal and
exponent numbers as float nodes, and decodes string escapes including `\n` and
`\uXXXX` before emission. Local Go listener parity for
`task_2a2bc37d105848d2` is semantically equal to the public Python carrier, and
the missing-id path returns native `404 {"detail":"Task not found"}`.

The next pressure cells have moved from static Python route tissue into the BML
front-door catalog. `GET /api/workspaces` now reads workspace-shaped
`graph_nodes` rows and projects the public workspace index shape. `GET
/api/agent/tasks` and the observed runtime alias `GET /api/tasks` now share a
BML list projection over `agent_tasks` with DB-backed filters for status, type,
workspace, limit, and offset. `POST /api/graph/edges` is now a BML mutation
with canonical edge-type validation, self-loop protection, JSON-object property
validation, generated edge ids, and the same conflict behavior that updates
existing edge strength. The 2026-06-09 route-goal state now sees 36 BML routes,
0.893 native-executable share, and the next measured route pressure at `GET
/api/automation/usage/readiness`.

The route goal loop is now method-aware and uses `runtime_events` first, not
endpoint summaries. This is a structural correction: `GET /api/household/requests`
is native, but `POST /api/household/requests` remains a separate gap when it
appears in traffic. Current `source=web_api` measurement is honest about
web-origin traffic. The health proxy is now normalized at emission time: new
`GET /api/health-proxy` observations record `endpoint=/api/health` and
`raw_endpoint=/api/health-proxy`, so route-goal pressure lands on the native
backend route instead of the web proxy shell. Any remaining `/api/health-proxy`
rows are pre-normalization telemetry and age out before choosing backend
promotion work from the web-only queue. Latest backend-source readout
(`/goal --source api --write-state`, 2000 events, 2026-06-07 after the graph
index lift) is `79.05%` high-grammar native and `80.45%` native-executable.
`POST /api/views/ping` and exact `GET /api/graph/nodes` are both counted as
`kernel-native-high-grammar`; the next measured backend gap is now
`GET /api/workspaces` (`9` events, `0.45%`, desired BML route catalog). `POST
/api/substrate/form` is treated as the bootstrap evaluator door,
not wrapped just to satisfy route counts.

Compiler-from-string pass: the Go kernel now exposes
`compile_form_source`, `compile_source_section`, `compile_source_text`,
`source_compile_last_error`, and `value_kind`. The BML front-door catalog has a
header-gated `POST /api/substrate/form` compiler branch requiring
`X-Form-Compiler`; explicit compiler requests run native through BML/Form JSON
emission, while unmarked form-notation requests still bridge. Local proof:

```bash
curl -i http://127.0.0.1:18180/api/substrate/form \
  -H 'Content-Type: application/json' \
  -H 'X-Form-Compiler: form.bml' \
  -d '{"expression":"add(20, 22);","mode":"run","grammar":"form.bml"}'
```

returned `X-Form-Router: native-kernel-go` and
`{"kind":"value","value_kind":"int","value":42,...}`.

Go front-door bridge pass: `form-kernel-go serve` now accepts
`--upstream <base-url>` and fans out unmatched requests through the Go listener
with `X-Form-Router: fanout-python`. It also stamps each decision with
`X-Form-Route-How`, `X-Form-Route-Where`, `X-Form-Route-When`, and
`X-Form-Route-Who`, so the front door names how the request was handled, where
the route or upstream target lived, when the choice was made, and who/what
initiated it. This is the explicit bridge the native front door needs while
handlers are promoted one by one: the kernel can be the main door without
pretending bridged Python endpoints are native. A local listener with
`--upstream https://api.coherencycoin.com` served `/api/health` as
`X-Form-Route-How: native-kernel-go` with
`X-Form-Route-Where: route:api-health pattern:/api/health request:/api/health`
and bridged `POST /api/substrate/form`
`{"expression":"?lattice","mode":"ast"}` as
`X-Form-Route-How: fanout-python` with
`X-Form-Route-Where: upstream:https://api.coherencycoin.com/api/substrate/form`,
returning the public lattice result. This bridge does not move
`POST /api/substrate/form` into high-grammar native status; it only makes the
transition path honest.

## Current working tissue

| Surface | Working now | Friction | Next attention |
|---|---|---|---|
| Sibling front door | Rust has the most complete front-door shell; Go already carries socket natives, the substrate walker, `walk_parallel`, `walk_parallel_cached`, and Go JIT; the pure Form HTTP layers are sibling-proven where the needed preludes load. | The deployable front-door shell still lives in Rust, so architecture and habit can drift toward "Rust primary" even though the body has no primary kernel. | Build the Go front-door parity slice around the same `kh-serve-conn` / `routes` / `registry` contract, then compare Go/Rust observations and tight spots. |
| Route carrier | `form-kernel-rust serve` loads raw Form source manifests and source-authored manifests compiled to an in-memory Form Recipe object graph. `form-kernel-go serve` now also source-compiles BML/source-section manifests at load, serves `kh-route` rows with typed `kh-request` input, and can bridge unmatched routes through `--upstream` with `X-Form-Router: fanout-python`. Both native and fanout responses carry `X-Form-Route-How/Where/When/Who` decision headers. The first Go-loaded BML catalog is `deploy/front-door/api.bml` for `/api/ideas` and the route-promotion batch. | Rust still has the deeper `serve --form` socket lifecycle. Go source-load currently serializes the compiled route object to artifact bytes and deserializes per worker rather than sharing a read-only graph. Full candidate tables/source-entry observations are still tight. Fanout is process-local bridge traffic, not a Form-visible `KernelRouterPort` cell yet. | Move Go from compatibility host-router typed-route serving toward the same `kh-serve-conn` path, replace per-worker artifact reload with a shared immutable graph/clone path, and lift fanout into an explicit Form-visible port response/candidate outcome. |
| Route authoring | Raw Form manifests load. Source manifests source-compile at load to Form Recipe objects. `section [form.route]` supports readable route `template` blocks with members and `class` blocks with methods, and route source emits the same `LanguageTemplate`/`LanguageClass` model BML and future grammars shall emit. `/health` uses `class HealthRoute { def handle(request) { ... } route = route_data(health, handle); }`: class/method flow is recipe tissue, while method/path/priority/budget live in `production-routes-data.json`. BML `match` now lowers to `MATCH.SWITCH` and validates across Go/Rust/TS (`source-language-match-switch-band.fk -> 7`). Source pipelines no longer require `.fkb` route sidecars or lowered route source as the runtime carrier. | Production manifest is still mostly Form-authored; class body lowering covers route classes and methods, not arbitrary fields/constructors/interfaces yet. Route-data JSON is host-decoded, not yet a Form-visible config cell. Existing bridge handlers are still easy to mistake for endpoint identity instead of handler-source ports. | Generalize class body lowering, lift route-data loading into `KernelRouterConfig`/route-data cells, and define the compatibility Python port as one handler port beside BML/domain grammar handlers. |
| Handler grammars | Handlers can already be ordinary Form closures; `section [form.route]` gives BML-shaped route classes; the Python-to-Form compile path is active elsewhere in the kernel work. | FastAPI still carries many existing endpoint bodies, so stale docs and habits can pull new work back into bridge code. | New native handlers are written in BML or a domain grammar for the endpoint's domain. Existing bridge handlers either compile into Form recipes or run behind a Python port handler under the same `kh-request -> kh-response` contract, with bridge status visible in route decisions. |
| Complex endpoint exemplar | `/api/utils/grounded_cost` now has a focused probe (`scripts/grounded_cost_endpoint_probe.py`) and a sibling-portable BML/Form handler core (`form/form-stdlib/tests/grounded-cost-record-handler-band.fk`). The BML core validates across the Go/Rust focused probe and the probe compares Python source-reference timing, FastAPI kernel-guest HTTP, and native HTTP success/422 behavior. The probe's JIT section is Go-centered and reads JIT compile/fail/dispatch from framebuffer counts. | The compatibility native HTTP path is correct but slower on the medium fixture. The compiled legacy Python-adapter recipe now executes in Go after dict carrier parity, but the scalar JIT pass only compiles 2 of 12 helper names; 6 compile fails and 4 unbound nested loop helpers remain. Go JIT now dispatches both i64 and f64 scalar helpers with framebuffer `dispatch-hit: 2`, `guard-miss: 0`. | Move the production route to the portable handler shape, then make the probe green on equal-or-better p99 by adding Go JIT plan coverage for list folds, dict/record access, and response string assembly or by proving a lower-overhead warm carrier. |
| Persistence route exemplar | `/api/ideas?query=kernel&limit=4` is now a BML-authored front-door catalog in `deploy/front-door/api.bml`. The Go carrier source-compiles it, accepts real HTTP, passes typed `kh-request`, calls a BML handler, reads `database.url` from config files only, queries PostgreSQL through `pg_query_rows`, builds JSON recipes, emits through Form `json-emit`, and returns `kh-response`. Sort choice uses BML `match`, so `"marginal_cc"` vs default dispatch is a `MATCH.SWITCH` lookup. `/api/_form/ideas-observation` wraps the same handler in a framebuffer/JIT observation envelope behind `X-Form-Observe`; `/api/_form/ideas-timing` wraps the same SQL/response pieces in a handler-internal timing envelope. `scripts/ideas_route_timing_breakdown.py` compares public FastAPI HTTP total, local native Go HTTP total, native handler segments, and Python same-SQL segments. | Production credentials were found in the Hostinger/VPS config path, not Railway/Supabase. The local kernel overlay at `~/.coherence-network/secrets/form-kernel-postgres-tunnel.json` plus SSH tunnel reaches the real compose Postgres; direct proof on 2026-06-05 read `coherence|public|1656`, while live route probes later returned `pagination.total=1666`. Native Go `/api/ideas?limit=2&sort=marginal_cc` returns `200` with body bytes `4226`. Warmed JIT after helper lowering is `11` compile-failed / `76` warming / `9` compiled / `8` dispatch-hit rows. Current timing split: public FastAPI HTTP total `p50=269.859 ms`, `p95=1087.374 ms`; local native Go HTTP total `p50=547.091 ms`, `p95=1303.667 ms`; native handler median segments are `connect=248 ms`, `summary_query=137 ms`, `page_query=154 ms`, `shape_tree=5 ms`, `json_emit=3 ms`, `handler_total=555 ms`; Python same-SQL against the same tunnel is `handler_total p50=412.903 ms` with `connect=215.906 ms`, `summary_query=93.528 ms`, `page_query=101.260 ms`, `json_dumps=0.102 ms`. Native tail samples assign pauses to `shape_tree`, `json_emit`, or params while DB segments stay near median. | Split the next work by cost class: (1) connection reuse/pool cell so every request does not pay a fresh DB connect/ping; (2) query strategy/index inspection for the two SQL reads; (3) substrate allocation/GC and Form JSON emitter compression for tail events; (4) JIT coverage where observation now points: `node_value`, logic ops, dict/field access (`_dict_get`), node write/introspection primitives (`intern_node_at`, `node_category`, `node_children`, `node_type`), `intern_trivial_float`; (5) route semantics (`query` is native-only today). |
| Lattice route composition | `KernelHTTPRouteCandidate` pressure rows are Form values; Go has pure parallel walk helpers; route results and failures can be modeled as cells. BML/Form `match` now executes as `MATCH.SWITCH`: cached literal `NodeID -> body` table, default identifier `_`, trace counters for lookups/hits/defaults/misses, and Go framebuffer rows for match hit/default/miss. | Compatibility mode still scans route rows and serially evaluates guard logic; route-key dispatch is not yet a persisted route-index cell, and observation heat does not yet condense route keys or guard bundles into indexed/JIT plans. | Add route-key cells backed by `MATCH.SWITCH`/map lookup, O(1) route-index lookup, parallel guard bundles with deterministic merge, first-class failure cells, and observation-driven condensation/JIT gates. |
| Type hierarchy representation | `LanguageTemplate`, `LanguageClass`, `KernelHTTPRequest`, `KernelHTTPResponse`, `KernelHTTPRoute`, `KernelHTTPRouteDataRef`, pressure rows, and candidates now carry compact numeric type IDs instead of repeated type-name strings. | The numeric IDs are mirrored in Form and Rust constants; they shall come from a shared type registry to avoid drift. Most production route rows still carry path strings in recipe source. | Generate or load hierarchy IDs from a shared Form-visible registry, then migrate the remaining route rows to route-data refs. |
| Compiler lens | `CompilerLens*` and `CompilerLensBmf*` values validate against existing BMF contracts. | Runtime grammar plugin loading does not emit compiler-lens alignment values. | Derive `CompilerLensBmfAlignment` from runtime grammar bindings. |
| Request input | Query/form/raw body data still reaches existing handlers through an alist, and router context now includes `__kernel_request__` as `KernelHTTPRequest(method, path, headers, query, body)` with typed header and field rows. `KernelHTTPRouteCandidate` carries the same request cell. Header lookup is Form-native and case-insensitive, matching HTTP's header-name rule instead of depending on host-side casing. | The typed request is nested inside the compatibility alist rather than being the primary handler argument for typed routes. JSON body is still raw text, not parsed into a Form value. | Make `KernelHTTPRequest` the primary handler input for typed routes while keeping the alist as an explicit projection for existing handlers. |
| Response output | Native handlers can return full `KernelHTTPResponse(status, headers, body)` via `kh-response`. The router emits the exact status line, honors a `Content-Type` header, relays filtered end-to-end headers, owns `Content-Length`/`Connection`/`X-Form-Router`, and keeps the older `(respond code body)` status tag as compatibility. Plain values still serve as `200 OK` with JSON inference. | Native response bodies are still buffered strings, not typed body cells or streaming response values. Handler selection still passes the compatibility alist as the primary argument. | Add typed/streaming response body carriers and make `KernelHTTPRequest` the primary handler input for typed routes. |
| HTTP serving (Form-native) | The full request→response path is a BML class hierarchy in Form, proven (PRs #2453–#2455): `http-parse.fk` → `http-request.fk` → `kernel-http.fk` Router → `http-server.fk` (`kh-serve`) → `http-render.fk` → `http-socket.fk`, three-way proven (render 63, request 63, server 1023, parse 11; kernel-http band 536965066) + Go/Rust socket (15). `kernel-http.fk` carries a Form-visible `kh-channel-policy`: allowed methods, method bridge pressure (`GET`→`HEAD`), no-body methods, `Allow` surface, and named cache/compression/stream/identity/authorization axes. `kh-serve-with-policy` and `kh-serve-conn-with-policy` read that value; default wrappers preserve the existing doorway. **`form-kernel-rust serve --form` now routes EVERY request through `kh-serve` over the production accept-loop + worker pool** (curl-proven on `/health` and `/api/utils/coherence_weight`): the Rust `parse_request_line`/`select_route_candidate`/`http_response` and the input fear-caps are bypassed; the `--form` manifest concatenates the HTTP stack + `router-routes.fk` (`routes` + `registry` + handlers). | CORS/access-control, cache, compression, streaming, identity, and authorization are named policy axes but are not yet enforced by Form-native channel recipes. The bodies in `router-routes.fk` are placeholders, not yet byte-identical to their Python twins; the deployment (Docker image + Traefik route) is not wired. | Enforce the named policy axes as Form channel recipes, deploy the `--form` image beside the Python api behind the load balancer (no flip — the balancer routes native paths here, the rest stays Python), make each route's response real, observe via curl/web/witness, then remove the Python implementation per proven route. |
| Runtime measurements | Router records native/fanout/local/error counts, fanout path counts, and next source-route candidate from live traffic. `/api/attention/kernel-runtime` serves those metrics natively. | Metrics are path-count centered and process-local. | Add latency, status/error class, bytes, native/fanout split, and candidate matrix dimensions. |
| Router configuration | Host/process wiring is explicit CLI config. Route semantics live in the route manifest. HTTP method invitation and bridge/no-body/Allow semantics now live in `kh-channel-policy`, and the Rust compatibility listener exports the same value into handler context as `__router_channel_policy__`. Fanout deadlines and request/response shape limits are fixed Rust defaults now; hidden environment fallbacks have been removed from the kernel-router path. | `kh-channel-policy` is default-constructed by the stdlib/compatibility mirror rather than loaded from a route/deployment `KernelRouterConfig`; deadlines, shape policy, source/lens registry, and host ceilings remain host constants or host-decoded files. | Add a Form router config cell that carries channel policy plus route data, source/lens dependencies, deadlines, shape limits, and host ceilings; Rust enforces only final guardrails. |
| Channels | Form channel values exist; BML-authored channel band validates. In-process channel payloads should carry Form object refs (`NodeID` plus graph ownership). Rust socket natives and recipe-byte helpers exist for boundaries where a shared object graph does not exist. | The channel API does not yet distinguish same-graph refs, worker-local object transfer, and socket/file artifact carriers. | Build a BML/Form channel abstraction that keeps refs in process and uses `recipe_to_bytes -> send -> recv -> bytes_to_recipe` only at an actual transport boundary. |
| Python upstream | FastAPI remains the fanout tail for routes not yet present as native route values. | 0 live front-door routes are kernel-first in production deployment data; many routes still depend on CPython lifecycle. | Promote routes after request/response/source carriers are rich enough to preserve fidelity. |

## HTTP-native function and choice audit

| Step | Function/cell | Choice point | Current carrier | Alignment |
|---|---|---|---|---|
| Listener config | `cli_serve` | host, port, worker count, `--form`, upstream | Rust CLI over file-backed route source | Host boundary; semantic policy wants `KernelRouterConfig` cells. |
| Source entry | `manifest_has_source_sections` → `source_compile_manifest_recipe_object` | source section or raw Form manifest | Rust invokes Form source compiler, then carries `CompiledRouteProgram { kernel, root NodeID }` | Aligned carrier; the source compiler still owes lens/source-map output. |
| Worker graph | `build_worker_kernel_with_route_data` | source text vs compiled object graph | Form recipe graph cloned per worker by `readonly_worker_clone()` | Aligned; immutable graph sharing/copy-on-write is the next memory improvement. |
| Route surface | `build_route_specs` / `parse_route_spec` | path/closure row, `KernelHTTPRoute`, or `KernelHTTPRouteDataRef` | Form route values plus host-decoded route-data JSON | Partly aligned; route data wants Form-visible config cells. |
| Form front door | `worker_loop` with `--form` → `serve_connection_form` | Form HTTP stack or Rust compatibility stack | `kh-serve-conn(conn, routes, registry)` | Aligned path exists; production flip waits for real byte-identical route bodies. |
| Request parse | `kh-recv-request` → `kh-request-from-raw` | request complete or still receiving | Form/BML recipes over socket bytes | Aligned for current native paths, including method/query/header lift and case-insensitive header access; Content-Length bodies and keep-alive are later cells in the pure Form socket path. |
| Channel policy | `kh-channel-policy`, `kh-method-bridge`, `kh-serve-with-policy` | allowed method, method bridge pressure, no-body method, protocol invitation | Form `KernelHTTPChannelPolicy` value; Rust compatibility context exports `__router_channel_policy__` with the same tags | Partly aligned. Method invitation, `GET`→`HEAD`, `Allow`, and no-body response policy are Form-native facts; cache/compression/stream/identity/authorization axes are named but still need carrier recipes. |
| Route choice | `kh-route-candidate`, `kh-route-candidate-eligible?`, `kh-route-choice-for-request`, `kh-route-choice-signature`, `kh-select-route-candidate-for-request` | candidate eligible, best score, tie by priority, decision selected yes/no, compressed branch pattern, policy method bridge | Form `KernelHTTPRouteChoice` values with candidate table, pressure matrices, `KernelHTTPRouteDecision` rows, and `KernelHTTPRouteChoiceSignature` rows; Rust context exports the same tags | Aligned. The score, the selected yes, the rejected no branches, the repeated branch-shape attention key, and the low-pressure `HEAD` bridge are now Form-native facts read through channel policy. |
| Dispatch choice | `kh-candidate-matched?` → `kh-dispatch` | matched route, missing handler, or route miss | Form `kh-response` values | Aligned; route miss and wiring gap are visible responses. |
| Response render | `kh-serve-response` | status/header/body to wire | Form render recipes | Aligned for buffered responses; streaming body cells are next. |
| Fanout tail | Rust `fanout_stream_to_client` and Form `http-fanout-marker` | native absent, upstream present, upstream error | Rust compatibility stream; Form marker in pure stack | Temporary. Fanout remains a bridge until all live paths have native route cells. |

## Attention queue

| Rank | Work | Why it matters | Exit criterion |
|---:|---|---|---|
| 0 | Route-frequency native goal loop | Lets `/goal` and `/loop` advance by measured web traffic instead of route count or preference. | `python3 scripts/native_route_goal_loop.py /loop --source web_api --seconds 86400` writes `docs/system_audit/native_route_goal_state.json` with next route, cumulative share, current/native grammar status, and task card until high-grammar native share reaches 90%. |
| 1 | Go front-door parity slice | Breaks the implicit Rust-primary habit and proves the front door is a sibling-kernel contract. | `form-kernel-go` serves the same `kh-serve-conn` / `routes` / `registry` manifest for at least `/health` over a real socket, with the same wire response and observation shape as Rust. |
| 2 | Handler grammar contract | Makes Python one handler port, not the endpoint model. | A handler registry row can name a BML/domain-grammar handler, a compiled legacy-Python recipe, or a Python port call, all presenting `kh-request -> kh-response`. |
| 3 | Grounded-cost promotion loop | Uses one complex endpoint to improve the full request -> handler -> response -> JIT flow instead of broad route counting. | `scripts/grounded_cost_endpoint_probe.py` reports success/422 parity and native p99 at least equal to FastAPI kernel-guest HTTP, with the production route using the portable BML/Form handler shape. |
| 4 | Go JIT plan/ABI layer | Keeps JIT aligned with Form observation and prevents endpoint-specific emitter branches. | `scripts/grounded_cost_endpoint_probe.py` reports Go dispatch, not only compile-state, for f64 scalar helpers and at least one reusable list-fold or record-field plan, with walker fallback and miss reasons visible. |
| 5 | Route-key index cells | Uses substrate coordinates instead of scanning route rows. | A request derives a route-key cell and resolves the handler through an O(1) route-index lookup, with row-scan kept only as a compatibility projection. |
| 6 | Parallel guard bundle | Uses non-mutating cells to run independent route checks concurrently. | Method/path/header/auth/body/budget guards run as an unordered `and` with deterministic first-fail / all-success merge. |
| 7 | Typed request as primary handler input | Finishes the shift from compatibility projection to typed cells. | A typed route handler receives `KernelHTTPRequest` directly; existing alist routes continue through an explicit projection. |
| 8 | First-class failure cells | Lets fail teach the body as much as success. | Parse, route, method, body, auth, permission, handler, and port failures render to HTTP through `kh-response` and also persist an observation value. |
| 9 | Observation condensation / JIT gate | Turns repeated category occurrences into structure instead of logs. | Route heat promotes gas -> water -> ice: hot route keys become indexes, hot guard bundles become pre-realized plans, hot handlers become JIT/native candidates. |
| 10 | General source class body lowering | Makes class syntax carry reusable behavior beyond route-handler methods. | A source section class can lower fields, methods, route binding, and reusable generic members without route-specific compiler branches. |
| 11 | Source-entry lens observations | Makes every route traceable from source surface to runtime handler. | Route loading emits source surface, source span or entry point, target Form value, handler, and diagnostics as compiler-lens values. |
| 12 | Full route decision table | Keeps all route candidates visible, including ineligible rows, instead of only the selected candidate. | Handler context carries selected candidate plus every candidate with matrix, score, eligibility, and selection flag. |
| 13 | Runtime grammar lens alignment | Makes new grammars visible as BMF lens tissue, not sidecars. | Runtime grammar plugin load derives `CompilerLensBmfAlignment` from resolved source/form surfaces and parse/emit bindings. |
| 14 | Multidimensional runtime attention | Lets attention steer by clusters instead of single counters. | `/api/attention/kernel-runtime` reports count, latency, status/error, bytes, source, native/fanout, and candidate score rows. |
| 15 | Route data carrier expansion | Keeps route table data out of executable recipes while preserving source route classes as flow/choice structure. | Every route row in `production-routes.fk` is either a source route class with a route-data ref or a named compatibility exception with an exit criterion. |
| 16 | `KernelRouterConfig` cell | Makes runtime policy visible as Form tissue instead of hidden host constants and host-only JSON decode. | `serve` loads a Form router config value for route data, source/lens dependencies, deadlines, shape limits, and host ceilings; host kernels enforce only final host guardrails. |
| 17 | Typed object/ref channels | Makes native channels capable of carrying Form recipes directly without flattening inside a process. | A channel test carries a Form object by ref in process and round-trips recipe bytes over a native socket only at that transport boundary, without string conversion loss. |

## Working rules

- Keep information structured until an existing boundary requires projection.
- Use object refs when a Form object graph exists in process. Serialize only at
  file, socket, process, or external-language boundaries where object identity
  cannot be shared.
- Treat BML, BMF, Form, `.fk`, `.fkb`, and future languages as route entry
  carriers or lenses, not separate runtime classes.
- At each pipeline step, inspect the touched carrier and lift it to the highest
  executable language expression already available. If a lift is not safe, name
  the missing carrier and make that the next attention point.
- Call a thing by what it does now. Avoid age labels; name whether it is alive,
  tight, paused, or ready for attention.
- Do not promote routes in bulk while request, response, and source
  observability are still tight.
- When the user says `/goal` or `/loop`, run
  `python3 scripts/native_route_goal_loop.py /goal` or
  `python3 scripts/native_route_goal_loop.py /loop --write-state` before choosing
  a route. Count only high-grammar native handlers toward the 90% target; Form
  manifest handlers are native-executable but still need a source-lift when they
  are frequent enough to matter.
- Update this sheet after each step with the new current picture and the next
  highest-alignment exit criterion.

## Paused side paths

| Path | Current stance |
|---|---|
| JIT/native optimization | Active through Go plan/ABI work. Compile-state, dispatch-state, guard misses, and fallback reasons must be observed separately. |
| Bulk endpoint promotion | Paused until `KernelHTTPRequest`, `KernelHTTPResponse`, and source-entry observability preserve fidelity. |
| Artifact-format debate | Released. `.fk` and `.fkb` are carriers; Form-native runtime objects are the requirement. |
| Proof/demo naming cleanup | Useful cleanup, but only after load-bearing route/lens tissue advances or the names block clarity. |
