---
idea_id: idea-realization-engine
status: done
source:
  - file: deploy/front-door/api.bml
    symbols: [api_substrate_kernel_image_proposals, SubstrateKernelImageProposalRoute]
  - file: deploy/kernel-router/docker-compose.kernel-router.yml
    symbols: [kernel-router-bml-front-door]
  - file: Dockerfile.kernel-router
    symbols: [api.bml]
  - file: scripts/verify_web_api_deploy.sh
    symbols: [check_kernel_image_native_proposal]
  - file: api/app/routers/substrate.py
    symbols: [KernelImageProposalRequest, KernelImageProposalOut, propose_kernel_image]
  - file: api/tests/test_substrate_kernel_image_proposals.py
    symbols: [test_kernel_image_proposal_accepts_canonical_core_preview, test_kernel_image_proposal_apply_intent_is_preview_only, test_kernel_image_proposal_rejects_unproven_source_with_trace]
  - file: api/tests/test_runtime_web_api_provenance.py
    symbols: [test_native_route_goal_loop_sees_workspace_and_task_routes_as_bml]
  - file: form/form-stdlib/kernel-image-proposal.fk
    symbols: [kip-candidate-image-json, kip-trust-envelope-json, kip-proposal-json, kip-test]
  - file: form/form-stdlib/tests/kernel-image-proposal-band.fk
    symbols: []
requirements:
  - "POST /api/substrate/kernel-image/proposals accepts BML source and returns a read-only kernel image proposal preview."
  - "Accepted previews return source hash, canonical source hash, candidate image hash, count deltas, proof trace, and trust envelope."
  - "Apply intent is carried but never mutates production from this public route."
  - "Unproven source returns a rejected preview with failed proof trace instead of silently passing."
  - "The front-door route catalog carries the same public endpoint as BML-native handler authority with Python marked as non-authoritative."
  - "Public production ingress routes this preview-only POST path to the BML front-door kernel service and deploy verification proves the native router header."
done_when:
  - 'file_declares("deploy/front-door/api.bml", "SubstrateKernelImageProposalRoute")'
  - 'file_exists("form/form-stdlib/kernel-image-proposal.fk")'
  - 'pytest_passes("api/tests/test_substrate_kernel_image_proposals.py")'
  - 'pytest_passes("api/tests/test_runtime_web_api_provenance.py")'
  - 'form_validate_passes("form-stdlib/core.fk form-stdlib/kernel-image-proposal.fk form-stdlib/tests/kernel-image-proposal-band.fk")'
  - 'public_verify_requires("POST /api/substrate/kernel-image/proposals", "X-Form-Router: native-kernel")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/kernel-image-proposal.fk form-stdlib/tests/kernel-image-proposal-band.fk && cd ../api && python3 -m pytest -q tests/test_substrate_kernel_image_proposals.py tests/test_runtime_web_api_provenance.py"
constraints:
  - "Do not mutate production, write kernel image files, open deploys, or bypass source-control proof from the public POST."
  - "This slice previews BML kernel-core image proposals only; broader Form expression mutation remains a follow-up."
---

# Spec: Kernel Image Proposal Public Interface

## Purpose

The public interface can receive Form/BML expression, but kernel mutation needs
a trust membrane before any source becomes authority. This spec carries the
kernel core image proposal route in the BML front-door catalog so the public
membrane is expressed through the kernel's own route primitive, with the Python
API left as a compatibility carrier. It lets the body show what a candidate
image would be, what proof passed or failed, and why no live mutation occurred.

## Requirements

- [ ] **R1**: `POST /api/substrate/kernel-image/proposals` accepts BML source in
  `expression`, defaults to preview mode, and returns a stable `proposal_id`.
- [ ] **R2**: Accepted previews return `source_hash`,
  `canonical_source_hash`, a `candidate_image.image_hash`, candidate counts,
  `diff.count_delta`, and a proof trace.
- [ ] **R3**: The trust envelope names the public protocol, BMA
  `kernel-image-proposal`, prediction residual, rollback state, and
  `mutation_performed=false`.
- [ ] **R4**: `requested_action="apply"` is carried as intent but still returns
  `mutation.allowed=false` and `mutation.performed=false`.
- [ ] **R5**: Unproven source returns `proposal_status="rejected-preview"` with
  failed proof steps and no candidate image.
- [ ] **R6**: `form/form-stdlib/kernel-image-proposal.fk` names the same
  preview-only trust membrane and sibling kernels agree on its proof band.
- [ ] **R7**: `deploy/front-door/api.bml` declares
  `SubstrateKernelImageProposalRoute` and returns `native_observation` with
  `handler="api_substrate_kernel_image_proposals"` and
  `python_authority=false`.
