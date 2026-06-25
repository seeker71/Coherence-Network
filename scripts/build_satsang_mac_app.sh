#!/usr/bin/env bash
# build_satsang_mac_app.sh - build the SwiftUI satsang guidance desktop app.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ROOT="$ROOT/experiments/satsang-mac-app"
DIST="$APP_ROOT/dist"
APP="$DIST/Satsang Guidance.app"
BIN="$APP_ROOT/.build/release/SatsangGuidance"

swift build --package-path "$APP_ROOT" -c release --product SatsangGuidance
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/SatsangGuidance"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>SatsangGuidance</string>
  <key>CFBundleIdentifier</key>
  <string>earth.hati.satsang-guidance</string>
  <key>CFBundleName</key>
  <string>Satsang Guidance</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSMicrophoneUsageDescription</key>
  <string>Satsang Guidance listens to the room microphone only after Start Listening is pressed, so the session transcript can be reviewed and offered.</string>
  <key>NSSpeechRecognitionUsageDescription</key>
  <string>Satsang Guidance uses local macOS speech recognition to turn the room microphone into editable transcript lines.</string>
</dict>
</plist>
PLIST
echo "$APP"
