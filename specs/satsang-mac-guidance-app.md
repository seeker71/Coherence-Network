---
idea_id: knowledge-and-resonance
status: active
source:
  - file: experiments/satsang-mac-app/Sources/SatsangGuidance/SatsangGuidanceApp.swift
    symbols: [SatsangGuidanceApp]
  - file: experiments/satsang-mac-app/Sources/SatsangGuidancePhone/SatsangGuidancePhoneApp.swift
    symbols: [SatsangGuidancePhoneApp]
  - file: experiments/satsang-mac-app/Sources/SatsangGuidanceKit/SatsangGuidanceRootView.swift
    symbols: [SatsangGuidanceRootView, SatsangHostShell, AppModel]
  - file: experiments/satsang-mac-app/Sources/SatsangGuidanceKit/RoomTranscriber.swift
    symbols: [RoomTranscriber]
  - file: experiments/satsang-mac-app/Sources/SatsangGuidanceKit/WearableHealthImporter.swift
    symbols: [WearableHealthImporter]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/SatsangNativeAppMode.swift
    symbols: [SatsangNativeAppMode, SatsangNativeAppModeReceipt]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/Transcript.swift
    symbols: [TranscriptUtterance, TranscriptParser]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/TrustedRoomMemory.swift
    symbols: [TrustedRoomMemoryStore, TrustedRoomMemoryContext, TrustedRoomSpeakerProfile, TrustedRoomMemorySessionRecord]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/TrustedHealthMemory.swift
    symbols: [TrustedHealthMemoryStore, TrustedHealthMemoryContext, TrustedHealthSample, TrustedHealthMemorySnapshot]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/TranscriptMerger.swift
    symbols: [TranscriptMerger]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/GuidanceRequest.swift
    symbols: [GuidanceRequest, GuidanceRequestSender]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/FormNativeRouting.swift
    symbols: [FormNativeLookupSignal, FormNativeRouteReceipt, FormNativeLookupRunner]
  - file: experiments/satsang-mac-app/Sources/SatsangMacCore/HostResourceInterface.swift
    symbols: [HostResourceInterface, FoundationHostResourceInterface, HostPlatformCarrier, FormHostBoundaryReceipt]
  - file: form/form-stdlib/satsang-guidance-event.fk
    symbols: [sge-target-known?, sge-turn-mode?, sge-all-transcripts?, sge-ready?, sge-receipt]
  - file: form/form-stdlib/satsang-host-boundary.fk
    symbols: [shb-app-runtime-allowed?, shb-runtime-forbidden?, shb-resource-kind?, shb-platform-target?, shb-boundary-ok?, shb-receipt]
  - file: form/form-stdlib/satsang-listen-route.fk
    symbols: [slr-decision, slr-remote-oracle?, slr-live-capture-receipt?, slr-side-channel-transcribe?, slr-receipt]
  - file: form/form-stdlib/satsang-room-memory.fk
    symbols: [srm-mic-exclusive-carrier?, srm-trust-ok?, srm-speaker-match?, srm-context-ready?, srm-receipt]
  - file: form/form-stdlib/satsang-health-memory.fk
    symbols: [shm-import-boundary?, shm-source-carrier?, shm-metric-kind?, shm-source-filter?, shm-trust-ok?, shm-receipt]
requirements:
  - "Mac desktop GUI can listen to the room microphone after explicit Start Listening"
  - "iPhone native SwiftUI GUI is present as a first-class app target"
  - "Mac and iPhone carriers share one tabbed native app body with Room, Guidance, Memory, Health, Learning, Resources, and Settings modes"
  - "The shared native app body includes a Health mode for explicit iPhone wearable import"
  - "The iPhone carrier reads HealthKit samples after Health permission and source filtering for Oura, Oz/O2, Wellue, ViHealth, oxygen, or oximeter sources"
  - "Imported health samples are stored in local health memory and summarized into later guidance context"
  - "Live room capture is the primary stream; speech transcription is only a side channel fed during that capture"
  - "Speech Recognition is never a before-recording or after-recording pass over stored audio"
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
  - "The request records detected host resource doors for file, process, audio-input, speech-transcript, and health-samples access"
  - "The request records resolved macOS, Windows, Android, and iPhone/iOS carrier mappings for every host resource door"
  - "The request records local trusted room-memory context from prior explicitly sent sessions"
  - "The send path stores a local session record, session index, and speaker-profile continuity receipt"
  - "The health import path stores a local import record, sample log, and latest health-memory context receipt"
  - "Recurring unnamed speakers match by stable voice_id/speaker_id when supplied; channel-only room mic continuity is not claimed as verified identity"
  - "Speaker continuity never uses macOS biometric speaker identification or any exclusive-mic biometric carrier"
  - "Python, Go, Rust, and TypeScript are rejected as app-boundary runtimes for this carrier"
