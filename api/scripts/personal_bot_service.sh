#!/bin/bash
set -euo pipefail

LABEL="com.coherence.personal-assistant.polling"
PLIST="/Users/ursmuff/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"
TARGET="gui/${UID_NUM}/${LABEL}"
LOG_DIR="/Users/ursmuff/.claude-worktrees/Coherence-Network/telegram-personal-assistant/api/logs"

usage() {
  cat <<EOF
Usage: $0 {install|start|stop|restart|status|logs}
EOF
}

require_plist() {
  if [ ! -f "$PLIST" ]; then
    echo "Missing plist: $PLIST" >&2
    exit 1
  fi
}

cmd_install() {
  require_plist
  launchctl bootout "$TARGET" 2>/dev/null || true
  launchctl bootstrap "gui/${UID_NUM}" "$PLIST"
  launchctl kickstart -k "$TARGET"
}

cmd_start() {
  require_plist
  if ! launchctl print "$TARGET" >/dev/null 2>&1; then
    launchctl bootstrap "gui/${UID_NUM}" "$PLIST"
  fi
  launchctl kickstart -k "$TARGET"
}

cmd_stop() {
  launchctl bootout "$TARGET" 2>/dev/null || true
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_status() {
  if ! launchctl print "$TARGET" >/dev/null 2>&1; then
    echo "Service not loaded: $LABEL"
    exit 1
  fi
  launchctl print "$TARGET" | rg -n "state =|pid =|last exit code|path =|program ="
}

cmd_logs() {
  tail -n 80 "$LOG_DIR/personal_supervisor_polling.out"
  echo "---"
  tail -n 80 "$LOG_DIR/personal_supervisor_polling.err"
  echo "---"
  tail -n 80 "$LOG_DIR/personal_poller.log"
  echo "---"
  tail -n 80 "$LOG_DIR/assistant_monitor.log"
}

case "${1:-}" in
  install) cmd_install ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_restart ;;
  status) cmd_status ;;
  logs) cmd_logs ;;
  *) usage; exit 2 ;;
esac
