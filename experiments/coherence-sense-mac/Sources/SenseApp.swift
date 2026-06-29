// SenseApp — the mac sibling of the Android sensing app. A single window, thin carrier
// over the fkwu sensing recipes. Swift captures the camera, runs the gates in fkwu,
// draws the four blocks, and speaks. The body (the (le ..) decisions) is native; this
// SwiftUI surface only displays and voices.
//
// Window blocks:
//   1. SPEAKING TOGGLE   — on => speak summary on a rhythm + immediately on a surprise spike
//   2. WHAT IS BEING SENSED — live presence / brightness / surprise readings
//   3. SURPRISE EVENTS   — scrolling timestamped spike log
//   4. INQUIRY-PLANE PROBES — WHAT · WHEN · WHERE · HOW · WHO · WHY, each a probing path

import SwiftUI
import AppKit

@main
struct SenseApp: App {
    @StateObject private var model = SenseModel()
    var body: some Scene {
        WindowGroup("Coherence Sense") {
            ContentView()
                .environmentObject(model)
                .frame(minWidth: 520, minHeight: 720)
                .onAppear { model.start() }
        }
        .windowResizability(.contentSize)
    }
}

enum Plane: String, CaseIterable, Identifiable {
    case what = "WHAT", when = "WHEN", where_ = "WHERE", how = "HOW", who = "WHO", why = "WHY"
    var id: String { rawValue }
}

struct ContentView: View {
    @EnvironmentObject var model: SenseModel
    @State private var speaking = false
    @State private var selectedPlane: Plane? = nil
    @State private var planeReading: String = ""

    private let voice = Voice()
    // Speak the summary on a steady rhythm while the toggle is on.
    private let rhythm = Timer.publish(every: 12, on: .main, in: .common).autoconnect()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                header

                speakingToggle
                sensedBlock
                surpriseBlock
                planesBlock

