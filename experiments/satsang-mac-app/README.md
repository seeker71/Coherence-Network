# Satsang Mac App

SwiftUI desktop carrier for a satsang guidance session.

It tails the local transcript file, lets the holder edit utterances, shows every
line that will be sent, and writes a `satsang-guidance-request` event for Sema or
another invoked presence.

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
