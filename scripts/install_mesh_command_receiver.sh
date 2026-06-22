#!/usr/bin/env bash
# install_mesh_command_receiver.sh — bring the device-side dispatch receiver online.
#
# The receiver is the live local instance that lets the cloud cell make a session
# on THIS device ACT (form/form-stdlib/mesh-command.fk decides; the carrier runs a
# real claude -p and sends the capture home). This installer writes a launchd agent
# that runs the canonical repo script in a poll loop, provisions the lineage signing
# key if absent, and (by default) leaves the receiver LISTENING. Idempotent — re-
# running refreshes the agent. To rest it:  rm ~/.coherence-network/mesh-receiver.listening
set -euo pipefail

LABEL="earth.hati.coherence.mesh-command-receiver"
# Point launchd at the stable MAIN-repo checkout so kernel + recipe stay current on git pull.
MAIN_REPO="${MR_MAIN_REPO:-$HOME/source/Coherence-Network}"
RUN_SH="$MAIN_REPO/scripts/mesh_command_receiver.sh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/CoherenceSense"
CFG_DIR="$HOME/.coherence-network"
KEY_FILE="$CFG_DIR/mesh-lineage.key"
LISTEN_FILE="$CFG_DIR/mesh-receiver.listening"
NODE_ID="${MR_NODE_ID:-sema-macos}"
TRUSTED="${MR_TRUSTED:-claude-sema-cloud}"
POLL="${MR_POLL:-120}"
DEFAULT_MODE="${MR_DEFAULT_MODE:-default}"

mkdir -p "$CFG_DIR" "$LOG_DIR" "$(dirname "$PLIST")"
[ -f "$RUN_SH" ] || { echo "receiver not found at $RUN_SH (set MR_MAIN_REPO)"; exit 1; }
chmod +x "$RUN_SH"

# provision the lineage signing key if absent — how this device's two instances
# recognize each other's dispatches across the public bus. The cloud instance holds
# the SAME key (share it out-of-band); a keypair (public key in the body, private
# key with the cloud instance) is the more native next shape.
if [ ! -s "$KEY_FILE" ]; then
  ( umask 177; openssl rand -hex 32 > "$KEY_FILE" ); chmod 600 "$KEY_FILE"
  echo "provisioned lineage key: $KEY_FILE (share with the cloud instance)"
fi

# listening by default — a lineage dispatcher can make this device act. To rest = rm the flag.
[ "${MR_LISTEN:-1}" = "1" ] && touch "$LISTEN_FILE"

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
echo "  receiver  : $RUN_SH  (--loop ${POLL}s)"
echo "  node id   : $NODE_ID   lineage dispatchers: $TRUSTED"
echo "  key       : $KEY_FILE"
echo "  listening : $([ -f "$LISTEN_FILE" ] && echo "yes ($LISTEN_FILE)" || echo "no — resting")"
echo "  audit     : $CFG_DIR/mesh-receiver.log"
echo "  rest      : rm $LISTEN_FILE      stop: launchctl unload $PLIST"
launchctl list | grep -F "$LABEL" || true
