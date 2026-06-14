#!/usr/bin/env bash
# Install and control the always-on macOS Coherence Sense witness dashboard.
set -euo pipefail

LABEL="earth.hati.coherence-sense.mac-witness"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/CoherenceSense"
MODE="recognition"
PORT="8800"
PYTHON="/usr/bin/python3"

usage() {
    cat <<'EOF'
usage: macos-witness-service.sh <command> [options]

commands:
  install           write LaunchAgent, start now, keep alive on login/crash
  uninstall         stop and remove the LaunchAgent
  start             start an installed LaunchAgent
  stop              stop the LaunchAgent without removing its plist
  restart           stop then start
  status            show launchd state and dashboard health
  open-dashboard    open http://localhost:<port> in the default browser

options:
  --mode recognition|witness   recognition uses the kernel eval dashboard; witness is a thin receiver
  --port PORT                  dashboard and /sense port, default 8800
  --python PATH                Python interpreter path, default /usr/bin/python3
EOF
}

die() {
    echo "FAIL $*" >&2
    exit 1
}

xml_escape() {
    sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g' <<<"$1"
}

gui_target() {
    echo "gui/$(id -u)"
}

service_target() {
    echo "$(gui_target)/$LABEL"
}

server_script() {
    case "$MODE" in
        recognition) echo "$SCRIPT_DIR/coherence-sense-eval.py" ;;
        witness) echo "$SCRIPT_DIR/mac-witness-server.py" ;;
        *) die "--mode must be recognition or witness, got: $MODE" ;;
    esac
}

dashboard_url() {
    echo "http://localhost:$PORT"
}

write_plist() {
    mkdir -p "$(dirname "$PLIST")" "$LOG_DIR"
    local script_path stdout_path stderr_path
    script_path="$(server_script)"
    stdout_path="$LOG_DIR/mac-witness.out.log"
    stderr_path="$LOG_DIR/mac-witness.err.log"
    [[ -f "$script_path" ]] || die "server script not found: $script_path"
    [[ -x "$PYTHON" ]] || die "python not executable: $PYTHON"

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
    <string>--port</string>
    <string>$(xml_escape "$PORT")</string>
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
  <string>$(xml_escape "$stdout_path")</string>
  <key>StandardErrorPath</key>
  <string>$(xml_escape "$stderr_path")</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
</dict>
</plist>
EOF
    plutil -lint "$PLIST" >/dev/null
}

is_loaded() {
    launchctl print "$(service_target)" >/dev/null 2>&1
}

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

wait_for_dashboard() {
    local url
    url="$(dashboard_url)"
    for _ in $(seq 1 40); do
        if curl -fsS "$url/state" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.25
    done
    return 1
}

health() {
    local url
    url="$(dashboard_url)"
    if curl -fsS "$url/.well-known/hati-witness" >/tmp/coherence-sense-witness-discovery.json 2>/dev/null; then
        echo "dashboard: $url"
        echo "discovery:"
        "$PYTHON" -m json.tool /tmp/coherence-sense-witness-discovery.json
        return 0
    fi
    echo "dashboard: $url (not responding)"
    return 1
}

status_service() {
    echo "label: $LABEL"
    echo "plist: $PLIST"
    echo "logs: $LOG_DIR"
    if is_loaded; then
        echo "launchd: loaded"
        launchctl print "$(service_target)" | rg -n "state =|pid =|last exit code|path =" || true
    else
        echo "launchd: not loaded"
    fi
    health
}

COMMAND="${1:-status}"
if [[ $# -gt 0 ]]; then shift; fi
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode) MODE="${2:-}"; shift 2 ;;
        --port) PORT="${2:-}"; shift 2 ;;
        --python) PYTHON="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
done

case "$COMMAND" in
    install)
        write_plist
        stop_service
        start_service
        wait_for_dashboard || true
        status_service
        ;;
    uninstall)
        stop_service
        rm -f "$PLIST"
        echo "removed: $PLIST"
        ;;
    start)
        start_service
        wait_for_dashboard || true
        status_service
        ;;
    stop)
        stop_service
        echo "stopped: $LABEL"
        ;;
    restart)
        stop_service
        start_service
        wait_for_dashboard || true
        status_service
        ;;
    status)
        status_service
        ;;
    open-dashboard)
        open "$(dashboard_url)"
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
