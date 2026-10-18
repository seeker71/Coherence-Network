# Proof of the current Form substrate

The executable authority is `fkwu`, bootstrapped from
`form/runtime/fkwu-uni.c`. Form source runs directly on that runtime; hot
compatible recipes enter its page JIT. Retired bootstrap carriers and generated
host paths are not part of the current proof claim.

Two focused observations establish the present floor:

- `form/fkwu form/bootstrap/ground.fk` returned `42`.
- `form/fkwu form/form/form-stdlib/tests/jit-page-band.bml` returned `63`.

These readings were taken for the 2026-10-18 kernel resnapshot. They are not a
recurring full-kernel suite. A later fkwu change earns the smallest focused
observation that proves its changed claim.

The Coherence Network application surface is
`form/form/apps/coherence-network/api.bml`. It names native route behavior and
readiness, while template-parameter dispatch, configuration, PostgreSQL,
persistence, and startup ownership remain direct work in the native application
host. The Python API is still a compatibility host for routes that have not yet
moved; it is not presented as kernel authority.

See `docs/system_audit/form_kernel_floor_2026-10-18.md` for the full floor and
the exact work exposed by the resnapshot.
