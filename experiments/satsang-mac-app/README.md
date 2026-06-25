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
protocol proof lives in `form/form-stdlib/satsang-guidance-event.fk`.

The first use of `Start Listening` asks macOS for microphone and speech
recognition permission. Partial speech appears immediately in the transcript
list as `room mic`; pressing `Stop Listening` commits the current partial line.
