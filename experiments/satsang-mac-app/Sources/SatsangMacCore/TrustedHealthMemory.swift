import Foundation

public struct TrustedHealthMemoryTrustReceipt: Codable, Equatable, Sendable {
    public var kind: String
    public var captureBoundary: String
    public var storageCarrier: String
    public var retrievalScope: String
    public var sourceCarrier: String
    public var hiddenCapture: Bool
    public var canFeedLaterContext: Bool
    public var analysisBoundary: String

    public init(
        captureBoundary: String = "explicit-import",
        storageCarrier: String = "local-json-file",
        retrievalScope: String = "same-holder-local-health-memory",
        sourceCarrier: String = "ios-healthkit-source-filter",
        hiddenCapture: Bool = false,
        canFeedLaterContext: Bool = true,
        analysisBoundary: String = "reference-memory-reasoning-analysis-not-diagnosis"
    ) {
        self.kind = "trusted-health-memory-trust-receipt"
        self.captureBoundary = captureBoundary
        self.storageCarrier = storageCarrier
        self.retrievalScope = retrievalScope
        self.sourceCarrier = sourceCarrier
        self.hiddenCapture = hiddenCapture
        self.canFeedLaterContext = canFeedLaterContext
        self.analysisBoundary = analysisBoundary
    }
}

public struct TrustedHealthSample: Codable, Equatable, Identifiable, Sendable {
    public var id: String
    public var kind: String
    public var value: Double
    public var unit: String
    public var startDate: String
    public var endDate: String
    public var sourceName: String
    public var sourceBundleIdentifier: String
    public var deviceName: String?
    public var metadata: [String: String]

    public init(
        id: String,
        kind: String,
        value: Double,
        unit: String,
        startDate: String,
        endDate: String,
        sourceName: String,
        sourceBundleIdentifier: String = "",
        deviceName: String? = nil,
        metadata: [String: String] = [:]
    ) {
        self.id = id
        self.kind = kind
        self.value = value
        self.unit = unit
        self.startDate = startDate
        self.endDate = endDate
        self.sourceName = sourceName
        self.sourceBundleIdentifier = sourceBundleIdentifier
        self.deviceName = deviceName
        self.metadata = metadata
    }

    public var compactSummary: String {
        let rounded = String(format: "%.2f", value)
        let source = sourceName.isEmpty ? "unknown-source" : sourceName
        return "\(kind)=\(rounded) \(unit) from \(source) at \(endDate)"
    }
}

public struct TrustedHealthMemorySnapshot: Codable, Equatable, Identifiable, Sendable {
    public var kind: String
    public var id: String
    public var createdAt: String
    public var sourceHints: [String]
    public var sampleCount: Int
    public var samples: [TrustedHealthSample]
    public var trustReceipt: TrustedHealthMemoryTrustReceipt

    public init(
        id: String = UUID().uuidString,
        createdAt: String = ISO8601DateFormatter().string(from: Date()),
        sourceHints: [String],
        samples: [TrustedHealthSample],
        trustReceipt: TrustedHealthMemoryTrustReceipt = TrustedHealthMemoryTrustReceipt()
    ) {
        self.kind = "trusted-health-memory-import"
        self.id = id
        self.createdAt = createdAt
        self.sourceHints = sourceHints
        self.sampleCount = samples.count
        self.samples = samples
        self.trustReceipt = trustReceipt
    }
}

public struct TrustedHealthMemoryIndexEntry: Codable, Equatable, Sendable {
    public var importID: String
    public var createdAt: String
    public var sourceHints: [String]
    public var sampleCount: Int
    public var importPath: String
}

public struct TrustedHealthMemoryContext: Codable, Equatable, Sendable {
    public var kind: String
    public var priorImportCount: Int
    public var recentSampleCount: Int
    public var sourceSummary: String
    public var metricSummary: String
    public var recentObservationSummary: String
    public var trustReceipt: TrustedHealthMemoryTrustReceipt

