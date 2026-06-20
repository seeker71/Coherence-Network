# Worktree Quickstart (Mandatory)

Date: 2026-02-17

Purpose: remove repeated setup mistakes by making every Codex/Claude thread follow one exact worktree startup flow.

## Windows 11 Host Bootstrap

Run once from a PowerShell prompt in any Coherence Network checkout:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows_host.ps1
```

What it prepares:

- Git Bash as the shell for repo `.sh` scripts.
- GNU Make from winget when `make` is missing.
- `%USERPROFILE%\.local\bin\python3` shim so Git Bash avoids the broken Windows Store `python3` alias and uses `py -3`.
- `~\.config\gh-seeker71` from the existing GitHub CLI login when `gh auth status` is already authenticated.
- `api\.env` and `web\.env.local` copied from examples when they do not already exist.
- PATH entries for GNU Make and `%USERPROFILE%\.local\bin`.

PowerShell notes for this host:

- Use `npm.cmd`, not `npm`, because `npm.ps1` can be blocked by execution policy.
- Open a fresh PowerShell after bootstrap so the updated user PATH is inherited. In the current shell, use the printed absolute `make.exe` command if needed.
- Git Bash is at `C:\Program Files\Git\bin\bash.exe`; the Makefile uses it automatically for startup targets on Windows.
- Run `gh auth login` before unbypassed `make prompt-guide` and PR checks if the bootstrap warns that GitHub CLI is not authenticated.

## Rule 0

- Never implement from the primary repo workspace.
- Always create/use a linked worktree under `~/.claude-worktrees/Coherence-Network/`.

## Start New Thread (copy/paste)

Windows PowerShell:

```powershell
git fetch origin main
git worktree add "$env:USERPROFILE\.claude-worktrees\Coherence-Network\<thread-name>" -b "codex/<thread-name>" origin/main
Set-Location "$env:USERPROFILE\.claude-worktrees\Coherence-Network\<thread-name>"
git pull --ff-only origin main
make prompt-guide
```

Git Bash / Linux / macOS:

```bash
git fetch origin main
git worktree add ~/.claude-worktrees/Coherence-Network/<thread-name> -b codex/<thread-name> origin/main
cd ~/.claude-worktrees/Coherence-Network/<thread-name>
git pull --ff-only origin main
make prompt-guide
```

## Mandatory Preflight (before edits)

```bash
make prompt-guide
```

Mandatory for every prompt (new or follow-up). This command is continuation-safe:
- clean worktree: runs cheap entry checks (`CLAUDE.md` orientation, branch/worktree safety, sibling continuity guidance),
- dirty worktree: runs the same cheap entry checks and treats the prompt as in-flight continuation,
- detached HEAD: fails fast with exact branch attach commands.
- sibling continuity guard: treats sibling worktrees, including dirty, detached, patch-equivalent, and old unpushed-ahead branches, as guidance. It fails fast only for recent unpushed-ahead sibling history without an upstream.
- autonomous worker sidecars under `.claude/worktrees/*` are excluded from sibling continuity risk so Claude workers can run in parallel without blocking Codex prompt entry.

Legacy alias: `make prompt-gate`.
Full proof on demand: `./scripts/prompt_entry_gate.sh --force-full` from Git Bash.
Equivalent minimal branch/worktree check: `make start-gate`.

### If prompt-gate blocks on continuity risk

Inspect sibling worktree risk report:

```bash
python3 scripts/worktree_continuity_guard.py --json
```

For each risky sibling worktree:

```bash
cd <worktree-path>
git status --short
git add <files> && git commit -m "<message>"   # if changes are ready
git push -u origin "$(git rev-parse --abbrev-ref HEAD)"   # if branch has no upstream
```

If the work is intentionally in progress, continue from that same worktree/thread when that is the right task. Sibling worktrees are integration candidates, not abandoned scratchpads: resume that branch, merge/cherry-pick it, or commit it intentionally before it needs to ship.

SQLite artifact rule:

- `data/coherence.db`, `api/data/coherence.db`, and SQLite sidecars such as `.db-wal` / `.db-shm` are treated as local runtime artifacts by the guards.
- DB-only dirtiness does not count as sibling continuity risk and does not need commit-evidence coverage.
- Before push/merge, prefer `git restore data/coherence.db api/data/coherence.db` unless the task explicitly changes a committed fixture or snapshot.
- If a task really does require a DB artifact change, document why in the commit evidence and tracking sheet.

Temporary bypass (not recommended):

```bash
PROMPT_GATE_SKIP_CONTINUITY=1 make prompt-guide
```

## Mandatory Local Guard (before commit/push)

Enable local git hook enforcement once per worktree (can be done once per checkout):

```bash
make install-pre-push-hook
```

Always rebase to latest main first:

```bash
git fetch origin main
git rebase origin/main
```

```bash
# Optional: set deployed n8n version when automation flows depend on n8n.
# Windows PowerShell: $env:N8N_VERSION = "1.123.17"
# Git Bash/Linux/macOS: export N8N_VERSION=1.123.17
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
./scripts/verify_worktree_local_web.sh
# optional explicit startup (for manual end-to-end contract check)
THREAD_RUNTIME_START_SERVERS=1 ./scripts/verify_worktree_local_web.sh
# optional smoke/e2e (run only when pushing runtime-impactful changes)
./scripts/thread-runtime.sh run-e2e
```

`worktree_pr_guard.py` runs expensive API, web build, and runtime web checks only when changed files touch those surfaces, unless the caller passes the matching `--force-*` flag. Hosted PR thread gates follow the same surface-aware shape for API, maintainability, and web build steps.

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

## Post-Merge Deploy Watch (fast path)

After merge, do not hand-watch every push. Let the deploy settle command follow the latest `main` SHA through Hostinger concurrency cancellations, wait for API SHA parity, and run the public deploy verifier once production is current:

```bash
./scripts/settle_public_deploy.sh https://api.coherencycoin.com https://coherencycoin.com
```

Interpretation:
- A canceled Hostinger run can be normal when a newer `main` push supersedes it.
- The settle command follows the newest Hostinger run on `main`, not the run that happened to start after your PR.
- Treat failure as real only when the latest run for current `main` fails or SHA parity times out.

## Recover Common Failures

- `make: The term 'make' is not recognized`: run `powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows_host.ps1`, then open a new PowerShell.
- `process_begin ... env bash ... failed` from GNU Make on Windows: rebase onto the Makefile startup target fix, or run `make prompt-guide` after this guide's Windows bootstrap.
- `Python was not found; run without arguments to install from the Microsoft Store`: run `.\scripts\setup_windows_host.ps1`; Git Bash will use `%USERPROFILE%\.local\bin\python3` -> `py -3`.
- `npm.ps1 cannot be loaded`: use `npm.cmd`, for example `cd web; npm.cmd ci`.
- `next: command not found`: run `cd web; npm.cmd ci --cache "$env:TEMP\coherence-npm-cache"` in PowerShell, or `cd web && npm ci --cache /tmp/npm-codex-cache` in Git Bash.
- missing pytest in worktree: create the API venv with `cd api; py -3 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e ".[dev]"`, then run `.\.venv\Scripts\pytest.exe -q`.
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

Windows PowerShell:

```powershell
Set-Location <primary-workspace>
git worktree remove "$env:USERPROFILE\.claude-worktrees\Coherence-Network\<thread-name>"
git branch -D "codex/<thread-name>"
```

Git Bash / Linux / macOS:

```bash
cd <primary-workspace>
git worktree remove ~/.claude-worktrees/Coherence-Network/<thread-name>
git branch -D codex/<thread-name> 2>/dev/null || true
```
