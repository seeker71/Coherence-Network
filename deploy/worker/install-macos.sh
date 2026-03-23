#!/bin/bash
# install-macos.sh — Register Coherence Network worker as a macOS launchd service
# Runs the local_runner in loop mode, restarts on failure, survives reboots.
#
# Usage:
#   chmod +x deploy/worker/install-macos.sh
#   ./deploy/worker/install-macos.sh
#
# To uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.coherence-network.worker.plist
#   rm ~/Library/LaunchAgents/com.coherence-network.worker.plist

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RUNNER="$REPO_DIR/api/scripts/local_runner.py"
LOG_DIR="$REPO_DIR/api/logs"
LOG_FILE="$LOG_DIR/worker_service.log"
ERR_FILE="$LOG_DIR/worker_service_err.log"
INTERVAL="${1:-15}"
TIMEOUT="${2:-300}"
PLIST_NAME="com.coherence-network.worker"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
PYTHON="$(which python3 || which python)"

echo "Coherence Network Worker — macOS Service Installer"
echo "======================================================"
echo "Repo:     $REPO_DIR"
echo "Runner:   $RUNNER"
echo "Python:   $PYTHON"
echo "Interval: ${INTERVAL}s"
echo "Timeout:  ${TIMEOUT}s"
echo "Log:      $LOG_FILE"
echo ""

# Ensure log directory
mkdir -p "$LOG_DIR"

# Ensure LaunchAgents directory
mkdir -p "$HOME/Library/LaunchAgents"

# Unload existing if present
if launchctl list | grep -q "$PLIST_NAME" 2>/dev/null; then
    echo "Unloading existing service..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

# Write the plist
cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>-u</string>
        <string>$RUNNER</string>
        <string>--loop</string>
        <string>--interval</string>
        <string>$INTERVAL</string>
        <string>--timeout</string>
        <string>$TIMEOUT</string>
        <string>--no-self-update</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUTF8</key>
        <string>1</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$HOME/.local/bin:$HOME/.nvm/versions/node/v22.0.0/bin</string>
    </dict>

    <key>StandardOutPath</key>
    <string>$LOG_FILE</string>

    <key>StandardErrorPath</key>
    <string>$ERR_FILE</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
PLIST

echo "Plist written to: $PLIST_PATH"

# Load the service
launchctl load "$PLIST_PATH"

echo ""
echo "Installed and started!"
echo ""
echo "Commands:"
echo "  Check status: launchctl list | grep coherence"
echo "  View log:     tail -f $LOG_FILE"
echo "  Stop:         launchctl unload $PLIST_PATH"
echo "  Restart:      launchctl unload $PLIST_PATH && launchctl load $PLIST_PATH"
echo "  Uninstall:    launchctl unload $PLIST_PATH && rm $PLIST_PATH"
