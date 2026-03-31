# Worktree and branch consolidation — 2026-03-06

All local changes from local worktrees and branches have been brought into the main worktree and **committed** on **codex/local-validation** (latest commit on branch) so nothing is abandoned.

## Worktrees checked

| Worktree path | Branch | Status |
|---------------|--------|--------|
| `/Users/ursmuff/source/Coherence-Network` | codex/local-validation | **All local changes consolidated here** (committed on this branch) |
| `~/.claude-worktrees/Coherence-Network/routing-test-heal` | codex/routing-test-heal | Clean; at 030cb30 (behind main). No unique commits. |
| `~/.claude-worktrees/Coherence-Network/routing-test-heal-20250305` | codex/routing-test-heal-20250305 | **Rescued:** `api/tests/conftest.py` (DB env wipe) + `commit_evidence_2026-03-05_routing-test-heal.json` copied into main worktree and committed. |
| `~/.claude-worktrees/Coherence-Network/routing-test-impl` | codex/routing-test-impl | Clean; behind main. No unique commits. |
| `~/.claude-worktrees/Coherence-Network/routing-test-impl-20260305` | codex/routing-test-impl-20260305 | Clean; behind main. |
| `~/.claude-worktrees/Coherence-Network/routing-test-spec` | codex/routing-test-spec | Clean; behind main. |
| `~/.claude-worktrees/Coherence-Network/routing-test-spec-2` | codex/routing-test-spec-2 | Clean; behind main. |
| `~/.claude-worktrees/Coherence-Network/slug-utility-20260305` | codex/slug-utility-20260305 | Clean; behind main. |

## Branches

- **codex/disable-codex-railway** — No commits ahead of origin/main (already on main or merged).
- **codex/local-validation** — Holds all consolidated changes (main worktree changes + rescued routing-test-heal-20250305 changes).

## What was consolidated

1. **Main worktree (Coherence-Network)**  
   CI gate fixes (executor_routing, orchestrator_policy, model_routing, openclaw tests, commit_progress fixture), MVP config, runtime/agent/docs/test edits, and new/untracked files (evidence, scripts, local_validation_proof).

2. **routing-test-heal-20250305 worktree**  
   - `api/tests/conftest.py`: wipe `DATABASE_URL`-style env vars before pytest collection unless `PYTEST_ALLOW_DATABASE_URL` is set (avoids local tests hitting shared Postgres/Supabase).  
   - `docs/system_audit/commit_evidence_2026-03-05_routing-test-heal.json`: evidence for that change.

All of the above are included in the single consolidated commit on **codex/local-validation** (on this branch). To bring other worktrees up to date: `git -C <worktree-path> fetch . codex/local-validation:codex/local-validation` and switch that worktree to the same branch, or remove obsolete worktrees with `git worktree remove` if no longer needed.
