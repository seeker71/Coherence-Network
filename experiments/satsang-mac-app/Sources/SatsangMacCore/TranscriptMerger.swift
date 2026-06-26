import Foundation

public enum TranscriptMerger {
    public static func merge(
        loaded: [TranscriptUtterance],
        current: [TranscriptUtterance]
    ) -> [TranscriptUtterance] {
        let currentByID = current.reduce(into: [TranscriptUtterance.ID: TranscriptUtterance]()) { out, row in
            out[row.id] = row
        }
        let loadedIDs = Set(loaded.map(\.id))

        var merged = loaded.map { next in
            var row = next
            if let current = currentByID[next.id], current.wasEdited {
                row.text = current.text
            }
            return row
        }

        let localRows = current.filter { row in
            !loadedIDs.contains(row.id) && isLocalSessionRow(row)
        }
        merged.append(contentsOf: localRows)
        return merged
    }

    public static func isLocalSessionRow(_ row: TranscriptUtterance) -> Bool {
        row.source == "manual"
            || row.source == "live-mic"
            || row.source == "live-mic-partial"
    }
}
