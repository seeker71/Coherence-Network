---
idea_id: deploy-reliability
status: active
source:
  - file: deploy/hostinger/auto-deploy.sh
    symbols: [TARGET_SHA, git fetch]
requirements:
  - "Hostinger deploy must fetch the remote branch into origin/<branch> before resolving or validating a target SHA."
  - "Manual workflow dispatch with an explicit merged main SHA must not fail only because the VPS repo has not materialized that commit object yet."
  - "If the explicit target is still missing after branch fetch, perform one explicit target fetch before failing normally."
done_when:
  - "bash syntax validation passes for the deploy script"
  - "the deploy script contains an explicit remote-tracking refspec fetch for the target branch"
  - "the deploy script contains an explicit target fetch fallback before git cat-file fails"
test: "bash -n deploy/hostinger/auto-deploy.sh"
constraints:
  - "Do not change workflow secrets, SSH targets, compose services, or public verification semantics."
  - "Keep the fix scoped to target SHA fetch and validation."
---

# Spec: Hostinger Deploy Target Fetch

## Purpose

Manual Hostinger deploy dispatch failed while deploying a freshly merged `main` SHA because the VPS deploy script ran `git fetch origin main` and then immediately validated the explicit SHA with `git cat-file`. On some remote repository states, that fetch shape does not update `refs/remotes/origin/main` or guarantee that the explicit target object is present before validation.

The deploy script should fetch the branch into the remote-tracking ref and retry one explicit target fetch before treating the SHA as invalid.

## Requirements

- [ ] **R1**: Replace the ambiguous branch fetch with an explicit `refs/heads/<branch>:refs/remotes/origin/<branch>` refspec fetch.
- [ ] **R2**: Preserve the existing default behavior where an empty target resolves from `origin/<branch>`.
- [ ] **R3**: If an explicit `TARGET_SHA` is missing after the branch fetch, perform one `git fetch origin <TARGET_SHA>` fallback before the final `git cat-file` validation.
- [ ] **R4**: Preserve existing reset, build, container restart, and public verification behavior.

## Files to Create/Modify

- `deploy/hostinger/auto-deploy.sh` — fetch target branch and explicit SHA reliably.
- `specs/hostinger-deploy-target-fetch.md` — this spec.
- `docs/system_audit/commit_evidence_2026-05-06_hostinger_deploy_target_fetch.json` — proof artifact.
- `docs/system_audit/model_executor_runs.jsonl` — proof record.

## Acceptance Tests

- Manual validation: `bash -n deploy/hostinger/auto-deploy.sh`
- Manual validation: `rg -n 'refs/heads/\\$\\{BRANCH\\}:refs/remotes/origin/\\$\\{BRANCH\\}|git fetch origin "\\$TARGET_SHA"' deploy/hostinger/auto-deploy.sh`
- Deployment validation: dispatch `hostinger-auto-deploy.yml` for the latest merged `main` SHA and run public deploy verification.

## Verification

```bash
bash -n deploy/hostinger/auto-deploy.sh
rg -n 'refs/heads/\$\{BRANCH\}:refs/remotes/origin/\$\{BRANCH\}|git fetch origin "\$TARGET_SHA"' deploy/hostinger/auto-deploy.sh
python3 scripts/validate_spec_quality.py --file specs/hostinger-deploy-target-fetch.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-06_hostinger_deploy_target_fetch.json
```

## Out of Scope

- Changing VPS host configuration.
- Changing Docker Compose service topology.
- Changing public verification assertions.

## Risks and Assumptions

- Some servers reject fetching an arbitrary SHA by object id. The explicit branch refspec is the primary fix because deployment targets are expected to be reachable from `main`; the SHA fetch is only a fallback.
- The workflow still relies on public deploy verification to prove the service is actually live after the remote script completes.

## Known Gaps

- Follow-up task: if future deploy logs show arbitrary SHA fetches rejected for reachable commits, add a small VPS-side deploy preflight that reports shallow depth, origin URL, and branch refspec before rollout.
