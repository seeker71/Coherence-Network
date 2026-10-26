---
idea_id: deploy-reliability
status: active
source:
  - file: deploy/hostinger/auto-deploy.sh
    symbols: [TARGET_SHA, git fetch]
  - file: .github/workflows/hostinger-auto-deploy.yml
    symbols: [Roll forward VPS]
  - file: deploy/hostinger/deploy-and-verify.sh
    symbols: [DEPLOY_PATH, TARGET_SHA]
  - file: deploy/hostinger/deploy-lock.sh
    symbols: [coherence_deploy_lock, coherence_deploy_close_descriptors]
  - file: scripts/verify_web_api_deploy.sh
    symbols: [check_fkwu_native_authority]
requirements:
  - "Hostinger deploy must fetch the remote branch into origin/<branch> before resolving or validating a target SHA."
  - "Manual workflow dispatch with an explicit merged main SHA must not fail only because the VPS repo has not materialized that commit object yet."
  - "If the explicit target is still missing after branch fetch, perform one explicit target fetch before failing normally."
  - "Direct, GitHub-triggered and VPS-cron deployment entry points acquire /tmp/coh-deploy.lock before mutation and retain it through rollout and public verification."
  - "Inherited ownership is reused without self-waiting; detached services close their copies without unlocking the parent."
  - "Post-deploy native authority proof must observe the selected c-bootstrap fkwu runtime, not retired sibling-router headers."
done_when:
  - "bash syntax validation passes for the deploy script"
  - "the deploy script contains an explicit remote-tracking refspec fetch for the target branch"
  - "the deploy script contains an explicit target fetch fallback before git cat-file fails"
  - "both deployment entry points share one inherited lock through public verification; real competing and detached-process tests pass"
  - "the public verifier proves fkwu and form-cli health while sibling kernels remain reference-only"
  - 'file_exists("deploy/hostinger/auto-deploy.sh")'
  - 'symbol_in_file("deploy/hostinger/auto-deploy.sh", "TARGET_SHA")'
  - 'symbol_in_file("deploy/hostinger/auto-deploy.sh", "git")'
test: "bash -n deploy/hostinger/auto-deploy.sh deploy/hostinger/deploy-and-verify.sh scripts/verify_web_api_deploy.sh"
constraints:
  - "Do not change workflow secrets, SSH targets, compose services, or non-native public verification coverage."
  - "Keep the fix scoped to target SHA fetch/validation, deployment-caller serialization, and the already-selected fkwu authority contract."
---

# Spec: Hostinger Deploy Target Fetch

## Purpose

Manual Hostinger deploy dispatch failed while deploying a freshly merged `main` SHA because the VPS deploy script ran `git fetch origin main` and then immediately validated the explicit SHA with `git cat-file`. On some remote repository states, that fetch shape does not update `refs/remotes/origin/main` or guarantee that the explicit target object is present before validation.

The deploy script should fetch the branch into the remote-tracking ref and retry one explicit target fetch before treating the SHA as invalid. Every caller must also share one VPS deployment lock so a cron rollout cannot recreate services while a GitHub rollout is proving readiness. That proof observes the c-bootstrap fkwu runtime selected by the later kernel-collapse contract; retired sibling-router headers are not production authority.

## Requirements

- [ ] **R1**: Replace the ambiguous branch fetch with an explicit `refs/heads/<branch>:refs/remotes/origin/<branch>` refspec fetch.
- [ ] **R2**: Preserve the existing default behavior where an empty target resolves from `origin/<branch>`.
- [ ] **R3**: If an explicit `TARGET_SHA` is missing after the branch fetch, perform one `git fetch origin <TARGET_SHA>` fallback before the final `git cat-file` validation.
- [ ] **R4**: Preserve existing reset, build, container restart, and non-native public verification coverage.
- [x] **R5**: Both deployment entry points acquire `/tmp/coh-deploy.lock` before mutation,
  waiting up to ten minutes when another owner holds it. The verification carrier retains
  ownership while its child deploys and until public proof completes. Inherited descriptors
  to the same inode are checked without self-waiting. A detached service closes only its own
  copies; it neither releases its parent's ownership nor retains it after the parent exits.
