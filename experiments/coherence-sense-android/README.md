# Coherence Sense — Android v0

The phone becomes a **sense organ of the network**. It reads the device's senses
(accelerometer, gyroscope, light, magnetometer), streams them to this Mac over WiFi, and shows what
the Mac witnesses back — the two **synchronizing in real time**. Nothing streams until you connect;
the senses are held until then.

## What v0 is — and isn't (honest lanes)

- **v0 — `mac-witness-server.py`:** senses · share · synchronize · witness. The phone streams its
  field; the Mac *witnesses* it (counts frames, holds the latest, shares it back). A **thin carrier**
  with no recognition logic — the simplest loop, for when you just want to see the two breathe together.
- **v0.1 — `coherence-sense-eval.py` (BUILT):** *predicting · learning · recognizing.* The body — the
  Form recipes proven three-way under `form/form-stdlib` — runs **per-frame on the kernel**. Each accel
  frame, the carrier writes a driver `.fk`, runs `signal-derivative` (still/moving) + `sequence-predictor`
  (the next state) through `form-kernel-rust` (~5ms), and the dashboard shows the **real recognition**,
  the **prediction**, and the **inference-error** (predicted-vs-actual — the learning signal). It also
  runs the **live learning-arc mechanism** (`learning-arc.fk`): a `nearest-shape` **challenger** interns
  the `signal-derivative` **champion**'s labels and recognizes the nearest exemplar; the dashboard shows
  its agreement with the champion. **Honest scope:** this is the *mechanism* (intern → recognize-nearest),
  not learning that generalizes — still/moving is a single threshold the champion already computes by hand,
  and there's no held-out test. Measured on the real UCI-HAR benchmark (`../har-benchmark/`), nearest-shape
  is a weak **non-parametric memorizer** (~81% vs ~96% SOTA; "model" = the whole dataset). The "small model
  matches SOTA" prize needs a *parametric* model (integer `mul` + quantized inference) — see the benchmark.
  The carrier only marshals integers in and reads the label out; the recognition is Form, via the kernel.
- **v1 — phone-native kernel (cdylib BUILT):** *autonomy.* The kernel itself runs **on the phone**.
  `form/form-kernel-rust/build-android.sh` now emits `libform_kernel_rust.so` — an ARM aarch64 shared
  object exporting `form_eval` (the same `run_source` evaluator, behind the `cabi` feature), verified
  via `ctypes` to recognize across the C boundary. What remains is a thin Kotlin JNI shim
  (`external fun formEval(src): String`), the `.so` in `jniLibs/arm64-v8a`, and the recipes bundled
  as assets — then the phone recognizes **without the Mac**.

So every verb you'd want is live today: senses, share, sync, AND recognition/prediction/learning-signal —
through the kernel, not in Python.

## Install the APK

1. Download the current Hati mesh build (release-signed):
   **https://hati.earth/downloads/hati-os/android/arm64/coherence-sense-hati-mesh-release.apk**
   (release asset: `coherence-sense-hati-mesh-release.apk` on `hati-os-v0.1.0-20260613`).
2. On the phone: Settings → allow installing from your browser/files app ("unknown sources").
3. Open the APK; install; launch **Coherence Sense**.

If a debug-signed build is already installed, Android will reject the release-signed APK as an update
because the signing keys differ. Uninstall the debug build once, then install the release-signed APK.
After that, signed updates with the same local Hati release key can replace the app normally.

From the repository root, rebuild + prove the public asset and mesh handshake after changes:

```bash
scripts/verify_android_sense_public_handshake.sh
```

That command builds the debug APK and signed release APK, builds the Hati public asset bundle, starts the Mac witness
surface, starts a local Hati mesh API, proves announce / heartbeat / list / offer / list, and writes
`.cache/android-sense-public-handshake/<stamp>/android-sense-public-handshake-summary.json`.

Publish only after the local proof passes:

```bash
scripts/verify_android_sense_public_handshake.sh --publish
```

That uploads the macOS package, Android native package, debug APK, signed release APK, checksums, and asset summary to
`hati-os-v0.1.0-20260613` with `gh release upload --clobber`.

The release APK is signed by a local Hati release key generated under
`~/.coherence-network/android/coherence-sense-release.jks`; the private key and
`experiments/coherence-sense-android/signing.properties` are not committed. This is still a direct
APK install, not a Play Store install.

