# Worker Service — Federation Node Runner

The local worker runs as a background service, processing tasks from the Coherence Network pipeline. It runs in its own git worktree to avoid conflicts with development work.

Prompt-gate note: `.claude/worktrees/*` lanes are treated as autonomous sidecars by the sibling continuity guard, so an active Claude worker does not block Codex prompt entry in another worktree.

## Architecture

```
C:\source\Coherence-Network\                         ← main repo (development)
C:\source\Coherence-Network\.claude\worktrees\
  └── worker\                                        ← worker worktree (tracks origin/main)

~/Library/LaunchAgents/com.coherence-network.worker.plist  ← macOS service
%APPDATA%\...\Startup\CoherenceNetworkWorker.vbs           ← Windows auto-start
```

The worker worktree is isolated — `git pull origin main` inside it does not affect the main repo or any active development worktrees.

## Setup (one-time)

### Windows

```powershell
# 1. Create the worker worktree (from the main repo)
cd C:\source\Coherence-Network
git worktree add .claude/worktrees/worker origin/main

# 2. Set it to track main
cd .claude\worktrees\worker
git checkout -B worker-main origin/main

# 3. Install to Startup folder (auto-start on login)
#    The VBS script at deploy/worker/start-worker.vbs is copied to:
#    %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CoherenceNetworkWorker.vbs
powershell -Command "Copy-Item deploy\worker\start-worker.vbs ([Environment]::GetFolderPath('Startup') + '\CoherenceNetworkWorker.vbs')"

# 4. Start now
cscript //nologo deploy\worker\start-worker.vbs
```

### macOS

```bash
# 1. Create the worker worktree
cd ~/source/Coherence-Network  # or wherever your repo is
git worktree add .claude/worktrees/worker origin/main

# 2. Set it to track main
cd .claude/worktrees/worker
git checkout -B worker-main origin/main

# 3. Install launchd service
chmod +x deploy/worker/install-macos.sh
./deploy/worker/install-macos.sh
```

## Operations

### Check status
```bash
cc status                    # network + node health
cc nodes                     # federation nodes
tail -f api/logs/worker_service.log  # live logs (from worker worktree)
```

### Manual start/stop

**Windows:**
```powershell
# Start
cscript //nologo C:\source\Coherence-Network\.claude\worktrees\worker\deploy\worker\start-worker.vbs

# Stop
taskkill /F /IM python.exe   # kills all python — be careful
# Or find the specific PID:
Get-Process python | Where-Object { $_.StartTime -gt (Get-Date).AddHours(-1) } | Stop-Process
```

**macOS:**
```bash
launchctl unload ~/Library/LaunchAgents/com.coherence-network.worker.plist   # stop
launchctl load ~/Library/LaunchAgents/com.coherence-network.worker.plist     # start
```

### Update to latest code
```bash
# Option 1: Send update command via cc
cc msg windows "Update to latest main"

# Option 2: Manual
cd C:\source\Coherence-Network\.claude\worktrees\worker
git pull origin main
# Then restart the worker
```

The runner has self-update built in (`--self-update` flag, on by default unless `--no-self-update`). When enabled, it runs `git pull origin main` before each poll cycle and restarts itself if new commits are found.

### Send commands to the worker
```bash
cc msg windows "Update to latest main"     # trigger self-update
cc msg mac "Update to latest main"         # same for mac node
cc msg windows "restart"                   # restart worker
```

## What survives restarts

| Event | Worker survives? | How |
|-------|-----------------|-----|
| **Windows login** | Yes | VBS in Startup folder |
| **macOS login** | Yes | launchd RunAtLoad |
| **System reboot** | Yes | Same as login |
| **Claude session end** | Yes | Worker is a separate process |
| **Worker crash** | macOS: Yes (KeepAlive), Windows: No (manual restart) |
| **Git worktree prune** | No — must recreate worktree |
| **Repo clone to new location** | No — must update VBS/plist paths |

## Provider tiers

The worker enforces provider quality tiers:

| Task type | Allowed providers | Rationale |
|-----------|------------------|-----------|
| **spec** | claude, codex, cursor | Needs strong reasoning |
| **review** | claude, codex, cursor | Needs deep evaluation |
| **impl** | claude, codex, cursor, gemini | Needs tool use |
| **test** | claude, codex, cursor, gemini | Needs tool use |
| **other** | all (including openrouter, ollama) | Simple tasks |

## Logs

Worker logs to `api/logs/worker_service.log` inside the worker worktree.

Key log patterns:
- `NODE_REGISTERED sha=XXXXXX` — node registered with git SHA
- `PROVIDER_TIER task=spec restricted to strong` — tier enforcement working
- `CLAIMED task=XXX type=spec` — task picked up
- `OUTCOME task=XXX success=True duration=15s` — task completed
- `SEED: created spec task` — new task seeded from open idea
- `SEED: truly stuck` — idea has 10+ failed tasks in one phase
