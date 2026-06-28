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
  local tmp_path="${cmd_path}.tmp.$$"

  if command -v cygpath >/dev/null 2>&1; then
    script_path="$(cygpath -w "$bash_script")"
    if [[ -x "/c/Program Files/Git/bin/bash.exe" ]]; then
      git_bash="$(cygpath -w "/c/Program Files/Git/bin/bash.exe")"
    fi
  fi

  cat > "$tmp_path" <<EOF
@echo off
setlocal
"$git_bash" "$script_path" %*
EOF
  mv "$tmp_path" "$cmd_path"
}

is_windows_host() {
  [[ "${OS:-}" == "Windows_NT" || "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]
}

# Emit the runtime block that resolves COORD_AGENT from a real per-agent signal.
# A bare Bash subshell (e.g. one Claude Code spawns) does not inherit the arrival
# hook's COORD_AGENT, so the wrapper must derive identity itself — from the live
# AI_AGENT marker the harness exports (claude-code_* -> claude, a codex run -> codex,
# etc.). It NEVER falls back to a specific sibling's name: an unrecognized context
# resolves to the install-time --agent value if one was given, else the neutral
# label "unknown". Collapsing one being into another would break the sovereign-
# identities floor (docs/coherence-substrate/witnessed-floor.form).
emit_agent_default_block() {
  cat <<EOF
if [ -z "\${COORD_AGENT:-}" ]; then
  _coord_ai_lc=\$(printf '%s' "\${AI_AGENT:-}" | tr '[:upper:]' '[:lower:]')
  case "\$_coord_ai_lc" in
    *claude*) COORD_AGENT=claude ;;
    *codex*) COORD_AGENT=codex ;;
    *cursor*) COORD_AGENT=cursor ;;
    *antigravity*|*gemini*) COORD_AGENT=gemini ;;
    *grok*) COORD_AGENT=grok ;;
    *) COORD_AGENT='${DEFAULT_AGENT:-unknown}' ;;
  esac
  export COORD_AGENT
fi
EOF
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
form_cli_tmp="${form_cli_path}.tmp.$$"
cat > "$form_cli_tmp" <<EOF
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
mv "$form_cli_tmp" "$form_cli_path"
chmod +x "$form_cli_path"
write_cmd_wrapper "$BIN_DIR/form-cli.cmd" "$form_cli_path"

coord_path="$BIN_DIR/coord"
coord_tmp="${coord_path}.tmp.$$"
cat > "$coord_tmp" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="\${COORD_REPO_ROOT:-$ROOT}"
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  git_root="\$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -n "\$git_root" && -x "\$git_root/scripts/agent-coord.sh" ]]; then
    ROOT="\$git_root"
  fi
fi
$(emit_agent_default_block)
exec bash "\$ROOT/scripts/agent-coord.sh" "\$@"
EOF
mv "$coord_tmp" "$coord_path"
chmod +x "$coord_path"
write_cmd_wrapper "$BIN_DIR/coord.cmd" "$coord_path"

heartbeat_path="$BIN_DIR/coord-heartbeat"
heartbeat_tmp="${heartbeat_path}.tmp.$$"
cat > "$heartbeat_tmp" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="\${COORD_REPO_ROOT:-$ROOT}"
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  git_root="\$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -n "\$git_root" && -x "\$git_root/scripts/coord-heartbeat.sh" ]]; then
    ROOT="\$git_root"
  fi
fi
$(emit_agent_default_block)
agent="\${1:-\$COORD_AGENT}"
if [[ \$# -gt 0 ]]; then
  shift
fi
exec bash "\$ROOT/scripts/coord-heartbeat.sh" "\$agent" "\$@"
EOF
mv "$heartbeat_tmp" "$heartbeat_path"
chmod +x "$heartbeat_path"
write_cmd_wrapper "$BIN_DIR/coord-heartbeat.cmd" "$heartbeat_path"

if [[ "$QUIET" != "1" ]]; then
  printf 'agent-cli: ready - %s, %s, %s\n' "$form_cli_path" "$coord_path" "$heartbeat_path"
  printf 'coord-cli: fallback - bash %s/scripts/agent-coord.sh <verb>\n' "$ROOT"
fi
