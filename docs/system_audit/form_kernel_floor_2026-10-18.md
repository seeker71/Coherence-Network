# fkwu/Form floor — 2026-10-18

This reading follows release `296bfa2a0728` and coherence-kernel
`0563230ff11e`. It treats fkwu as the only kernel. Retired carriers are bootstrap
history, not runtime choices, fallbacks, or recurring validation targets.

## Executable floor

- `runtime/fkwu-uni.c` bootstraps the `fkwu` executable.
- Form source runs directly through fkwu. Hot compatible recipes use the page
  JIT (`jit_fn_bind` / `jit_cpu_run`); a missing JIT shape is implementation
  work in that path, never a reason to restore lowering.
- The native `form-cli` build and proof are Form/BML flows entered through
  `gate/form-cli-build-run.bml`. The remaining shell wrapper only selects an
  image-built carrier or invokes that gate once for a local carrier.
- A copied native CLI bundle now publishes its `.source.id` beside the
  executable, image, symbols, and attestation. The same Form gate answers the
  current source identity without rebuilding, so cache selection no longer
  depends on retired generated bootstrap files.
- Direct native CLI arguments now enter the same Form REPL as piped commands.
  Form source and image paths remain fkwu runtime inputs; verbs are staged as
  one bounded Form turn. The focused bundle build published source identity
  `c835bb8d8cee24f8` after the native source-copy repair.
- The image reads that v3 bundle directly. Independent carrier reproduction
  remains a separately requested observation, not a recurring deployment gate;
  this release does not claim it ran. The deleted bootstrap table, stamp, and
  source-digest files no longer participate in runtime identity.
- Private build copies use the existing Form source-tree organ and its ignore
  rules, without Git metadata or an arbitrary traversal-depth cutoff. Docker
  provides shared-memory storage for the native build; the parent revision no
  longer invalidates the pinned kernel's builder layer.
- fkwu already carries native cells, sockets, HTTP client operations, crypto,
  and host I/O. The Form stdlib carries JSON and kernel HTTP composition.
- The current Coherence Network application catalog is
  `form/apps/coherence-network/api.bml`. It names native route handlers and the
  readiness contract, but it is not yet a complete public application host.

The runtime repair exposed by the Linux build replaced an undeclared host-size
cast with fkwu's own size type and kept Darwin-only JIT release state inside its
platform boundary. The focused rebuild returned `42` from the bootstrap ground
recipe and `63` from the page-JIT band. No broad kernel suite is part of this
floor reading.

## Effect on this repository

- Twenty-two utility recipes that remain called by the compatibility API now
  live as application-owned `.fk` source under `api/app/form_recipes/`. They
  execute through fkwu without the deleted seedbank or generated host tree.
- Those app recipes use the Form `add` operator directly. The `_plus` spelling
  left by the retired lowering flow is gone; no lowering route was restored.
- Federation and dialogue recipes preserve their declared SHA-256 prelude.
  fkwu owns its high-grammar realization; Python no longer concatenates the
  BML body into direct Form or strips its prelude declaration.
- The retired native router, its host harnesses, route manifests, canary probes,
  and Docker service have been released.
- Current production, setup, kernel, pulse, and route-teaching surfaces now
  name fkwu alone. Sibling-router claims remain only as explicitly historical
  evidence or one-way deployment cleanup for old containers.
- Eighteen completed specs and five kernel-router design sheets whose only
  executable owners were released with that router have been released too.
  Their landed evidence remains in dated system-audit records; current specs
  and teachings now point at the fkwu/BML application host.
- The browser-side kernel copy and its `/substrate/form` playground have
  been released. The public Python evaluator already returns HTTP 410; keeping
  a second browser kernel implied authority that the deployed body did not
  have.
- The Python `form_cli.py` implementation, host grammar bridge/demo, `ask+`
  carrier, and tests that asserted deleted kernel graph-port files have been
  released. The difficult-conversation session counsel is now an app-owned BML
  recipe called directly by the hooks, with no Python mirror.
- Duplicate offline/c-bootstrap/coreutils guides, graph/offline specs, and the
  Python grammar-coverage audit have been released. Their host-passthrough,
  lowering, and removed-organ claims no longer compete with the live fkwu/JIT
  floor.
- The live Native Kernel Binary, One Engine, and Kernel Knows Itself concepts
  now name fkwu as the sole runtime and the page JIT as the direct speed path.
  Other kernel sources remain bootstrap history only.
- Routine bootstrap and platform-comparison workflows have been released.
  Validation is now claimed only by the changed
  surface; fkwu validation is required when fkwu changes.
- Delivery guidance and the native `delivery_care.bml` recipe replace recurring
  procedural gates. Main retains deletion/non-fast-forward protection; approval,
  resolved-thread, and linear-history requirements no longer block useful work.
  Repeated deployment schedules have been retired. Host carrier files publish
  atomically so an executing release retains its original file.
- The production API remains a Python compatibility host around routes that
  have not yet moved behind the native Form application host. This is current
  location, not destination authority.

## Work exposed by the resnapshot

The next work is direct and belongs in Form/BML:

1. Give the native HTTP server template-parameter dispatch so routes such as
   `/ideas/{id}` bind parameters without a host router.
2. Bring file-backed application configuration, PostgreSQL access, persistence,
   and startup ownership into the fkwu/Form host.
3. Move route families from the Python compatibility host to
   `api.bml`, preserving their observed effects and removing each Python owner
   once its native replacement is live.
4. Return a native browser door only after the fkwu application host serves it.
5. Close every newly observed hot-shape gap in the page JIT itself. Lowering is
   not an accepted continuation path.

## Validation boundary

This resnapshot deliberately avoids the old broad suite. The fkwu runtime
repair receives only the focused compile, bootstrap, and page-JIT readings
above. Repository edits receive structural checks.

## Trust trace

Exact source locations and runtime surfaces were read through the native fkwu
Form lookup path. The later `form-cli ask` returned dictionary/source references,
but no NodeID or sufficiency receipt; it is a partial native lookup, not a fully
trusted answer. Architecture
synthesis and this prose used the rented OpenAI Codex reasoning lane and are
grounded here in the cited live source paths rather than reported as native
generation.
