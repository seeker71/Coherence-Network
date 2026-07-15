---
idea_id: coherence-kernel-one-home
status: done
source:
  - file: .gitmodules
    symbols: [submodule.form]
  - file: api/app/services/form_kernel_bridge.py
    symbols: [resolve_recipe_path(), app_recipes_dir(), seedbank_examples_dir()]
  - file: api/scripts/local_runner.py
    symbols: [_create_worktree(), _create_standalone_task_repo(), _initialize_worktree_submodules()]
  - file: api/scripts/agent_runner.py
    symbols: [_initialize_repo_submodules(), _repo_submodules_match_reviewed_pins()]
  - file: scripts/prepare_form_submodule.py
    symbols: [preserve_legacy_form(), verify_reviewed_form()]
  - file: api/tests/test_kernel_submodule_contract.py
    symbols: [test_form_is_pinned_path_preserving_kernel_submodule(), test_kernel_regeneration_is_owned_by_submodule(), test_network_endpoint_recipes_are_owned_by_the_api()]
requirements:
  - "Coherence Network consumes coherence-kernel as an exact gitlink at the existing form/ path."
  - "Kernel deltas are reconciled upstream while Network-owned endpoint recipes remain with the API."
  - "CI, deploy, clone, and autonomous-worktree paths initialize the recursive submodule before use."
  - "Existing form/form-stdlib and form/form-kernel-* consumer paths remain valid."
  - "Kernel bootstrap regeneration is authored inside coherence-kernel; the consumer has no script that writes committed form/ artifacts."
done_when:
  - "A recursive clone populates form/ at the superproject's pinned gitlink SHA."
  - "Shared and application recipe ownership tests pass."
  - "Host deploy and task-worktree bootstrap contracts pass."
  - 'file_exists(".gitmodules")'
  - 'file_exists("api/tests/test_kernel_submodule_contract.py")'
  - 'pytest_passes("api/tests/test_kernel_submodule_contract.py")'
test: "cd api && python3 -m pytest -q tests/test_kernel_submodule_contract.py tests/test_form_kernel_bridge_structure_access.py tests/test_api_dockerfile_contract.py"
constraints:
  - "Do not mount the whole coherence-kernel repository at form/, which would create form/form/."
  - "Do not use a compatibility symlink; Windows checkouts must receive a real directory tree."
  - "Do not copy or fork canonical kernel sources back into the superproject."
---

# Spec: Coherence Kernel Submodule Consumer

## Purpose

Give the Form runtime one canonical source while preserving every established
Coherence Network consumer path. The replacement prevents the two repositories
from silently drifting, without making CI, deploys, Windows hosts, or isolated
task worktrees operate on an empty gitlink.

## Requirements

- [x] **R1**: Replace the tracked top-level `form/` source tree with a gitlink to
  the exact `coherence-kernel` `form-submodule` snapshot whose root tree equals
  canonical `main:form`.
- [x] **R2**: Reconcile every newer Network kernel delta before the cut: land the
  `fam-tanh` band and astro recipe upstream, move the ten live Network endpoint
  recipes to `api/app/form_recipes/`, and preserve the intentional retirement of
  `form-gen.fk`.
- [x] **R3**: Keep existing paths such as `form/form-stdlib/` and
  `form/form-kernel-rust/` valid so Dockerfiles, scripts, and runtime callers do
  not gain a second topology.
- [x] **R4**: Initialize recursive submodules in GitHub Actions, Hostinger deploy,
  Windows worker startup, documented clone/worktree entry, prompt entry, and
  autonomous task-repository creation.
- [x] **R5**: Resolve bare app-owned recipes from `api/app/form_recipes/` before
  falling through to shared recipes in the coherence-kernel seedbank.
- [x] **R6**: Keep every maintainer carrier that writes committed kernel
  bootstrap artifacts inside `form/scripts/`; the consumer root retains only
  read/build/run carriers for the reviewed gitlink.

## Research Inputs