done_when:
  - "Swift package tests pass for parsing, request writing, trusted room-memory, trusted health-memory, host-boundary, and route-gate receipts"
  - "Swift package builds the GUI executable"
  - "satsang-guidance-event, satsang-listen-route, satsang-room-memory, and satsang-health-memory Form bands cross four-way with verdict 255; satsang-host-boundary crosses four-way with verdict 2097151"
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-guidance-event.fk form-stdlib/tests/satsang-guidance-event-band.fk && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-host-boundary.fk form-stdlib/tests/satsang-host-boundary-band.fk && ./validate.sh form-stdlib/core.fk form-stdlib/form-cli-router.fk form-stdlib/form-cli-judge.fk form-stdlib/form-cli-sufficiency.fk form-stdlib/satsang-listen-route.fk form-stdlib/tests/satsang-listen-route-band.fk && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-room-memory.fk form-stdlib/tests/satsang-room-memory-band.fk && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-health-memory.fk form-stdlib/tests/satsang-health-memory-band.fk"
constraints:
  - "Do not auto-send hidden transcripts; the user presses Send"
  - "The GUI edits local event payloads only; speech capture starts only from explicit user action"
  - "The presence speaks only when the turn is offered, named-and-asked, or button-invoked"
  - "App-boundary resource code stays in the minimal host carrier; shared logic belongs in Form"
---

# Satsang Native Guidance App

## Purpose

This spec creates the native satsang companion app surface. macOS and iPhone
share one SwiftUI/Form-native body with tabs for Room, Guidance, Memory,
Health, Learning, Resources, and Settings. Room speech and detected transcript
files are visible, editable, and sent as an explicit guidance request to Sema or
another invoked presence only when a turn is offered. The carrier listens only
after explicit user action, reads local transcript files, imports iPhone
HealthKit wearable samples after explicit permission, and writes local protocol
memory.

## Requirements

- [x] The GUI loads detected transcript lines from a JSONL or JSON-array file.
- [x] The GUI is a single tabbed native app surface with Room, Guidance,
      Memory, Health, Learning, Resources, and Settings modes.
- [x] The GUI starts/stops native macOS microphone transcription with explicit
      user action.
- [x] The iPhone SwiftUI app target uses the same shared GUI/body and has the
      same live capture side-channel speech path available behind iOS
      microphone and speech permissions.
- [x] The GUI keeps listening through no-speech intervals by restarting only the
      speech recognition side channel.
- [x] The GUI shows a live microphone level while listening.
- [x] The GUI starts microphone metering separately from Speech Recognition
      authorization so permission delays do not leave a silent requesting state.
- [x] The GUI keeps one live capture tap open and feeds Speech Recognition as a
      concurrent side channel during capture, never as a before/after recording
      pass.
- [x] Live microphone partials appear as editable `room mic` transcript rows.
- [x] The GUI allows editing individual utterances before sending.
- [x] Manual and live rows survive transcript-file reloads.
- [x] The send action includes all loaded transcript lines in the request.
- [x] The send action writes a local trusted room-memory session record, index,
      speaker profiles, and latest context receipt after explicit Send.
- [x] Later sends include prior-session context and speaker-profile summary in
      the request.
- [x] The iPhone Health mode requests HealthKit read permission and imports
      source-filtered wearable samples into local health memory.
- [x] The source filter defaults cover Oura, Oz/O2, Wellue, ViHealth, oxygen,
      and oximeter sources while allowing the holder to edit the source list.
- [x] Imported health memory writes a local import record, sample log, JSON
      context, and Form context.
- [x] Later sends include compact health-memory context in the local Form/RAG
      request.
- [x] Recurring unnamed speakers can match by stable `voice_id` / `speaker_id`
      when supplied by a transcript producer; `room mic` without a voice id is
      carried as channel continuity, not verified identity.
- [x] Speaker continuity stays on the active transcript/listening lane:
      transcript ids, visible labels, or a future passive shared-stream sidecar.
      macOS biometric speaker identification and exclusive-mic biometric
      carriers are rejected by the room-memory proof.
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
      append, atomic file write, process stdin/stdout, audio input, speech
      transcription, and health samples.
- [x] The request records a complete macOS/Windows/Android/iPhone carrier
      matrix for those same resource doors.
- [x] A Form proof names the valid event/protocol boundary.
- [x] A Form proof names the generic host ABI and detected resource-door boundary.
- [x] A Form proof names the remote-last listen/transcribe route boundary with
      primary live capture and side-channel transcription.

