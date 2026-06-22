#!/usr/bin/env bash
# install_kernel_memory_witness.sh — bring the kernel memory witness home.
#
# Mirrors the presence-carrier pattern: the canonical guardian lives in the repo
# (scripts/kernel_memory_witness.sh, version-controlled, reproducible on any
# machine); this installer copies it to a stable runtime location that survives
# worktree cleanup, writes a launchd agent, and loads it. Idempotent — re-running
# refreshes the runtime copy and reloads the agent.
set -euo pipefail

LABEL="earth.hati.coherence.kernel-memory-witness"
SRC="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kernel_memory_witness.sh"
RUN_DIR="$HOME/.coherence-witness"
RUN_SH="$RUN_DIR/kernel-memory-witness.sh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/CoherenceSense"
CAP_GB="${FORM_KERNEL_MEM_CAP_GB:-16}"

mkdir -p "$RUN_DIR" "$LOG_DIR" "$(dirname "$PLIST")"
cp "$SRC" "$RUN_SH"
chmod +x "$RUN_SH"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RUN_SH</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>FORM_KERNEL_MEM_CAP_GB</key>
    <string>$CAP_GB</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/kernel-memory-witness.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/kernel-memory-witness.err.log</string>
</dict>
</plist>
PLIST_EOF

# Reload cleanly (unload-if-present, then load).
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "installed + loaded: $LABEL"
echo "  runtime : $RUN_SH"
echo "  plist   : $PLIST"
echo "  cap     : ${CAP_GB} GB"
echo "  log     : $LOG_DIR/kernel-memory-witness.log"
launchctl list | grep -F "$LABEL" || true
