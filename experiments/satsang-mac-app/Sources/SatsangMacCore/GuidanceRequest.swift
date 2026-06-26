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
    public var memoryContext: TrustedRoomMemoryContext?
    public var healthContext: TrustedHealthMemoryContext?

    public init(
        id: String = UUID().uuidString,
        createdAt: String = ISO8601DateFormatter().string(from: Date()),
        sessionTitle: String,
        targetPresence: String,
        invocation: String,
        turnMode: String,
        guidanceQuestion: String,
        utterances: [TranscriptUtterance],
        routeReceipt: FormNativeRouteReceipt? = nil,
        memoryContext: TrustedRoomMemoryContext? = nil,
        healthContext: TrustedHealthMemoryContext? = nil
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
        self.memoryContext = memoryContext
        self.healthContext = healthContext
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
        if let memoryContext {
            rows.append(TrustedRoomMemoryStore.formEnvelope(memoryContext, indent: "  "))
        }
        if let healthContext {
            rows.append(TrustedHealthMemoryStore.formEnvelope(healthContext, indent: "  "))
        }
        rows.append("  (utterances")
        for utterance in utterances {
            rows.append("    (utterance \"\(Self.escape(utterance.speaker))\" \"\(Self.escape(utterance.timestamp))\" \"\(Self.escape(utterance.text))\" \"\(Self.escape(utterance.voiceID ?? ""))\" \"\(Self.escape(utterance.speakerProfileID ?? ""))\")")
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
        rows.append("    (host-boundary-kind \"\(escape(receipt.hostBoundary.kind))\")")
        rows.append("    (shared-logic \"\(escape(receipt.hostBoundary.sharedLogic))\")")
        rows.append("    (host-carrier \"\(escape(receipt.hostBoundary.hostCarrier))\")")
        rows.append("    (host-resource-interface \"\(escape(receipt.hostBoundary.resourceInterface))\")")
        rows.append("    (platform-targets \"\(escape(receipt.hostBoundary.platformTargets.joined(separator: ",")))\")")
        rows.append("    (allowed-resource-kinds \"\(escape(receipt.hostBoundary.allowedResourceKinds.joined(separator: ",")))\")")
        rows.append("    (host-resource-door-count \(receipt.hostBoundary.resourceDoors.count))")
        rows.append("    (host-resource-door-summary \"\(escape(receipt.hostBoundary.doorSummary))\")")
        rows.append("    (host-platform-carrier-count \(receipt.hostBoundary.platformCarriers.count))")
        rows.append("    (host-platform-carrier-summary \"\(escape(receipt.hostBoundary.platformCarrierSummary))\")")
        rows.append("    (app-boundary-runtimes \"\(escape(receipt.hostBoundary.appBoundaryRuntimes.joined(separator: ",")))\")")
        rows.append("    (forbidden-runtime-carriers \"\(escape(receipt.hostBoundary.forbiddenRuntimeCarriers.joined(separator: ",")))\")")
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
    public var host: any HostResourceInterface

    public init(queueURL: URL, host: any HostResourceInterface = FoundationHostResourceInterface()) {
        self.queueURL = queueURL
        self.latestJSONURL = queueURL.deletingLastPathComponent().appendingPathComponent("latest-request.json")
        self.latestFormURL = queueURL.deletingLastPathComponent().appendingPathComponent("latest-request.form")
        self.host = host
    }

    public func send(_ request: GuidanceRequest) throws -> GuidanceSendResult {
        guard !request.utterances.isEmpty else { throw GuidanceSendError.emptyTranscript }
        guard !request.guidanceQuestion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw GuidanceSendError.emptyQuestion
        }

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let line = try encoder.encode(request)
        try host.appendLine(line, to: queueURL)

        let pretty = JSONEncoder()
        pretty.outputFormatting = [.prettyPrinted, .sortedKeys]
        try host.writeData(pretty.encode(request), to: latestJSONURL, options: .atomic)
        try host.writeData(Data(request.formEnvelope.utf8), to: latestFormURL, options: .atomic)

        return GuidanceSendResult(
            queueURL: queueURL,
            latestJSONURL: latestJSONURL,
            latestFormURL: latestFormURL
        )
    }
}
