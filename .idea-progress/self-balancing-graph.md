# Idea progress — idea-0f1d59d58f25 (MCP npm/PyPI publish)

## Current task
- **Task ID**: task_9159679b305d7b7a
- **Status**: COMPLETE — worktree creation fallback for impl/test when `git worktree add` fails

## Completed phases
### Runner worktree reliability (task_9159679b305d7b7a)
- Implemented standalone-repo fallback in `api/scripts/local_runner.py` after primary `git worktree add` failure (reclaim slot → `_create_standalone_task_repo`).
- Added regression test for fallback; adjusted failure test to mock standalone returning `None`.
- Repaired `.gitignore` corruption (literal `\n` line from bad echo).

## Key decisions
- Prefer reclaim + existing `_create_standalone_task_repo` over widening `_repo_is_linked_worktree` heuristics so any `worktree add` failure (permissions, lock, ref races) gets the same recovery path as linked worktrees.

## Blockers
- MCP package publication to npm/PyPI remains future work; this task addressed runner “Worktree creation failed” for impl tasks.
