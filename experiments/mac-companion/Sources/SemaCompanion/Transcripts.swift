import SwiftUI
import AppKit

// Transcripts — the recordings and their transcripts made accessible, natively. Scans the
// private satsang folder, groups each session's audio with every transcript view (readable,
// speakers, diarized, clean, raw, subtitles), opens any of them inline, and reveals/plays the
// source. Translations are shown as an honest pending until NL->NL translation runs.

struct SatsangSession: Identifiable {
    let id: String            // stem, e.g. satsang-20260708-110048
    var recording: URL?       // .m4a
    var bytes: Int64 = 0
    var views: [(label: String, url: URL)] = []   // transcript views
    var date: String {
        // stem: satsang-YYYYMMDD-HHMMSS
        let parts = id.split(separator: "-")
        guard parts.count >= 3 else { return id }
        let d = parts[1], t = parts[2]
        if d.count == 8 && t.count == 6 {
            return "\(d.prefix(4))-\(d.dropFirst(4).prefix(2))-\(d.dropFirst(6)) \(t.prefix(2)):\(t.dropFirst(2).prefix(2))"
        }
        return id
    }
}

@MainActor
final class TranscriptsModel: ObservableObject {
    @Published var sessions: [SatsangSession] = []
    @Published var selected: String? = nil
    @Published var loadedLabel: String = ""
    @Published var loadedText: String = ""

    let root = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Documents/Coherence-private/satsang")

    func scan() {
        var byStem: [String: SatsangSession] = [:]
        let fm = FileManager.default
        let files = (try? fm.contentsOfDirectory(at: root, includingPropertiesForKeys: [.fileSizeKey])) ?? []
        for f in files {
            let name = f.lastPathComponent
            guard name.hasPrefix("satsang-") else { continue }
            // stem = first 3 dash-parts: satsang-DATE-TIME
            let comps = name.split(separator: ".")[0].split(separator: "-")
            guard comps.count >= 3 else { continue }
            let stem = comps.prefix(3).joined(separator: "-")
            var s = byStem[stem] ?? SatsangSession(id: stem)
            if name.hasSuffix(".m4a") {
                s.recording = f
                s.bytes = Int64((try? f.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0)
            } else if let label = viewLabel(name) {
                s.views.append((label, f))
            }
            byStem[stem] = s
        }
        sessions = byStem.values
            .map { var s = $0; s.views.sort { viewOrder($0.label) < viewOrder($1.label) }; return s }
            .sorted { $0.id > $1.id }
        if selected == nil { selected = sessions.first?.id }
    }

    private func viewLabel(_ name: String) -> String? {
        if name.hasSuffix(".readable.txt") { return "readable" }
        if name.hasSuffix(".speakers.txt") { return "speakers" }
        if name.hasSuffix(".diarized.txt") { return "diarized" }
        if name.hasSuffix(".clean.txt") { return "clean" }
        if name.hasSuffix(".raw.txt") { return "raw" }
        if name.hasSuffix(".clean.srt") || name.hasSuffix(".srt") { return "subtitles" }
        return nil
    }
    private func viewOrder(_ l: String) -> Int {
        ["readable", "speakers", "diarized", "clean", "raw", "subtitles"].firstIndex(of: l) ?? 9
    }

    func load(_ url: URL, label: String) {
        loadedLabel = label
        loadedText = (try? String(contentsOf: url, encoding: .utf8)) ?? "(could not read \(url.lastPathComponent))"
    }
    func reveal(_ url: URL) { NSWorkspace.shared.activateFileViewerSelecting([url]) }
    func play(_ url: URL) { NSWorkspace.shared.open(url) }
}

struct TranscriptsRoom: View {
    @StateObject private var model = TranscriptsModel()

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HeaderBar(title: "Transcripts",
                      subtitle: "\(model.sessions.count) session\(model.sessions.count == 1 ? "" : "s") — recordings + every transcript view")
            if model.sessions.isEmpty {
                VStack(spacing: 6) {
                    Image(systemName: "text.bubble").font(.system(size: 36)).foregroundStyle(.secondary)
                    Text("No sessions in ~/Documents/Coherence-private/satsang yet.").foregroundStyle(.secondary)
                    Text("Record on the phone → satsang-mesh-sync pulls and transcribes here.")
                        .font(.caption).foregroundStyle(.tertiary)
                }.frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                HSplitView {
                    // sessions
                    List(model.sessions, selection: $model.selected) { s in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(s.date).font(.headline)
                            Text("\(s.views.count) views · \(byteStr(s.bytes))")
                                .font(.caption).foregroundStyle(.secondary)
                        }.tag(s.id)
                    }.frame(minWidth: 180, maxWidth: 240)

                    // detail
                    if let s = model.sessions.first(where: { $0.id == model.selected }) {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack(spacing: 8) {
                                if let rec = s.recording {
                                    Button { model.play(rec) } label: { Label("Play recording", systemImage: "play.circle") }
                                    Button { model.reveal(rec) } label: { Label("Reveal", systemImage: "folder") }
                                }
                                Spacer()
                            }
                            HStack(spacing: 6) {
                                ForEach(s.views, id: \.label) { v in
                                    Button(v.label) { model.load(v.url, label: v.label) }
                                        .buttonStyle(.bordered)
                                        .tint(model.loadedLabel == v.label ? .blue : .secondary)
                                }
                                // translations — honest pending
                                Text("translations: pending").font(.caption).foregroundStyle(.tertiary)
                            }
                            Divider()
                            if model.loadedText.isEmpty {
                                Text("Pick a transcript view above.").foregroundStyle(.secondary)
                                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                            } else {
                                ScrollView {
                                    Text(model.loadedText)
                                        .font(.system(.body, design: .monospaced))
                                        .textSelection(.enabled)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(8)
                                }
                            }
                        }.padding(12)
                    }
                }
            }
        }
        .onAppear { model.scan() }
    }

    private func byteStr(_ b: Int64) -> String {
        if b > 1_000_000 { return String(format: "%.0f MB", Double(b) / 1_000_000) }
        if b > 1_000 { return String(format: "%.0f KB", Double(b) / 1_000) }
        return "\(b) B"
    }
}
