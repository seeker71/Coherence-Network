#!/usr/bin/env bash
# install-room-relay-launchd.sh — make the room-ear relay DURABLE on this Mac.
#
# The relay (mac-room-relay.py) is the phone's transcription+translation door: POST /hear a wav →
# whisper-cli (small model: multilingual transcribe + --translate to English) → form_cli_ask (body-first
# agent). It must stay up for the always-on ear to mean anything; as a bare background process it dies
# silently (the recurring "device not listening/transcribing" failure). This installs it as a launchd
# service: RunAtLoad (starts at login) + KeepAlive (auto-restarts on crash) + restart on whisper hang.
#
# Interim carrier, named honestly: the relay is Python; the destination is a kernel-served serve --form
# route. This keeps the ear alive until that lands; swap ProgramArguments then.
#
# Usage: bash experiments/coherence-sense-android/install-room-relay-launchd.sh [COHERENCE_ROOT]
set -euo pipefail
ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"   # repo root (for scripts/form_cli_ask.sh)
PRES="$HOME/.coherence-presence"; mkdir -p "$PRES"
PY="$(command -v python3 || echo /opt/homebrew/bin/python3)"
PATH_LINE="$(dirname "$PY"):/usr/bin:/bin:/usr/sbin:/sbin"
LABEL="earth.hati.coherence-sense.room-relay"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

# stable copy so a worktree cleanup never silently breaks the service
cp "$(dirname "${BASH_SOURCE[0]}")/mac-room-relay.py" "$PRES/mac-room-relay.py"

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$PRES/mac-room-relay.py</string></array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>COHERENCE_ROOT</key><string>$ROOT</string>
    <key>HOME</key><string>$HOME</string>
    <key>PATH</key><string>$PATH_LINE</string>
  </dict>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$PRES/room-relay.log</string>
  <key>StandardErrorPath</key><string>$PRES/room-relay.log</string>
</dict>
</plist>
PL

# free the port if a bare process holds it, then (re)load the service
lsof -nP -iTCP:8910 -sTCP:LISTEN 2>/dev/null | grep -v COMMAND | awk '{print $2}' | xargs kill 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
sleep 3
echo "service: $(launchctl list | grep room-relay || echo NOT-LOADED)"
curl -sS --max-time 5 http://127.0.0.1:8910/health || echo "  (relay not answering yet — check $PRES/room-relay.log)"
echo
