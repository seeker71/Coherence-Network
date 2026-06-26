import Foundation

public struct TrustedRoomMemoryTrustReceipt: Codable, Equatable, Sendable {
    public var kind: String
    public var captureBoundary: String
    public var storageCarrier: String
    public var retrievalScope: String
    public var voiceMatchCarrier: String
    public var hiddenCapture: Bool
    public var canFeedLaterContext: Bool

    public init(
        captureBoundary: String = "explicit-send",
        storageCarrier: String = "local-json-file",
        retrievalScope: String = "same-holder-local-room-memory",
        voiceMatchCarrier: String = "transcript-voice-id-or-speaker-label",
        hiddenCapture: Bool = false,
        canFeedLaterContext: Bool = true
    ) {
        self.kind = "trusted-room-memory-trust-receipt"
        self.captureBoundary = captureBoundary
        self.storageCarrier = storageCarrier
        self.retrievalScope = retrievalScope
        self.voiceMatchCarrier = voiceMatchCarrier
        self.hiddenCapture = hiddenCapture
        self.canFeedLaterContext = canFeedLaterContext
    }
}

public struct TrustedRoomSpeakerProfile: Codable, Equatable, Identifiable, Sendable {
    public var id: String
    public var stableKey: String
    public var displayName: String
    public var sourceLabels: [String]
    public var voiceIDs: [String]
    public var utteranceCount: Int
    public var firstSeenAt: String
    public var lastSeenAt: String

    public var isVoiceObserved: Bool {
        !voiceIDs.isEmpty
    }
}

public struct TrustedRoomMemoryTurn: Codable, Equatable, Sendable {
    public var utteranceID: String
    public var timestamp: String
    public var speakerID: String
    public var speaker: String
    public var voiceID: String?
    public var text: String
    public var source: String
    public var confidence: Double?
    public var wasEdited: Bool
}

public struct TrustedRoomMemorySessionRecord: Codable, Equatable, Identifiable, Sendable {
    public var kind: String
    public var id: String
    public var title: String
    public var createdAt: String
    public var updatedAt: String
    public var targetPresence: String
    public var turnMode: String
    public var utteranceCount: Int
    public var speakerIDs: [String]
    public var turns: [TrustedRoomMemoryTurn]
    public var trustReceipt: TrustedRoomMemoryTrustReceipt

    public init(
        id: String,
        title: String,
        createdAt: String,
        updatedAt: String,
        targetPresence: String,
        turnMode: String,
        turns: [TrustedRoomMemoryTurn],
        trustReceipt: TrustedRoomMemoryTrustReceipt
    ) {
        self.kind = "trusted-room-memory-session"
        self.id = id
        self.title = title
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.targetPresence = targetPresence
        self.turnMode = turnMode
        self.utteranceCount = turns.count
        self.speakerIDs = Array(Set(turns.map(\.speakerID))).sorted()
        self.turns = turns
        self.trustReceipt = trustReceipt
    }
}

public struct TrustedRoomMemoryIndexEntry: Codable, Equatable, Sendable {
    public var sessionID: String
    public var title: String
    public var createdAt: String
    public var updatedAt: String
    public var utteranceCount: Int
    public var speakerIDs: [String]
    public var sessionPath: String
}

public struct TrustedRoomMemoryContext: Codable, Equatable, Sendable {
    public var kind: String
    public var priorSessionCount: Int
    public var priorTurnCount: Int
    public var speakerCount: Int
    public var speakerSummary: String
    public var recentExchangeSummary: String
    public var trustReceipt: TrustedRoomMemoryTrustReceipt

    public init(
        priorSessionCount: Int,
        priorTurnCount: Int,
        speakerCount: Int,
        speakerSummary: String,
        recentExchangeSummary: String,
        trustReceipt: TrustedRoomMemoryTrustReceipt = TrustedRoomMemoryTrustReceipt()
    ) {
        self.kind = "trusted-room-memory-context"
        self.priorSessionCount = priorSessionCount
        self.priorTurnCount = priorTurnCount
        self.speakerCount = speakerCount
        self.speakerSummary = speakerSummary
        self.recentExchangeSummary = recentExchangeSummary
        self.trustReceipt = trustReceipt
    }

    public static func empty() -> TrustedRoomMemoryContext {
        TrustedRoomMemoryContext(
            priorSessionCount: 0,
            priorTurnCount: 0,
            speakerCount: 0,
            speakerSummary: "no prior speakers",
            recentExchangeSummary: "no prior sessions"
        )
    }

    public var summaryLine: String {
        "Trusted memory: \(priorSessionCount) prior sessions, \(speakerCount) speaker profiles"
    }
}

public struct TrustedRoomMemoryRecordResult: Codable, Equatable, Sendable {
    public var sessionURL: URL
    public var indexURL: URL
    public var speakersURL: URL
    public var contextJSONURL: URL
    public var contextFormURL: URL
    public var speakerCount: Int

    public var summary: String {
        "stored session, \(speakerCount) speaker profiles"
    }
}