## Files

- `experiments/satsang-mac-app/Package.swift` - Swift package.
- `experiments/satsang-mac-app/Sources/SatsangGuidance/SatsangGuidanceApp.swift` - macOS SwiftUI app entry point.
- `experiments/satsang-mac-app/Sources/SatsangGuidancePhone/SatsangGuidancePhoneApp.swift` - iPhone SwiftUI app entry point.
- `experiments/satsang-mac-app/Support/SatsangGuidancePhone/Info.plist` - iPhone permission metadata template.
- `experiments/satsang-mac-app/Sources/SatsangGuidanceKit/SatsangGuidanceRootView.swift` - shared tabbed SwiftUI GUI.
- `experiments/satsang-mac-app/Sources/SatsangGuidanceKit/RoomTranscriber.swift` - native Apple room microphone capture with speech transcription as a side channel.
- `experiments/satsang-mac-app/Sources/SatsangGuidanceKit/WearableHealthImporter.swift` - conditional iPhone HealthKit importer for source-filtered wearable samples.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/SatsangNativeAppMode.swift` - shared tab/mode receipt.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/Transcript.swift` - transcript parser.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/TrustedRoomMemory.swift` - local session index, speaker-profile, and prior-context memory store.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/TrustedHealthMemory.swift` - local health import index, sample log, and prior-context memory store.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/TranscriptMerger.swift` - transcript reload merge policy.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/GuidanceRequest.swift` - event writer.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/FormNativeRouting.swift` - local Form/RAG route receipt writer.
- `experiments/satsang-mac-app/Sources/SatsangMacCore/HostResourceInterface.swift` - generic host resource interface, detected resource doors, resolved platform carriers, and host-boundary receipt.
- `experiments/satsang-mac-app/Tests/SatsangMacCoreTests/SatsangMacCoreTests.swift` - package tests.
- `scripts/build_satsang_mac_app.sh` - `.app` bundle builder.
- `form/form-stdlib/satsang-guidance-event.fk` - Form protocol.
- `form/form-stdlib/tests/satsang-guidance-event-band.fk` - Form proof.
- `form/form-stdlib/satsang-host-boundary.fk` - generic host ABI, detected resource-door, and forbidden runtime protocol.
- `form/form-stdlib/tests/satsang-host-boundary-band.fk` - generic host ABI and detected resource-door proof.
- `form/form-stdlib/satsang-listen-route.fk` - remote-last listen/transcribe route protocol.
- `form/form-stdlib/tests/satsang-listen-route-band.fk` - remote-last route proof.
- `form/form-stdlib/satsang-room-memory.fk` - explicit local trusted room-memory protocol.
- `form/form-stdlib/tests/satsang-room-memory-band.fk` - trusted room-memory proof.
- `form/form-stdlib/satsang-health-memory.fk` - explicit local trusted health-memory protocol.
- `form/form-stdlib/tests/satsang-health-memory-band.fk` - trusted health-memory proof.
- `docs/coherence-substrate/satsang-guidance-event.form` - teaching.
- `docs/coherence-substrate/satsang-room-memory.form` - room-memory teaching.
- `docs/coherence-substrate/satsang-health-memory.form` - health-memory teaching.

## Acceptance Tests

- `swift test --package-path experiments/satsang-mac-app` passes.
- `swift build --package-path experiments/satsang-mac-app --product SatsangGuidance` passes.
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-guidance-event.fk form-stdlib/tests/satsang-guidance-event-band.fk` returns `255`.
- `swift build --package-path experiments/satsang-mac-app --product SatsangGuidancePhone` passes.
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-host-boundary.fk form-stdlib/tests/satsang-host-boundary-band.fk` returns `2097151`.
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/form-cli-router.fk form-stdlib/form-cli-judge.fk form-stdlib/form-cli-sufficiency.fk form-stdlib/satsang-listen-route.fk form-stdlib/tests/satsang-listen-route-band.fk` returns `255`.
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-room-memory.fk form-stdlib/tests/satsang-room-memory-band.fk` returns `255`.
- `cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-health-memory.fk form-stdlib/tests/satsang-health-memory-band.fk` returns `255`.
- Manual validation: launch the app, press Start Listening, allow macOS
  microphone/speech prompts, speak into the room, edit a transcript line, press
  Send, and see a JSON/Form event under
  `~/.coherence-network/satsang-guidance/`.
- Manual validation: send one session, start a later session with the same
  `voice_id` / `speaker_id` in the transcript file, and confirm the guidance
  request includes prior context plus the same speaker profile ID.
- Manual validation: leave the app listening during silence and confirm it stays
  in listening state instead of closing on `No speech detected`.
- Manual validation: if Speech Recognition permission is still pending or
  denied, confirm the app still shows microphone activity and an explicit status.
- Manual validation: while Speech Recognition attaches, cycles, or waits through
  silence, confirm the live mic level remains active and the listener does not
  restart the capture stream.
- Manual validation: on an iPhone with HealthKit data from Oura or an Oz/O2
  source, open Health mode, press Import, grant Health permission, and confirm
  local files appear under `~/.coherence-network/health-memory/`.

## Verification

```zsh
swift test --package-path experiments/satsang-mac-app
swift build --package-path experiments/satsang-mac-app --product SatsangGuidance
swift build --package-path experiments/satsang-mac-app --product SatsangGuidancePhone
scripts/build_satsang_mac_app.sh
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-guidance-event.fk form-stdlib/tests/satsang-guidance-event-band.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-host-boundary.fk form-stdlib/tests/satsang-host-boundary-band.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/form-cli-router.fk form-stdlib/form-cli-judge.fk form-stdlib/form-cli-sufficiency.fk form-stdlib/satsang-listen-route.fk form-stdlib/tests/satsang-listen-route-band.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-room-memory.fk form-stdlib/tests/satsang-room-memory-band.fk
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/satsang-health-memory.fk form-stdlib/tests/satsang-health-memory-band.fk
python3 scripts/validate_spec_quality.py --file specs/satsang-mac-guidance-app.md
```

## Out of Scope

- Autonomous interruption by Sema or another presence.
- Invoking a remote LLM directly from the GUI.
- Direct Oura Cloud OAuth or direct Oz/O2 Bluetooth pairing in this PR.
- Replacing macOS Speech with a fully Form-native acoustic decoder.
- Using macOS biometric speaker identification or any exclusive-mic biometric
  carrier for room-memory speaker continuity.
- Shipping full Windows or Android GUI packages in this PR.
- App Store/TestFlight signing or a device-signed iPhone archive in this PR.

## Risks

- Local transcript producers use more than one JSON shape, so the parser accepts
  common field aliases and ignores lines without text.
- A packaged `.app` launched outside the repo still writes the local event queue
  and latest Form envelope under `~/.coherence-network/satsang-guidance/`.
- The app does not replace turn-taking learning; it records that the turn was
  offered or manually invoked.
- macOS microphone permission must be accepted before the app can listen to the
  room; Speech Recognition permission must be accepted before the transcription
  side channel can attach to the already-open live capture stream.
- The listener can only transcribe audio that reaches the selected macOS input
  device; system speaker playback may not loop back into the microphone.
- The local Form/RAG lookup depends on a repo-local `form/form-cli` binary or a
  user-local `~/.local/bin/form-cli`. If neither exists, the request records
  that local lookup was unavailable before requesting remote oracle handling.
- Trusted room memory is local file-backed memory. It recognizes recurring
  unnamed speakers only when a transcript producer supplies a stable voice
  identifier, or when the same visible channel label is used. Channel-label
  continuity is not verified identity. Acoustic continuity beyond transcript
  ids must share the already-open listening stream and yield continuity labels,
  not biometric identity.
- The portable host ABI and Windows/Android carrier mappings are resolved in
  this PR; real Windows/Android device builds still need to promote each
  declared door to an observed/open runtime receipt.
- The iPhone target is native SwiftUI source in the shared Swift package. A
  device-signed archive still needs an Apple team/profile and installed iOS SDK
  support outside this source patch. iOS cannot spawn arbitrary subprocesses, so
  the process stdin/stdout resource door is declared as an embedded Form runtime
  adapter until fkwu is packaged in-process.
- HealthKit only returns data types and sources the holder grants. Oura can
  reach this lane through its Apple Health export; Oz/O2 devices reach it when
  their companion app writes compatible Apple Health samples. Device-specific
  Bluetooth or vendor-cloud routes require their own consent and protocol work.

## Known Gaps and Follow-up Tasks

- Follow-up task: add a signed notarized macOS bundle once the app surface settles.
- Follow-up task: add a signed iPhone archive/TestFlight lane once the Apple
  team/profile is available.
- Follow-up task: add direct Oura OAuth and direct Oz/O2 Bluetooth carriers when
  the holder wants source-native data beyond Apple Health.
- Follow-up task: wire a live Sema presence process to consume the event queue and
  return a visible transmission inside the GUI.
- Follow-up task: add a passive shared-audio continuity sidecar only if it can
  consume the already-open listening stream without interrupting transcription.