- `2026-07-15` - [coherence-kernel PR #223](https://github.com/seeker71/coherence-kernel/pull/223) — reconciles the last reusable Network kernel delta before the consumer cut.
- `2026-07-15` - [coherence-kernel PR #227](https://github.com/seeker71/coherence-kernel/pull/227) — removes the last validator reach-back into the consumer superproject.
- `2026-07-15` - [coherence-kernel PR #228](https://github.com/seeker71/coherence-kernel/pull/228) — restores typed JSON and executable fourth-arm bootstrap proof.
- `2026-07-15` - [coherence-kernel PR #229](https://github.com/seeker71/coherence-kernel/pull/229) — moves the remaining bootstrap regeneration carriers into the canonical kernel.
- `2026-07-15` - generated `form-submodule` commit `9124fc7` — tree `f1e9daea` exactly equals canonical `c0372e9:form`.
- `2026-07-15` - `coherence-kernel` commits `1c6f456c` and `2ab224ec` — identify the canonical-home migration and the self-contained `form/` boundary.
- `2026-07-15` - current Git object comparison — observed 13 Network-only paths and 107 differing shared paths before reconciliation.

## Files to Create/Modify

- `.gitmodules` and `form` — path-preserving, exact coherence-kernel gitlink.
- `api/app/form_recipes/` — ten Network-owned live endpoint recipes.
- `api/app/services/form_kernel_bridge.py` — app-first then shared recipe resolution.
- `api/scripts/local_runner.py` — task-worktree submodule initialization.
- `api/scripts/agent_runner.py` and `api/scripts/commit_progress.py` — recursive checkout hydration and material-edit commit guards.
- `scripts/prepare_form_submodule.py` — lossless one-time tree-to-gitlink transition and exact-pin cleanliness verification.
- `scripts/regen_{fkwu_bootstrap,t_flat,form_cli_bootstrap,standard_lane_binaries}.sh` — retired consumer copies; their executable replacements live in canonical `form/scripts/`.
- `scripts/gen_bp_table.py` and `scripts/scan_form_blueprints.py` — read-only consumer boundary for kernel-owned Blueprint tables.
- `api/tests/test_kernel_submodule_contract.py` — gitlink, pin, topology, and ownership proof.
- `.github/workflows/*.yml` — recursive submodule checkout and exact gitlink path triggers.
- `deploy/hostinger/auto-deploy.sh` and `deploy/worker/start-worker.vbs` — deployed checkout initialization.
- `AGENTS.md`, `README.md`, and `docs/WORKTREE-QUICKSTART.md` — complete clone/worktree entry commands.

## Acceptance Tests

- `api/tests/test_kernel_submodule_contract.py::test_form_is_pinned_path_preserving_kernel_submodule`
- `api/tests/test_kernel_submodule_contract.py::test_network_endpoint_recipes_are_owned_by_the_api`
- `api/tests/test_form_kernel_bridge_structure_access.py::TestRecipeResolution`
- `api/tests/test_edge_cases_regression.py` worktree-focused tests.
- `scripts/test_hostinger_deploy_form_paths.sh` deployment bootstrap contract.
- Manual validation: fresh `git clone --recurse-submodules` resolves
  `form/validate.sh` and `form/form-stdlib/core.fk` at the pinned gitlink.

## Verification

```bash
git submodule status --recursive
cd api && python3 -m pytest -q tests/test_kernel_submodule_contract.py tests/test_form_kernel_bridge_structure_access.py tests/test_api_dockerfile_contract.py
cd api && python3 -m pytest -q tests/test_edge_cases_regression.py -k worktree
bash scripts/test_hostinger_deploy_form_paths.sh
python3 scripts/validate_spec_quality.py --file specs/coherence-kernel-submodule-consumer.md
make prompt-guide
make wellness
```

## Out of Scope

- Converting the Network-owned `kernels/` compatibility and Python-BMF material into a submodule.
- Replacing the separate reduced browser runtime under `web/lib/form-kernel/vendor/`.
- Auto-advancing the pinned gitlink whenever coherence-kernel main changes.

## Risks and Assumptions

- Risk: a checkout can contain an empty `form/` gitlink; every execution entry
  initializes it or fails with the exact repair command.
- Risk: nested path filters do not observe a gitlink SHA change; workflows that
  watch Form include the exact `form` path.
- Assumption: `form-submodule` remains a generated distribution branch and all
  authored kernel changes continue to land on coherence-kernel `main` first.

## Known Gaps and Follow-up Tasks

- Follow-up task `coherence-kernel-blueprint-publication-gate`: Blueprint table
  generation and registry mutation are intentionally blocked in
  this consumer. The current `coherence-kernel` main tree does not yet carry the
  publication scripts that historically lived in Coherence Network. Move that
  authoring/publish gate upstream before the next Blueprint allocation, prove it
  there, then advance this reviewed gitlink. Read-only `--check` remains available
  here, and future kernel updates continue through an explicit upstream change
  followed by a reviewed gitlink bump.
