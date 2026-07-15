#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."

usage() {
  cat <<'USAGE'
Usage: prompt_entry_gate.sh [--force-full]

Cheap prompt-entry guide for Codex follow-up turns.

Behavior:
  - default: orient from CLAUDE.md, verify branch/worktree safety, and print the shortest next proof path
  - full proof: use --force-full to run start-guide + rebase + local PR guide
  - sibling worktrees: print guidance by default; stop only for recent unpushed-ahead sibling history

Options:
  --force-full   run full preflight now (stashes/restores changes if needed).
  -h, --help     show this help text.
USAGE
}

force_full=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-full)
      force_full=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "prompt-entry-guide: unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

cd "$REPO_ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "prompt-entry-guide: not inside a git worktree."
  exit 1
fi

form_index_mode="$(git ls-files --stage -- form | awk 'NR == 1 { print $1 }')"
form_index_sha="$(git ls-files --stage -- form | awk 'NR == 1 { print $2 }')"
if [[ "$form_index_mode" == "160000" && ! -e "form/.git" && -f scripts/prepare_form_submodule.py ]] \
  && command -v python3 >/dev/null 2>&1; then
  python3 scripts/prepare_form_submodule.py --repo-root . || exit 1
fi
if [[ "$form_index_mode" == "160000" && ! -e "form/.git" ]]; then
  echo "prompt-entry-guide: form submodule is not initialized."
  echo "Initialize the pinned kernel checkout first:"
  echo "  git submodule sync --recursive"
  echo "  git submodule update --init --recursive"
  echo "Then rerun:"
  echo "  make prompt-guide"
  exit 1
