# Source-language kernel router tracking sheet

This is the current picture. Update it in place as the route body changes. Do
not preserve history here; keep the live goal, what works, what is tight, and
where attention moves next.

## Living goal

Every authored language can express Form-native cells and recipes that the
kernel can run. BML is the first high-level route dialect being grown deeply,
not the name of the shared runtime object model. BMF is the bidirectional lens
layer. Form recipes and cells are runtime truth. Rust hosts sockets, HTTP
framing, workers, deadlines, and opaque host ports.

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

## Current working tissue

| Surface | Working now | Friction | Next attention |
|---|---|---|---|
| Route carrier | `form-kernel-rust serve` loads raw Form source manifests and source-authored manifests compiled to an in-memory Form Recipe object graph. The router carries `RouteProgram::RecipeObject(Arc<CompiledRouteProgram>)`; workers clone the compiled `Kernel` graph with `readonly_worker_clone()` and walk the root `NodeID`. No route-runtime serialization/deserialization is required. Selected `KernelHTTPRouteCandidate` pressure rows are exposed as Form values. `/health` is now authored as a `RouteCell` class in a `section [form.bml]` source dialect and projected through `KernelHTTPRouteDataRef`. | The selected candidate is inspectable as Form tissue; the full candidate set, source-entry observability, and shared immutable graph overlays are still tight. | Carry the full candidate table, not only the selected candidate. |
| Route authoring | Raw Form manifests load. Source manifests source-compile at load to Form Recipe objects. `section [form.bml]` supports readable route `template` blocks with members and `class` blocks with methods, and BML now emits the same `LanguageTemplate`/`LanguageClass` model future grammars should emit. `/health` uses `class HealthRoute { def handle(request) { ... } route = route_data(health, handle); }`: class/method flow is recipe tissue, while method/path/priority/budget live in `production-routes-data.json`. Source pipelines no longer require `.fkb` route sidecars or lowered route source as the runtime carrier. | Production manifest is still mostly Form-authored; class body lowering covers route classes and methods, not arbitrary fields/constructors/interfaces yet. Route-data JSON is host-decoded, not yet a Form-visible config cell. | Generalize class body lowering and lift route-data loading into `KernelRouterConfig`/route-data cells that attention can inspect. |
| Type hierarchy representation | `LanguageTemplate`, `LanguageClass`, `KernelHTTPRequest`, `KernelHTTPResponse`, `KernelHTTPRoute`, `KernelHTTPRouteDataRef`, pressure rows, and candidates now carry compact numeric type IDs instead of repeated type-name strings. | The numeric IDs are mirrored in Form and Rust constants; they should come from a shared type registry to avoid drift. Most production route rows still carry path strings in recipe source. | Generate or load hierarchy IDs from a shared Form-visible registry, then migrate the remaining route rows to route-data refs. |
| Compiler lens | `CompilerLens*` and `CompilerLensBmf*` values validate against existing BMF contracts. | Runtime grammar plugin loading does not emit compiler-lens alignment values. | Derive `CompilerLensBmfAlignment` from runtime grammar bindings. |
| Request input | Query/form/raw body data still reaches existing handlers through an alist, and router context now includes `__kernel_request__` as `KernelHTTPRequest(method, path, headers, query, body)` with typed header and field rows. `KernelHTTPRouteCandidate` carries the same request cell. | The typed request is nested inside the compatibility alist rather than being the primary handler argument for typed routes. JSON body is still raw text, not parsed into a Form value. | Make `KernelHTTPRequest` the primary handler input for typed routes while keeping the alist as an explicit projection for existing handlers. |
| Response output | Native handlers return body text/JSON; router frames status `200 OK` and infers JSON content type. | Form handlers cannot yet return full `KernelHTTPResponse(status, headers, body)`. | Let native handlers return `KernelHTTPResponse` and emit exact status/header/body. |
| Runtime measurements | Router records native/fanout/local/error counts, fanout path counts, and next source-route candidate from live traffic. `/api/attention/kernel-runtime` serves those metrics natively. | Metrics are path-count centered and process-local. | Add latency, status/error class, bytes, native/fanout split, and candidate matrix dimensions. |
| Router configuration | Host/process wiring is explicit CLI config. Route semantics live in the route manifest. Fanout deadlines and request/response shape limits are fixed Rust defaults now; hidden environment fallbacks have been removed from the kernel-router path. | Tunable policy is not yet a Form-visible `KernelRouterConfig` cell, so attention cannot inspect or modify it as tissue. | Add a Form router config cell for deadlines, shape policy, source/lens registry, and host ceilings. |
| Channels | Form channel values exist; BML-authored channel band validates. In-process channel payloads should carry Form object refs (`NodeID` plus graph ownership). Rust socket natives and recipe-byte helpers exist for boundaries where a shared object graph does not exist. | The channel API does not yet distinguish same-graph refs, worker-local object transfer, and socket/file artifact carriers. | Build a BML/Form channel abstraction that keeps refs in process and uses `recipe_to_bytes -> send -> recv -> bytes_to_recipe` only at an actual transport boundary. |
| Python upstream | FastAPI remains the fanout tail for routes not yet present as native route values. | 0 live front-door routes are kernel-first in production deployment data; many routes still depend on CPython lifecycle. | Promote routes after request/response/source carriers are rich enough to preserve fidelity. |

