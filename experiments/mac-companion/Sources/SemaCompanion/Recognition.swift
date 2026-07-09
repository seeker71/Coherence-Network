import SwiftUI

// Recognition — the live stream of what the body is actually recognizing right now. Not the
// board's per-domain summary (that's Learning) but the moving feed: each recent frame the
// oracle+native named, with its top label and confidence, newest first. Reads the same honest
// store the trainer writes (vision-training/samples.jsonl) plus known voiceprints. Empty is
// empty — a quiet field says quiet.

struct Recognition: Identifiable {
    let id: String
    let label: String
    let confidence: Double
    let oracle: String
    let kind: String   // "sight" | "voice"
}

@MainActor
final class RecognitionModel: ObservableObject {
    @Published var stream: [Recognition] = []
    @Published var voices: [String] = []
    private let visionStore = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".coherence-network/vision-training/samples.jsonl")
    private let speakers = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".coherence-network/hati/mac-speakers.json")

    func start() { Task { while !Task.isCancelled { load(); try? await Task.sleep(nanoseconds: 4_000_000_000) } } }

    func load() {
        var out: [Recognition] = []
        if let text = try? String(contentsOf: visionStore, encoding: .utf8) {
            for line in text.split(separator: "\n").suffix(60).reversed() {
                guard let d = line.data(using: .utf8),
                      let obj = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                      let id = obj["id"] as? String,
                      let labels = obj["labels"] as? [[String: Any]] else { continue }
                let top = labels.max { ($0["confidence"] as? Double ?? 0) < ($1["confidence"] as? Double ?? 0) }
                let label = top?["label"] as? String ?? "—"
                let conf = top?["confidence"] as? Double ?? 0
                out.append(Recognition(id: id, label: label, confidence: conf,
                                       oracle: obj["oracle"] as? String ?? "oracle", kind: "sight"))
            }
        }
        stream = out
        if let d = try? Data(contentsOf: speakers),
           let arr = try? JSONSerialization.jsonObject(with: d) as? [[Any]] {
            voices = arr.compactMap { $0.first as? String }
        }
    }
}

struct RecognitionRoom: View {
    @StateObject private var model = RecognitionModel()
    @EnvironmentObject var camera: CameraModel
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HeaderBar(title: "Recognition",
                      subtitle: model.stream.isEmpty && model.voices.isEmpty
                        ? "quiet — nothing recognized yet"
                        : "\(model.stream.count) recent sights · \(model.voices.count) known voices")
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    CameraBanner(camera: camera)
                    if !model.voices.isEmpty {
                        SectionLabel("known voices")
                        FlowChips(items: model.voices)
                    }
                    if !model.stream.isEmpty {
                        SectionLabel("sight stream (newest first)")
                        VStack(spacing: 6) {
                            ForEach(model.stream) { r in RecognitionRow(r: r) }
                        }
                    }
                    if model.stream.isEmpty && model.voices.isEmpty {
                        Text("No camera or voice recognitions on the store yet. When the cameras\nsend frames and voices enroll, they appear here live.")
                            .font(.caption).foregroundStyle(.secondary).padding(.top, 20)
                    }
                }.padding(14)
            }
        }
        .onAppear { model.start() }
    }
}

struct RecognitionRow: View {
    let r: Recognition
    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: r.kind == "voice" ? "waveform" : "eye")
                .foregroundStyle(.secondary).frame(width: 18)
            Text(r.label).font(.body)
            Spacer()
            Text(String(format: "%.0f%%", r.confidence * 100))
                .font(.caption.monospaced())
                .foregroundStyle(r.confidence >= 0.6 ? .green : r.confidence >= 0.3 ? .orange : .secondary)
            Text(r.oracle).font(.caption2).foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.gray.opacity(0.06)))
    }
}

struct CameraBanner: View {
    @ObservedObject var camera: CameraModel
    var body: some View {
        HStack(spacing: 10) {
            Circle().fill(camera.running ? Color.red : Color.gray.opacity(0.4)).frame(width: 9, height: 9)
            VStack(alignment: .leading, spacing: 1) {
                Text(camera.running ? "camera live" : "camera resting").font(.subheadline.bold())
                Text(camera.status).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Button(camera.running ? "Rest" : "Wake") { camera.running ? camera.stop() : camera.start() }
                .font(.caption)
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.gray.opacity(0.07)))
    }
}
