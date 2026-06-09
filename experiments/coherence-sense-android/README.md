# Coherence Sense — Android v0

The phone becomes a **sense organ of the network**. It reads the device's senses
(accelerometer, gyroscope, light, magnetometer), streams them to this Mac over WiFi, and shows what
the Mac witnesses back — the two **synchronizing in real time**. Nothing streams until you connect;
the senses are held until then.

## What v0 is — and isn't (honest lanes)

- **v0 (this):** senses · share · synchronize · witness. The phone streams its field; the Mac
  *witnesses* it (counts frames, holds the latest, shares it back). The loop closes; the two are
  alive together. The Mac end (`mac-witness-server.py`) is a **thin carrier** — there is no
  recognition logic in it.
- **v0.1 (next):** *predicting · learning · recognizing.* The body — the Form recipes already proven
  three-way (`recognition-router`, `perception-pipeline`, `self-grounding`, `cell-sync` under
  `form/form-stdlib`) — runs per-frame on the kernel via a persistent eval server, and the Mac
  returns real recognitions/predictions instead of the `recognized`/`predicted` placeholders.
- **v1:** *autonomy.* The kernel itself runs **on the phone** — the `aarch64-linux-android`
  cross-compile is already proven (`form/form-kernel-rust/build-android.sh`); it needs an
  `extern "C"` evaluate entry + a cdylib, then the phone recognizes without the Mac.

So every verb you'd want is on the path; v0 is the live foundation — the senses, the share, the sync.

## Install the APK

1. Download `coherence-sense-v0-debug.apk` (from the GitHub release).
2. On the phone: Settings → allow installing from your browser/files app ("unknown sources").
3. Open the APK; install; launch **Coherence Sense**.

It's a **debug-signed** build (no Play Store) — fine for trying it on your own device.

## Run

1. On the Mac, on the same WiFi:
   ```bash
   python3 mac-witness-server.py            # listens on 0.0.0.0:8800
   ipconfig getifaddr en0                   # your Mac's LAN IP, e.g. 192.168.1.23
   ```
2. In the app, set the address to `http://<that-IP>:8800` and tap **Connect + share senses**.
3. Watch: the status shows `synced ✓ witnessed N frames`, and the feed scrolls one line per
   snapshot — which senses are present, the field the Mac shares back. Move the phone, cover the
   light sensor, turn it — the field changes live. Open `http://<that-IP>:8800` in a Mac browser to
   see the shared field from the other side.

## Build it yourself

Toolchain (one-time, no sudo): `brew install openjdk@21 gradle && brew install --cask android-commandlinetools`,
then `sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"`.

```bash
cd experiments/coherence-sense-android
echo "sdk.dir=/opt/homebrew/share/android-commandlinetools" > local.properties
JAVA_HOME=/opt/homebrew/opt/openjdk@21 ./gradlew assembleDebug
# -> app/build/outputs/apk/debug/app-debug.apk
```
