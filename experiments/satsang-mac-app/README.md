# Satsang Native App

SwiftUI native carrier for a satsang guidance session.

The macOS app and iPhone app share one tabbed SwiftUI body: Room, Guidance,
Memory, Learning, Resources, and Settings. The Room mode listens to the room
microphone after `Start Listening` is pressed, keeps that live capture as the
primary stream, turns concurrent side-channel speech transcription into editable
transcript lines, can also follow a local transcript file, shows every line that
will be sent, and writes a `satsang-guidance-request` event for Sema or another
invoked presence.

Default transcript:

```text
~/.coherence-network/agent-room-memory/transcript.jsonl
```

Default event queue:

```text
~/.coherence-network/satsang-guidance/events.jsonl
```

Trusted room memory is stored locally beside the transcript:

```text
~/.coherence-network/agent-room-memory/session-index.jsonl
~/.coherence-network/agent-room-memory/speaker-profiles.json
~/.coherence-network/agent-room-memory/sessions/
~/.coherence-network/agent-room-memory/latest-context.form
```

Run from the repo root:

```zsh
swift run --package-path experiments/satsang-mac-app SatsangGuidance
```

Run the iPhone SwiftUI shell as a package product on the host for source-level
validation:

```zsh
swift run --package-path experiments/satsang-mac-app SatsangGuidancePhone
```

Build an `.app` bundle:

```zsh
scripts/build_satsang_mac_app.sh
open "experiments/satsang-mac-app/dist/Satsang Guidance.app"
```

The GUI does not invoke an external receiver. Pressing Send writes the JSONL
event, a latest JSON receipt, and a latest `.form` envelope directly. The Form
protocol proofs live in `form/form-stdlib/satsang-guidance-event.fk`,
`form/form-stdlib/satsang-host-boundary.fk`, and
`form/form-stdlib/satsang-listen-route.fk`.

Pressing Send also records the offered exchange in the local trusted room memory
store. Later sends include a compact prior-context summary and speaker-profile
summary in the guidance request. A transcript producer's `voice_id` /
`speaker_id` becomes stable speaker continuity across sessions; when no voice id
exists, the app falls back to the visible speaker label and records that as
channel continuity, not verified identity. The app does not open a separate
macOS biometric speaker-identification lane; any future acoustic continuity
sidecar must share the already-open listening stream. The memory proof lives in
`form/form-stdlib/satsang-room-memory.fk`.

The app boundary is intentionally small. Shared routing and sufficiency logic is
Form-native; Swift is the current Apple host carrier for GUI, microphone, speech,
file, and process resources. The request receipt names a generic host OS
resource interface with resolved macOS, Windows, Android, and iPhone/iOS carrier
mappings.
Each Send receipt includes detected host resource doors for file read, file
append, atomic file write, process stdin/stdout, audio input, and speech
transcription, plus the cross-platform carrier matrix for those same doors.
Python, Go, Rust, and TypeScript are not app-boundary runtimes for this carrier.
Windows and Android are carrier mappings in this package, not full GUI apps yet.
The iPhone target is native SwiftUI source; a device-signed archive still needs
an Apple team/profile plus installed iOS SDK support. The permission metadata
template lives at `Support/SatsangGuidancePhone/Info.plist`, and iOS routes the
Form process door through an embedded runtime adapter rather than arbitrary
subprocess spawning.

Before Send writes the event, the app asks the repo-local native `form-cli`
for a local body/RAG answer. The resulting route receipt is stored inside the
JSON and `.form` request. `remoteOracleRequested` is set only when the
Form-native body and local RAG/local-LLM lane are not sufficient; the GUI does
not call the remote oracle itself.

The first use of `Start Listening` asks the Apple host for microphone and speech
recognition permission. The microphone meter starts as soon as microphone access
is available. Speech Recognition then attaches as a side channel fed by the
already-open live capture tap; it is not a before-recording or after-recording
pass over stored audio. Partial speech appears in the transcript list as `room
mic`; pressing `Stop Listening` commits the current partial line. If Speech
reports a no-speech interval, the listener keeps the capture stream open and
restarts only the recognition side channel. The Room tab shows a live microphone
level while listening, so the holder can see whether the room is reaching the
mic even while Speech permission is still pending.
