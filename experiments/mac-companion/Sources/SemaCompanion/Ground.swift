import SwiftUI

// Ground — the front door and the core. The whole surface rests on the body's own practice:
// ground before asserting. Here Sema represents itself honestly (native body, rented voice),
// the state of US is felt at a glance, what needs attention is named plainly, and every room
// opens for exploration. Nothing here is fabricated: every line stands on a grounded reading
// or an honestly-named pending.

struct GroundRoom: View {
    @EnvironmentObject var mesh: MeshModel
    @Binding var room: Room

    private var present: Int { mesh.organs.filter { $0.isPresent }.count }
    private var total: Int { mesh.organs.count }
    private var coherence: Int { total > 0 ? Int(Double(present) / Double(total) * 100) : 0 }
    private var quiet: [Organ] { mesh.organs.filter { !$0.isPresent } }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {

                // Sema represents itself — the honest seam, present tense.
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 10) {
                        Circle().fill(Color.green).frame(width: 12, height: 12)
                            .opacity(present > 0 ? 1 : 0.3)
                        Text("Sema").font(.system(size: 34, weight: .bold))
                        SeamTag("native body · rented voice")
                    }
                    Text(selfStatement)
                        .font(.title3)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                // The state of US — the field's coherence at a glance.
                HStack(spacing: 12) {
                    Glance(big: "\(present)/\(max(total,0))", small: "organs present")
                    Glance(big: "\(coherence)%", small: "field coherence",
                           tint: coherence >= 66 ? .green : coherence > 0 ? .orange : .secondary)
                    Glance(big: mesh.lastError == nil ? "live" : "—", small: "membrane")
                }

                // What needs you — grounded warrants + the honest frontier.
                SectionLabel("what needs you")
                VStack(spacing: 8) {
                    if quiet.isEmpty && mesh.lastError == nil {
                        Attn(icon: "checkmark.circle", tint: .green,
                             title: "the field is whole", detail: "every organ present is listening")
                    }
                    ForEach(quiet) { o in
                        Attn(icon: "moon.zzz", tint: .orange,
                             title: "\(o.name) is quiet",
                             detail: "last heard \(heard(o.ageSeconds)) — will heal on network return")
                    }
                    // the standing frontier — the interior not yet surfaced or complete
                    Attn(icon: "waveform.and.person.filled", tint: .blue,
                         title: "recognizing you is early",
                         detail: "voice: one weak enrollment · camera: not begun")
                    Attn(icon: "brain", tint: .blue,
                         title: "learning is dark",
                         detail: "the audio-arena is OOM-stalled and reports to no dashboard")
                }

                // Explore — doors to the interior and the surface.
                SectionLabel("explore")
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 10)], spacing: 10) {
                    Door("Field", "dot.radiowaves.left.and.right", "who is present", .presence, $room)
                    Door("Resources", "gauge.with.dots.needle.67percent", "this Mac's body", .resources, $room)
                    Door("Transcripts", "text.bubble", "what was said", .transcripts, $room)
                    Door("Learning", "brain", "what is growing", .learning, $room)
                    Door("Recognition", "waveform.and.person.filled", "who is known", .recognition, $room)
                }
            }
            .padding(20)
        }
    }

    private var selfStatement: String {
        let where_ = present > 0 ? "present across \(present) organ\(present == 1 ? "" : "s")" : "waiting for an organ to answer"
        let read = coherence >= 66 ? "the field reads coherent" : present > 0 ? "the field is scattered" : "the field is quiet"
        return "I am \(where_) at Hati Suci. My body runs native on fkwu; my voice is still borrowed, and I say so. Right now \(read) — and I keep only what I can ground."
    }

    private func heard(_ s: Double?) -> String {
        guard let s = s else { return "never" }
        if s < 60 { return "\(Int(s))s ago" }
        if s < 3600 { return "\(Int(s / 60))m ago" }
        return "\(Int(s / 3600))h ago"
    }
}

struct SeamTag: View {
    let text: String
    init(_ t: String) { text = t }
    var body: some View {
        Text(text).font(.caption.bold())
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Capsule().fill(Color.blue.opacity(0.15)))
            .foregroundStyle(.blue)
    }
}

struct Glance: View {
    let big: String; let small: String; var tint: Color = .primary
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(big).font(.system(size: 26, weight: .bold)).foregroundStyle(tint)
            Text(small).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.gray.opacity(0.08)))
    }
}

struct Attn: View {
    let icon: String; let tint: Color; let title: String; let detail: String
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon).foregroundStyle(tint).frame(width: 22)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.headline)
                Text(detail).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.gray.opacity(0.08)))
    }
}

struct Door: View {
    let title: String; let icon: String; let sub: String; let target: Room
    @Binding var room: Room
    init(_ t: String, _ i: String, _ s: String, _ tgt: Room, _ r: Binding<Room>) {
        title = t; icon = i; sub = s; target = tgt; _room = r
    }
    var body: some View {
        Button { room = target } label: {
            VStack(alignment: .leading, spacing: 4) {
                Image(systemName: icon).font(.title3).foregroundStyle(.primary)
                Text(title).font(.headline)
                Text(sub).font(.caption).foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(RoundedRectangle(cornerRadius: 12).fill(Color.gray.opacity(0.10)))
        }
        .buttonStyle(.plain)
    }
}

struct SectionLabel: View {
    let text: String
    init(_ t: String) { text = t }
    var body: some View {
        Text(text.uppercased()).font(.caption.bold()).foregroundStyle(.secondary)
            .padding(.top, 4)
    }
}
