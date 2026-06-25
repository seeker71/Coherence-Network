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
            ]
        )

        let result = try sender.send(request)
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.queueURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.latestJSONURL.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: result.latestFormURL.path))
        let form = try String(contentsOf: result.latestFormURL)
        XCTAssertTrue(form.contains("(target \"sema\")"))
        XCTAssertTrue(form.contains("hello edited"))
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
