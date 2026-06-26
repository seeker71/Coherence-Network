import Foundation

public struct FormNativeLookupSignal: Codable, Equatable, Sendable {
    public var lane: String
    public var attempted: Bool
    public var grounded: Bool
    public var sufficient: Bool
    public var output: String
    public var sourceIDs: [String]
    public var hasOutput: Bool
    public var shapeOK: Bool
    public var contentScore: Int
    public var confidenceScore: Int
    public var trustScore: Int
    public var retriesLeft: Int

    public init(
        lane: String,
        attempted: Bool,
        grounded: Bool,
        sufficient: Bool,
        output: String = "",
        sourceIDs: [String] = [],
        hasOutput: Bool,
        shapeOK: Bool,
        contentScore: Int,
        confidenceScore: Int,
        trustScore: Int,
        retriesLeft: Int = 0
    ) {
        self.lane = lane
        self.attempted = attempted
        self.grounded = grounded
        self.sufficient = sufficient
        self.output = output
        self.sourceIDs = sourceIDs
        self.hasOutput = hasOutput
        self.shapeOK = shapeOK
        self.contentScore = max(0, min(100, contentScore))
        self.confidenceScore = max(0, min(100, confidenceScore))
        self.trustScore = max(0, min(100, trustScore))
        self.retriesLeft = max(0, retriesLeft)
    }

    public static func bodyProtocol(sourceIDs: [String], sufficient: Bool = false) -> FormNativeLookupSignal {
        FormNativeLookupSignal(
            lane: "form-native-body",
            attempted: true,
            grounded: !sourceIDs.isEmpty,
            sufficient: sufficient,
            output: sourceIDs.joined(separator: "\n"),
            sourceIDs: sourceIDs,
            hasOutput: !sourceIDs.isEmpty,
            shapeOK: true,
            contentScore: sufficient ? 90 : 45,
            confidenceScore: 90,
            trustScore: 90
        )
    }

    public static func formCLIOutput(_ output: String, retriesLeft: Int = 0) -> FormNativeLookupSignal {
        let trimmed = output.trimmingCharacters(in: .whitespacesAndNewlines)
        let sourceIDs = Self.extractSourceIDs(from: trimmed)
        let grounded = trimmed.contains("grounded:") || !sourceIDs.isEmpty
        let miss = trimmed.isEmpty || trimmed == "cell"
        let sufficient = grounded && !miss
        return FormNativeLookupSignal(
            lane: "form-native-rag-local-llm",
            attempted: true,
            grounded: grounded,
            sufficient: sufficient,
            output: trimmed,
            sourceIDs: sourceIDs,
            hasOutput: !trimmed.isEmpty,
            shapeOK: !trimmed.isEmpty,
            contentScore: sufficient ? 82 : (miss ? 20 : 45),
            confidenceScore: grounded ? 72 : 35,
            trustScore: grounded ? 72 : 35,
            retriesLeft: retriesLeft
        )
    }

    public static func unavailable(_ lane: String, reason: String) -> FormNativeLookupSignal {
        FormNativeLookupSignal(
            lane: lane,
            attempted: false,
            grounded: false,
            sufficient: false,
            output: reason,
            hasOutput: !reason.isEmpty,
            shapeOK: true,
            contentScore: 0,
            confidenceScore: 0,
            trustScore: 0
        )
    }

    private static func extractSourceIDs(from output: String) -> [String] {
        output
            .split(whereSeparator: \.isWhitespace)
            .map(String.init)
            .map { token in
                token.hasPrefix("grounded:") ? String(token.dropFirst("grounded:".count)) : token
            }
            .filter { $0.hasPrefix("docs/") || $0.hasPrefix("specs/") || $0.hasPrefix("form/") }
    }
}

public struct FormNativeRouteReceipt: Codable, Equatable, Sendable {
    public var kind: String
    public var listenReceipt: String
    public var transcribeRoute: String
    public var formRequestKind: String
    public var hostBoundary: FormHostBoundaryReceipt
    public var bodyLookup: FormNativeLookupSignal
    public var ragLookup: FormNativeLookupSignal
    public var sufficiencyVerdict: String
    public var sufficiencyReason: String
    public var decision: String
    public var remoteOracleRequested: Bool
    public var remoteOracle: String

