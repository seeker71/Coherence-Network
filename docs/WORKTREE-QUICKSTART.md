# Worktree Quickstart (Mandatory)

Date: 2026-02-17

Purpose: remove repeated setup mistakes by making every Codex/Claude thread follow one exact worktree startup flow.

## Rule 0

- Never implement from the primary repo workspace.
- Always create/use a linked worktree under `~/.claude-worktrees/Coherence-Network/`.

## Start New Thread (copy/paste)

From primary workspace:

```bash
git fetch origin main
git worktree add ~/.claude-worktrees/Coherence-Network/<thread-name> -b codex/<thread-name> origin/main
```

Enter worktree:

```bash
cd ~/.claude-worktrees/Coherence-Network/<thread-name>
git pull --ff-only origin main
```

## Mandatory Preflight (before edits)

```bash
python3 scripts/ensure_worktree_start_clean.py --json
```

Must pass all:
- running in linked worktree (not primary workspace),
- current worktree clean,
- primary workspace clean,
- latest `main` CI green,
- no open PRs with failing checks.

## Mandatory Local Guard (before commit/push)

Always rebase to latest main first:

```bash
git fetch origin main
git rebase origin/main
```

```bash
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
./scripts/verify_worktree_local_web.sh
```

Optional remote/deploy gate check:

```bash
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

## Close Thread

After merge and deploy validation:

```bash
cd /Users/ursmuff/source/Coherence-Network
git worktree remove ~/.claude-worktrees/Coherence-Network/<thread-name>
git branch -D codex/<thread-name> 2>/dev/null || true
```
