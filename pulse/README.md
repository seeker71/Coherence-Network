# Pulse — the independent Form witness

Pulse runs reusable BML templates through the pinned fkwu native source/JIT door.
It observes the public API and web origins, remembers samples in its own SQLite
volume, derives silence receipts, and serves the existing read-only JSON API.
Its process and storage stay independent of the API, PostgreSQL and Neo4j.

## The living surface

- `GET /pulse/now`: current organs and unresolved silences.
- `GET /pulse/history?days=N`: daily bars, uptime and exact nearest-rank p50/p95.
- `GET /pulse/silences?days=N`: silence history and repair notes.
- `GET /pulse/health`: native witness liveness and durable sample count.
- `GET /`: service identity and endpoint discovery.

History and silence windows accept every integer from 1 through 180; the default
is 90. Organs and assertions live in `organs.json`. Shared upstreams are observed
once per round, in parallel native workers. TLS verifies certificates through
fkwu's existing TLS resource. Each sample carries its own observed completion time.
The HTTP listener uses native sockets; neither curl nor a host web server is used.

## Source owners

`templates.bml` carries reusable HTTP, declarative assertion and SQLite resource
templates. `store.bml` carries durable query/rollup/repair templates; `probe.bml`
specializes them from the organ catalog. `main.bml` owns cadence and the independent
native HTTP child. `http.bml` owns the public boundary; `fetch.bml` owns a native
network arrival. The sole external application resource is SQLite's existing
file engine, crossed once per probe round and once per public database read.
SQLite SQL is authored inside BML; there is no host-language business logic.

## Configuration and running

`config.json` is the production configuration. A git-ignored `config.local.json`
beside it can supply a complete local configuration. Values come from files,
including public origins, database/work paths, interval, retention, port and CORS.
For local use choose writable database/work paths, then:

```sh
cd form
./fkwu ../pulse/main.bml
```

The host provides SQLite and libssl with trusted CA roots. The container builds
the unchanged pinned fkwu and supplies those resources. Build from the repository
root with `pulse/Dockerfile`; keep the existing `pulse_data:/data` volume.
Native `api/app/form_recipes/deployment_compose_care.bml` moves the Compose build
context to that root and retires the former PULSE_* environment configuration,
preserving routing, volumes and unrelated operator settings.

## Memory and repair

The existing `samples` and `silences` tables, IDs and notes remain authoritative.
Additive daily counts and latency histograms are populated transactionally once
and maintained at the SQLite write boundary. They retain exact percentile ranks;
the sliding window's partial first day is read from raw samples. No history
window, latency threshold or failure is hidden by a cache.

Three consecutive observed failures open a silence. Five minutes of unresolved
silence escalates severity. Three observed successes close it at the first closing
success and preserve a `boundary_repair_protocol: choice=re_enter` note with its
count and evidence window. Explicitly unobserved historical samples remain
unknown and do not enter uptime, percentile or repair evidence. Stale samples
become unknown after three probe intervals. An unresolved silence keeps the
overall witness at least strained. Raw samples retain 180 days; silences persist.

## Focused observation and delivery

Reuse existing grounding. When this application boundary changes, one
`observe.bml` fixture observes nearest-rank history, supported windows and durable
three-sample silence repair on a separate database. A native network round and
actual HTTP responses establish the running replacement. No kernel suite or
sibling-kernel validation belongs to this application movement.

Before replacing a running witness, take a private SQLite online backup. Observe
the replacement against that snapshot, then land and deploy with the original
volume. Verify service identity, current samples, history and silence receipts.
An API restart is observable independently; whole-host loss still calls for a
separately hosted witness rather than a claim this process cannot establish.