    public init(
        listenReceipt: String = "primary-live-room-capture-receipt",
        transcribeRoute: String = "speech-side-channel-during-live-capture",
        formRequestKind: String = "satsang-guidance-request",
        hostBoundary: FormHostBoundaryReceipt = FormHostBoundaryReceipt(),
        bodyLookup: FormNativeLookupSignal,
        ragLookup: FormNativeLookupSignal,
        remoteOracle: String = "remote-llm-oracle"
    ) {
        self.kind = "satsang-listen-transcribe-route"
        self.listenReceipt = listenReceipt
        self.transcribeRoute = transcribeRoute
        self.formRequestKind = formRequestKind
        self.hostBoundary = hostBoundary
        self.bodyLookup = bodyLookup
        self.ragLookup = ragLookup
        self.remoteOracle = remoteOracle

        if bodyLookup.grounded && bodyLookup.sufficient {
            self.sufficiencyVerdict = "accept-local"
            self.sufficiencyReason = "form-native-body-sufficient"
            self.decision = "use-form-native-body"
            self.remoteOracleRequested = false
        } else {
            let verdict = Self.sufficiencyVerdict(for: ragLookup)
            if ragLookup.grounded && verdict == 0 {
                self.sufficiencyVerdict = "accept-local"
                self.sufficiencyReason = "form-native-rag-sufficient"
                self.decision = "use-form-native-rag-llm"
                self.remoteOracleRequested = false
            } else if verdict == 1 {
                self.sufficiencyVerdict = "retry-local"
                self.sufficiencyReason = Self.sufficiencyReason(for: ragLookup)
                self.decision = "retry-form-native-rag"
                self.remoteOracleRequested = false
            } else {
                self.sufficiencyVerdict = "escalate-remote"
                self.sufficiencyReason = Self.sufficiencyReason(for: ragLookup)
                self.decision = "request-remote-llm-oracle"
                self.remoteOracleRequested = true
            }
        }
    }

    public var summary: String {
        if remoteOracleRequested {
            return "Form route: native insufficient; remote oracle requested"
        }
        return "Form route: \(decision)"
    }

    private static func sufficiencyVerdict(for signal: FormNativeLookupSignal) -> Int {
        if !(signal.hasOutput && signal.shapeOK) {
            return signal.retriesLeft > 0 ? 1 : 2
        }
        return quality(for: signal) >= 60 && aboveFloor(signal) ? 0 : 2
    }

    private static func sufficiencyReason(for signal: FormNativeLookupSignal) -> String {
        if !signal.hasOutput { return "empty-local-output" }
        if !signal.shapeOK { return "bad-local-shape" }
        if signal.contentScore < 25 { return "weak-local-content" }
        if signal.confidenceScore < 25 { return "low-local-confidence" }
        if signal.trustScore < 25 { return "low-local-trust" }
        return "local-quality-below-threshold"
    }

    private static func quality(for signal: FormNativeLookupSignal) -> Int {
        ((2 * signal.contentScore) + signal.confidenceScore + signal.trustScore) / 4
    }

    private static func aboveFloor(_ signal: FormNativeLookupSignal) -> Bool {
        signal.contentScore >= 25 && signal.confidenceScore >= 25 && signal.trustScore >= 25
    }
}

public struct FormNativeLookupRunner: Sendable {
    public var formCLIURL: URL
    public var workingDirectory: URL
    public var host: any HostResourceInterface

    public init(
        formCLIURL: URL,
        workingDirectory: URL,
        host: any HostResourceInterface = FoundationHostResourceInterface()
    ) {
        self.formCLIURL = formCLIURL
        self.workingDirectory = workingDirectory
        self.host = host
    }

    static func normalizeAskInput(_ question: String) -> String {
        question
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: " ")
    }

    public func ask(_ question: String) -> FormNativeLookupSignal {
        guard host.isExecutableFile(at: formCLIURL) else {
            return .unavailable("form-native-rag-local-llm", reason: "form-cli executable not found at \(formCLIURL.path)")
        }
        let normalizedQuestion = Self.normalizeAskInput(question)

        do {
            let text = try host.runExecutable(
                at: formCLIURL,
                workingDirectory: workingDirectory,
                standardInput: "ask \(normalizedQuestion)\n"
            )
            return .formCLIOutput(text)
        } catch {
            return .unavailable("form-native-rag-local-llm", reason: error.localizedDescription)
        }
    }
}
