# Branch Compost - 2026-04-26

## Summary

Released 53 remote branches whose tip commits were reachable from `origin/main`, had no active worktree, and had no open PR.

Pruned 43 local branches with `git branch -d`.

Ran `git worktree prune --verbose`; no stale worktree records were reported.

Held open 1 likely-safe branch for separate cluster confirmation:

- `worker/test/ux-web-ecosystem-links/task_c6a`

Held open 1248 remote branches with unmerged commits, active worktrees, open PRs, recent activity, or unknown status.

## Presence Notes

`python3 scripts/agent_status.py --diff` is not supported in this checkout. Presence was sensed with:

- `python3 scripts/agent_status.py`
- `python3 scripts/agent_status.py --json`

The scan reported two running API tasks and one conflict warning: `task/task_a3ce585e890` and `task/task_ed6c3f59ee9` both touch `.gitignore`.

## Counts After First Compost

- Remote refs under `refs/remotes/origin`: 1251
- Local branches in the repository: 127
- Worktrees: 65

## Released Remote Branches

- `fix/hygiene-and-tests`
- `codex/ae92-local-validation-20260401`
- `codex/ae92-config-json-operator-20260403`
- `claude/clever-volhard`
- `codex/vision-now-spectrum`
- `codex/vision-energy-embedded`
- `codex/deploy-memory-attunement`
- `codex/ci-node24-actions`
- `codex/public-deploy-contract-paths`
- `claude/nice-dubinsky-246f84`
- `claude/cycle-13-presence`
- `claude/cycle-14-here`
- `claude/cycle-15-lineage`
- `claude/cycle-16-landing`
- `claude/cycle-17-voice-ripen`
- `claude/cycle-17-postgres-evolve`
- `claude/cycle-18-og-previews`
- `claude/cycle-18-metadatabase`
- `claude/cycle-19-waiting`
- `claude/cycle-20-locale-header`
- `claude/cycle-21-join-i18n`
- `claude/cycle-22-domain-list-i18n`
- `claude/blog-ana-walks`
- `claude/cycle-24-locale-autodetect`
- `claude/cycle-a-fix-meet-width`
- `claude/cycle-a-mobile-keystone`
- `claude/cycle-b-translator-lifespan`
- `claude/cycle-c-welcome`
- `claude/cycle-d-invite`
- `claude/cycle-e-since-last`
- `claude/cycle-f-keyless`
- `claude/cycle-g-meeting-voice`
- `claude/cycle-h-invite-attrib`
- `claude/cycle-i-kin`
- `claude/cycle-j-named-invite`
- `claude/cycle-k-invite-lang`
- `claude/cycle-l-ana-continues`
- `claude/cycle-l-screenshots`
- `claude/cycle-m-real-arc`
- `claude/cycle-n-panel-primitive`
- `claude/cycle-o-auto-contributor`
- `claude/cycle-p-voices-choir`
- `claude/cycle-q-warmth-returns`
- `claude/cycle-r-profile-garden`
- `claude/cycle-s-chain-persistence`
- `claude/cycle-t-reactions-graduate`
- `claude/cycle-u-count-to-phrase`
- `claude/agent-memory-system-8b00y`
- `task/task_eb6a3145af6`
- `task/task_856ad2e8ac3`
- `task/task_249234e789a`
- `task/task_5e105967f0d`
- `task/task_6d5f9f4dd67`
