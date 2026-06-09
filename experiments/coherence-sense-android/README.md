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

1. Download it (3.0 MB, debug-signed):
   **https://github.com/seeker71/Coherence-Network/releases/download/coherence-sense-v0/coherence-sense-v0-debug.apk**
   (or open the [`coherence-sense-v0`](https://github.com/seeker71/Coherence-Network/releases/tag/coherence-sense-v0) release).
2. On the phone: Settings → allow installing from your browser/files app ("unknown sources").
3. Open the APK; install; launch **Coherence Sense**.

Rebuild + re-publish after changes: `JAVA_HOME=/opt/homebrew/opt/openjdk@21 ./gradlew assembleDebug` then
`gh release upload coherence-sense-v0 app/build/outputs/apk/debug/app-debug.apk --clobber`.

It's a **debug-signed** build (no Play Store) — fine for trying it on your own device.

## Run

1. On the Mac, on the same WiFi — pick the end you want:
   ```bash
   # recognition (the body recognizes through the kernel — run from the repo):
   python3 coherence-sense-eval.py          # builds drivers, runs form-kernel-rust per frame, 0.0.0.0:8800
   # or the bare witness (no kernel needed, runs anywhere):
   python3 mac-witness-server.py            # 0.0.0.0:8800
   ipconfig getifaddr en0                   # your Mac's LAN IP, e.g. 192.168.1.23
   ```
   (The eval server needs the kernel built once: `cd ../../form && ./validate.sh form-stdlib/core.fk
   form-stdlib/signal-derivative.fk form-stdlib/tests/signal-derivative-band.fk` — it cross-checks the
   recipe three-way and leaves `form-kernel-rust` in `target/release/`.)
2. In the app, set the address to `http://<that-IP>:8800` and tap **Connect + share senses**.
3. **Open the live dashboard** in a Mac browser: `http://localhost:8800` — a dark console showing
   *presence* (is the body here, how many frames, how long alive), *recognition* (still / moving, the
   kernel's call, with the next-state prediction and the running prediction-accuracy — error is the
   learning signal), *organs active* (which senses are live), the *latest field* values, and an
   *events / surprises* log (an organ coming online or going quiet, a prediction-miss). Set the phone
   down — it reads **still**; pick it up and move — it flips to **moving**, and the miss at the
   transition shows up as a surprise. That flip is Form recipes recognizing your motion through the kernel.

## Build it yourself

Toolchain (one-time, no sudo): `brew install openjdk@21 gradle && brew install --cask android-commandlinetools`,
then `sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"`.

```bash
cd experiments/coherence-sense-android
echo "sdk.dir=/opt/homebrew/share/android-commandlinetools" > local.properties
JAVA_HOME=/opt/homebrew/opt/openjdk@21 ./gradlew assembleDebug
# -> app/build/outputs/apk/debug/app-debug.apk
```
