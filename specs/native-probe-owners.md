---
idea_id: pipeline-reliability
status: active
source:
  - file: api/app/form_recipes/native_health.bml
    symbols: [nh-project, nh-contention]
  - file: api/app/form_recipes/native_health_observation.bml
  - file: api/app/form_recipes/native_instance_pulse.bml
    symbols: [nip-project, nip-self, nip-peers]
  - file: api/app/form_recipes/native_substrate.bml
    symbols: [nsub-page, nsub-kernel-status, nsub-ingest, nsub-cell, nsub-cells, nsub-stats]
  - file: api/app/form_recipes/native_named_persistence.bml
  - file: api/app/form_recipes/native_http.bml
  - file: api/app/form_recipes/native_api.bml
  - file: api/app/form_recipes/native_api_handlers.bml
  - file: api/app/form_recipes/deployment_compose_care.bml
  - file: api/config/native_api.json
  - file: api/app/main.py
  - file: api/app/middleware/serialized_observation.py
  - file: api/app/middleware/read_tracking.py
  - file: api/tests/test_observation_liveness.py
  - file: api/app/routers/health.py
  - file: api/app/routers/concepts.py
  - file: api/app/routers/substrate.py
  - file: api/app/routers/agent_diagnostics_routes.py
  - file: api/app/routers/pulse.py
  - file: api/app/services/instance_pulse_service.py
  - file: Dockerfile.api
  - file: deploy/hostinger/auto-deploy.sh
  - file: scripts/verify_web_api_deploy.sh
requirements:
  - "R1: Form/BML on the fkwu JIT owns public health, readiness, persistence, contention, instance pulse and substrate probe routes."
  - "R2: Public health reports the serving image identity and live PostgreSQL observation without routine audit, kernel challenge or witness work."
  - "R3: Native source offers and cell reads share reusable native persistence; replaced Python owners, unused Neo4j and disconnected release gates retire."
  - "R4: Compatibility concept reads yield through the framework worker; read sensing and runtime-event persistence follow completed response delivery through bounded serialized workers. Concurrent ping stays responsive while the request still owns accepted observations."
done_when:
  - "One affected native observation reads health/readiness, contention and substrate source/cell effects with explicit runtime and immutable image identity."
  - "Replaced Python probe owners and unused release-gate functions are absent; compatibility ping/version still describe their actual process."
  - "The merged target serves publicly through native routing; released Neo4j ownership and dependency references are absent from the live Compose model."
test: "cd form && ./fkwu --check ../api/app/form_recipes/native_api.bml"
constraints:
  - "Native probe implementation stays in Form/BML on the pinned fkwu JIT. Compatibility middleware scheduling stays with its existing Python carrier; it adds no probe or persistence authority."
  - "Observe only changed claims; no routine kernel, audit or historical response-parity suites."
  - "Private source stays outside public ingestion; active peer observations and unrelated service state retain their owners."
---

# Native probe owners — live dependency readings without routine audit gates

Health describes the serving process and its present dependency, not every
historical invariant in the repository. `native_health.bml` reads PostgreSQL
and immutable image identity directly. Readiness, persistence shape and
write-lane contention reuse that native boundary. The compatibility process
keeps its own ping/version surface; another process's success is not its breath.

`native_instance_pulse.bml` gives self/now one present native reading and reads
stored peer observations without polling from a request. File-backed federation
configuration offers the instance identity and visibility. The local Python
checking pool and environment switches retire; active federation peer writes
and their persisted observations keep their owner until the write effect moves.

`native_substrate.bml` resolves public page sources, observes the running kernel,
accepts public source offers and reads cells. `native_named_persistence.bml`
owns reusable content-addressed values and named cells in PostgreSQL. Existing
lattice rows remain read projections while callers move; no second Python
write authority is introduced. HTTP parsing, request bodies, route templates
and methods share native meaning with the deployment description.

The image binds parent and kernel revisions at build time in
`config/image_identity.json`. A newer host configuration cannot relabel the
serving release. The image preserves the canonical `/app/form` source home:
`/app/form/form/form-stdlib`, `/app/form/control` and `/app/form/runtime`.
The owned-target deployment read and public route observation
prove the actual movement; audit, schema, carrier challenge and witness work
belong to an explicit affected claim. The authenticated independent observer
retains its target/nonce ownership separately from ordinary health.

PostgreSQL already owns graph state. The unused Neo4j service, driver and
discovery sensor leave with their dependency references. Reusable Compose care
releases only explicitly named service owners and project volumes unheld by
surviving services. The external native Pulse witness remains the observation
owner; federation peer records remain active persistence, not duplicate local
probe work to delete indiscriminately.

## Compatibility observation and liveness

A slow read-promotion scan or runtime-event write must yield the ASGI loop.
The synchronous concept read uses the framework worker, including graph,
canonical-view and translation calls. Each existing observer uses one worker
admission after the complete response body has been sent. The ASGI request
awaits that work through its background-task lifecycle and preserves existing
background work. Failure responses without an available response object still
await capture directly. Admission belongs to the worker
until it finishes, including after raw request-task cancellation; waiting
requests remain cancellable. Request headers are copied into
values before worker admission. The owner retains only its one admitted task;
no detached waiting queue or new retention is added.
Graceful shutdown awaits both admitted observers; the host retains its process
termination deadline. Stats read snapshots of mutable counters. Ping keeps its existing persistence
exemption and can answer while another request is waiting for observation.

The concurrency proof is `cd api && .venv/bin/python -m pytest -q tests/test_observation_liveness.py`: hold a real observer with a synchronization
barrier, receive a concurrent ping before releasing it, then verify the accepted
observation completes. An actual concept-route barrier covers its graph read;
ASGI send observations prove the full response body precedes read and runtime
observation. A second request cannot start a second sensing worker.
This is a compatibility scheduling proof; native health retains its own owner.

## Verification

The source admission command above checks the application closure, not a live
dependency claim. Use the focused native route observation for the changed
probe effect, source/diff reads for retirement, then the merged rollout's owned
target and public native route evidence. Reuse those readings while inputs
hold. `native_health_observation.bml` implements the explicitly authenticated
nonce observation; importing it alone is not execution proof. No old
response-shape, kernel comparison, routine audit or archive-parity gate is added.

See also: [deployment guide](../docs/DEPLOY.md),
[production substrate](../docs/PRODUCTION-SUBSTRATE.md),
[Pulse silence repair](pulse-silence-boundary-repair.md).
