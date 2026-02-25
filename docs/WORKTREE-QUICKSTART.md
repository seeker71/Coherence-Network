# Worktree Quickstart (Mandatory)

Date: 2026-02-17

Purpose: remove repeated setup mistakes by making every Codex/Claude thread follow one exact worktree startup flow.

## Rule 0

- Never implement from the primary repo workspace.
- Always create/use a linked worktree under `~/.claude-worktrees/Coherence-Network/`.

## Start New Thread (copy/paste)

From primary workspace:

```bash
./scripts/fetch_origin_main.sh
git worktree add ~/.claude-worktrees/Coherence-Network/<thread-name> -b codex/<thread-name> origin/main
```

Enter worktree:

```bash
cd ~/.claude-worktrees/Coherence-Network/<thread-name>
git pull --ff-only origin main
```

## Mandatory Preflight (before edits)

```bash
./scripts/auto_heal_start_gate.sh --with-pr-gate --with-rebase
```

Recommended. This command:
- stashes local changes temporarily,
- runs `make start-gate`,
- refreshes `origin/main` with `git fetch/rebase` when requested,
- runs local preflight guard.

Equivalent legacy flow (manual/clean tree): `make start-gate`.

## Mandatory Local Guard (before commit/push)

Enable local git hook enforcement once per worktree (can be done once per checkout):

```bash
make install-pre-push-hook
```

Always rebase to latest main first:

```bash
./scripts/fetch_origin_main.sh
git rebase origin/main
```

```bash
# Optional: set deployed n8n version when automation flows depend on n8n
# export N8N_VERSION=1.123.17
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
./scripts/verify_worktree_local_web.sh
# optional explicit startup (for manual end-to-end contract check)
THREAD_RUNTIME_START_SERVERS=1 ./scripts/verify_worktree_local_web.sh
# optional smoke/e2e (run only when pushing runtime-impactful changes)
./scripts/thread-runtime.sh run-e2e
```

Optional remote/deploy gate check:

```bash
# Optional n8n security-floor enforcement in remote/deploy-aware mode:
# N8N_VERSION=1.123.17 python3 scripts/worktree_pr_guard.py --mode all --branch "$(git rev-parse --abbrev-ref HEAD)"
python3 scripts/worktree_pr_guard.py --mode all --branch "$(git rev-parse --abbrev-ref HEAD)"
```

## Commit + PR

```bash
git add <files>
git commit -m "<message>"
git push -u origin codex/<thread-name>
gh pr create --base main --head codex/<thread-name> --title "<title>" --body "<body>"
```

## Merge (after checks)

Use rebase merge:

```bash
gh api -X PUT repos/seeker71/Coherence-Network/pulls/<pr_number>/merge -f merge_method=rebase
gh api -X DELETE repos/seeker71/Coherence-Network/git/refs/heads/codex/<thread-name>
```

## Recover Common Failures

- `next: command not found`: run `cd web && npm ci --cache /tmp/npm-codex-cache`.
- missing pytest in worktree: use repo venv path for validation:
  - `cd api && /Users/ursmuff/source/Coherence-Network/api/.venv/bin/pytest -q`.
- maintainability gate fail: run
  - `python3 api/scripts/run_maintainability_audit.py --output maintainability_audit_report.json --fail-on-regression`
  and refactor before re-push.

If running parallel threads, isolate runtime ports with:

```bash
THREAD_RUNTIME_API_BASE_PORT=18100 THREAD_RUNTIME_WEB_BASE_PORT=3110 ./scripts/verify_worktree_local_web.sh
THREAD_RUNTIME_API_BASE_PORT=18200 THREAD_RUNTIME_WEB_BASE_PORT=3120 ./scripts/verify_worktree_local_web.sh
```

`verify_worktree_local_web.sh` will auto-allocate the first available pair near each base so active threads can run concurrently.

## Close Thread

After merge and deploy validation:

```bash
cd /Users/ursmuff/source/Coherence-Network
git worktree remove ~/.claude-worktrees/Coherence-Network/<thread-name>
git branch -D codex/<thread-name> 2>/dev/null || true
```