- [ ] **R8**: The Hostinger kernel-router overlay routes public
  `POST /api/substrate/kernel-image/proposals` traffic to the BML front-door
  route catalog and `scripts/verify_web_api_deploy.sh` fails if the response
  lacks `X-Form-Router: native-kernel`.

## API Contract

### `POST /api/substrate/kernel-image/proposals`

**Request**
```json
{
  "expression": "BML source text",
  "grammar": "bml",
  "requested_action": "preview",
  "source_label": "optional provenance"
}
```

**Response 200**
```json
{
  "state": "kernel-image-proposal-preview",
  "proposal_status": "accepted-preview",
  "proof_passed": true,
  "candidate_image": {
    "kind": "KERNEL-CORE-IMAGE",
    "image_hash": "sha256:..."
  },
  "mutation": {
    "allowed": false,
    "performed": false
  },
  "native_observation": {
    "grammar": "BML",
    "handler": "api_substrate_kernel_image_proposals",
    "carrier": "front-door route catalog",
    "python_authority": false
  }
}
```

Rejected previews also return `200`, with `proposal_status` set to
`rejected-preview`, `proof_passed=false`, failed proof steps, and no candidate
image. This keeps public feedback observable without turning parser failure into
authority.

## Files to Create/Modify

- `deploy/front-door/api.bml` - public BML route authority and native handler.
- `deploy/kernel-router/docker-compose.kernel-router.yml` - public path-specific BML ingress.
- `Dockerfile.kernel-router` - packages the BML front-door catalog in the router image.
- `deploy/hostinger/auto-deploy.sh` - starts and locally proves the BML front-door service.
- `scripts/verify_web_api_deploy.sh` - public deploy contract for native route provenance.
- `scripts/kernel_front_door_local_preflight.sh` - local packaging proof for the BML catalog.
- `api/app/routers/substrate.py` - compatibility preview route and response models.
- `api/tests/test_substrate_kernel_image_proposals.py` - compatibility API contract proof.
- `api/tests/test_runtime_web_api_provenance.py` - native route provenance proof.
- `form/form-stdlib/kernel-image-proposal.fk` - Form trust membrane.
- `form/form-stdlib/tests/kernel-image-proposal-band.fk` - sibling-kernel proof.
- `specs/kernel-image-proposal-public-interface.md` - this contract.
- `specs/INDEX.md` - regenerated spec index.

## Acceptance Tests

- `api/tests/test_substrate_kernel_image_proposals.py::test_kernel_image_proposal_accepts_canonical_core_preview`
- `api/tests/test_substrate_kernel_image_proposals.py::test_kernel_image_proposal_apply_intent_is_preview_only`
- `api/tests/test_substrate_kernel_image_proposals.py::test_kernel_image_proposal_rejects_unproven_source_with_trace`
- `api/tests/test_runtime_web_api_provenance.py::test_native_route_goal_loop_sees_workspace_and_task_routes_as_bml`
- `form/form-stdlib/tests/kernel-image-proposal-band.fk` returns `11111`.

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/kernel-image-proposal.fk form-stdlib/tests/kernel-image-proposal-band.fk
cd api && python3 -m pytest -q tests/test_substrate_kernel_image_proposals.py tests/test_runtime_web_api_provenance.py
cd api && python3 -m ruff check tests/test_runtime_web_api_provenance.py
scripts/kernel_front_door_local_preflight.sh
bash -n deploy/hostinger/auto-deploy.sh deploy/kernel-router/entrypoint.sh scripts/kernel_front_door_local_preflight.sh scripts/verify_web_api_deploy.sh
./scripts/verify_web_api_deploy.sh https://api.coherencycoin.com https://coherencycoin.com
python3 scripts/validate_spec_quality.py --file specs/kernel-image-proposal-public-interface.md
```

## Out of Scope

- Live production mutation from a public POST.
- Writing `.fkb` artifacts from the public route.
- Opening a PR or deploy automatically from this route.
- Supporting non-BML kernel mutation proposals.

## Risks and Assumptions

- The BML route currently verifies the kernel-core candidate through explicit
  source markers and declared count values; richer declaration parsing can move
  into the native BML parser without changing the public route contract.
- This route is a trust membrane, not final self-mutation. The next gate remains
  source-control evidence, review, CI, deploy, and public SHA verification.

## Gaps

- The native front-door lift is present. Remaining growth is deeper BML
  declaration parsing inside the handler so proof counts come from parsed
  structure rather than conservative source markers.
- Follow-up task: replace marker/count extraction in
  `api_substrate_kernel_image_proposals` with native BML declaration parser
  output while preserving the public route contract.
- Follow-up task: collapse the path-specific BML service into the general
  kernel-router front door once the broader production route manifest can carry
  BML catalog routes and mutable route semantics in one service.
