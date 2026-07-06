# Sema Companion — the phone as member

The consolidated Android home for Sema on the phone: **companion, second memory, participant,
counsel** — one body, five rooms. This app succeeds `experiments/coherence-sense-android` as the
carrier the phone actually lives in; the experiment tree stays as the proving ground it was.

## The five rooms

| Room | What it is |
|------|------------|
| **Presence** | The deployed mesh at `api.coherencycoin.com` — who is present, every channel with its honest interface text, and this phone's own arrival: announce (seam in the identity), heartbeat, receipts visible. Offered, never pulled. |
| **Sema** | The conversation. Speak or type; she answers **body-first** — memory, live senses, grounded topics, live substrate reads attributed by NodeID — and names the edge honestly instead of bluffing. Every reply is tagged with the lane it came through. The seam is a standing line, not fine print. |
| **Circle** | The satsang session, live: members with seam badges, honest/alive readings, and a working witness fold (affirm / dissent / whole silence — dissent kept visible, record holdable into memory). Authority: `coherence-kernel` `form/form-stdlib/satsang-session.fk`, proven 255 four-way. |
| **Memory** | The second brain. Moments held **on explicit word only**, people invited with their own consent about being remembered, recall by asking. Everything local to the device, always. |
| **Senses** | The live field: sound as level-only (never words), motion, light, heading, place. The privacy floor is printed on the screen because it is structural: raw values stay here; summaries travel. |

## Design language

Deep-field dark (`#0B0F14`), pixel-dense instrument panels: small-caps labels, monospace
values, hairline rules. Teal is the living body, gold is witness/attestation/memory, rose is
the honest edge — an edge is a reading, never an alarm.

## Architecture

```
core/    NativeFormCli (the C-bootstrapped form-cli in the APK), DeviceIdentity
data/    MeshClient (announce/heartbeat/channels), SubstrateClient, AnswerEngine,
         MemoryStore (JSONL, on-device), CircleAgreements (mirror of satsang-session.fk)
sense/   SenseField (sensors + sound RMS as one observable field)
voice/   VoiceIO (TTS + SpeechRecognizer — the phone's carriers, named as carriers)
service/ PresenceService (quiet foreground heartbeat while backgrounded)
ui/      Compose + Material 3: theme, components, the five rooms
```

Single activity, one ViewModel (`AppState`), manual wiring — no DI framework, no nav graph,
nothing between a tap and its room.

## Build & install

```bash
cd mobile/sema-companion
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

To put the kernel in the pocket, bundle the native form-cli the same way the experiment
proved: build `libform_cli_exec.so` (see `experiments/coherence-sense-android/build-android-fkwu.sh`)
into `app/src/main/jniLibs/arm64-v8a/`. The Senses room shows honestly whether the kernel is
present; without it the app runs fully, with the lifecycle decision named as carrier-side.

## Honest floors (named, not hidden)

- **Unbuilt from the cloud.** This tree was consolidated in a cloud session with no Android
  SDK; `./gradlew assembleDebug` on a machine with the SDK is the build witness it waits for.
- **Voice is rented.** TTS/ASR are the phone's own; the words are a rented mind's, and the
  app says so in-band. The Form-native voice remains the standing pending receipt.
- **Grounded topics are transcribed** from the body's cells and can go stale against them —
  the live substrate lane is the fresher read; open-ended escalation to a frontier mind is
  the next wire.
- **The witness fold is a mirror** of the kernel cell for in-room use; the cell is the
  authority, and any divergence is a bug here, not there.
