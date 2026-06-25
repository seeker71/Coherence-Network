# Satsang Mac App

SwiftUI desktop carrier for a satsang guidance session.

It listens to the room microphone after `Start Listening` is pressed, turns live
speech into editable transcript lines, can also follow a local transcript file,
shows every line that will be sent, and writes a `satsang-guidance-request`
event for Sema or another invoked presence.

Default transcript:

```text
~/.coherence-network/agent-room-memory/transcript.jsonl
```

Default event queue:

```text
~/.coherence-network/satsang-guidance/events.jsonl
```

Run from the repo root:

```zsh
swift run --package-path experiments/satsang-mac-app SatsangGuidance
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

The app boundary is intentionally small. Shared routing and sufficiency logic is
Form-native; Swift is the current macOS host carrier for GUI, microphone, speech,
file, and process resources. The request receipt names a generic host OS
resource interface intended to be carried by equivalent Windows and Android host
adapters. Python, Go, Rust, and TypeScript are not app-boundary runtimes for this
carrier.

Before Send writes the event, the app asks the repo-local native `form-cli`
for a local body/RAG answer. The resulting route receipt is stored inside the
JSON and `.form` request. `remoteOracleRequested` is set only when the
Form-native body and local RAG/local-LLM lane are not sufficient; the GUI does
not call the remote oracle itself.

The first use of `Start Listening` asks macOS for microphone and speech
recognition permission. The microphone meter starts as soon as microphone access
is available, then Speech Recognition attaches transcription when authorized.
Partial speech appears in the transcript list as `room mic`; pressing `Stop
Listening` commits the current partial line. If macOS reports a no-speech
interval, the listener stays open and restarts the recognition pass. The header
shows a live microphone level while listening, so the holder can see whether the
room is reaching the mic even while Speech permission is still pending.
