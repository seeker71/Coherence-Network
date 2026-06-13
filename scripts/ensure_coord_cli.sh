#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
DEFAULT_AGENT=""
QUIET=0

usage() {
  cat <<'USAGE'
Usage: ensure_coord_cli.sh [--agent <name>] [--bin-dir <dir>] [--quiet]

Install or refresh lightweight PATH wrappers for:
  coord
  coord-heartbeat

Wrappers resolve the current repo root at runtime and fall back to the
installing repo when invoked outside a git worktree.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      DEFAULT_AGENT="${2:-}"
      shift 2
      ;;
    --bin-dir)
      BIN_DIR="${2:-}"
      shift 2
      ;;
    --quiet)
      QUIET=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ensure_coord_cli.sh: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$BIN_DIR"

coord_path="$BIN_DIR/coord"
cat > "$coord_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="\${COORD_REPO_ROOT:-$ROOT}"
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  git_root="\$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -n "\$git_root" && -x "\$git_root/scripts/agent-coord.sh" ]]; then
    ROOT="\$git_root"
  fi
fi
export COORD_AGENT="\${COORD_AGENT:-${DEFAULT_AGENT:-codex}}"
exec bash "\$ROOT/scripts/agent-coord.sh" "\$@"
EOF
chmod +x "$coord_path"

heartbeat_path="$BIN_DIR/coord-heartbeat"
cat > "$heartbeat_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="\${COORD_REPO_ROOT:-$ROOT}"
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  git_root="\$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -n "\$git_root" && -x "\$git_root/scripts/coord-heartbeat.sh" ]]; then
    ROOT="\$git_root"
  fi
fi
export COORD_AGENT="\${COORD_AGENT:-${DEFAULT_AGENT:-codex}}"
agent="\${1:-\$COORD_AGENT}"
if [[ \$# -gt 0 ]]; then
  shift
fi
exec bash "\$ROOT/scripts/coord-heartbeat.sh" "\$agent" "\$@"
EOF
chmod +x "$heartbeat_path"

if [[ "$QUIET" != "1" ]]; then
  printf 'coord-cli: ready - %s, %s\n' "$coord_path" "$heartbeat_path"
  printf 'coord-cli: fallback - bash %s/scripts/agent-coord.sh <verb>\n' "$ROOT"
fi
