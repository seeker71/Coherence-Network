#!/usr/bin/env bash
# Install and control the always-on macOS Coherence Sense host organ.
# Twin of macos-witness-service.sh: the witness RECEIVES the phone's senses; this
# daemon SENSES the Mac's own organs and self-registers on the cloud Hati mesh.
set -euo pipefail

LABEL="earth.hati.coherence-sense.mac-sense-organ"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/CoherenceSense"
PYTHON="/opt/homebrew/bin/python3"
MESH="https://api.coherencycoin.com/api"
WITNESS="http://127.0.0.1:8800"
INTERVAL="5"
MEDIA="on"
# tools the media senses need (ffmpeg/sox/rec) live in /opt/homebrew/bin, which
# launchd does not put on PATH by default.
TOOL_PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

usage() {
    cat <<'EOF'
usage: macos-sense-organ-service.sh <command> [options]

commands:
  install    write LaunchAgent, start now, keep alive on login/crash
  uninstall  stop and remove the LaunchAgent
  start|stop|restart|status
  tail       follow the organ log

options:
  --mesh URL        cloud Hati mesh base, default https://api.coherencycoin.com/api
  --interval S      heartbeat/sense interval seconds, default 5
  --no-media        host vitals only (skip mic/camera/screen)
  --python PATH     interpreter, default /opt/homebrew/bin/python3
EOF
}

die() { echo "FAIL $*" >&2; exit 1; }
xml_escape() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g' <<<"$1"; }
gui_target() { echo "gui/$(id -u)"; }
service_target() { echo "$(gui_target)/$LABEL"; }

write_plist() {
    mkdir -p "$(dirname "$PLIST")" "$LOG_DIR"
    local script_path="$SCRIPT_DIR/mac-sense-organ.py"
    [[ -f "$script_path" ]] || die "organ script not found: $script_path"
    [[ -x "$PYTHON" ]] || die "python not executable: $PYTHON"
    local media_arg=""
    [[ "$MEDIA" == "off" ]] && media_arg="    <string>--no-media</string>"

    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(xml_escape "$PYTHON")</string>
    <string>$(xml_escape "$script_path")</string>
    <string>--mesh</string>
    <string>$(xml_escape "$MESH")</string>
    <string>--witness</string>
    <string>$(xml_escape "$WITNESS")</string>
    <string>--interval</string>
    <string>$(xml_escape "$INTERVAL")</string>
$media_arg
  </array>
  <key>WorkingDirectory</key>
  <string>$(xml_escape "$SCRIPT_DIR")</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>StandardOutPath</key>
  <string>$(xml_escape "$LOG_DIR/mac-sense-organ.out.log")</string>
  <key>StandardErrorPath</key>
  <string>$(xml_escape "$LOG_DIR/mac-sense-organ.err.log")</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
    <key>PATH</key>
    <string>$(xml_escape "$TOOL_PATH")</string>
  </dict>
</dict>
</plist>
EOF
    plutil -lint "$PLIST" >/dev/null
}

is_loaded() { launchctl print "$(service_target)" >/dev/null 2>&1; }
stop_service() {
    launchctl bootout "$(gui_target)" "$PLIST" >/dev/null 2>&1 || true
    launchctl bootout "$(service_target)" >/dev/null 2>&1 || true
}
start_service() {
    [[ -f "$PLIST" ]] || die "LaunchAgent not installed: $PLIST"
    if is_loaded; then
        launchctl kickstart -k "$(service_target)" >/dev/null
    else
        launchctl bootstrap "$(gui_target)" "$PLIST"
        launchctl kickstart -k "$(service_target)" >/dev/null
    fi
}
status_service() {
    echo "label: $LABEL"; echo "plist: $PLIST"; echo "logs: $LOG_DIR/mac-sense-organ.{out,err}.log"
    if is_loaded; then
        echo "launchd: loaded"
        launchctl print "$(service_target)" | grep -nE "state =|pid =|last exit code" || true
    else
        echo "launchd: not loaded"
    fi
    [[ -f "$LOG_DIR/mac-sense-organ.out.log" ]] && { echo "--- last log ---"; tail -4 "$LOG_DIR/mac-sense-organ.out.log"; }
}

COMMAND="${1:-status}"; [[ $# -gt 0 ]] && shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mesh) MESH="${2:-}"; shift 2 ;;
        --interval) INTERVAL="${2:-}"; shift 2 ;;
        --no-media) MEDIA="off"; shift ;;
        --python) PYTHON="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
done

case "$COMMAND" in
    install) write_plist; stop_service; start_service; sleep 2; status_service ;;
    uninstall) stop_service; rm -f "$PLIST"; echo "removed: $PLIST" ;;
    start) start_service; sleep 2; status_service ;;
    stop) stop_service; echo "stopped: $LABEL" ;;
    restart) stop_service; start_service; sleep 2; status_service ;;
    status) status_service ;;
    tail) tail -f "$LOG_DIR/mac-sense-organ.out.log" ;;
    -h|--help|help) usage ;;
    *) usage >&2; exit 2 ;;
esac
