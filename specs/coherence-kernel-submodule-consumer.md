---
idea_id: coherence-kernel-one-home
status: done
source:
  - file: .gitmodules
    symbols: [submodule.form]
  - file: form/form/form-stdlib/bml/source-tree.bml
    symbols: [tracked-files(), stw-files()]
  - file: form/form/form-stdlib/bml/native-socket-dispatch.bml
    symbols: [nsd-open(), nsd-serve()]
  - file: pulse/http.bml
    symbols: [cell_call(), nsd-open()]
requirements:
  - "Coherence Network consumes coherence-kernel as an exact gitlink at the existing form/ path."
  - "Authored fkwu changes land on kernel main; this consumer tracks that same source authority while pinning an immutable commit."
  - "Kernel deltas are reconciled upstream while Network-owned recipes remain with their application."
  - "CI, deploy, clone, and autonomous-worktree paths initialize the recursive submodule before use."
  - "The existing form/runtime and form/form/form-stdlib fkwu source/JIT paths remain valid; sibling kernels are bootstrap references."
  - "Kernel bootstrap regeneration is authored inside coherence-kernel; the consumer has no script that writes committed form/ artifacts."
done_when:
  - "A recursive clone populates form/ at the superproject's pinned gitlink SHA."
  - "The affected application admits its recipe closure from the pinned native source."
  - "The immutable release build and affected public observation retain their exact source identity."
  - 'file_exists(".gitmodules")'
  - 'file_exists("form/runtime/fkwu-uni.c")'
  - 'file_exists("pulse/http.bml")'
test: "cd form && ./fkwu --check ../pulse/http.bml"
constraints:
  - "Preserve the admitted fkwu source/JIT layout and application recipe paths at the existing form/ gitlink."
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

- [x] **R1**: Keep `form/` as an exact immutable `coherence-kernel` main-source
  gitlink. `.gitmodules` tracks that same authority. The optional curated
  distribution serves other consumers, not a second authoring home or a
  branch-name release gate for this one.
- [x] **R2**: Reconcile every newer Network kernel delta before the cut: land the
  `fam-tanh` band and astro recipe upstream, move the ten live Network endpoint
  recipes to `api/app/form_recipes/`, and preserve the intentional retirement of
  `form-gen.fk`.
- [x] **R3**: Keep `form/runtime/` and `form/form/form-stdlib/` valid so the fkwu
  JIT and application callers share one topology. Other kernels remain bootstrap
  references aligned with fkwu, not recurring consumer-validation targets.
- [x] **R4**: Initialize recursive submodules in GitHub Actions, Hostinger deploy,
  Windows worker startup, documented clone/worktree entry, prompt entry, and
  autonomous task-repository creation.
- [x] **R5**: Resolve bare app-owned recipes from `api/app/form_recipes/` before
  falling through to shared recipes in the coherence-kernel seedbank.
- [x] **R6**: Keep kernel build/publication care with the kernel's native doors
  (`form/gate/` and `form/form/form-stdlib/bml/`); the consumer builds and runs the
  pinned source without holding another copy of kernel implementation.

## Research Inputs

- `2026-07-15` - [coherence-kernel PR #223](https://github.com/seeker71/coherence-kernel/pull/223) — reconciles the last reusable Network kernel delta before the consumer cut.
- `2026-07-15` - [coherence-kernel PR #227](https://github.com/seeker71/coherence-kernel/pull/227) — removes the last validator reach-back into the consumer superproject.
- `2026-07-15` - [coherence-kernel PR #228](https://github.com/seeker71/coherence-kernel/pull/228) — restores typed JSON and executable fourth-arm bootstrap proof.
- `2026-07-15` - [coherence-kernel PR #229](https://github.com/seeker71/coherence-kernel/pull/229) — moves the remaining bootstrap regeneration carriers into the canonical kernel.
- `2026-07-15` - generated `form-submodule` commit `9124fc7` — tree `f1e9daea` exactly equals canonical `c0372e9:form`.
- `2026-07-15` - `coherence-kernel` commits `1c6f456c` and `2ab224ec` — identify the canonical-home migration and the self-contained `form/` boundary.
- `2026-07-15` - current Git object comparison — observed 13 Network-only paths and 107 differing shared paths before reconciliation.

## Files to Create/Modify

The July migration references below describe that completed cut, not a routine
validation prescription. Current authority is `.gitmodules`, the immutable
gitlink, native source closure and affected application boundary above.

- `.gitmodules` and `form` — path-preserving, exact coherence-kernel gitlink.
- `api/app/form_recipes/` — ten Network-owned live endpoint recipes.
- `api/app/services/form_kernel_bridge.py` — app-first then shared recipe resolution.
- `api/scripts/local_runner.py` — task-worktree submodule initialization.
- `api/scripts/agent_runner.py` and `api/scripts/commit_progress.py` — recursive checkout hydration and material-edit commit guards.
- `scripts/prepare_form_submodule.py` — lossless one-time tree-to-gitlink transition and exact-pin cleanliness verification.
- `scripts/regen_{fkwu_bootstrap,t_flat,form_cli_bootstrap,standard_lane_binaries}.sh` — retired consumer copies; their executable replacements live in canonical `form/form/scripts/`.
- `scripts/gen_bp_table.py` and `scripts/scan_form_blueprints.py` — read-only consumer boundary for kernel-owned Blueprint tables.
- `api/tests/test_kernel_submodule_contract.py` — gitlink, pin, topology, and ownership proof.
- `.github/workflows/*.yml` — recursive submodule checkout and exact gitlink path triggers.
- `deploy/hostinger/auto-deploy.sh` and `deploy/worker/start-worker.vbs` — deployed checkout initialization.
- `AGENTS.md`, `README.md`, and `docs/WORKTREE-QUICKSTART.md` — complete clone/worktree entry commands.

## Acceptance Tests

- Manual validation when initialization changes: a recursive checkout resolves
  the exact gitlink and the fkwu source/JIT paths.
- Changed application inputs give native recipe admission work; image assembly
  already performs that admission, so retain its source-keyed evidence.
- The immutable build records its source seal and the affected public route
  observes the deployed behavior. Branch names do not substitute for this proof.

## Verification

Reuse current initialization, admission and release receipts. A changed pin,
caller or observed failure gives the relevant boundary work. For an admission
finding, the smallest source read is `cd form && ./fkwu --check ../pulse/http.bml`;
do not repeat it when the matching immutable build has already admitted those
bytes. No routine kernel or sibling suite is part of a consumer bump. Runtime
changes, when genuinely needed, get their focused native observation at source.

Reference commands for a new initialization or admission finding (reuse an
existing matching receipt rather than running them again):

```sh
git submodule status --recursive
cd form && ./fkwu --check ../pulse/http.bml
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
- Source authority: authored changes land on kernel `main`; this consumer pins
  those immutable source commits and tracks `main` explicitly. Keep retired
  limitations retired there too. Optional distribution carries remain available
  without becoming a second authority for consumer fixes.

## Known Gaps and Follow-up Tasks

- Native Blueprint, grammar and cell evolution belongs with its upstream source
  owner. A missing capability carries the actual caller, source inputs and
  finding there; it is work, not a blanket consumer publication blocker.
- Legacy Blueprint-table generators remain bootstrap references. A changed
  bootstrap input can give its owner focused work without turning sibling-kernel
  comparison into a recurring application release requirement.
- Follow-up task `coherence-kernel-source-continuity`: when a concurrent parent
  change touches the gitlink, retain all currently
  admitted features in the chosen descendant. Record the source identity and
  affected observation; do not restore retired paths merely to match an older
  branch guide.
