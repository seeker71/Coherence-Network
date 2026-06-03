# Compost Register - 2026-06-03

## Released This Breath

- `form/form-kernel-rust/examples/router-bml-proof.bml` - removed. The living
  route surface is `deploy/kernel-router/production-routes.fk`, where
  `/api/attention/kernel-runtime` is served by the kernel from live router
  metrics.
- `form/form-kernel-rust/router_bml_proof_harness.py` - removed with the route
  manifest it exercised. The branch no longer keeps a Python harness for a
  deleted BML router artifact.

## Still Tight

- `form/form-kernel-rust/examples/router-proof.fk` - still named as a
  proof-shaped router manifest; transform or fold into the real deployment
  route surface in a later breath.
- `form/form-kernel-rust/examples/router-body-proof.fk` - same router family,
  still proof-shaped.
- `form/form-kernel-rust/examples/router-real-app-proof.fk` - same router
  family, still proof-shaped.
- `kernels/KERNEL_AS_ROUTER.md` - still names the endpoint recipe family with
  `_demo` paths. Align those references after the endpoint recipe files and
  their harness constants are renamed together.