## Attention queue

| Rank | Work | Why it matters | Exit criterion |
|---:|---|---|---|
| 1 | `KernelHTTPResponse` handler output | Lets routes express status and headers natively. | A native handler returns non-200 status plus headers and the router emits exact HTTP status/header/body. |
| 2 | Typed request as primary handler input | Finishes the shift from compatibility projection to typed cells. | A typed route handler receives `KernelHTTPRequest` directly; existing alist routes continue through an explicit projection. |
| 3 | General source class body lowering | Makes class syntax carry reusable behavior beyond route-handler methods. | A source section class can lower fields, methods, route binding, and reusable generic members without route-specific compiler branches. |
| 4 | Source-entry lens observations | Makes every route traceable from source surface to runtime handler. | Route loading emits source surface, source span or entry point, target Form value, handler, and diagnostics as compiler-lens values. |
| 5 | Full route decision table | Keeps all route candidates visible, including ineligible rows, instead of only the selected candidate. | Handler context carries selected candidate plus every candidate with matrix, score, eligibility, and selection flag. |
| 6 | Runtime grammar lens alignment | Makes new grammars visible as BMF lens tissue, not sidecars. | Runtime grammar plugin load derives `CompilerLensBmfAlignment` from resolved source/form surfaces and parse/emit bindings. |
| 7 | Multidimensional runtime attention | Lets attention steer by clusters instead of single counters. | `/api/attention/kernel-runtime` reports count, latency, status/error, bytes, source, native/fanout, and candidate score rows. |
| 8 | Route data carrier expansion | Keeps route table data out of executable recipes while preserving source route classes as flow/choice structure. | Every route row in `production-routes.fk` is either a source route class with a route-data ref or a named compatibility exception with an exit criterion. |
| 9 | `KernelRouterConfig` cell | Makes runtime policy visible as Form tissue instead of hidden host constants and host-only JSON decode. | `serve` loads a Form router config value for route data, source/lens dependencies, deadlines, shape limits, and host ceilings; Rust only enforces the final host guardrails. |
| 10 | Typed object/ref channels | Makes native channels capable of carrying Form recipes directly without flattening inside a process. | A channel test carries a Form object by ref in process and round-trips recipe bytes over a native socket only at that transport boundary, without string conversion loss. |

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
- Update this sheet after each step with the new current picture and the next
  highest-alignment exit criterion.

## Paused side paths

| Path | Current stance |
|---|---|
| JIT/native optimization | Paused until route promotion is blocked by recipe-walk speed. |
| Bulk endpoint promotion | Paused until `KernelHTTPRequest`, `KernelHTTPResponse`, and source-entry observability preserve fidelity. |
| Artifact-format debate | Released. `.fk` and `.fkb` are carriers; Form-native runtime objects are the requirement. |
| Proof/demo naming cleanup | Useful cleanup, but only after load-bearing route/lens tissue advances or the names block clarity. |
