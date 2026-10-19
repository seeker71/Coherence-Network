#!/usr/bin/env bash
# install_kernel_steward.sh — a thin launchd carrier for the body's kernel steward (carrier tissue, not logic).
#
# The logic is Form: observe/kernel-steward-run.bml in the coherence-kernel checkout reads every fkwu on this host,
# names the orphans (a kernel whose source file is gone) and stops them, reports the heavy unleased ones, and leaves a
# ledger row and a glass snapshot. This script only gives that door a heartbeat: a launchd agent that runs it every
# two minutes from the runner checkout, rebuilding the seed first when the source is newer than the binary.
#
#   bash scripts/install_kernel_steward.sh            install (or reinstall) and start
#   bash scripts/install_kernel_steward.sh --remove   stop and remove
#
# Why not the old kernel_memory_witness: a 16 GB resident cap would stop a sibling's legitimate 55 GB model session.
# Size is not the signal; purpose is (the source file gone). The 28-hour orphan of 2026-10-19 is the case.
set -euo pipefail
LABEL="com.coherence.kernel-steward"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
KERNEL="${COHERENCE_KERNEL_CHECKOUT:-$HOME/source/coherence-kernel}"
LOGDIR="$HOME/Library/Logs/CoherenceSense"
RUNNER="$HOME/.coherence-presence/kernel-steward-tick.sh"
UID_NUM="$(id -u)"

if [ "${1:-}" = "--remove" ]; then
  launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
  rm -f "$PLIST" "$RUNNER"
  echo "kernel steward removed"
  exit 0
fi

mkdir -p "$LOGDIR" "$(dirname "$RUNNER")" "$(dirname "$PLIST")"
cat >"$RUNNER" <<EOF
#!/bin/sh
# one tick of the body's kernel steward (installed by install_kernel_steward.sh)
cd "$KERNEL" || exit 0
if [ ! -x fkwu ] || [ runtime/fkwu-uni.c -nt fkwu ]; then cc -O2 -o fkwu runtime/fkwu-uni.c || exit 0; fi
printf 'act 1\n' | ./fkwu observe/kernel-steward-run.bml 2>/dev/null | head -20
EOF
chmod +x "$RUNNER"

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>$RUNNER</string></array>
  <key>StartInterval</key><integer>120</integer>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$LOGDIR/kernel-steward.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/kernel-steward.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl enable "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST"
launchctl print "gui/$UID_NUM/$LABEL" 2>/dev/null | grep -E "state =|pid =" | head -2 || true
echo "kernel steward installed: $LABEL every 120 s from $KERNEL; log $LOGDIR/kernel-steward.log"
