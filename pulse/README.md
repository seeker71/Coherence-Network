# Pulse — the independent Form witness

Pulse runs reusable BML templates through the pinned fkwu native source/JIT door.
It observes the public API and web origins, remembers every sample in native Form
Recipe pages, derives silence receipts, and serves the existing read-only JSON API.
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

`templates.bml` carries reusable HTTP and declarative assertion templates.
`form-persistence.bml` carries typed snapshots, publication ownership and checksummed
transaction frames. `native-store.bml` specializes them into replayable raw-page,
daily histogram and silence indexes. `store.bml` owns query/repair templates; `probe.bml`
specializes them from the organ catalog. `main.bml` owns cadence and the independent
native HTTP child. `http.bml` owns the public boundary; `fetch.bml` owns a native
network arrival. Persistence crosses only the existing native file resources;
there is no database process, SQL interpreter or host-language business logic.

## Configuration and running

`config.json` is the production configuration. A git-ignored `config.local.json`
beside it can supply a complete local configuration. Values come from files,
including public origins, store/legacy/work paths, interval, port and CORS.
For local use choose writable store/work paths, then:

```sh
cd form
./fkwu ../pulse/main.bml
```

The host provides libssl with trusted CA roots. The container builds
the unchanged pinned fkwu and supplies those resources. Build from the repository
root with `pulse/Dockerfile`; keep the existing `pulse_data:/data` volume.
Native `api/app/form_recipes/deployment_compose_care.bml` moves the Compose build
context to that root and retires the former PULSE_* environment configuration,
preserving routing, volumes and unrelated operator settings.

## Memory and repair

Raw rows retain their original row IDs, fields, silence IDs and repair notes.
Native daily counts and latency histograms retain exact percentile ranks;
the sliding window's partial first day is read from raw samples. No history
window, latency threshold or failure is hidden by a cache.

Three consecutive observed failures open a silence. Five minutes of unresolved
silence escalates severity. Three observed successes close it at the first closing
success and preserve a `boundary_repair_protocol: choice=re_enter` note with its
count and evidence window. Explicitly unobserved historical samples remain
unknown and do not enter uptime, percentile or repair evidence. Stale samples
become unknown after three probe intervals. An unresolved silence keeps the
overall witness at least strained. All imported and subsequent history persists;
the public 1–180-day window is a read shape, not a deletion policy.

## History handoff and recovery

`sqlite-import.bml` reads the legacy file format directly, including committed,
checksum-valid WAL frames. `import-history.bml` streams the base archive into native
pages using resumable native workers. `migrate.bml` takes file-backed configuration
on stdin: `source`, `store_path`, and `work_path`. Run it against an immutable private
snapshot while the old witness continues serving. At cutover, startup reads rows
after the imported row ID and refreshes silence closures/notes from `legacy_path`.
It then archives the original database and WAL under the native store's
`retired-sqlite/` directory. No external SQLite runtime participates in import or service.

Native transaction frames are flushed before indexed pages, and those pages before
their checkpoint. Recovery replays complete frames idempotently and retains a torn
tail intact. Missing or unreadable existing Recipe pages are findings, not empty
history. `snapshot.bml` makes a consistent native snapshot through streaming file
resources; supply a fresh `destination` outside `store_path`. Legacy recovery copies
remain private and recoverable; they are not an active persistence path.

The container's `fkwu.conf` gives each native task private temporary nodes
(`FK_FIELD_OFF 1`). Durable Recipe files carry memory between tasks. Reads,
observation waves and import ranges end their own task process, releasing temporary
nodes rather than accumulating a second shared-field copy of the entire archive.
The listener and cadence owner stay small; all task code still uses the fkwu JIT.

## Focused observation and delivery

Reuse existing grounding. When this application boundary changes, one
`observe.bml` fixture observes nearest-rank history, supported windows and durable
three-sample silence repair and crash replay on a separate native store. A native network round and
actual HTTP responses establish the running replacement. No kernel suite or
sibling-kernel validation belongs to this application movement.

Before replacing a running witness, retain its private consistent snapshot. Observe
the replacement against that archive, then land and deploy with the original
volume. For a legacy SQLite volume, follow the one-time handoff above. Verify
service identity, current samples, history and silence receipts.
An API restart is observable independently; whole-host loss still calls for a
separately hosted witness rather than a claim this process cannot establish.