## App self-update floor

The app checks `https://hati.earth/downloads/hati-os/hati-os-public-assets-summary.json` on launch.
It prefers the published signed `coherence-sense-hati-mesh-release.apk` SHA-256 and falls back to the
debug APK only if the signed release asset is not present yet. It compares that SHA with the APK currently
installed on the phone. If a newer APK is published, **Settings → Install update** downloads it from
`https://hati.earth/downloads/hati-os/android/arm64/coherence-sense-hati-mesh-release.apk`, verifies the
hash, and opens Android's package installer.

Android still requires human consent for sideloaded APK replacement unless the app is installed as a
privileged/device-owner updater. That is the honest floor. The north star is a signed Hati app update
lane where the mesh can announce releases, verify signatures and hashes, and route the update through
the highest-trust installer available on that host.

## Run

1. On the Mac, on the same WiFi — pick the end you want:
   ```bash
   # recognition (the body recognizes through the kernel — run from the repo):
   python3 coherence-sense-eval.py          # builds drivers, runs form-kernel-rust per frame, 0.0.0.0:8800
   # or the bare witness (no kernel needed, runs anywhere):
   python3 mac-witness-server.py            # 0.0.0.0:8800
   ```
   (The eval server needs the kernel built once: `cd ../../form && ./validate.sh form-stdlib/core.fk
   form-stdlib/signal-derivative.fk form-stdlib/tests/signal-derivative-band.fk` — it cross-checks the
   recipe three-way and leaves `form-kernel-rust` in `target/release/`.)
2. Open the app. It listens for the Mac's `_hati-witness._tcp` service and fills the witness lane
   automatically. Leave the mesh API as `https://api.coherencycoin.com/api` and tap **Start sharing**.
   If you tap before the Mac appears, the button waits and starts sharing when discovery resolves.
   Manual IP entry lives behind **Settings** only as a fallback when the local network blocks mDNS.
3. **Open the live dashboard** in a Mac browser: `http://localhost:8800` — a dark console showing
   *presence* (is the body here, how many frames, how long alive), *recognition* (still / moving, the
   kernel's call, with the next-state prediction and the running prediction-accuracy — error is the
   learning signal), *organs active* (which senses are live), the *latest field* values, and an
   *events / surprises* log (an organ coming online or going quiet, a prediction-miss). Set the phone
   down — it reads **still**; pick it up and move — it flips to **moving**, and the miss at the
   transition shows up as a surprise. That flip is Form recipes recognizing your motion through the kernel.

### Keep the Mac witness always running

Install the macOS user service once:

```bash
cd experiments/coherence-sense-android
chmod +x macos-witness-service.sh
./macos-witness-service.sh install --mode recognition --port 8800
```

That writes `~/Library/LaunchAgents/earth.hati.coherence-sense.mac-witness.plist`, starts the Mac
recognition witness now, restarts it after a crash, and starts it again at login. The dashboard remains
`http://localhost:8800`; Android discovers the same service as `_hati-witness._tcp`.

Useful commands:

```bash
./macos-witness-service.sh status
./macos-witness-service.sh open-dashboard
./macos-witness-service.sh restart
./macos-witness-service.sh uninstall
```

Logs live at `~/Library/Logs/CoherenceSense/mac-witness.out.log` and
`~/Library/Logs/CoherenceSense/mac-witness.err.log`.

### Keep the Android + Mac learning receipt proven

