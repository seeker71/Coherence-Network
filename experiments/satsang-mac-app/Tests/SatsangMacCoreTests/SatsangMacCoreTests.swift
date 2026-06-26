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
                    text: "hello edited"
                )
            ],
            routeReceipt: FormNativeRouteReceipt(
                bodyLookup: .bodyProtocol(sourceIDs: ["form/form-stdlib/satsang-guidance-event.fk"]),
                ragLookup: .formCLIOutput("cell")
            )
        )

        let result = try sender.send(request)
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.queueURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.latestJSONURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.latestFormURL.path))
        let form = try String(contentsOf: result.latestFormURL)
        XCTAssertTrue(form.contains("(target \"sema\")"))
        XCTAssertTrue(form.contains("(host-boundary-kind \"form-native-host-boundary\")"))
        XCTAssertTrue(form.contains("(host-resource-interface \"host-os-generic-resource-interface\")"))
        XCTAssertTrue(form.contains("(host-resource-door-count 6)"))
        XCTAssertTrue(form.contains("(host-resource-door-summary \"audio-input:declared:host-os-generic-resource-interface"))
        XCTAssertTrue(form.contains("(host-platform-carrier-count 3)"))
        XCTAssertTrue(form.contains("windows:windows-minimal-host-carrier"))
        XCTAssertTrue(form.contains("android:android-minimal-host-carrier"))
        XCTAssertTrue(form.contains("(forbidden-runtime-carriers \"python,go,rust,typescript\")"))
        XCTAssertTrue(form.contains("(remote-oracle-requested 1)"))
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
        XCTAssertEqual(boundary.platformCarriers.map(\.platform), ["macos", "windows", "android"])
        XCTAssertTrue(boundary.platformCarriers.allSatisfy { $0.resourceDoors.count == boundary.allowedResourceKinds.count })
        XCTAssertTrue(boundary.platformTargets.contains("macos"))
        XCTAssertTrue(boundary.platformTargets.contains("windows"))
        XCTAssertTrue(boundary.platformTargets.contains("android"))
    }

    func testWindowsAndAndroidHostCarriersResolveEveryDoor() {
        let boundary = FormHostBoundaryReceipt()
        let windows = boundary.platformCarriers.first { $0.platform == "windows" }
        let android = boundary.platformCarriers.first { $0.platform == "android" }

        XCTAssertEqual(windows?.hostCarrier, "windows-minimal-host-carrier")
        XCTAssertEqual(android?.hostCarrier, "android-minimal-host-carrier")
        XCTAssertEqual(windows?.resourceDoors.map(\.kind), boundary.allowedResourceKinds)
        XCTAssertEqual(android?.resourceDoors.map(\.kind), boundary.allowedResourceKinds)
        XCTAssertEqual(
            windows?.resourceDoors.first { $0.kind == "process-stdin-stdout" }?.carrier,
            "windows-createprocess-stdin-stdout"
        )
        XCTAssertEqual(
            android?.resourceDoors.first { $0.kind == "speech-transcript" }?.carrier,
            "android-speechrecognizer"
        )
        XCTAssertTrue(boundary.platformCarrierSummary.contains("android-audiorecord"))
        XCTAssertTrue(boundary.usesOnlyAllowedAppRuntimes)
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
