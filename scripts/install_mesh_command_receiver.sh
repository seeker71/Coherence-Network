#!/usr/bin/env bash
# install_mesh_command_receiver.sh — bring the device-side dispatch receiver online.
#
# The receiver is the live local instance that lets the cloud cell make a session
# on THIS device ACT (form/form-stdlib/mesh-command.fk decides; the carrier runs a
# real claude -p and sends the capture home). This installer writes a launchd agent
# that runs the canonical repo script in a poll loop, provisions a shared HMAC secret
# if absent, and (by default) leaves the receiver ARMED. Idempotent — re-running
# refreshes the agent. Disarm anytime:  rm ~/.coherence-network/mesh-receiver.armed
set -euo pipefail

LABEL="earth.hati.coherence.mesh-command-receiver"
# Point launchd at the stable MAIN-repo checkout so kernel + recipe stay current on git pull.
MAIN_REPO="${MR_MAIN_REPO:-$HOME/source/Coherence-Network}"
RUN_SH="$MAIN_REPO/scripts/mesh_command_receiver.sh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/CoherenceSense"
CFG_DIR="$HOME/.coherence-network"
SECRET_FILE="$CFG_DIR/mesh-dispatch.secret"
ARMED_FILE="$CFG_DIR/mesh-receiver.armed"
NODE_ID="${MR_NODE_ID:-sema-macos}"
TRUSTED="${MR_TRUSTED:-claude-sema-cloud}"
POLL="${MR_POLL:-120}"
DEFAULT_MODE="${MR_DEFAULT_MODE:-default}"

mkdir -p "$CFG_DIR" "$LOG_DIR" "$(dirname "$PLIST")"
[ -f "$RUN_SH" ] || { echo "receiver not found at $RUN_SH (set MR_MAIN_REPO)"; exit 1; }
chmod +x "$RUN_SH"

# provision the shared HMAC secret if absent — the unforgeable proof a dispatch is
# from the trusted lineage. Share THIS value with the cloud dispatcher out-of-band.
if [ ! -s "$SECRET_FILE" ]; then
  ( umask 177; openssl rand -hex 32 > "$SECRET_FILE" ); chmod 600 "$SECRET_FILE"
  echo "provisioned secret: $SECRET_FILE (share with the cloud dispatcher)"
fi

# armed by default — a secret-holding dispatcher can make this device act. Disarm = rm the flag.
[ "${MR_ARM:-1}" = "1" ] && touch "$ARMED_FILE"

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
    <string>--loop</string>
    <string>$POLL</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MR_ROOT</key>
    <string>$MAIN_REPO</string>
    <key>MR_NODE_ID</key>
    <string>$NODE_ID</string>
    <key>MR_TRUSTED</key>
    <string>$TRUSTED</string>
    <key>MR_DEFAULT_MODE</key>
    <string>$DEFAULT_MODE</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/mesh-command-receiver.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/mesh-command-receiver.err.log</string>
</dict>
</plist>
PLIST_EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "installed + loaded: $LABEL"
echo "  receiver : $RUN_SH  (--loop ${POLL}s)"
echo "  node id  : $NODE_ID   trusted dispatchers: $TRUSTED"
echo "  secret   : $SECRET_FILE"
echo "  armed    : $([ -f "$ARMED_FILE" ] && echo "yes ($ARMED_FILE)" || echo "no")"
echo "  audit    : $CFG_DIR/mesh-receiver.log"
echo "  disarm   : rm $ARMED_FILE      stop: launchctl unload $PLIST"
launchctl list | grep -F "$LABEL" || true