public final class TrustedRoomMemoryStore: @unchecked Sendable {
    public var rootURL: URL
    public var host: any HostResourceInterface

    private var sessionsURL: URL { rootURL.appendingPathComponent("sessions") }
    private var indexURL: URL { rootURL.appendingPathComponent("session-index.jsonl") }
    private var speakersURL: URL { rootURL.appendingPathComponent("speaker-profiles.json") }
    private var latestContextJSONURL: URL { rootURL.appendingPathComponent("latest-context.json") }
    private var latestContextFormURL: URL { rootURL.appendingPathComponent("latest-context.form") }

    public init(rootURL: URL, host: any HostResourceInterface = FoundationHostResourceInterface()) {
        self.rootURL = rootURL
        self.host = host
    }

    public func utterancesWithSpeakerProfiles(_ utterances: [TranscriptUtterance]) -> [TranscriptUtterance] {
        utterances.map { utterance in
            var row = utterance
            row.speakerProfileID = row.speakerProfileID ?? Self.speakerProfileID(for: row)
            return row
        }
    }

    public func context(maxSessions: Int = 3, maxTurns: Int = 8) throws -> TrustedRoomMemoryContext {
        let entries = try loadIndex()
        let selectedEntries = Array(entries.suffix(maxSessions))
        let sessions = try selectedEntries.compactMap { try loadSession(path: $0.sessionPath) }
        let turns = Array(sessions.flatMap(\.turns).suffix(maxTurns))
        let speakers = try loadSpeakers()
        let speakerSummary = speakers
            .sorted { $0.lastSeenAt > $1.lastSeenAt }
            .prefix(8)
            .map { "\($0.displayName)[\($0.id)] turns=\($0.utteranceCount)" }
            .joined(separator: "; ")
        let exchangeSummary = turns
            .map { "\($0.speaker): \(Self.compact($0.text, limit: 120))" }
            .joined(separator: " | ")

        return TrustedRoomMemoryContext(
            priorSessionCount: sessions.count,
            priorTurnCount: turns.count,
            speakerCount: speakers.count,
            speakerSummary: speakerSummary.isEmpty ? "no prior speakers" : speakerSummary,
            recentExchangeSummary: exchangeSummary.isEmpty ? "no prior sessions" : exchangeSummary
        )
    }

    @discardableResult
    public func record(_ request: GuidanceRequest) throws -> TrustedRoomMemoryRecordResult {
        try host.createDirectory(at: sessionsURL)
        let profiled = utterancesWithSpeakerProfiles(request.utterances)
        let now = ISO8601DateFormatter().string(from: Date())
        let receipt = TrustedRoomMemoryTrustReceipt(
            voiceMatchCarrier: profiled.contains { ($0.voiceID ?? "").isEmpty == false }
                ? "transcript-voice-id-or-speaker-label"
                : "channel-label-only"
        )
        var speakers = try loadSpeakers()
        let turns = profiled.map { utterance in
            let speakerID = utterance.speakerProfileID ?? Self.speakerProfileID(for: utterance)
            upsertSpeaker(
                id: speakerID,
                stableKey: Self.speakerStableKey(for: utterance),
                utterance: utterance,
                seenAt: utterance.timestamp.isEmpty ? now : utterance.timestamp,
                speakers: &speakers
            )
            return TrustedRoomMemoryTurn(
                utteranceID: utterance.id,
                timestamp: utterance.timestamp,
                speakerID: speakerID,
                speaker: utterance.speaker,
                voiceID: utterance.voiceID,
                text: utterance.text,
                source: utterance.source,
                confidence: utterance.confidence,
                wasEdited: utterance.wasEdited
            )
        }
        let record = TrustedRoomMemorySessionRecord(
            id: request.id,
            title: request.sessionTitle,
            createdAt: request.createdAt,
            updatedAt: now,
            targetPresence: request.targetPresence,
            turnMode: request.turnMode,
            turns: turns,
            trustReceipt: receipt
        )
        let sessionURL = sessionsURL.appendingPathComponent("\(Self.fileSafe(request.id)).json")
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try host.writeData(try encoder.encode(record), to: sessionURL, options: .atomic)

        let indexEntry = TrustedRoomMemoryIndexEntry(
            sessionID: record.id,
            title: record.title,
            createdAt: record.createdAt,
            updatedAt: record.updatedAt,
            utteranceCount: record.utteranceCount,
            speakerIDs: record.speakerIDs,
            sessionPath: sessionURL.path
        )
        let lineEncoder = JSONEncoder()
        lineEncoder.outputFormatting = [.sortedKeys]
        try host.appendLine(try lineEncoder.encode(indexEntry), to: indexURL)
        try host.writeData(try encoder.encode(speakers.sorted { $0.id < $1.id }), to: speakersURL, options: .atomic)

        let latestContext = try context()
        try host.writeData(try encoder.encode(latestContext), to: latestContextJSONURL, options: .atomic)
        try host.writeData(Data(Self.formEnvelope(latestContext).utf8), to: latestContextFormURL, options: .atomic)

        return TrustedRoomMemoryRecordResult(
            sessionURL: sessionURL,
            indexURL: indexURL,
            speakersURL: speakersURL,
            contextJSONURL: latestContextJSONURL,
            contextFormURL: latestContextFormURL,
            speakerCount: speakers.count
        )
    }

