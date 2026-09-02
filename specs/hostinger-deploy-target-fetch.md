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
  - file: scripts/verify_web_api_deploy.sh
    symbols: [check_fkwu_native_authority]
requirements:
  - "Hostinger deploy must fetch the remote branch into origin/<branch> before resolving or validating a target SHA."
  - "Manual workflow dispatch with an explicit merged main SHA must not fail only because the VPS repo has not materialized that commit object yet."
  - "If the explicit target is still missing after branch fetch, perform one explicit target fetch before failing normally."
  - "GitHub-triggered and VPS-cron deployments must serialize on /tmp/coh-deploy.lock through rollout and public verification."
  - "Post-deploy native authority proof must observe the selected c-bootstrap fkwu runtime, not retired sibling-router headers."
done_when:
  - "bash syntax validation passes for the deploy script"
  - "the deploy script contains an explicit remote-tracking refspec fetch for the target branch"
  - "the deploy script contains an explicit target fetch fallback before git cat-file fails"
  - "the Hostinger workflow holds the same deployment lock used by the VPS cron caller until public verification completes"
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
- [ ] **R5**: The GitHub SSH rollout waits up to ten minutes on
  `/tmp/coh-deploy.lock`, the same lock held by the VPS cron caller, and holds it while one
  carrier invokes `auto-deploy.sh` followed by `verify_web_api_deploy.sh`. Concurrent callers
  cannot interleave container recreation with another rollout's post-deploy readiness proof.
- [ ] **R6**: Public native authority verification requires a verified c-bootstrap fkwu
  observation, verified form-cli carrier, and `differential-reference-only` sibling role from
  health, plus an available fkwu kernel status. It no longer requires headers from sibling
  router containers that the production deploy contract retires before observation.

## Files to Create/Modify

- `deploy/hostinger/auto-deploy.sh` — fetch target branch and explicit SHA reliably.
- `deploy/hostinger/deploy-and-verify.sh` — keep rollout and public proof inside one lock lifetime.
- `.github/workflows/hostinger-auto-deploy.yml` — serialize the GitHub rollout with the VPS cron caller.
- `scripts/test_hostinger_deploy_form_paths.sh` — deployment-lock regression proof.
- `scripts/verify_web_api_deploy.sh` — observe fkwu as the selected production authority.
- `specs/hostinger-deploy-target-fetch.md` — this spec.
- `docs/system_audit/commit_evidence_2026-05-06_hostinger_deploy_target_fetch.json` — proof artifact.
- `docs/system_audit/commit_evidence_2026-09-02_hostinger_deploy_lock.json` — shared-lock proof artifact.
- `docs/system_audit/model_executor_runs.jsonl` — proof record.

## Acceptance Tests

- Manual validation: `bash -n deploy/hostinger/auto-deploy.sh deploy/hostinger/deploy-and-verify.sh scripts/verify_web_api_deploy.sh`
- Manual validation: `rg -n 'refs/heads/\\$\\{BRANCH\\}:refs/remotes/origin/\\$\\{BRANCH\\}|git fetch origin "\\$TARGET_SHA"' deploy/hostinger/auto-deploy.sh`
- Manual validation: `bash scripts/test_hostinger_deploy_form_paths.sh`
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
- The workflow's 35-minute outer timeout includes up to ten minutes waiting for the shared lock, leaving at least 25 minutes for the rollout itself.

## Known Gaps

- Follow-up task: if future deploy logs show arbitrary SHA fetches rejected for reachable commits, add a small VPS-side deploy preflight that reports shallow depth, origin URL, and branch refspec before rollout.
