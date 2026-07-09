import SwiftUI
import AVFoundation

// stable tool paths in this environment
private let speakerPy = NSHomeDirectory() + "/.coherence-network/satsang-venv/bin/python"
private let speakerScript = NSHomeDirectory() + "/source/Coherence-Network/experiments/satsang-voice/speaker_profiles.py"

// nonisolated so it can run off the main actor (assignment) as well as on it (refresh)
func runSpeakerTool(_ args: [String]) -> Data {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: speakerPy)
    p.arguments = [speakerScript] + args
    let out = Pipe(); p.standardOutput = out; p.standardError = Pipe()
    do { try p.run() } catch { return Data() }
    let d = out.fileHandleForReading.readDataToEndOfFile()
    p.waitUntilExit()
    return d
}

// Speakers — the face of the voice book. Known people (a name over a centroid of real
// voiceprints) and the UNASSIGNED pool: voices the body heard but could not yet name. You
// HEAR a pooled sample (play its clip) and assign it a person; that folds into the profile and
// sharpens it. The continuous organ keeps adding matched samples on its own — this room is for
// the ones it wasn't sure about, and for naming someone the first time.

struct SpeakerProfile: Identifiable, Decodable {
    let person: String
    let n: Int
    let updated_at: String
    var id: String { person }
}
struct PooledSample: Identifiable, Decodable {
    let id: String
    let wav: String
    let source: String?
    let ts: String?
    let nearest_score: Double?
}

@MainActor
final class SpeakerModel: ObservableObject {
    @Published var profiles: [SpeakerProfile] = []
    @Published var pooled: [PooledSample] = []
    @Published var busy = false
    private var player: AVAudioPlayer?

    func start() { Task { while !Task.isCancelled { refresh(); try? await Task.sleep(nanoseconds: 6_000_000_000) } } }

    struct Book: Decodable { let profiles: [SpeakerProfile] }

    func refresh() {
        if let book = try? JSONDecoder().decode(Book.self, from: runSpeakerTool(["json"])) {
            profiles = book.profiles.sorted { $0.n > $1.n }
        }
        pooled = (try? JSONDecoder().decode([PooledSample].self, from: runSpeakerTool(["unassigned"]))) ?? []
    }

    func play(_ sample: PooledSample) {
        let url = URL(fileURLWithPath: sample.wav)
        guard FileManager.default.fileExists(atPath: sample.wav) else { return }
        player = try? AVAudioPlayer(contentsOf: url)
        player?.play()
    }

    func assign(_ sample: PooledSample, to person: String) {
        let name = person.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        busy = true
        Task.detached {
            _ = runSpeakerTool(["assign", sample.id, name])
            await MainActor.run { self.busy = false; self.refresh() }
        }
    }
}

struct SpeakersRoom: View {
    @StateObject private var model = SpeakerModel()
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HeaderBar(title: "Speakers",
                      subtitle: "\(model.profiles.count) known · \(model.pooled.count) to assign")
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if !model.profiles.isEmpty {
                        SectionLabel("known voices")
                        VStack(spacing: 6) {
                            ForEach(model.profiles) { ProfileRow(p: $0) }
                        }
                    }
                    SectionLabel("unassigned — hear and name")
                    if model.pooled.isEmpty {
                        Text("Nothing waiting. Voices the organ recognizes fold in on their own;\nonly the uncertain ones land here.")
                            .font(.caption).foregroundStyle(.secondary)
                    } else {
                        VStack(spacing: 8) {
                            ForEach(model.pooled) { s in
                                PooledRow(sample: s, known: model.profiles.map { $0.person },
                                          onPlay: { model.play(s) },
                                          onAssign: { model.assign(s, to: $0) })
                            }
                        }
                    }
                }.padding(14)
            }
        }
        .onAppear { model.start() }
    }
}

struct ProfileRow: View {
    let p: SpeakerProfile
    var body: some View {
        HStack {
            Image(systemName: "person.wave.2.fill").foregroundStyle(.blue)
            Text(p.person).font(.headline)
            Spacer()
            Text("\(p.n) samples").font(.caption.monospaced()).foregroundStyle(.secondary)
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.gray.opacity(0.07)))
    }
}

struct PooledRow: View {
    let sample: PooledSample
    let known: [String]
    let onPlay: () -> Void
    let onAssign: (String) -> Void
    @State private var name = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Button(action: onPlay) { Image(systemName: "play.circle.fill").font(.title2) }
                    .buttonStyle(.plain).foregroundStyle(.green)
                VStack(alignment: .leading, spacing: 1) {
                    Text(sample.source ?? "room").font(.caption)
                    if let s = sample.nearest_score {
                        Text("nearest match \(String(format: "%.2f", s))").font(.caption2).foregroundStyle(.tertiary)
                    }
                }
                Spacer()
                Text(sample.id.prefix(8)).font(.caption2.monospaced()).foregroundStyle(.tertiary)
            }
            HStack(spacing: 6) {
                TextField("name this voice…", text: $name)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { onAssign(name); name = "" }
                Button("Assign") { onAssign(name); name = "" }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            if !known.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(known, id: \.self) { person in
                            Button(person) { onAssign(person) }
                                .buttonStyle(.plain)
                                .font(.caption2)
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(Capsule().fill(Color.blue.opacity(0.14)))
                                .foregroundStyle(.blue)
                        }
                    }
                }
            }
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.gray.opacity(0.06)))
    }
}
