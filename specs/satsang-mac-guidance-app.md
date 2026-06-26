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
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/FormNativeRouting.swift
    symbols: [FormNativeLookupSignal, FormNativeRouteReceipt, FormNativeLookupRunner]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/HostResourceInterface.swift
    symbols: [HostResourceInterface, FoundationHostResourceInterface, FormHostBoundaryReceipt]
  - file: form/form-stdlib/satsang-guidance-event.fk
    symbols: [sge-target-known?, sge-turn-mode?, sge-all-transcripts?, sge-ready?, sge-receipt]
  - file: form/form-stdlib/satsang-host-boundary.fk
    symbols: [shb-app-runtime-allowed?, shb-runtime-forbidden?, shb-resource-kind?, shb-platform-target?, shb-boundary-ok?, shb-receipt]
  - file: form/form-stdlib/satsang-listen-route.fk
    symbols: [slr-decision, slr-remote-oracle?, slr-receipt]
requirements:
  - "Mac desktop GUI can listen to the room microphone after explicit Start Listening"
  - "No-speech intervals do not stop the active room listener"
  - "A live microphone level shows whether the room is reaching the app"
  - "Microphone activity is visible separately from Speech Recognition authorization"
  - "Mac desktop GUI shows detected transcripts from the local transcript file"
  - "Transcript lines can be edited before sending"
  - "The full transcript set is included in the guidance request"
  - "The request names Sema or another invoked presence and a turn-offered protocol mode"
  - "The send path records Form-native body/RAG lookup before any remote oracle request"
  - "Remote LLM oracle routing is only an explicit request when the native sufficiency gate fails"
  - "Shared app logic is declared Form-native and host access crosses a generic host OS resource interface"
  - "The request records detected host resource doors for file, process, audio-input, and speech-transcript access"
  - "Python, Go, Rust, and TypeScript are rejected as app-boundary runtimes for this carrier"
done_when:
  - "Swift package tests pass for parsing, request writing, host-boundary, and route-gate receipts"
  - "Swift package builds the GUI executable"
  - "satsang-guidance-event and satsang-listen-route Form bands cross four-way with verdict 255; satsang-host-boundary crosses four-way with verdict 4095"
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-guidance-event.fk form-stdlib/tests/satsang-guidance-event-band.fk && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-host-boundary.fk form-stdlib/tests/satsang-host-boundary-band.fk && ./validate.sh form-stdlib/core.fk form-stdlib/form-cli-router.fk form-stdlib/form-cli-judge.fk form-stdlib/form-cli-sufficiency.fk form-stdlib/satsang-listen-route.fk form-stdlib/tests/satsang-listen-route-band.fk"
constraints:
  - "Do not auto-send hidden transcripts; the user presses Send"
  - "The GUI edits local event payloads only; speech capture starts only from explicit user action"
  - "The presence speaks only when the turn is offered, named-and-asked, or button-invoked"
  - "App-boundary resource code stays in the minimal host carrier; shared logic belongs in Form"
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
- [x] The GUI keeps listening through no-speech intervals by restarting the
      speech recognition pass.
- [x] The GUI shows a live microphone level while listening.
- [x] The GUI starts microphone metering separately from Speech Recognition
      authorization so permission delays do not leave a silent requesting state.
- [x] Live microphone partials appear as editable `room mic` transcript rows.
- [x] The GUI allows editing individual utterances before sending.
- [x] Manual and live rows survive transcript-file reloads.
- [x] The send action includes all loaded transcript lines in the request.
- [x] The request records target presence, invocation text, turn mode, and
      guidance question.
- [x] The send action runs a local Form CLI ask and records the body/RAG
      sufficiency receipt in JSON and Form output.
- [x] The route receipt sets `remoteOracleRequested` only when the local native
      sufficiency gate does not accept the body/RAG result.
- [x] The request records a host-boundary receipt: Form shared logic, a generic
      host OS resource interface, Swift as the minimal host carrier, and
      Python/Go/Rust/TypeScript forbidden at the app boundary.
- [x] The request records detected host resource doors for file read, file
      append, atomic file write, process stdin/stdout, audio input, and speech
      transcription.
- [x] A Form proof names the valid event/protocol boundary.
- [x] A Form proof names the generic host ABI and detected resource-door boundary.
- [x] A Form proof names the remote-last listen/transcribe route boundary.

## Files

