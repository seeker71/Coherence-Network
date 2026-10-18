# fkwu/Form floor — 2026-10-18

This reading follows the current parent `origin/main` and coherence-kernel
`ea25e00d0`. It treats fkwu as the only kernel. Retired carriers are bootstrap
history, not runtime choices, fallbacks, or recurring validation targets.

## Executable floor

- `runtime/fkwu-uni.c` bootstraps the `fkwu` executable.
- Form source runs directly through fkwu. Hot compatible recipes use the page
  JIT (`jit_fn_bind` / `jit_cpu_run`); a missing JIT shape is implementation
  work in that path, never a reason to restore lowering.
- The native `form-cli` build and proof are Form/BML flows entered through
  `gate/form-cli-build-run.bml`. The remaining shell wrapper only selects an
  image-built carrier or invokes that gate once for a local carrier.
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
- The retired native router, its host harnesses, route manifests, canary probes,
  and Docker service have been released.
- The browser-side kernel copy and its `/substrate/form` playground have
  been released. The public Python evaluator already returns HTTP 410; keeping
  a second browser kernel implied authority that the deployed body did not
  have.
- Routine bootstrap and platform-comparison workflows have been released.
  Validation is now claimed only by the changed
  surface; fkwu validation is required when fkwu changes.
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
Form lookup path. `form-cli ask` did not return within its bounded attempt, so
it supplied no grounded answer and was not retried unchanged. Architecture
synthesis and this prose used the rented OpenAI Codex reasoning lane and are
grounded here in the cited live source paths rather than reported as native
generation.
