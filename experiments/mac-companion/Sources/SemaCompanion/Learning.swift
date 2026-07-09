import SwiftUI

// Learning — the training board. Every recognition domain the body is learning: how far toward
// the target sample count, the native-vs-oracle PARITY (the local success rate), the state, and
// the live recognized STREAM. Reads the honest feed at ~/.coherence-network/training-status.json
// (written by training-status.sh); pending domains say pending, never faked.

struct TrainingDomain: Identifiable, Decodable {
    let domain: String
    let samples: Int
    let target: Int
    let parity: Double?
    let state: String
    let stream: [String]
    var id: String { domain }
    var progress: Double { target > 0 ? min(1, Double(samples) / Double(target)) : 0 }
}
struct TrainingBoard: Decodable { let domains: [TrainingDomain]; let ts: String? }

@MainActor
final class LearningModel: ObservableObject {
    @Published var domains: [TrainingDomain] = []
    @Published var loadedAt: Date? = nil
    private let url = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".coherence-network/training-status.json")

    func start() { Task { while !Task.isCancelled { load(); try? await Task.sleep(nanoseconds: 5_000_000_000) } } }
    func load() {
        guard let data = try? Data(contentsOf: url),
              let board = try? JSONDecoder().decode(TrainingBoard.self, from: data) else { return }
        domains = board.domains
        loadedAt = Date()
    }
}

struct LearningRoom: View {
    @StateObject private var model = LearningModel()
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HeaderBar(title: "Learning",
                      subtitle: model.domains.isEmpty ? "no training board yet — run training-status.sh"
                                                      : "\(model.domains.filter { $0.samples > 0 }.count) of \(model.domains.count) domains training")
            ScrollView {
                VStack(spacing: 10) {
                    ForEach(model.domains) { d in DomainCard(d: d) }
                }.padding(14)
            }
        }
        .onAppear { model.start() }
    }
}

struct DomainCard: View {
    let d: TrainingDomain
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(d.domain).font(.headline)
                Spacer()
                if let p = d.parity {
                    Text(String(format: "%.0f%% native", p * 100))
                        .font(.subheadline.bold())
                        .foregroundStyle(p >= 0.9 ? .green : p >= 0.5 ? .orange : .secondary)
                } else {
                    Text(d.state).font(.caption).foregroundStyle(.secondary)
                }
            }
            HStack(spacing: 8) {
                ProgressView(value: d.progress).frame(maxWidth: .infinity)
                Text("\(d.samples)/\(d.target)").font(.caption.monospaced()).foregroundStyle(.secondary)
            }
            if d.parity != nil { Text(d.state).font(.caption).foregroundStyle(.secondary) }
            if !d.stream.isEmpty {
                Text("recognizing").font(.caption2).foregroundStyle(.tertiary)
                FlowChips(items: Array(d.stream.prefix(12)))
            }
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.gray.opacity(0.08)))
    }
}

struct FlowChips: View {
    let items: [String]
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 70), spacing: 6)], alignment: .leading, spacing: 6) {
            ForEach(items, id: \.self) { s in
                Text(s).font(.caption2)
                    .padding(.horizontal, 7).padding(.vertical, 3)
                    .background(Capsule().fill(Color.blue.opacity(0.14)))
                    .foregroundStyle(.blue)
            }
        }
    }
}