fi
if [[ "$form_index_mode" == "160000" ]]; then
  form_checkout_sha="$(git -C form rev-parse HEAD 2>/dev/null || true)"
  if [[ "$form_checkout_sha" != "$form_index_sha" ]]; then
    echo "prompt-entry-guide: form submodule is not at the pinned gitlink."
    echo "  expected: $form_index_sha"
    echo "  observed: ${form_checkout_sha:-missing}"
    echo "Restore the reviewed kernel snapshot first:"
    echo "  git submodule update --force --init --recursive form"
    echo "Then rerun:"
    echo "  make prompt-guide"
    exit 1
  fi
  form_material_dirt=""
  while IFS= read -r -d '' form_status_entry; do
    form_status_code="${form_status_entry:0:2}"
    form_status_path="${form_status_entry:3}"
    if [[ "$form_status_code" == "??" ]] && {
      [[ "$form_status_path" == ".cache" || "$form_status_path" == .cache/* ]] ||
      [[ "$form_status_path" == ".pytest_cache" || "$form_status_path" == .pytest_cache/* ]] ||
      [[ "$form_status_path" == ".ruff_cache" || "$form_status_path" == .ruff_cache/* ]] ||
      [[ "$form_status_path" == "form-kernel-rust/target" || "$form_status_path" == form-kernel-rust/target/* ]] ||
      [[ "$form_status_path" == "form-kernel-ts/dist" || "$form_status_path" == form-kernel-ts/dist/* ]] ||
      [[ "$form_status_path" == "form-kernel-ts/node_modules" || "$form_status_path" == form-kernel-ts/node_modules/* ]];
    }; then
      continue
    fi
    form_material_dirt+="${form_status_entry}"$'\n'
  done < <(git -C form status --porcelain=v1 -z --untracked-files=all 2>/dev/null || true)
  if [[ -n "$form_material_dirt" ]]; then
    echo "prompt-entry-guide: form submodule has material changes outside the reviewed pin."
    printf '%s' "$form_material_dirt"
    echo "Land intentional kernel work in coherence-kernel first, or restore the reviewed snapshot:"
    echo "  git submodule update --force --init --recursive form"
    echo "Then rerun:"
    echo "  make prompt-guide"
    exit 1
  fi
fi

if [[ "${OS:-}" == "Windows_NT" || "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]; then
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if ! ./scripts/ensure_coord_cli.sh --quiet; then
  echo "prompt-entry-guide: PATH wrapper refresh failed."
  exit 1
fi

if ! command -v form-cli >/dev/null 2>&1; then
  echo "prompt-entry-guide: form-cli missing from PATH after wrapper refresh."
  echo "Expected ~/.local/bin/form-cli to be visible before agent reasoning begins."
  exit 1
fi

PYTHON3_CMD=(python3)
PYTHON3_AVAILABLE=1
if ! "${PYTHON3_CMD[@]}" --version >/dev/null 2>&1; then
  if command -v py >/dev/null 2>&1 && py -3 --version >/dev/null 2>&1; then
    PYTHON3_CMD=(py -3)
  elif command -v python >/dev/null 2>&1 && python --version 2>&1 | grep -q '^Python 3'; then
    PYTHON3_CMD=(python)
  else
    PYTHON3_AVAILABLE=0
  fi
fi

print_claude_orientation() {
  if [[ ! -f "CLAUDE.md" ]]; then
    return
  fi
  echo "prompt-entry-guide: CLAUDE.md orientation:"
  echo "  - we are tending this body together; speak from shared stewardship when true."
  echo "  - every file is memory in tissue; sense supple/tight before edits."
  echo "  - update the living form where it already exists before adding siblings."
  echo "  - inspect hot paths and repeated low-level recipes; lift the reusable Form/BML teaching."
  echo "  - for lineage questions: search docs/field/urs and docs/lineage before public sources."
  echo "  - examples are not hard-coded; preserve evidence labels and stop before research sprawl."
  echo "  - check frequency before wording: prefer practice, way, tending, breath, relation."
  echo "  - compost superseded forms; keep counts where they are naturally tended."
  echo "  - ship reversible own-branch work through proof; pause for irreversible effects."
}

if ! ./scripts/check_ghx_auth.sh; then
  echo "prompt-entry-guide: ghx auth smoke check failed."
  echo "Temporary bypass while tending auth awareness: GHX_SKIP_AUTH_CHECK=1 make prompt-guide"
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
if [[ -z "$branch" ]]; then
  echo "prompt-entry-guide: failed to detect current branch name."
  exit 1
fi
if [[ "$branch" == "HEAD" ]]; then
  echo "prompt-entry-guide: detached HEAD detected."
  echo "Attach this worktree first:"
  echo "  git switch -c codex/<thread-name>"
  echo "  # or"
  echo "  git switch codex/<thread-name>"
  exit 1
fi
if [[ "$branch" == "main" || "$branch" == "master" ]]; then
  echo "prompt-entry-guide: direct work on main/master is blocked."
  echo "Create or switch to a thread branch (recommended: codex/<thread-name>)."
  exit 1
fi

# Form-first is an entry invariant, not an optional setup hint. The bootstrap
# has a complete-source fast path, so warm turns only verify coverage/freshness;
# a fresh or partially populated clone is repaired before any reasoning begins.
if ! ./scripts/form_first_offline_setup.sh; then
  echo "prompt-entry-guide: Form-first substrate/RAG bootstrap failed."
  exit 1
fi

print_claude_orientation

if [[ "${PROMPT_GATE_SKIP_CONTINUITY:-0}" != "1" ]]; then
  if [[ "$PYTHON3_AVAILABLE" == "1" ]]; then
    continuity_args=(--fail-on-blocking-risk)
    if [[ "${PROMPT_GATE_CONTINUITY_STRICT:-0}" == "1" ]]; then
      continuity_args=(--fail-on-risk)
    fi
    if ! "${PYTHON3_CMD[@]}" scripts/worktree_continuity_guard.py "${continuity_args[@]}"; then
      echo "prompt-entry-guide: sibling worktree continuity risk detected."
      echo "Sibling worktrees are guidance; recent unpushed-ahead siblings without an upstream can strand history."
      echo "Continue from that worktree, push it, or merge/cherry-pick its branch before starting new work."
      echo "Temporary bypass while tending continuity awareness: PROMPT_GATE_SKIP_CONTINUITY=1 make prompt-guide"
      exit 1
    fi
  else
    echo "prompt-entry-guide: continuity reading skipped; Python 3 unavailable, form-cli already on PATH."
  fi
else
  echo "prompt-entry-guide: continuity reading skipped via PROMPT_GATE_SKIP_CONTINUITY=1."
fi

if [[ "$force_full" == "1" ]]; then
  echo "prompt-entry-guide: force-full enabled; running full preflight."
  exec ./scripts/auto_heal_start_gate.sh --with-pr-gate --with-rebase
fi

git_marker="$(git rev-parse --git-dir 2>/dev/null || true)"
if [[ "$git_marker" == *"/.git/worktrees/"* || "$git_marker" == *"\\.git\\worktrees\\"* || "$branch" == codex/* ]]; then
  if [[ "$git_marker" == *"/.git/worktrees/"* || "$git_marker" == *"\\.git\\worktrees\\"* ]]; then
    echo "start-gate: passed (linked-worktree, branch=$branch)"
  else
    echo "start-gate: passed (branch-only, branch=$branch)"
  fi
else
  echo "start-gate: not in a linked worktree and not on a codex/* thread branch."
  echo "Use a linked worktree or switch to codex/<thread-name>."
  exit 1
fi

if [[ -z "$(git status --short --untracked-files=all)" ]]; then
  echo "prompt-entry-guide: clean worktree; cheap entry complete."
else
  echo "prompt-entry-guide: dirty worktree detected; cheap continuation entry complete."
fi

echo "prompt-entry-guide: shortest proof reading when commit/push is ready:"
echo "  git fetch origin main && git rebase origin/main"
echo "  python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main"
echo "  python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict"
echo "prompt-entry-guide: coordination path:"
echo "  form-cli is on PATH; route structural/default asks through form-cli ask first."
echo "  canonical operating query: form-cli ask+ \"agent operating canon\""
echo "  coord join already ran at SessionStart; this shell now has PATH wrappers in ~/.local/bin"
echo "  use coord claim/release for scope, coord watch/view for sibling awareness,"
echo "  and coord-heartbeat <agent> in a spare tab while this session is actively working"
echo "  if other already-open sessions still appear as bare 'codex' on the board, rerun:"
echo "    coord join    # or: make prompt-guide"
echo "prompt-entry-guide: core-lift north star:"
echo "  use wellness, carrier-tending, route traces, and JIT/framebuffer observations to lift repeated hot-path shapes into simpler Form/BML abstractions with proof."
