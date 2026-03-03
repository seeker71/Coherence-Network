#!/bin/bash
set -euo pipefail

LABEL="com.coherence.personal-assistant.monitor"
PLIST="/Users/ursmuff/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"
TARGET="gui/${UID_NUM}/${LABEL}"
SCRIPT_PATH="/Users/ursmuff/.claude-worktrees/Coherence-Network/telegram-personal-assistant/api/scripts/personal_bot_monitor.sh"
WORKDIR="/Users/ursmuff/.claude-worktrees/Coherence-Network/telegram-personal-assistant/api"
LOG_DIR="/Users/ursmuff/.claude-worktrees/Coherence-Network/telegram-personal-assistant/api/logs"
INTERVAL_SEC="${PERSONAL_BOT_MONITOR_INTERVAL_SEC:-120}"

usage() {
  cat <<EOF
Usage: $0 {install|start|stop|restart|status|run-once|logs}
EOF
}

write_plist() {
  mkdir -p "$(dirname "$PLIST")" "$LOG_DIR"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>${SCRIPT_PATH}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${WORKDIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>StartInterval</key>
    <integer>${INTERVAL_SEC}</integer>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/personal_bot_monitor_runner.out</string>

    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/personal_bot_monitor_runner.err</string>

    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
  </dict>
</plist>
EOF
}

cmd_install() {
  write_plist
  launchctl bootout "$TARGET" 2>/dev/null || true
  launchctl bootstrap "gui/${UID_NUM}" "$PLIST"
  launchctl kickstart -k "$TARGET"
}

cmd_start() {
  if [ ! -f "$PLIST" ]; then
    write_plist
  fi
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
  launchctl print "$TARGET" | rg -n "state =|last exit code|path =|program =|run interval =|runs ="
}

cmd_run_once() {
  /bin/bash "$SCRIPT_PATH"
}

cmd_logs() {
  tail -n 120 "$LOG_DIR/personal_bot_monitor.log" 2>/dev/null || true
  echo "---"
  tail -n 120 "$LOG_DIR/personal_bot_monitor_runner.out" 2>/dev/null || true
  echo "---"
  tail -n 120 "$LOG_DIR/personal_bot_monitor_runner.err" 2>/dev/null || true
}

case "${1:-}" in
  install) cmd_install ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_restart ;;
  status) cmd_status ;;
  run-once) cmd_run_once ;;
  logs) cmd_logs ;;
  *) usage; exit 2 ;;
esac