                footer
            }
            .padding(28)
        }
        .background(Color(red: 0.043, green: 0.055, blue: 0.078))
        .onReceive(rhythm) { _ in
            if speaking { voice.speak(summarySentence()) }
        }
        .onReceive(NotificationCenter.default.publisher(for: .surpriseSpike)) { note in
            if speaking {
                let mag = (note.object as? Int) ?? model.surprise
                voice.speak("Surprise. Magnitude \(mag).", interrupt: true)
            }
        }
    }

    // MARK: header

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Coherence Sense — mac")
                .font(.system(size: 22, weight: .bold))
                .foregroundColor(Color(red: 0.50, green: 0.71, blue: 1.0))
            Text("a thin carrier over fkwu sensing recipes — the eye on this Mac's metal")
                .font(.system(size: 12))
                .foregroundColor(Color(red: 0.55, green: 0.61, blue: 0.70))
            Text(model.cameraState)
                .font(.system(size: 12, weight: .medium))
                .foregroundColor(Color(red: 0.62, green: 0.70, blue: 0.82))
                .padding(.top, 2)
        }
    }

    // MARK: 1 — speaking toggle

    private var speakingToggle: some View {
        card {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("SPEAKING")
                        .font(.system(size: 13, weight: .heavy)).tracking(2)
                        .foregroundColor(Color(red: 0.50, green: 0.71, blue: 1.0))
                    Text(speaking
                         ? "voicing the summary on a rhythm + on each surprise spike"
                         : "silent — sensing and display continue")
                        .font(.system(size: 12))
                        .foregroundColor(Color(red: 0.62, green: 0.70, blue: 0.82))
                }
                Spacer()
                Toggle("", isOn: $speaking)
                    .toggleStyle(.switch)
                    .labelsHidden()
                    .onChange(of: speaking) { _, on in
                        if on { voice.speak(summarySentence()) } else { voice.hush() }
                    }
            }
        }
    }

    // MARK: 2 — what is being sensed

    private var sensedBlock: some View {
        card {
            VStack(alignment: .leading, spacing: 12) {
                blockTitle("WHAT IS BEING SENSED")
                reading("presence",
                        model.present ? "yes" : "no",
                        model.present ? Color(red: 0.36, green: 0.89, blue: 0.65)
                                      : Color(red: 0.53, green: 0.59, blue: 0.67))
                reading("brightness", "\(model.brightness) / 255",
                        Color(red: 0.79, green: 0.85, blue: 0.95))
                reading("surprise",
                        model.surprised ? "SPIKE (\(model.surprise))" : "\(model.surprise)",
                        model.surprised ? Color(red: 0.95, green: 0.78, blue: 0.47)
                                        : Color(red: 0.79, green: 0.85, blue: 0.95))
                Divider().background(Color.white.opacity(0.08))
                Text(model.recipeNative
                     ? "gate run by fkwu on metal: \(model.lastExpr)"
                     : "fkwu unreachable — \(model.lastExpr)")
                    .font(.system(size: 10.5, design: .monospaced))
                    .foregroundColor(Color(red: 0.42, green: 0.46, blue: 0.54))
                Text("presence + surprise: recipe-run (fkwu (le ..) gate) · salience magnitude: carrier-computed")
                    .font(.system(size: 10.5))
                    .foregroundColor(Color(red: 0.42, green: 0.46, blue: 0.54))
            }
        }
    }

    private func reading(_ label: String, _ value: String, _ color: Color) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 14))
                .foregroundColor(Color(red: 0.62, green: 0.70, blue: 0.82))
            Spacer()
            Text(value)
                .font(.system(size: 18, weight: .semibold, design: .rounded))
                .foregroundColor(color)
        }
    }

    // MARK: 3 — surprise events

    private var surpriseBlock: some View {
        card {
            VStack(alignment: .leading, spacing: 10) {
                blockTitle("SURPRISE EVENTS")
                if model.events.isEmpty {
                    Text("no spikes yet — a still room is a quiet body")
                        .font(.system(size: 12))
                        .foregroundColor(Color(red: 0.42, green: 0.46, blue: 0.54))
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(model.events) { e in
                                HStack {
                                    Text(stamp(e.at))
                                        .font(.system(size: 12, design: .monospaced))
                                        .foregroundColor(Color(red: 0.55, green: 0.61, blue: 0.70))
                                    Spacer()
                                    Text("salience \(e.salience)  ·  bright \(e.brightness)")
                                        .font(.system(size: 12, weight: .medium))
                                        .foregroundColor(Color(red: 0.95, green: 0.78, blue: 0.47))
                                }
                            }
                        }
                    }
                    .frame(maxHeight: 160)
                }
            }
        }
    }

    // MARK: 4 — inquiry-plane probes

    private var planesBlock: some View {
        card {
            VStack(alignment: .leading, spacing: 12) {
                blockTitle("INQUIRY-PLANE PROBES")
                let cols = [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())]
                LazyVGrid(columns: cols, spacing: 10) {
                    ForEach(Plane.allCases) { p in
                        Button {
                            selectedPlane = p
                            planeReading = probe(p)
                            // each probe is also a tiny said-aloud sense when speaking
                            // is on, so the planes are audible doors too.
                        } label: {
                            Text(p.rawValue)
                                .font(.system(size: 13, weight: .heavy)).tracking(1)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                                .background(selectedPlane == p
                                            ? Color(red: 0.50, green: 0.71, blue: 1.0).opacity(0.22)
                                            : Color.white.opacity(0.05))
                                .foregroundColor(selectedPlane == p
                                                 ? Color(red: 0.70, green: 0.82, blue: 1.0)
                                                 : Color(red: 0.79, green: 0.85, blue: 0.95))
                                .cornerRadius(8)
                        }
                        .buttonStyle(.plain)
                    }
                }
                if let p = selectedPlane {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(p.rawValue)
                            .font(.system(size: 12, weight: .heavy))
                            .foregroundColor(Color(red: 0.50, green: 0.71, blue: 1.0))
                        Text(planeReading)
                            .font(.system(size: 13))
                            .foregroundColor(Color(red: 0.79, green: 0.85, blue: 0.95))
                    }
                    .padding(.top, 4)
                }
            }
        }
    }

    private func probe(_ p: Plane) -> String {
        switch p {
        case .what:
            return "the scene: \(model.sceneNote)"
        case .when:
            let f = DateFormatter(); f.dateFormat = "HH:mm:ss"; f.timeZone = TimeZone(identifier: "UTC")
            return "clock: \(f.string(from: Date())) UTC  ·  \(model.frameCount) frames sensed"
        case .where_:
            return "scene / brightness: \(model.brightness)/255 — "
                + (model.present ? "a lit, occupied field" : "a dim / empty field")
        case .how:
            return "not yet inferred (motion-kinematics plane pending)"
        case .who:
            return "unknown (face-embed pending)"
        case .why:
            return "not yet inferred (intent plane pending)"
        }
    }

    // MARK: chrome

    private var footer: some View {
        Text("body native, carrier thin · C-bootstrap fkwu on this Mac · no go/rust/clang/python/bash in the gate loop")
            .font(.system(size: 10.5))
            .foregroundColor(Color(red: 0.36, green: 0.40, blue: 0.48))
    }

    private func blockTitle(_ t: String) -> some View {
        Text(t)
            .font(.system(size: 13, weight: .heavy)).tracking(2)
            .foregroundColor(Color(red: 0.50, green: 0.71, blue: 1.0))
    }

    private func card<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        content()
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.white.opacity(0.04))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.white.opacity(0.07), lineWidth: 1))
            .cornerRadius(12)
    }

    private func summarySentence() -> String {
        let pres = model.present ? "presence yes" : "presence no"
        let surp = model.surprised ? "with a surprise spike" : "the field is steady"
        return "\(pres), brightness \(model.brightness) of 255, \(surp)."
    }

    private func stamp(_ d: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "HH:mm:ss"; f.timeZone = TimeZone(identifier: "UTC")
        return f.string(from: d) + " UTC"
    }
}
