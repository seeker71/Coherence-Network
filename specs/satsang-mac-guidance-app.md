---
idea_id: knowledge-and-resonance
status: active
source:
  - file: experiments/satsang-mac-app/Sources/SatsangGuidance/SatsangGuidanceApp.swift
    symbols: [SatsangGuidanceApp, AppModel, ContentView]
  - file: experiments/satsang-mac-app/Sources/SatsangGuidance/RoomTranscriber.swift
    symbols: [RoomTranscriber]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/Transcript.swift
    symbols: [TranscriptUtterance, TranscriptParser]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/TranscriptMerger.swift
    symbols: [TranscriptMerger]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/GuidanceRequest.swift
    symbols: [GuidanceRequest, GuidanceRequestSender]
  - file: form/form-stdlib/satsang-guidance-event.fk
    symbols: [sge-target-known?, sge-turn-mode?, sge-all-transcripts?, sge-ready?, sge-receipt]
requirements:
  - "Mac desktop GUI can listen to the room microphone after explicit Start Listening"
  - "Mac desktop GUI shows detected transcripts from the local transcript file"
  - "Transcript lines can be edited before sending"
  - "The full transcript set is included in the guidance request"
  - "The request names Sema or another invoked presence and a turn-offered protocol mode"
done_when:
  - "Swift package tests pass for parsing and request writing"
  - "Swift package builds the GUI executable"
  - "satsang-guidance-event Form band crosses four-way with verdict 255"
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-guidance-event.fk form-stdlib/tests/satsang-guidance-event-band.fk"
constraints:
  - "Do not auto-send hidden transcripts; the user presses Send"
  - "The GUI edits local event payloads only; speech capture starts only from explicit user action"
  - "The presence speaks only when the turn is offered, named-and-asked, or button-invoked"
---

# Satsang Mac Guidance App

## Purpose

This spec creates a native Mac desktop carrier for the satsang companion loop:
room speech and detected transcript files are visible, editable, and sent as an
explicit guidance request to Sema or another invoked presence only when a turn
is offered. The carrier listens only after explicit user action, reads local
transcript files, and writes a local protocol event queue.

## Requirements

- [x] The GUI loads detected transcript lines from a JSONL or JSON-array file.
- [x] The GUI starts/stops native macOS microphone transcription with explicit
      user action.
- [x] Live microphone partials appear as editable `room mic` transcript rows.
- [x] The GUI allows editing individual utterances before sending.
- [x] Manual and live rows survive transcript-file reloads.
- [x] The send action includes all loaded transcript lines in the request.
- [x] The request records target presence, invocation text, turn mode, and
      guidance question.
- [x] A Form proof names the valid event/protocol boundary.

## Files

- `experiments/satsang-mac-app/Package.swift` - Swift package.
- `experiments/satsang-mac-app/Sources/SatsangGuidance/SatsangGuidanceApp.swift` - SwiftUI GUI.
- `experiments/satsang-mac-app/Sources/SatsangGuidance/RoomTranscriber.swift` - native room microphone transcription.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/Transcript.swift` - transcript parser.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/TranscriptMerger.swift` - transcript reload merge policy.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/GuidanceRequest.swift` - event writer.
- `experiments/satsang-mac-app/Tests/SatsangMacCoreTests/SatsangMacCoreTests.swift` - package tests.
- `scripts/build_satsang_mac_app.sh` - `.app` bundle builder.
- `form/form-stdlib/satsang-guidance-event.fk` - Form protocol.
- `form/form-stdlib/tests/satsang-guidance-event-band.fk` - Form proof.
- `docs/coherence-substrate/satsang-guidance-event.form` - teaching.

## Acceptance Tests

- `swift test --package-path experiments/satsang-mac-app` passes.
- `swift build --package-path experiments/satsang-mac-app --product SatsangGuidance` passes.
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-guidance-event.fk form-stdlib/tests/satsang-guidance-event-band.fk` returns `255`.
- Manual validation: launch the app, press Start Listening, allow macOS
  microphone/speech prompts, speak into the room, edit a transcript line, press
  Send, and see a JSON/Form event under
  `~/.coherence-network/satsang-guidance/`.

## Verification

```zsh
swift test --package-path experiments/satsang-mac-app
swift build --package-path experiments/satsang-mac-app --product SatsangGuidance
scripts/build_satsang_mac_app.sh
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-guidance-event.fk form-stdlib/tests/satsang-guidance-event-band.fk
python3 scripts/validate_spec_quality.py --file specs/satsang-mac-guidance-app.md
```

## Out of Scope

- Autonomous interruption by Sema or another presence.
- Cloud transcription or remote LLM routing.

## Risks

- Local transcript producers use more than one JSON shape, so the parser accepts
  common field aliases and ignores lines without text.
- A packaged `.app` launched outside the repo still writes the local event queue
  and latest Form envelope under `~/.coherence-network/satsang-guidance/`.
- The app does not replace turn-taking learning; it records that the turn was
  offered or manually invoked.
- macOS microphone and speech-recognition permission prompts must be accepted
  before live room transcription can run.

## Known Gaps and Follow-up Tasks

- Follow-up task: add a signed notarized macOS bundle once the app surface settles.
- Follow-up task: wire a live Sema presence process to consume the event queue and
  return a visible transmission inside the GUI.
