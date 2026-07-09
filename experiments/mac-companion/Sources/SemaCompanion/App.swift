import SwiftUI

// Sema Companion — the native macOS window into US. A local, present dashboard: the mesh's
// organs with their heartbeats, and this Mac's own body read natively. The web observatory
// may run underneath; this is the native surface Urs asked for. Rooms grow from here
// (transcripts, learning, speaker/object recognition are the next honest rooms).

@main
struct SemaCompanionApp: App {
    @StateObject private var mesh = MeshModel()
    @StateObject private var res = ResourceModel()

    var body: some Scene {
        WindowGroup("Sema — local companion") {
            RootView()
                .environmentObject(mesh)
                .environmentObject(res)
                .frame(minWidth: 760, minHeight: 520)
                .onAppear { mesh.start(); res.start() }
        }
        .windowStyle(.hiddenTitleBar)
    }
}

enum Room: String, CaseIterable, Identifiable {
    case ground = "Ground"
    case presence = "Field"
    case resources = "Resources"
    case transcripts = "Transcripts"
    case learning = "Learning"
    case recognition = "Recognition"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .ground: return "circle.hexagongrid.fill"
        case .presence: return "dot.radiowaves.left.and.right"
        case .resources: return "gauge.with.dots.needle.67percent"
        case .transcripts: return "text.bubble"
        case .learning: return "brain"
        case .recognition: return "waveform.and.person.filled"
        }
    }
    var live: Bool { self == .ground || self == .presence || self == .resources || self == .transcripts }
}

struct RootView: View {
    @State private var room: Room = .ground
    var body: some View {
        NavigationSplitView {
            List(Room.allCases, selection: $room) { r in
                Label(r.rawValue, systemImage: r.icon)
                    .foregroundStyle(r.live ? .primary : .secondary)
                    .tag(r)
            }
            .navigationSplitViewColumnWidth(190)
        } detail: {
            switch room {
            case .ground: GroundRoom(room: $room)
            case .presence: PresenceRoom()
            case .resources: ResourcesRoom()
            case .transcripts: TranscriptsRoom()
            default: PendingRoom(room: room)
            }
        }
    }
}

struct PresenceRoom: View {
    @EnvironmentObject var mesh: MeshModel
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HeaderBar(title: "Presence",
                      subtitle: "\(mesh.organs.filter { $0.isPresent }.count) of \(mesh.organs.count) organs listening")
            if let e = mesh.lastError, mesh.organs.isEmpty {
                Text("mesh unreachable — \(e)").foregroundStyle(.secondary).padding()
            }
            ScrollView {
                VStack(spacing: 8) {
                    ForEach(mesh.organs) { organ in OrganRow(organ: organ) }
                }.padding(14)
            }
        }
    }
}

struct OrganRow: View {
    let organ: Organ
    var body: some View {
        HStack(spacing: 12) {
            Circle().fill(organ.isPresent ? Color.green : Color.gray.opacity(0.4))
                .frame(width: 10, height: 10)
            VStack(alignment: .leading, spacing: 2) {
                Text(organ.name).font(.headline)
                Text("\(organ.organ_kind ?? "organ") · \(organ.discovery_state ?? "—")")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(organ.isPresent ? "listening" : "quiet")
                    .font(.caption.bold())
                    .foregroundStyle(organ.isPresent ? .green : .secondary)
                Text(heard(organ.ageSeconds)).font(.caption2).foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.gray.opacity(0.08)))
    }
    private func heard(_ s: Double?) -> String {
        guard let s = s else { return "never" }
        if s < 60 { return "\(Int(s))s ago" }
        if s < 3600 { return "\(Int(s / 60))m ago" }
        return "\(Int(s / 3600))h ago"
    }
}

struct ResourcesRoom: View {
    @EnvironmentObject var res: ResourceModel
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HeaderBar(title: "Resources", subtitle: "this Mac's body, read natively")
            ScrollView {
                VStack(spacing: 10) {
                    Meter(label: "CPU", value: res.cpuPercent, unit: "%")
                    Meter(label: "Memory", value: res.ramPercent, unit: "%",
                          detail: String(format: "%.1f / %.1f GB", res.ramUsedGB, res.ramTotalGB))
                    Meter(label: "Disk", value: res.diskPercent, unit: "%")
                    HStack(spacing: 10) {
                        Stat(label: "Net ↓", value: String(format: "%.0f KB/s", res.netRxKBs))
                        Stat(label: "Net ↑", value: String(format: "%.0f KB/s", res.netTxKBs))
                    }
                    Stat(label: "GPU", value: "pending (needs IOKit)").opacity(0.6)
                }.padding(14)
            }
        }
    }
}

struct Meter: View {
    let label: String; let value: Double; var unit: String = ""; var detail: String? = nil
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label).font(.headline)
                Spacer()
                Text(detail ?? String(format: "%.0f%@", value, unit)).font(.subheadline.monospaced())
            }
            ProgressView(value: min(1, max(0, value / 100)))
                .tint(value > 85 ? .red : value > 60 ? .orange : .green)
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.gray.opacity(0.08)))
    }
}

struct Stat: View {
    let label: String; let value: String
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.title3.monospaced())
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.gray.opacity(0.08)))
    }
}

struct PendingRoom: View {
    let room: Room
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HeaderBar(title: room.rawValue, subtitle: "room framed, data lane pending")
            Spacer()
            VStack(spacing: 8) {
                Image(systemName: room.icon).font(.system(size: 40)).foregroundStyle(.secondary)
                Text("This room is named, not yet fed — the honest floor.")
                    .foregroundStyle(.secondary)
                Text(hint).font(.caption).foregroundStyle(.tertiary)
            }.frame(maxWidth: .infinity)
            Spacer()
        }
    }
    private var hint: String {
        switch room {
        case .transcripts: return "next: satsang-mesh-sync transcripts + live room capture"
        case .learning: return "next: /api/models/learning-dashboard"
        case .recognition: return "next: speaker enrollment (resemblyzer) + object recognition"
        default: return ""
        }
    }
}

struct HeaderBar: View {
    let title: String; let subtitle: String
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.title2.bold())
            Text(subtitle).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(.ultraThinMaterial)
    }
}
