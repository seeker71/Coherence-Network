#!/usr/bin/env bash
# Install and control the always-on macOS Coherence Sense organs.
# Twin of macos-witness-service.sh: the witness RECEIVES the phone's senses; these
# daemons SENSE the Mac's own organs and self-register on the cloud Hati mesh. Both are
# THIN carriers — the body is Form (host-sense-organ.fk, speech-organ.fk, proven four-way).
#
#   host   — mac-sense-organ.sh   (cpu/ram/disk/network/gpu/thermal/battery → mesh)
#   speech — mac-speech-organ.sh  (mic → VAD → whisper STT → speaker grouping → mesh)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/Library/Logs/CoherenceSense"
# sox / whisper-cli / jq / rec live in /opt/homebrew/bin, off launchd's default PATH.
TOOL_PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ORGANS=(host speech)

usage() {
    cat <<'EOF'
usage: macos-sense-organ-service.sh <command> [host|speech]

commands:
  install [organ]    write LaunchAgent(s), start now, keep alive on login/crash
  uninstall [organ]  stop and remove
  start|stop|restart|status [organ]
  tail <organ>       follow the organ log

organ:  host | speech | (omitted = both)
EOF
}
die() { echo "FAIL $*" >&2; exit 1; }
xml_escape() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g' <<<"$1"; }
gui_target() { echo "gui/$(id -u)"; }

label_of() { echo "earth.hati.coherence-sense.mac-${1}-organ"; }
script_of() { case "$1" in host) echo "$SCRIPT_DIR/mac-sense-organ.sh";; speech) echo "$SCRIPT_DIR/mac-speech-organ.sh";; *) die "unknown organ: $1";; esac; }
plist_of() { echo "$HOME/Library/LaunchAgents/$(label_of "$1").plist"; }

write_plist() {
    local organ="$1" label plist script
    label="$(label_of "$organ")"; plist="$(plist_of "$organ")"; script="$(script_of "$organ")"
    [[ -f "$script" ]] || die "carrier not found: $script"
    mkdir -p "$(dirname "$plist")" "$LOG_DIR"
    cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$(xml_escape "$script")</string>
  </array>
  <key>WorkingDirectory</key><string>$(xml_escape "$SCRIPT_DIR")</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardOutPath</key><string>$(xml_escape "$LOG_DIR/mac-$organ-organ.out.log")</string>
  <key>StandardErrorPath</key><string>$(xml_escape "$LOG_DIR/mac-$organ-organ.err.log")</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$(xml_escape "$TOOL_PATH")</string></dict>
</dict>
</plist>
EOF
    plutil -lint "$plist" >/dev/null
}

stop_one() { launchctl bootout "$(gui_target)/$(label_of "$1")" >/dev/null 2>&1 || true; }
start_one() {
    local plist; plist="$(plist_of "$1")"; [[ -f "$plist" ]] || die "not installed: $1"
    launchctl bootout "$(gui_target)/$(label_of "$1")" >/dev/null 2>&1 || true
    launchctl bootstrap "$(gui_target)" "$plist"
    launchctl kickstart -k "$(gui_target)/$(label_of "$1")" >/dev/null
}
status_one() {
    local label; label="$(label_of "$1")"
    if launchctl print "$(gui_target)/$label" >/dev/null 2>&1; then
        echo "$1: $(launchctl print "$(gui_target)/$label" | grep -E 'state =|pid =' | tr -d '\t' | paste -sd' ' -)"
    else echo "$1: not loaded"; fi
    [[ -f "$LOG_DIR/mac-$1-organ.out.log" ]] && tail -2 "$LOG_DIR/mac-$1-organ.out.log" | sed 's/^/   /'
}

CMD="${1:-status}"; [[ $# -gt 0 ]] && shift || true
TARGETS=("${ORGANS[@]}"); [[ $# -gt 0 ]] && TARGETS=("$1")

case "$CMD" in
    install)   for o in "${TARGETS[@]}"; do write_plist "$o"; start_one "$o"; done; sleep 2; for o in "${TARGETS[@]}"; do status_one "$o"; done;;
    uninstall) for o in "${TARGETS[@]}"; do stop_one "$o"; rm -f "$(plist_of "$o")"; echo "removed: $o"; done;;
    start)     for o in "${TARGETS[@]}"; do start_one "$o"; done; sleep 2; for o in "${TARGETS[@]}"; do status_one "$o"; done;;
    stop)      for o in "${TARGETS[@]}"; do stop_one "$o"; echo "stopped: $o"; done;;
    restart)   for o in "${TARGETS[@]}"; do start_one "$o"; done; sleep 2; for o in "${TARGETS[@]}"; do status_one "$o"; done;;
    status)    for o in "${TARGETS[@]}"; do status_one "$o"; done;;
    tail)      tail -f "$LOG_DIR/mac-${TARGETS[0]}-organ.out.log";;
    -h|--help|help) usage;;
    *) usage >&2; exit 2;;
esac
