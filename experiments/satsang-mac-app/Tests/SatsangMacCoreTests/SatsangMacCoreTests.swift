import XCTest
@testable import SatsangMacCore

final class SatsangMacCoreTests: XCTestCase {
    func testTranscriptParserReadsJSONLAndPreservesSpeaker() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let file = dir.appendingPathComponent("transcript.jsonl")
        try """
        {"ts": 1760000000, "speaker": "Voz 1", "text": "Sema, what is alive here?", "confidence": 0.91}
        {"timestamp": "2026-06-25T06:00:00Z", "voice_id": "Voz 2", "transcript": "The room is listening."}
        """.write(to: file, atomically: true, encoding: .utf8)

        let rows = try TranscriptParser.load(from: file)
        XCTAssertEqual(rows.count, 2)
        XCTAssertEqual(rows[0].speaker, "Voz 1")
        XCTAssertEqual(rows[1].text, "The room is listening.")
        XCTAssertEqual(rows[0].confidence, 0.91)
        XCTAssertEqual(rows[1].voiceID, "Voz 2")
    }

    func testGuidanceRequestWritesQueueLatestAndFormEnvelope() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let queue = dir.appendingPathComponent("events.jsonl")
        let sender = GuidanceRequestSender(queueURL: queue)
        let request = GuidanceRequest(
            id: "req-1",
            createdAt: "2026-06-25T06:00:00Z",
            sessionTitle: "Test session",
            targetPresence: "sema",
            invocation: "turn offered",
            turnMode: "turn-offered",
            guidanceQuestion: "What wants to be offered?",
            utterances: [
                TranscriptUtterance(
                    id: "u1",
                    timestamp: "2026-06-25T06:00:00Z",
                    speaker: "Voz 1",
                    detectedText: "hello",
                    text: "hello edited",
                    voiceID: "voice-1",
                    speakerProfileID: "speaker-1"
                )
            ],
            routeReceipt: FormNativeRouteReceipt(
                bodyLookup: .bodyProtocol(sourceIDs: ["form/form-stdlib/satsang-guidance-event.fk"]),
                ragLookup: .formCLIOutput("cell")
            ),
            memoryContext: TrustedRoomMemoryContext(
                priorSessionCount: 1,
                priorTurnCount: 2,
                speakerCount: 1,
                speakerSummary: "Voz 1[speaker-1] turns=2",
                recentExchangeSummary: "Voz 1: prior exchange"
            ),
            healthContext: TrustedHealthMemoryContext(
                priorImportCount: 1,
                recentSampleCount: 2,
                sourceSummary: "Oura Ring 4=1; Wellue O2Ring S=1",
                metricSummary: "heart-rate=1; spo2=1",
                recentObservationSummary: "spo2=97.00 % from Wellue O2Ring S"
            )
        )

        let result = try sender.send(request)
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.queueURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.latestJSONURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.latestFormURL.path))
        let form = try String(contentsOf: result.latestFormURL)
        XCTAssertTrue(form.contains("(target \"sema\")"))
        XCTAssertTrue(form.contains("(host-boundary-kind \"form-native-host-boundary\")"))
        XCTAssertTrue(form.contains("(listen-receipt \"primary-live-room-capture-receipt\")"))
        XCTAssertTrue(form.contains("(transcribe-route \"speech-side-channel-during-live-capture\")"))
        XCTAssertTrue(form.contains("(host-resource-interface \"host-os-generic-resource-interface\")"))
        XCTAssertTrue(form.contains("(host-resource-door-count 7)"))
        XCTAssertTrue(form.contains("(host-resource-door-summary \"audio-input:declared:host-os-generic-resource-interface"))
        XCTAssertTrue(form.contains("health-samples:declared:host-os-generic-resource-interface"))
        XCTAssertTrue(form.contains("(host-platform-carrier-count 4)"))
        XCTAssertTrue(form.contains("windows:windows-minimal-host-carrier"))
        XCTAssertTrue(form.contains("android:android-minimal-host-carrier"))
        XCTAssertTrue(form.contains("ios:iphone-minimal-host-carrier"))
        XCTAssertTrue(form.contains("ios-healthkit"))
        XCTAssertTrue(form.contains("(forbidden-runtime-carriers \"python,go,rust,typescript\")"))
        XCTAssertTrue(form.contains("(remote-oracle-requested 1)"))
        XCTAssertTrue(form.contains("(trusted-room-memory-context"))
        XCTAssertTrue(form.contains("(prior-session-count 1)"))
        XCTAssertTrue(form.contains("(hidden-capture 0)"))
        XCTAssertTrue(form.contains("(trusted-health-memory-context"))
        XCTAssertTrue(form.contains("(prior-import-count 1)"))
        XCTAssertTrue(form.contains("(source-carrier \"ios-healthkit-source-filter\")"))
        XCTAssertTrue(form.contains("(analysis-boundary \"reference-memory-reasoning-analysis-not-diagnosis\")"))
        XCTAssertTrue(form.contains("speaker-1"))
        XCTAssertTrue(form.contains("hello edited"))
    }

    func testNativeRouteKeepsRemoteBehindSufficiencyGate() {
        let body = FormNativeLookupSignal.bodyProtocol(
            sourceIDs: ["form/form-stdlib/satsang-guidance-event.fk"],
            sufficient: false
        )
        let groundedRAG = FormNativeLookupSignal.formCLIOutput("grounded:docs/coherence-substrate/satsang-guidance-event.form")
        let localReceipt = FormNativeRouteReceipt(bodyLookup: body, ragLookup: groundedRAG)

        XCTAssertEqual(localReceipt.decision, "use-form-native-rag-llm")
        XCTAssertFalse(localReceipt.remoteOracleRequested)
        XCTAssertEqual(localReceipt.listenReceipt, "primary-live-room-capture-receipt")
        XCTAssertEqual(localReceipt.transcribeRoute, "speech-side-channel-during-live-capture")

        let missReceipt = FormNativeRouteReceipt(bodyLookup: body, ragLookup: .formCLIOutput("cell"))
        XCTAssertEqual(missReceipt.decision, "request-remote-llm-oracle")
        XCTAssertTrue(missReceipt.remoteOracleRequested)
    }

    func testBodySufficientRouteNeverRequestsRemoteOracle() {
        let body = FormNativeLookupSignal.bodyProtocol(
            sourceIDs: ["form/form-stdlib/satsang-guidance-event.fk"],
            sufficient: true
        )
        let weakRAG = FormNativeLookupSignal.formCLIOutput("cell")
        let receipt = FormNativeRouteReceipt(bodyLookup: body, ragLookup: weakRAG)

        XCTAssertEqual(receipt.decision, "use-form-native-body")
        XCTAssertFalse(receipt.remoteOracleRequested)
    }

    func testFormCLIAskInputIsSingleLine() {
        let normalized = FormNativeLookupRunner.normalizeAskInput("""
        What wants to be offered?
        room mic: first line
        Voz 2: second line
        """)

        XCTAssertEqual(normalized, "What wants to be offered? room mic: first line Voz 2: second line")
    }

    func testHostBoundaryReceiptKeepsAppRuntimeSmall() {
        let boundary = FormHostBoundaryReceipt()

        XCTAssertTrue(boundary.usesOnlyAllowedAppRuntimes)
        XCTAssertEqual(boundary.sharedLogic, "form-native-shared-logic")
        XCTAssertEqual(boundary.resourceInterface, "host-os-generic-resource-interface")
        XCTAssertEqual(boundary.appBoundaryRuntimes, ["form", "swift-minimal-host-carrier"])
        XCTAssertEqual(boundary.forbiddenRuntimeCarriers, ["python", "go", "rust", "typescript"])
        XCTAssertEqual(boundary.resourceDoors.map(\.kind), boundary.allowedResourceKinds)
        XCTAssertEqual(boundary.platformCarriers.map(\.platform), ["macos", "windows", "android", "ios"])
        XCTAssertTrue(boundary.platformCarriers.allSatisfy { $0.resourceDoors.count == boundary.allowedResourceKinds.count })
        XCTAssertTrue(boundary.platformTargets.contains("macos"))
        XCTAssertTrue(boundary.platformTargets.contains("windows"))
        XCTAssertTrue(boundary.platformTargets.contains("android"))
        XCTAssertTrue(boundary.platformTargets.contains("ios"))
    }

    func testWindowsAndroidAndIPhoneHostCarriersResolveEveryDoor() {
        let boundary = FormHostBoundaryReceipt()
        let windows = boundary.platformCarriers.first { $0.platform == "windows" }
        let android = boundary.platformCarriers.first { $0.platform == "android" }
        let ios = boundary.platformCarriers.first { $0.platform == "ios" }

        XCTAssertEqual(windows?.hostCarrier, "windows-minimal-host-carrier")
        XCTAssertEqual(android?.hostCarrier, "android-minimal-host-carrier")
        XCTAssertEqual(ios?.hostCarrier, "iphone-minimal-host-carrier")
        XCTAssertEqual(windows?.resourceDoors.map(\.kind), boundary.allowedResourceKinds)
        XCTAssertEqual(android?.resourceDoors.map(\.kind), boundary.allowedResourceKinds)
        XCTAssertEqual(ios?.resourceDoors.map(\.kind), boundary.allowedResourceKinds)
        XCTAssertEqual(
            windows?.resourceDoors.first { $0.kind == "process-stdin-stdout" }?.carrier,
            "windows-createprocess-stdin-stdout"
        )
        XCTAssertEqual(
            android?.resourceDoors.first { $0.kind == "speech-transcript" }?.carrier,
            "android-speechrecognizer"
        )
        XCTAssertEqual(
            ios?.resourceDoors.first { $0.kind == "speech-transcript" }?.carrier,
            "ios-speech"
        )
        XCTAssertEqual(
            ios?.resourceDoors.first { $0.kind == "process-stdin-stdout" }?.carrier,
            "ios-embedded-form-cli-adapter"
        )
        XCTAssertTrue(boundary.platformCarrierSummary.contains("android-audiorecord"))
        XCTAssertTrue(boundary.platformCarrierSummary.contains("ios-avfoundation"))
        XCTAssertTrue(boundary.usesOnlyAllowedAppRuntimes)
    }

    func testNativeAppModesDefineSingleTabbedShell() {
        let receipt = SatsangNativeAppModeReceipt()

        XCTAssertEqual(receipt.kind, "satsang-native-tabbed-app")
        XCTAssertEqual(receipt.singleAppBody, "form-native-satsang-guidance-body")
        XCTAssertEqual(receipt.defaultMode, "room")
        XCTAssertEqual(receipt.modes, ["room", "guidance", "memory", "health", "learning", "resources", "settings"])
        XCTAssertEqual(SatsangNativeAppMode.allCases.map(\.title), ["Room", "Guidance", "Memory", "Health", "Learning", "Resources", "Settings"])
    }

    func testTrustedRoomMemoryStoresSessionAndFeedsLaterContext() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let store = TrustedRoomMemoryStore(rootURL: dir)
        let firstUtterances = store.utterancesWithSpeakerProfiles([
            TranscriptUtterance(
                id: "u1",
                timestamp: "2026-06-25T06:00:00Z",
                speaker: "Voz 1",
                detectedText: "first exchange",
                voiceID: "voice-a"
            )
        ])
        let firstProfile = firstUtterances[0].speakerProfileID
        let first = GuidanceRequest(
            id: "session-1",
            createdAt: "2026-06-25T06:00:00Z",
            sessionTitle: "First room",
            targetPresence: "sema",
            invocation: "turn offered",
            turnMode: "turn-offered",
            guidanceQuestion: "What is here?",
            utterances: firstUtterances
        )

        XCTAssertEqual(try store.context().priorSessionCount, 0)
        let result = try store.record(first)
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.sessionURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.indexURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.speakersURL.path))
        let recordedSession = try JSONDecoder().decode(
            TrustedRoomMemorySessionRecord.self,
            from: Data(contentsOf: result.sessionURL)
        )
        XCTAssertEqual(recordedSession.trustReceipt.voiceMatchCarrier, "transcript-voice-id-or-speaker-label")
        XCTAssertNotEqual(recordedSession.trustReceipt.voiceMatchCarrier, "macos-biometric-voice-id")

        let context = try store.context()
        XCTAssertEqual(context.priorSessionCount, 1)
        XCTAssertEqual(context.speakerCount, 1)
        XCTAssertTrue(context.recentExchangeSummary.contains("first exchange"))
        XCTAssertTrue(context.speakerSummary.contains(firstProfile ?? "missing"))

        let nextUtterances = store.utterancesWithSpeakerProfiles([
            TranscriptUtterance(
                id: "u2",
                timestamp: "2026-06-25T06:10:00Z",
                speaker: "Someone unnamed",
                detectedText: "later exchange",
                voiceID: "voice-a"
            )
        ])
        XCTAssertEqual(nextUtterances[0].speakerProfileID, firstProfile)

        let next = GuidanceRequest(
            id: "session-2",
            createdAt: "2026-06-25T06:10:00Z",
            sessionTitle: "Second room",
            targetPresence: "sema",
            invocation: "turn offered",
            turnMode: "turn-offered",
            guidanceQuestion: "What carries forward?",
            utterances: nextUtterances,
            memoryContext: context
        )
        XCTAssertTrue(next.formEnvelope.contains("(prior-session-count 1)"))
        XCTAssertTrue(next.formEnvelope.contains("first exchange"))
        XCTAssertTrue(next.formEnvelope.contains(firstProfile ?? "missing"))
    }

    func testTrustedHealthMemoryStoresWearableSamplesAndFeedsLaterContext() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let store = TrustedHealthMemoryStore(rootURL: dir)
        let snapshot = TrustedHealthMemorySnapshot(
            id: "health-1",
            createdAt: "2026-06-26T18:00:00Z",
            sourceHints: ["Oura Ring 4", "Wellue O2Ring S", "com.ouraring.oura", "com.viatom.vihealth"],
            samples: [
                TrustedHealthSample(
                    id: "s1",
                    kind: "heart-rate",
                    value: 61,
                    unit: "count/min",
                    startDate: "2026-06-26T17:59:00Z",
                    endDate: "2026-06-26T18:00:00Z",
                    sourceName: "Oura Ring 4",
                    sourceBundleIdentifier: "com.ouraring.oura"
                ),
                TrustedHealthSample(
                    id: "s2",
                    kind: "spo2",
                    value: 97,
                    unit: "%",
                    startDate: "2026-06-26T17:50:00Z",
                    endDate: "2026-06-26T18:00:00Z",
                    sourceName: "Wellue O2Ring S",
                    sourceBundleIdentifier: "com.viatom.vihealth",
                    metadata: ["stage": "sleep"]
                )
            ]
        )

        XCTAssertEqual(try store.context().priorImportCount, 0)
        let result = try store.record(snapshot)
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.importURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.indexURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.sampleLogURL.path))

        let context = try store.context()
        XCTAssertEqual(context.priorImportCount, 1)
        XCTAssertEqual(context.recentSampleCount, 2)
        XCTAssertTrue(context.sourceSummary.contains("Oura Ring 4=1"))
        XCTAssertTrue(context.sourceSummary.contains("Wellue O2Ring S=1"))
        XCTAssertTrue(context.metricSummary.contains("heart-rate=1"))
        XCTAssertTrue(context.metricSummary.contains("spo2=1"))
        XCTAssertTrue(context.recentObservationSummary.contains("spo2=97.00 % from Wellue O2Ring S"))
        XCTAssertEqual(context.trustReceipt.captureBoundary, "explicit-import")
        XCTAssertFalse(context.trustReceipt.hiddenCapture)
        XCTAssertTrue(TrustedHealthMemoryStore.formEnvelope(context).contains("(trusted-health-memory-context"))
    }

    func testDetectedHostResourceDoorsStayGeneric() {
        let host = FoundationHostResourceInterface()
        let dir = host.homeDirectory.appendingPathComponent(".coherence-network/satsang-guidance-test")
        let formCLI = URL(fileURLWithPath: "/definitely/not/form-cli")
        let doors = host.detectResourceDoors(
            transcriptURL: dir.appendingPathComponent("transcript.jsonl"),
            queueURL: dir.appendingPathComponent("events.jsonl"),
            formCLIURL: formCLI
        )
        let boundary = FormHostBoundaryReceipt(resourceDoors: doors)

        XCTAssertTrue(boundary.usesOnlyAllowedAppRuntimes)
        XCTAssertEqual(doors.map(\.kind), ["file-read", "file-append", "file-write-atomic", "process-stdin-stdout"])
        XCTAssertEqual(doors.last?.state, "unavailable")
        XCTAssertFalse(boundary.doorSummary.contains("AVFoundation"))
    }

    func testTranscriptMergePreservesManualRowsAcrossReload() {
        let loaded = [
            TranscriptUtterance(
                id: "file-1",
                timestamp: "2026-06-25T06:00:00Z",
                speaker: "Voz 1",
                detectedText: "from file"
            )
        ]
        let manual = TranscriptUtterance(
            id: "manual-1",
            timestamp: "2026-06-25T06:00:02Z",
            speaker: "manual",
            detectedText: "",
            text: "holder note",
            source: "manual"
        )

        let merged = TranscriptMerger.merge(loaded: loaded, current: [manual])

        XCTAssertEqual(merged.map(\.id), ["file-1", "manual-1"])
        XCTAssertEqual(merged.last?.text, "holder note")
    }

    func testTranscriptMergePreservesEditsOnReloadedRows() {
        let loaded = [
            TranscriptUtterance(
                id: "file-1",
                timestamp: "2026-06-25T06:00:00Z",
                speaker: "Voz 1",
                detectedText: "detected original"
            )
        ]
        let edited = TranscriptUtterance(
            id: "file-1",
            timestamp: "2026-06-25T06:00:00Z",
            speaker: "Voz 1",
            detectedText: "detected original",
            text: "edited by holder"
        )

        let merged = TranscriptMerger.merge(loaded: loaded, current: [edited])

        XCTAssertEqual(merged.count, 1)
        XCTAssertEqual(merged[0].text, "edited by holder")
    }
}