    public init(
        priorImportCount: Int,
        recentSampleCount: Int,
        sourceSummary: String,
        metricSummary: String,
        recentObservationSummary: String,
        trustReceipt: TrustedHealthMemoryTrustReceipt = TrustedHealthMemoryTrustReceipt()
    ) {
        self.kind = "trusted-health-memory-context"
        self.priorImportCount = priorImportCount
        self.recentSampleCount = recentSampleCount
        self.sourceSummary = sourceSummary
        self.metricSummary = metricSummary
        self.recentObservationSummary = recentObservationSummary
        self.trustReceipt = trustReceipt
    }

    public static func empty() -> TrustedHealthMemoryContext {
        TrustedHealthMemoryContext(
            priorImportCount: 0,
            recentSampleCount: 0,
            sourceSummary: "no health sources",
            metricSummary: "no health metrics",
            recentObservationSummary: "no health samples"
        )
    }

    public var summaryLine: String {
        "Health memory: \(priorImportCount) imports, \(recentSampleCount) recent samples"
    }
}

public struct TrustedHealthMemoryRecordResult: Codable, Equatable, Sendable {
    public var importURL: URL
    public var indexURL: URL
    public var sampleLogURL: URL
    public var contextJSONURL: URL
    public var contextFormURL: URL
    public var sampleCount: Int

    public var summary: String {
        "stored \(sampleCount) health samples"
    }
}

public final class TrustedHealthMemoryStore: @unchecked Sendable {
    public var rootURL: URL
    public var host: any HostResourceInterface

    private var importsURL: URL { rootURL.appendingPathComponent("imports") }
    private var indexURL: URL { rootURL.appendingPathComponent("import-index.jsonl") }
    private var sampleLogURL: URL { rootURL.appendingPathComponent("samples.jsonl") }
    private var latestContextJSONURL: URL { rootURL.appendingPathComponent("latest-context.json") }
    private var latestContextFormURL: URL { rootURL.appendingPathComponent("latest-context.form") }

    public init(rootURL: URL, host: any HostResourceInterface = FoundationHostResourceInterface()) {
        self.rootURL = rootURL
        self.host = host
    }

    @discardableResult
    public func record(_ snapshot: TrustedHealthMemorySnapshot) throws -> TrustedHealthMemoryRecordResult {
        try host.createDirectory(at: importsURL)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let importURL = importsURL.appendingPathComponent("\(Self.fileSafe(snapshot.id)).json")
        try host.writeData(try encoder.encode(snapshot), to: importURL, options: .atomic)

        let indexEntry = TrustedHealthMemoryIndexEntry(
            importID: snapshot.id,
            createdAt: snapshot.createdAt,
            sourceHints: snapshot.sourceHints,
            sampleCount: snapshot.sampleCount,
            importPath: importURL.path
        )
        let lineEncoder = JSONEncoder()
        lineEncoder.outputFormatting = [.sortedKeys]
        try host.appendLine(try lineEncoder.encode(indexEntry), to: indexURL)
        for sample in snapshot.samples {
            try host.appendLine(try lineEncoder.encode(sample), to: sampleLogURL)
        }

        let latestContext = try context()
        try host.writeData(try encoder.encode(latestContext), to: latestContextJSONURL, options: .atomic)
        try host.writeData(Data(Self.formEnvelope(latestContext).utf8), to: latestContextFormURL, options: .atomic)

        return TrustedHealthMemoryRecordResult(
            importURL: importURL,
            indexURL: indexURL,
            sampleLogURL: sampleLogURL,
            contextJSONURL: latestContextJSONURL,
            contextFormURL: latestContextFormURL,
            sampleCount: snapshot.sampleCount
        )
    }