- `experiments/satsang-mac-app/Package.swift` - Swift package.
- `experiments/satsang-mac-app/Sources/SatsangGuidance/SatsangGuidanceApp.swift` - SwiftUI GUI.
- `experiments/satsang-mac-app/Sources/SatsangGuidance/RoomTranscriber.swift` - native room microphone transcription.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/Transcript.swift` - transcript parser.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/TranscriptMerger.swift` - transcript reload merge policy.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/GuidanceRequest.swift` - event writer.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/FormNativeRouting.swift` - local Form/RAG route receipt writer.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/HostResourceInterface.swift` - generic host resource interface, detected resource doors, and host-boundary receipt.
- `experiments/satsang-mac-app/Tests/SatsangMacCoreTests/SatsangMacCoreTests.swift` - package tests.
- `scripts/build_satsang_mac_app.sh` - `.app` bundle builder.
- `form/form-stdlib/satsang-guidance-event.fk` - Form protocol.
- `form/form-stdlib/tests/satsang-guidance-event-band.fk` - Form proof.
- `form/form-stdlib/satsang-host-boundary.fk` - generic host ABI, detected resource-door, and forbidden runtime protocol.
- `form/form-stdlib/tests/satsang-host-boundary-band.fk` - generic host ABI and detected resource-door proof.
- `form/form-stdlib/satsang-listen-route.fk` - remote-last listen/transcribe route protocol.
- `form/form-stdlib/tests/satsang-listen-route-band.fk` - remote-last route proof.
- `docs/coherence-substrate/satsang-guidance-event.form` - teaching.

## Acceptance Tests

- `swift test --package-path experiments/satsang-mac-app` passes.
- `swift build --package-path experiments/satsang-mac-app --product SatsangGuidance` passes.
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-guidance-event.fk form-stdlib/tests/satsang-guidance-event-band.fk` returns `255`.
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-host-boundary.fk form-stdlib/tests/satsang-host-boundary-band.fk` returns `4095`.
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/form-cli-router.fk form-stdlib/form-cli-judge.fk form-stdlib/form-cli-sufficiency.fk form-stdlib/satsang-listen-route.fk form-stdlib/tests/satsang-listen-route-band.fk` returns `255`.
- Manual validation: launch the app, press Start Listening, allow macOS
  microphone/speech prompts, speak into the room, edit a transcript line, press
  Send, and see a JSON/Form event under
  `~/.coherence-network/satsang-guidance/`.
- Manual validation: leave the app listening during silence and confirm it stays
  in listening state instead of closing on `No speech detected`.
- Manual validation: if Speech Recognition permission is still pending or
  denied, confirm the app still shows microphone activity and an explicit status.

## Verification

```zsh
swift test --package-path experiments/satsang-mac-app
swift build --package-path experiments/satsang-mac-app --product SatsangGuidance
scripts/build_satsang_mac_app.sh
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-guidance-event.fk form-stdlib/tests/satsang-guidance-event-band.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-host-boundary.fk form-stdlib/tests/satsang-host-boundary-band.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/form-cli-router.fk form-stdlib/form-cli-judge.fk form-stdlib/form-cli-sufficiency.fk form-stdlib/satsang-listen-route.fk form-stdlib/tests/satsang-listen-route-band.fk
python3 scripts/validate_spec_quality.py --file specs/satsang-mac-guidance-app.md
```

## Out of Scope

- Autonomous interruption by Sema or another presence.
- Invoking a remote LLM directly from the GUI.
- Replacing macOS Speech with a fully Form-native acoustic decoder.
- Replacing the current SwiftUI macOS GUI carrier with Windows or Android host
  adapters in this PR.

## Risks

- Local transcript producers use more than one JSON shape, so the parser accepts
  common field aliases and ignores lines without text.
- A packaged `.app` launched outside the repo still writes the local event queue
  and latest Form envelope under `~/.coherence-network/satsang-guidance/`.
- The app does not replace turn-taking learning; it records that the turn was
  offered or manually invoked.
- macOS microphone permission must be accepted before the app can listen to the
  room; Speech Recognition permission must be accepted before live room
  transcription can run.
- The listener can only transcribe audio that reaches the selected macOS input
  device; system speaker playback may not loop back into the microphone.
- The local Form/RAG lookup depends on a repo-local `form/form-cli` binary or a
  user-local `~/.local/bin/form-cli`. If neither exists, the request records
  that local lookup was unavailable before requesting remote oracle handling.
- The portable host ABI and detected resource-door receipt are contracts in
  this PR; Windows and Android still need their own thin host adapters over the
  same Form/shared body.

## Known Gaps and Follow-up Tasks

- Follow-up task: add a signed notarized macOS bundle once the app surface settles.
- Follow-up task: wire a live Sema presence process to consume the event queue and
  return a visible transmission inside the GUI.