- [ ] **R6**: Public native authority verification requires a verified c-bootstrap fkwu
  observation, verified form-cli carrier, and `differential-reference-only` sibling role from
  health, plus an available fkwu kernel status. It no longer requires headers from sibling
  router containers that the production deploy contract retires before observation.

## Files to Create/Modify

- `deploy/hostinger/auto-deploy.sh` — fetch target branch and explicit SHA reliably.
- `deploy/hostinger/deploy-and-verify.sh` — keep rollout and public proof inside one lock lifetime.
- `deploy/hostinger/deploy-lock.sh` — one ownership boundary for both entry points.
- `deploy/hostinger/install-gitnexus.sh` — end lock inheritance at the detached service.
- `scripts/test_hostinger_deploy_lock.sh` — real Linux ownership and release proof.
- `.github/workflows/test.yml` — run the process proof in Linux CI.
- `.github/workflows/hostinger-auto-deploy.yml` — serialize the GitHub rollout with the VPS cron caller.
- `scripts/test_hostinger_deploy_form_paths.sh` — deployment-lock regression proof.
- `scripts/verify_web_api_deploy.sh` — observe fkwu as the selected production authority.
- `specs/hostinger-deploy-target-fetch.md` — this spec.
- `docs/system_audit/commit_evidence_2026-05-06_hostinger_deploy_target_fetch.json` — proof artifact.
- `docs/system_audit/commit_evidence_2026-09-02_hostinger_deploy_lock.json` — shared-lock proof artifact.
- `docs/system_audit/commit_evidence_2026-10-26_deploy_owner.json` — direct-entry and descriptor-lifetime proof.
- `docs/system_audit/model_executor_runs.jsonl` — proof record.

## Acceptance Tests

- Manual validation: `bash -n deploy/hostinger/auto-deploy.sh deploy/hostinger/deploy-and-verify.sh scripts/verify_web_api_deploy.sh`
- Manual validation: `rg -n 'refs/heads/\\$\\{BRANCH\\}:refs/remotes/origin/\\$\\{BRANCH\\}|git fetch origin "\\$TARGET_SHA"' deploy/hostinger/auto-deploy.sh`
- Manual validation: `bash scripts/test_hostinger_deploy_form_paths.sh`
- Linux validation: `bash scripts/test_hostinger_deploy_lock.sh`
- Deployment validation: dispatch `hostinger-auto-deploy.yml` for the latest merged `main` SHA and run public deploy verification.

## Verification

```bash
bash -n deploy/hostinger/auto-deploy.sh deploy/hostinger/deploy-and-verify.sh scripts/verify_web_api_deploy.sh
rg -n 'refs/heads/\$\{BRANCH\}:refs/remotes/origin/\$\{BRANCH\}|git fetch origin "\$TARGET_SHA"' deploy/hostinger/auto-deploy.sh
python3 scripts/validate_spec_quality.py --file specs/hostinger-deploy-target-fetch.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-06_hostinger_deploy_target_fetch.json
```

## Out of Scope

- Changing VPS host configuration.
- Changing Docker Compose service topology.
- Restoring retired sibling-router containers as production execution authorities.
- Changing workflow secrets or SSH targets.

## Risks and Assumptions

- Some servers reject fetching an arbitrary SHA by object id. The explicit branch refspec is the primary fix because deployment targets are expected to be reachable from `main`; the SHA fetch is only a fallback.
- The locked carrier relies on public deploy verification to prove the service is actually live before it returns and releases the lock.
- The workflow's 150-minute outer timeout includes the ten-minute lock wait, the native build owner's two-hour bound, activation and public verification.

## Known Gaps

- Follow-up task: if future deploy logs show arbitrary SHA fetches rejected for reachable commits, add a small VPS-side deploy preflight that reports shallow depth, origin URL, and branch refspec before rollout.
