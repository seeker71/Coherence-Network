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
  form-cli
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

write_cmd_wrapper() {
  local cmd_path="$1"
  local bash_script="$2"
  local script_path="$bash_script"
  local git_bash="C:\\Program Files\\Git\\bin\\bash.exe"

  if command -v cygpath >/dev/null 2>&1; then
    script_path="$(cygpath -w "$bash_script")"
    if [[ -x "/c/Program Files/Git/bin/bash.exe" ]]; then
      git_bash="$(cygpath -w "/c/Program Files/Git/bin/bash.exe")"
    fi
  fi

  cat > "$cmd_path" <<EOF
@echo off
setlocal
"$git_bash" "$script_path" %*
EOF
}

is_windows_host() {
  [[ "${OS:-}" == "Windows_NT" || "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]
}

write_python_shims() {
  is_windows_host || return 0
  command -v py >/dev/null 2>&1 || return 0
  py -3 --version >/dev/null 2>&1 || return 0
  local py_launcher
  py_launcher="$(command -v py || true)"
  if [[ -n "$py_launcher" && ! -f "$py_launcher" && -f "$py_launcher.exe" ]]; then
    py_launcher="$py_launcher.exe"
  fi

  local name shim_path cmd_path
  for name in python python3; do
    shim_path="$BIN_DIR/$name"
    cmd_path="$BIN_DIR/$name.cmd"
    rm -f "$shim_path"
    cat > "$cmd_path" <<'EOF'
@echo off
py -3 %*
EOF
  done

  if [[ -n "$py_launcher" && -f "$py_launcher" ]]; then
    cp "$py_launcher" "$BIN_DIR/python.exe"
    cp "$py_launcher" "$BIN_DIR/python3.exe"
  fi
}

write_python_shims

form_cli_path="$BIN_DIR/form-cli"
cat > "$form_cli_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="\${FORM_CLI_REPO_ROOT:-$ROOT}"
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  git_root="\$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -n "\$git_root" && -x "\$git_root/bin/form-cli" ]]; then
    ROOT="\$git_root"
  fi
fi
export FORM_CLI_REPO_ROOT="\$ROOT"
exec bash "\$ROOT/bin/form-cli" "\$@"
EOF
chmod +x "$form_cli_path"
write_cmd_wrapper "$BIN_DIR/form-cli.cmd" "$form_cli_path"

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
write_cmd_wrapper "$BIN_DIR/coord.cmd" "$coord_path"

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
write_cmd_wrapper "$BIN_DIR/coord-heartbeat.cmd" "$heartbeat_path"

if [[ "$QUIET" != "1" ]]; then
  printf 'agent-cli: ready - %s, %s, %s\n' "$form_cli_path" "$coord_path" "$heartbeat_path"
  printf 'coord-cli: fallback - bash %s/scripts/agent-coord.sh <verb>\n' "$ROOT"
fi
