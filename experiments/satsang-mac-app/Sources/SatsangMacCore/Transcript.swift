import Foundation

public struct TranscriptUtterance: Codable, Equatable, Identifiable, Sendable {
    public var id: String
    public var timestamp: String
    public var speaker: String
    public var detectedText: String
    public var text: String
    public var source: String
    public var confidence: Double?

    public init(
        id: String,
        timestamp: String,
        speaker: String,
        detectedText: String,
        text: String? = nil,
        source: String = "local-transcript",
        confidence: Double? = nil
    ) {
        self.id = id
        self.timestamp = timestamp
        self.speaker = speaker
        self.detectedText = detectedText
        self.text = text ?? detectedText
        self.source = source
        self.confidence = confidence
    }

    public var wasEdited: Bool {
        text.trimmingCharacters(in: .whitespacesAndNewlines) != detectedText.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

public enum TranscriptParser {
    public static func load(
        from url: URL,
        host: any HostResourceInterface = FoundationHostResourceInterface()
    ) throws -> [TranscriptUtterance] {
        guard let data = try host.readData(from: url) else { return [] }
        let text = String(decoding: data, as: UTF8.self)
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.hasPrefix("[") {
            let object = try JSONSerialization.jsonObject(with: data)
            guard let rows = object as? [[String: Any]] else { return [] }
            return rows.enumerated().compactMap { index, row in
                utterance(from: row, fallbackIndex: index, rawLine: nil)
            }
        }

        return text.split(whereSeparator: \.isNewline).enumerated().compactMap { index, line in
            guard let data = String(line).data(using: .utf8),
                  let row = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { return nil }
            return utterance(from: row, fallbackIndex: index, rawLine: String(line))
        }
    }

    public static func utterance(from row: [String: Any], fallbackIndex: Int, rawLine: String?) -> TranscriptUtterance? {
        let detected = firstString(row, keys: ["text", "transcript", "utterance", "content", "original", "translation"])
        guard let detected, !detected.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }

        let timestamp = firstString(row, keys: ["timestamp", "ts", "time", "created_at", "createdAt"])
            ?? firstNumber(row, keys: ["timestamp", "ts", "time"]).map(timestampString)
            ?? ISO8601DateFormatter().string(from: Date())
        let speaker = firstString(row, keys: ["speaker", "speaker_id", "voice", "voice_id", "label", "name"])
            ?? "unknown"
        let source = firstString(row, keys: ["source", "path", "carrier"]) ?? "local-transcript"
        let confidence = firstNumber(row, keys: ["confidence", "conf", "speechiness"])
        let id = firstString(row, keys: ["id", "uuid", "turn_id"])
            ?? stableFallbackID(index: fallbackIndex, timestamp: timestamp, speaker: speaker, text: detected)

        return TranscriptUtterance(
            id: id,
            timestamp: timestamp,
            speaker: speaker,
            detectedText: detected,
            source: source,
            confidence: confidence
        )
    }

    private static func firstString(_ row: [String: Any], keys: [String]) -> String? {
        for key in keys {
            if let value = row[key] as? String, !value.isEmpty { return value }
            if let value = row[key] as? CustomStringConvertible {
                let string = value.description
                if !string.isEmpty { return string }
            }
        }
        return nil
    }

    private static func firstNumber(_ row: [String: Any], keys: [String]) -> Double? {
        for key in keys {
            if let value = row[key] as? Double { return value }
            if let value = row[key] as? Int { return Double(value) }
            if let value = row[key] as? String, let parsed = Double(value) { return parsed }
        }
        return nil
    }

    private static func timestampString(_ value: Double) -> String {
        let seconds = value > 10_000_000_000 ? value / 1000.0 : value
        return ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: seconds))
    }

    private static func stableFallbackID(index: Int, timestamp: String, speaker: String, text: String) -> String {
        let prefix = text.prefix(32).replacingOccurrences(of: "\n", with: " ")
        return "\(index)-\(timestamp)-\(speaker)-\(prefix)"
    }
}