From the repository root, prove the connected phone and Mac witness shape as
learning organs:

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/nearest-shape.fk form-stdlib/classifier-eval.fk form-stdlib/co-learning.fk form-stdlib/co-learning-stream.fk form-stdlib/champion-challenger.fk form-stdlib/colearning-retire.fk form-stdlib/choice-receipt.fk form-stdlib/branch-choice-order.fk form-stdlib/choice-receipt-learning.fk form-stdlib/oracle-catalog.fk form-stdlib/text-summary-learning.fk form-stdlib/llm-feature-channel-floor.fk form-stdlib/android-mesh-learning.fk form-stdlib/tests/android-mesh-learning-band.fk
```

That validates capability/liveness receipt rows, typed channels, active
mic/camera/GPU summary samples, and native-first learning routes without a
Python receipt helper. It records the shape of liveness and channel readiness,
not raw sensor values, location coordinates, package inventory, or the adb
serial.

For the four-way gate:

```bash
cd form && bash scripts/fourth-arm-gate.sh android-mesh-learning witness-state-receipt
```

The current receipt feeds the Form-native learning floor: summarize, code-lower,
tool-select, and distill-retire can route native-first. When the app is
unlocked, sharing, and permissioned, mic RMS, camera luma, and GPU EGL readback
summary counters can lift speech, vision, and multimodal alignment to
native-first routing; heldout wins are still required before retiring their
teachers.

To prove source-backed oracle emission cycles from the live witness counters:

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/nearest-shape.fk form-stdlib/classifier-eval.fk form-stdlib/co-learning.fk form-stdlib/co-learning-stream.fk form-stdlib/champion-challenger.fk form-stdlib/colearning-retire.fk form-stdlib/choice-receipt.fk form-stdlib/branch-choice-order.fk form-stdlib/choice-receipt-learning.fk form-stdlib/oracle-catalog.fk form-stdlib/text-summary-learning.fk form-stdlib/llm-feature-channel-floor.fk form-stdlib/android-mesh-learning.fk form-stdlib/witness-state-receipt.fk form-stdlib/tests/witness-state-receipt-band.fk
```

That proves summary-only STT, vision, multimodal, and GPU label rows from
active counters, and it classifies stale or non-increasing cycles as blocked in
Form. The remaining host gap is direct Form HTTP/resource sampling of
`http://localhost:8800/state` and direct Form process/device carriers for adb.

## Hati mesh identity + channels

On first launch, the app creates a stable install-scoped organ id such as
`hati-organ-android-…`. That id is distinct for your install, another person's install, and any
other device/cell. The app does not silently read your phone number or email. If you want the organ
bound to you, enter a cell id or email label in the optional identity field; that binding is explicit.
When you connect, the app announces itself to `hati.mesh` through the public API:

- `POST /api/hati/mesh/organs/announce` — organ id, kind, target, capabilities, and lanes.
- `POST /api/hati/mesh/organs/heartbeat` — listening state, active channels, and flow rates.
- `GET /api/hati/mesh/organs` — recent mesh organs the app can see.
- `POST /api/hati/mesh/channels/offer` — channel offers to another organ.
- `GET /api/hati/mesh/channels` — channel/flow rows involving this organ.

The current APK actively streams and measures `sensor:signal` flow, announces / heartbeats on
`hati.mesh:presence`, and displays mesh silence as channel data. It declares and displays offerable
`screen:write`, `network:http`, and `bluetooth:presence` channels. The mic lane has an active RMS
summary floor, the camera lane has an active luma summary floor, and the GPU lane has an active
OpenGL ES/EGL readback summary floor when sharing is active and permissions are granted. The app
does not retain raw audio, camera frames, or GPU buffers.

The local Mac witness is also a discoverable channel. Both `mac-witness-server.py` and
`coherence-sense-eval.py` advertise `_hati-witness._tcp` on the LAN and serve
`/.well-known/hati-witness` / `/discover` with service name, mode, port, sample paths, and fallback
URLs. The floor is zero-typed setup on a normal same-WiFi LAN; the north star is signed organ
heartbeats negotiating the highest-fidelity carrier without hidden ambient host access.

The resource dashboard also makes accelerator floors visible. GPU now has a summary readback floor;
DSP/NPU remains cataloged until NNAPI/vendor delegate receipts are added. MLX is explicit unsupported
on Android; the north-star Android equivalent is GPU/NNAPI, while macOS carries the Apple MLX lane.

Before release, capture actual screenshots of the Android app and the matching macOS/web service
surface, then record self-review and sister-agent review notes. Do that at least before release,
and no more often than every couple of hours unless the same app surface is in an active refinement
loop.

## Build it yourself

Toolchain (one-time, no sudo): `brew install openjdk@21 gradle && brew install --cask android-commandlinetools`,
then `sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"`.

```bash
cd experiments/coherence-sense-android
echo "sdk.dir=/opt/homebrew/share/android-commandlinetools" > local.properties
JAVA_HOME=/opt/homebrew/opt/openjdk@21 ./gradlew assembleDebug
# -> app/build/outputs/apk/debug/app-debug.apk

# signed release APK (creates a local non-committed key on first run)
./build_signed_release.sh
# -> app/build/outputs/apk/release/app-release.apk
```
