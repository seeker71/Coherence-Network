import Foundation

public struct GuidanceRequest: Codable, Equatable, Sendable {
    public var kind: String
    public var id: String
    public var createdAt: String
    public var sessionTitle: String
    public var targetPresence: String
    public var invocation: String
    public var turnMode: String
    public var guidanceQuestion: String
    public var utterances: [TranscriptUtterance]
    public var routeReceipt: FormNativeRouteReceipt?

    public init(
        id: String = UUID().uuidString,
        createdAt: String = ISO8601DateFormatter().string(from: Date()),
        sessionTitle: String,
        targetPresence: String,
        invocation: String,
        turnMode: String,
        guidanceQuestion: String,
        utterances: [TranscriptUtterance],
        routeReceipt: FormNativeRouteReceipt? = nil
    ) {
        self.kind = "satsang-guidance-request"
        self.id = id
        self.createdAt = createdAt
        self.sessionTitle = sessionTitle
        self.targetPresence = targetPresence
        self.invocation = invocation
        self.turnMode = turnMode
        self.guidanceQuestion = guidanceQuestion
        self.utterances = utterances
        self.routeReceipt = routeReceipt
    }

    public var editedCount: Int {
        utterances.filter(\.wasEdited).count
    }

    public var formEnvelope: String {
        var rows: [String] = []
        rows.append("(satsang-guidance-request")
        rows.append("  (id \"\(Self.escape(id))\")")
        rows.append("  (created-at \"\(Self.escape(createdAt))\")")
        rows.append("  (session \"\(Self.escape(sessionTitle))\")")
        rows.append("  (target \"\(Self.escape(targetPresence))\")")
        rows.append("  (turn-mode \"\(Self.escape(turnMode))\")")
        rows.append("  (question \"\(Self.escape(guidanceQuestion))\")")
        rows.append("  (utterance-count \(utterances.count))")
        rows.append("  (edited-count \(editedCount))")
        if let routeReceipt {
            rows.append(Self.routeEnvelope(routeReceipt))
        }
        rows.append("  (utterances")
        for utterance in utterances {
            rows.append("    (utterance \"\(Self.escape(utterance.speaker))\" \"\(Self.escape(utterance.timestamp))\" \"\(Self.escape(utterance.text))\")")
        }
        rows.append("  ))")
        return rows.joined(separator: "\n") + "\n"
    }

    private static func escape(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "\\n")
    }

    private static func routeEnvelope(_ receipt: FormNativeRouteReceipt) -> String {
        var rows: [String] = []
        rows.append("  (routing")
        rows.append("    (kind \"\(escape(receipt.kind))\")")
        rows.append("    (listen-receipt \"\(escape(receipt.listenReceipt))\")")
        rows.append("    (transcribe-route \"\(escape(receipt.transcribeRoute))\")")
        rows.append("    (form-request-kind \"\(escape(receipt.formRequestKind))\")")
        rows.append("    (body-lane \"\(escape(receipt.bodyLookup.lane))\")")
        rows.append("    (body-grounded \(receipt.bodyLookup.grounded ? 1 : 0))")
        rows.append("    (body-sufficient \(receipt.bodyLookup.sufficient ? 1 : 0))")
        rows.append("    (rag-lane \"\(escape(receipt.ragLookup.lane))\")")
        rows.append("    (rag-grounded \(receipt.ragLookup.grounded ? 1 : 0))")
        rows.append("    (rag-sufficient \(receipt.ragLookup.sufficient ? 1 : 0))")
        rows.append("    (sufficiency-verdict \"\(escape(receipt.sufficiencyVerdict))\")")
        rows.append("    (sufficiency-reason \"\(escape(receipt.sufficiencyReason))\")")
        rows.append("    (decision \"\(escape(receipt.decision))\")")
        rows.append("    (remote-oracle-requested \(receipt.remoteOracleRequested ? 1 : 0))")
        rows.append("    (remote-oracle \"\(escape(receipt.remoteOracle))\"))")
        return rows.joined(separator: "\n")
    }
}

public struct GuidanceSendResult: Equatable, Sendable {
    public var queueURL: URL
    public var latestJSONURL: URL
    public var latestFormURL: URL
}

public enum GuidanceSendError: Error, LocalizedError {
    case emptyTranscript
    case emptyQuestion

    public var errorDescription: String? {
        switch self {
        case .emptyTranscript:
            return "No transcript lines are present."
        case .emptyQuestion:
            return "The guidance question is empty."
        }
    }
}

public final class GuidanceRequestSender: @unchecked Sendable {
    public var queueURL: URL
    public var latestJSONURL: URL
    public var latestFormURL: URL

    public init(queueURL: URL) {
        self.queueURL = queueURL
        self.latestJSONURL = queueURL.deletingLastPathComponent().appendingPathComponent("latest-request.json")
        self.latestFormURL = queueURL.deletingLastPathComponent().appendingPathComponent("latest-request.form")
    }

    public func send(_ request: GuidanceRequest) throws -> GuidanceSendResult {
        guard !request.utterances.isEmpty else { throw GuidanceSendError.emptyTranscript }
        guard !request.guidanceQuestion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw GuidanceSendError.emptyQuestion
        }

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let line = try encoder.encode(request)
        try FileManager.default.createDirectory(at: queueURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: queueURL.path) {
            FileManager.default.createFile(atPath: queueURL.path, contents: nil)
        }
        let handle = try FileHandle(forWritingTo: queueURL)
        try handle.seekToEnd()
        try handle.write(contentsOf: line)
        try handle.write(contentsOf: Data("\n".utf8))
        try handle.close()

        let pretty = JSONEncoder()
        pretty.outputFormatting = [.prettyPrinted, .sortedKeys]
        try pretty.encode(request).write(to: latestJSONURL, options: .atomic)
        try request.formEnvelope.write(to: latestFormURL, atomically: true, encoding: .utf8)

        return GuidanceSendResult(
            queueURL: queueURL,
            latestJSONURL: latestJSONURL,
            latestFormURL: latestFormURL
        )
    }
}
