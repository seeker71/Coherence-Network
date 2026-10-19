# Pulse — the independent Form witness

Pulse runs reusable BML templates through the pinned fkwu native source/JIT door.
It observes the public API and web origins, remembers every sample in native Form
Recipe pages, derives silence receipts, and serves the existing read-only JSON API.
Its process and storage stay independent of the API, PostgreSQL and Neo4j. The
public `/pulse` page is served directly by the same native read owner.

## The living surface

- `GET /pulse/now`: current organs and unresolved silences.
- `GET /pulse/history?days=N`: daily bars, uptime and exact nearest-rank p50/p95.
- `GET /pulse/silences?days=N`: silence history and repair notes.
- `GET /pulse/health`: native witness liveness and durable sample count.
- `GET /`: service identity and endpoint discovery.
- `GET /pulse?days=N`: native HTML with daily evidence and complete repair notes.

History and silence windows accept every integer from 1 through 180; the default
is 90. Organs and assertions live in `organs.json`. Shared upstreams are observed
once per round, in parallel native workers. TLS verifies certificates through
fkwu's existing TLS resource. Each sample carries its own observed completion time.
The HTTP listener uses Form-emitted Linux socket/readiness operations through
the existing CPU-image JIT. Neither curl nor a host web server is used. Private
copy-on-write request contexts retain admitted read cells and held request values;
no request executable, JSON spool or nested read process is needed. Slow headers,
archive rendering and output backpressure leave other peers free to progress.

## Source owners

`templates.bml` carries reusable HTTP and declarative assertion templates.
`form-persistence.bml` carries typed snapshots, publication ownership, weighted
histograms, balanced JSON spans and checksummed transaction frames.
`native-store.bml` specializes them into replayable raw-page,
daily histogram, exact range-summary, daily-card and silence indexes. `store.bml` owns query/repair templates; `probe.bml`
specializes them from the organ catalog. `main.bml` owns cadence and the independent
native HTTP child. `http.bml` owns the public boundary; `fetch.bml` owns a native
network arrival. Persistence crosses only the existing native file resources;
there is no database process, SQL interpreter or host-language business logic.
`html.bml` supplies escaped document/disclosure templates; `web.bml` specializes
them for Pulse. One coherent native snapshot replaces the three HTTP reads and
React hydration path. Day links reveal full daily readings and every overlapping
silence; the complete archive link has no thirty-record display cap. The page
keeps ordinary site navigation on the configured canonical web origin, including
when it is read at the independent Pulse origin. Silence windows use interval
overlap, retaining closed receipts that began before the cutoff and ended within it.
The bucket's source-sequence-keyed end bound keeps that read exact and bounded.
Sorted closed-interval endpoints and open counts supply the page's exact archive
count without loading every note. Full interval rows are read when disclosed.
The page offers 7/30/90/180-day windows and accepts the API's existing 1–180-day range.
The default page remains seven days. No JavaScript or external assets are needed.
HTML carries `Cache-Control: no-store, no-transform` and `script-src 'none'`:
fresh native evidence stays intact across proxies rather than acquiring analytics.

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
the sliding window's partial first day reads the smaller raw-page side of its
cutoff. A prefix is subtracted from the exact daily count/histogram; a suffix is
used directly. Both preserve observed-only rows and nearest-rank weights. No history
window, latency threshold or failure is hidden by a cache.
Daily cards and aligned binary range summaries are durable derived indexes,
not time-to-live response caches. Each transaction publishes changed leaves,
cards and ancestor summaries before its checkpoint. Six levels describe physical
fan-in: longer ranges use additional blocks, without a retention or read cap.
Startup derives indexes once and reconciles changed raw-day sequence coordinates;
an older writer's subsequent rows therefore remain visible at handoff. Native
`index.bml` workers keep temporary index construction inside each organ's task.

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
their checkpoint. Independent pages share a staged-byte publication barrier;
dependent indexes cross a following barrier. Recovery checkpoints the next journal
before archiving a torn predecessor, replays complete frames idempotently, and retains a torn
tail intact. Missing or unreadable existing Recipe pages are findings, not empty
history. `snapshot.bml` makes a consistent native snapshot through streaming file
resources; supply a fresh `destination` outside `store_path`. Legacy recovery copies
remain private and recoverable; they are not an active persistence path.

The container's `fkwu.conf` gives each native task private temporary nodes
(`FK_FIELD_OFF 1`). Durable Recipe files carry memory between tasks. Reads,
observation waves and import ranges end their own task process, releasing temporary
nodes rather than accumulating a second shared-field copy of the entire archive.
The listener and cadence owner stay small; all task code still uses the fkwu JIT.
Compound JSON is emitted as balanced spans, retaining canonical Form scalar
escaping. Histogram counts are accumulated once; daily pages are read once per
history request. Health reads its single atomic checkpoint without a history lock.
Other reads take short publication-boundary snapshots, render outside the writer
lock and verify the ending checkpoint. An overlapping write re-enters the same
read; neither a partial view nor its transient stop is published. Native cell
diagnostics still surface when the source version is stable. The generic
`fp-coherent` template carries that ownership rather than serializing whole reads.

## Focused observation and delivery

Reuse existing grounding. When this application boundary changes, one
`observe.bml` fixture observes nearest-rank history, supported windows and durable
three-sample silence repair and crash replay on a separate native store. A native network round and
actual HTTP responses establish the running replacement. No kernel suite or
sibling-kernel validation belongs to this application movement.
For a changed web boundary, `web-observe.bml` reads the complete native HTML,
checks escaping and weighted ranks, and reports its payload and elapsed time.
`trace.bml` replaces the retired curl trace with one native parallel wave. Complete
bodies and headers remain private; total time and the serving runtime header are
reported separately. Unexposed TLS stage timestamps are not fabricated.

Before replacing a running witness, retain its private consistent snapshot. Observe
the replacement against that archive, then land and deploy with the original
volume. For a legacy SQLite volume, follow the one-time handoff above. Verify
service identity, current samples, history and silence receipts.
An API restart is observable independently; whole-host loss still calls for a
separately hosted witness rather than a claim this process cannot establish.