    public static func speakerProfileID(for utterance: TranscriptUtterance) -> String {
        "speaker-\(stableHash(speakerStableKey(for: utterance)))"
    }

    public static func speakerStableKey(for utterance: TranscriptUtterance) -> String {
        let key = utterance.voiceID?.trimmingCharacters(in: .whitespacesAndNewlines)
        if let key, !key.isEmpty {
            return "voice-id:\(key.lowercased())"
        }
        return "speaker-label:\(utterance.speaker.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())"
    }

    public static func formEnvelope(_ context: TrustedRoomMemoryContext, indent: String = "") -> String {
        [
            "\(indent)(trusted-room-memory-context",
            "\(indent)  (prior-session-count \(context.priorSessionCount))",
            "\(indent)  (prior-turn-count \(context.priorTurnCount))",
            "\(indent)  (speaker-count \(context.speakerCount))",
            "\(indent)  (speaker-summary \"\(escape(context.speakerSummary))\")",
            "\(indent)  (recent-exchange-summary \"\(escape(context.recentExchangeSummary))\")",
            "\(indent)  (capture-boundary \"\(escape(context.trustReceipt.captureBoundary))\")",
            "\(indent)  (storage-carrier \"\(escape(context.trustReceipt.storageCarrier))\")",
            "\(indent)  (retrieval-scope \"\(escape(context.trustReceipt.retrievalScope))\")",
            "\(indent)  (voice-match-carrier \"\(escape(context.trustReceipt.voiceMatchCarrier))\")",
            "\(indent)  (hidden-capture \(context.trustReceipt.hiddenCapture ? 1 : 0))",
            "\(indent)  (feeds-later-context \(context.trustReceipt.canFeedLaterContext ? 1 : 0)))",
        ].joined(separator: "\n")
    }

    private func loadIndex() throws -> [TrustedRoomMemoryIndexEntry] {
        guard let data = try host.readData(from: indexURL) else { return [] }
        return String(decoding: data, as: UTF8.self)
            .split(whereSeparator: \.isNewline)
            .compactMap { line in
                guard let data = String(line).data(using: .utf8) else { return nil }
                return try? JSONDecoder().decode(TrustedRoomMemoryIndexEntry.self, from: data)
            }
    }

    private func loadSession(path: String) throws -> TrustedRoomMemorySessionRecord? {
        guard let data = try host.readData(from: URL(fileURLWithPath: path)) else { return nil }
        return try JSONDecoder().decode(TrustedRoomMemorySessionRecord.self, from: data)
    }

    private func loadSpeakers() throws -> [TrustedRoomSpeakerProfile] {
        guard let data = try host.readData(from: speakersURL) else { return [] }
        return try JSONDecoder().decode([TrustedRoomSpeakerProfile].self, from: data)
    }

    private func upsertSpeaker(
        id: String,
        stableKey: String,
        utterance: TranscriptUtterance,
        seenAt: String,
        speakers: inout [TrustedRoomSpeakerProfile]
    ) {
        if let index = speakers.firstIndex(where: { $0.id == id }) {
            speakers[index].sourceLabels = Self.appendUnique(utterance.speaker, to: speakers[index].sourceLabels)
            if let voiceID = utterance.voiceID {
                speakers[index].voiceIDs = Self.appendUnique(voiceID, to: speakers[index].voiceIDs)
            }
            speakers[index].utteranceCount += 1
            speakers[index].lastSeenAt = max(speakers[index].lastSeenAt, seenAt)
            return
        }

        let display = utterance.speaker.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "unknown voice"
            : utterance.speaker
        speakers.append(TrustedRoomSpeakerProfile(
            id: id,
            stableKey: stableKey,
            displayName: display,
            sourceLabels: [display],
            voiceIDs: utterance.voiceID.map { [$0] } ?? [],
            utteranceCount: 1,
            firstSeenAt: seenAt,
            lastSeenAt: seenAt
        ))
    }

    private static func appendUnique(_ value: String, to values: [String]) -> [String] {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !values.contains(trimmed) else { return values }
        return values + [trimmed]
    }

    private static func stableHash(_ value: String) -> String {
        var hash: UInt64 = 14_695_981_039_346_656_037
        for byte in value.utf8 {
            hash ^= UInt64(byte)
            hash &*= 1_099_511_628_211
        }
        return String(hash, radix: 16)
    }

    private static func compact(_ value: String, limit: Int) -> String {
        let oneLine = value
            .replacingOccurrences(of: "\n", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if oneLine.count <= limit { return oneLine }
        return String(oneLine.prefix(limit))
    }

    private static func escape(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "\\n")
    }

    private static func fileSafe(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))
        let scalars = value.unicodeScalars.map { allowed.contains($0) ? Character($0) : "-" }
        let safe = String(scalars)
        return safe.isEmpty ? UUID().uuidString : safe
    }
}