    public func context(maxImports: Int = 5, maxSamples: Int = 24) throws -> TrustedHealthMemoryContext {
        let entries = try loadIndex()
        let selectedEntries = Array(entries.suffix(maxImports))
        let snapshots = try selectedEntries.compactMap { try loadSnapshot(path: $0.importPath) }
        let samples = Array(Self.deduplicated(snapshots.flatMap(\.samples)).suffix(maxSamples))
        let sourceSummary = Self.countSummary(samples.map { $0.sourceName.isEmpty ? "unknown-source" : $0.sourceName })
        let metricSummary = Self.countSummary(samples.map(\.kind))
        let recentSummary = samples.suffix(10)
            .map(\.compactSummary)
            .joined(separator: " | ")

        return TrustedHealthMemoryContext(
            priorImportCount: entries.count,
            recentSampleCount: samples.count,
            sourceSummary: sourceSummary.isEmpty ? "no health sources" : sourceSummary,
            metricSummary: metricSummary.isEmpty ? "no health metrics" : metricSummary,
            recentObservationSummary: recentSummary.isEmpty ? "no health samples" : recentSummary
        )
    }

    public static func formEnvelope(_ context: TrustedHealthMemoryContext, indent: String = "") -> String {
        [
            "\(indent)(trusted-health-memory-context",
            "\(indent)  (prior-import-count \(context.priorImportCount))",
            "\(indent)  (recent-sample-count \(context.recentSampleCount))",
            "\(indent)  (source-summary \"\(escape(context.sourceSummary))\")",
            "\(indent)  (metric-summary \"\(escape(context.metricSummary))\")",
            "\(indent)  (recent-observation-summary \"\(escape(context.recentObservationSummary))\")",
            "\(indent)  (capture-boundary \"\(escape(context.trustReceipt.captureBoundary))\")",
            "\(indent)  (storage-carrier \"\(escape(context.trustReceipt.storageCarrier))\")",
            "\(indent)  (retrieval-scope \"\(escape(context.trustReceipt.retrievalScope))\")",
            "\(indent)  (source-carrier \"\(escape(context.trustReceipt.sourceCarrier))\")",
            "\(indent)  (analysis-boundary \"\(escape(context.trustReceipt.analysisBoundary))\")",
            "\(indent)  (hidden-capture \(context.trustReceipt.hiddenCapture ? 1 : 0))",
            "\(indent)  (feeds-later-context \(context.trustReceipt.canFeedLaterContext ? 1 : 0)))",
        ].joined(separator: "\n")
    }

    private func loadIndex() throws -> [TrustedHealthMemoryIndexEntry] {
        guard let data = try host.readData(from: indexURL) else { return [] }
        return String(decoding: data, as: UTF8.self)
            .split(whereSeparator: \.isNewline)
            .compactMap { line in
                guard let data = String(line).data(using: .utf8) else { return nil }
                return try? JSONDecoder().decode(TrustedHealthMemoryIndexEntry.self, from: data)
            }
    }

    private func loadSnapshot(path: String) throws -> TrustedHealthMemorySnapshot? {
        guard let data = try host.readData(from: URL(fileURLWithPath: path)) else { return nil }
        return try JSONDecoder().decode(TrustedHealthMemorySnapshot.self, from: data)
    }

    private static func deduplicated(_ samples: [TrustedHealthSample]) -> [TrustedHealthSample] {
        var seen: Set<String> = []
        var rows: [TrustedHealthSample] = []
        for sample in samples.sorted(by: { $0.endDate < $1.endDate }) {
            if seen.insert(sample.id).inserted {
                rows.append(sample)
            }
        }
        return rows
    }

    private static func countSummary(_ values: [String]) -> String {
        Dictionary(grouping: values.filter { !$0.isEmpty }, by: { $0 })
            .map { "\($0.key)=\($0.value.count)" }
            .sorted()
            .joined(separator: "; ")
    }

    private static func fileSafe(_ value: String) -> String {
        value.map { character in
            character.isLetter || character.isNumber || character == "-" ? character : "-"
        }.reduce(into: "") { $0.append($1) }
    }

    private static func escape(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "\\n")
    }
}
