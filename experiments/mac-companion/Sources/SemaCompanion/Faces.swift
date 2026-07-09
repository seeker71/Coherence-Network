import SwiftUI
import AppKit

// Faces — the seeing twin of Speakers. Known people (a name over a centroid of face feature-prints)
// and the pool of faces the body saw but could not yet name. You SEE a pooled face (its frame) and
// assign a person; it folds into the profile and sharpens it. The face-distill organ auto-folds
// confident matches on its own — this room is for the uncertain ones and the first naming.

struct FaceProfile: Identifiable, Decodable {
    let person: String; let n: Int; let updated_at: String
    var id: String { person }
}
struct PooledFace: Identifiable, Decodable {
    let id: String
    let frame: String?
    let nearest_score: Double?
    let ts: String?
}

private let facePy = NSHomeDirectory() + "/.coherence-network/satsang-venv/bin/python"
private let faceScript = NSHomeDirectory() + "/source/Coherence-Network/experiments/satsang-voice/face_profiles.py"

func runFaceTool(_ args: [String]) -> Data {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: facePy)
    p.arguments = [faceScript] + args
    let out = Pipe(); p.standardOutput = out; p.standardError = Pipe()
    do { try p.run() } catch { return Data() }
    let d = out.fileHandleForReading.readDataToEndOfFile()
    p.waitUntilExit()
    return d
}

@MainActor
final class FaceModel: ObservableObject {
    @Published var profiles: [FaceProfile] = []
    @Published var pooled: [PooledFace] = []
    struct Book: Decodable { let profiles: [FaceProfile] }

    func start() { Task { while !Task.isCancelled { refresh(); try? await Task.sleep(nanoseconds: 6_000_000_000) } } }
    func refresh() {
        if let b = try? JSONDecoder().decode(Book.self, from: runFaceTool(["json"])) {
            profiles = b.profiles.sorted { $0.n > $1.n }
        }
        pooled = (try? JSONDecoder().decode([PooledFace].self, from: runFaceTool(["unassigned"]))) ?? []
    }
    func assign(_ face: PooledFace, to person: String) {
        let name = person.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        Task.detached { _ = runFaceTool(["assign", face.id, name]); await MainActor.run { self.refresh() } }
    }
}

struct FacesRoom: View {
    @StateObject private var model = FaceModel()
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HeaderBar(title: "Faces", subtitle: "\(model.profiles.count) known · \(model.pooled.count) to name")
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if !model.profiles.isEmpty {
                        SectionLabel("known people")
                        VStack(spacing: 6) { ForEach(model.profiles) { FaceProfileRow(p: $0) } }
                    }
                    SectionLabel("unassigned — see and name")
                    if model.pooled.isEmpty {
                        Text("No faces waiting. Frames from the Mac and phone cameras flow into the\nrecognition pipeline; a face the organ can't place yet lands here to name.")
                            .font(.caption).foregroundStyle(.secondary)
                    } else {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 10)], spacing: 10) {
                            ForEach(model.pooled) { f in
                                PooledFaceCard(face: f, known: model.profiles.map { $0.person },
                                               onAssign: { model.assign(f, to: $0) })
                            }
                        }
                    }
                }.padding(14)
            }
        }
        .onAppear { model.start() }
    }
}

struct FaceProfileRow: View {
    let p: FaceProfile
    var body: some View {
        HStack {
            Image(systemName: "person.crop.square.fill").foregroundStyle(.purple)
            Text(p.person).font(.headline)
            Spacer()
            Text("\(p.n) faces").font(.caption.monospaced()).foregroundStyle(.secondary)
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.gray.opacity(0.07)))
    }
}

struct PooledFaceCard: View {
    let face: PooledFace
    let known: [String]
    let onAssign: (String) -> Void
    @State private var name = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            FaceThumb(path: face.frame, box: nil)
                .frame(height: 110).frame(maxWidth: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            HStack(spacing: 4) {
                TextField("name…", text: $name)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { onAssign(name); name = "" }
                Button("Set") { onAssign(name); name = "" }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            if !known.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 4) {
                        ForEach(known, id: \.self) { person in
                            Button(person) { onAssign(person) }
                                .buttonStyle(.plain).font(.caption2)
                                .padding(.horizontal, 6).padding(.vertical, 2)
                                .background(Capsule().fill(Color.purple.opacity(0.14)))
                                .foregroundStyle(.purple)
                        }
                    }
                }
            }
        }
        .padding(8)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.gray.opacity(0.06)))
    }
}

struct FaceThumb: View {
    let path: String?
    let box: [Double]?
    var body: some View {
        if let path = path, let img = NSImage(contentsOfFile: path) {
            Image(nsImage: img).resizable().aspectRatio(contentMode: .fill)
        } else {
            ZStack { Rectangle().fill(Color.gray.opacity(0.2))
                     Image(systemName: "photo").foregroundStyle(.secondary) }
        }
    }
}
