import SwiftUI
import SatsangMacCore

@main
struct SatsangGuidanceApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .frame(minWidth: 1040, minHeight: 700)
        }
        .windowStyle(.titleBar)
    }
}

@MainActor
final class AppModel: ObservableObject {
    @Published var transcriptPath: String
    @Published var queuePath: String
    @Published var sessionTitle: String = "Satsang session"
    @Published var targetPresence: String = "sema"
    @Published var invocation: String = "Guidance is invited when your turn is offered."
    @Published var guidanceQuestion: String = "What wants to be offered to the circle now?"
    @Published var turnMode: String = "turn-offered"
    @Published var followTranscript: Bool = true
    @Published var isListening: Bool = false
    @Published var partialTranscript: String = ""
    @Published var utterances: [TranscriptUtterance] = []
    @Published var selectedID: TranscriptUtterance.ID?
    @Published var status: String = "Ready"

    private var timer: Timer?
    private let roomTranscriber = RoomTranscriber()

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        transcriptPath = ProcessInfo.processInfo.environment["SATSANG_TRANSCRIPT_PATH"]
            ?? home.appendingPathComponent(".coherence-network/agent-room-memory/transcript.jsonl").path
        queuePath = ProcessInfo.processInfo.environment["SATSANG_GUIDANCE_EVENTS"]
            ?? home.appendingPathComponent(".coherence-network/satsang-guidance/events.jsonl").path
        roomTranscriber.onStateChange = { [weak self] listening, message in
            self?.isListening = listening
            self?.status = message
        }
        roomTranscriber.onPartial = { [weak self] text in
            self?.upsertLiveDraft(text)
        }
        roomTranscriber.onUtterance = { [weak self] utterance in
            self?.commitLiveUtterance(utterance)
        }
        reload()
        timer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.followTranscript else { return }
                self.reload(silent: true)
            }
        }
    }

    var selectedUtterance: TranscriptUtterance? {
        guard let selectedID else { return utterances.first }
        return utterances.first { $0.id == selectedID }
    }

    var transcriptText: String {
        utterances.map { "\($0.speaker): \($0.text)" }.joined(separator: "\n")
    }

    func reload(silent: Bool = false) {
        do {
            let loaded = try TranscriptParser.load(from: URL(fileURLWithPath: expanded(transcriptPath)))
            utterances = TranscriptMerger.merge(loaded: loaded, current: utterances)
            if selectedID == nil { selectedID = utterances.first?.id }
            if !silent { status = "Loaded \(utterances.count) transcript lines" }
        } catch {
            status = "Load failed: \(error.localizedDescription)"
        }
    }

    func addManualLine() {
        let now = ISO8601DateFormatter().string(from: Date())
        let utterance = TranscriptUtterance(
            id: UUID().uuidString,
            timestamp: now,
            speaker: "manual",
            detectedText: "",
            text: "",
            source: "manual"
        )
        utterances.append(utterance)
        selectedID = utterance.id
    }

    func deleteSelected() {
        guard let selectedID else { return }
        utterances.removeAll { $0.id == selectedID }
        if selectedID == "live-draft" {
            partialTranscript = ""
        }
        self.selectedID = utterances.first?.id
    }

    func updateSelectedText(_ text: String) {
        guard let selectedID,
              let index = utterances.firstIndex(where: { $0.id == selectedID })
        else { return }
        utterances[index].text = text
    }

    func send() {
        commitLiveDraftIfNeeded()
        let request = GuidanceRequest(
            sessionTitle: sessionTitle,
            targetPresence: targetPresence,
            invocation: invocation,
            turnMode: turnMode,
            guidanceQuestion: guidanceQuestion,
            utterances: utterances
        )
        do {
            let sender = GuidanceRequestSender(
                queueURL: URL(fileURLWithPath: expanded(queuePath))
            )
            let result = try sender.send(request)
            status = "Sent \(request.utterances.count) lines to \(targetPresence). Form envelope: \(result.latestFormURL.path)"
        } catch {
            status = "Send failed: \(error.localizedDescription)"
        }
    }

    func toggleListening() {
        if isListening {
            roomTranscriber.stop()
        } else {
            status = "Requesting microphone and speech permissions"
            roomTranscriber.start()
        }
    }

    func commitLiveDraftIfNeeded() {
        let trimmed = partialTranscript.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let now = ISO8601DateFormatter().string(from: Date())
        commitLiveUtterance(TranscriptUtterance(
            id: "live-\(UUID().uuidString)",
            timestamp: now,
            speaker: "room mic",
            detectedText: trimmed,
            text: trimmed,
            source: "live-mic"
        ))
    }

    func exportEditedTranscript() {
        do {
            let url = URL(fileURLWithPath: expanded(queuePath))
                .deletingLastPathComponent()
                .appendingPathComponent("edited-transcript.jsonl")
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.sortedKeys]
            let data = try utterances.map { try String(decoding: encoder.encode($0), as: UTF8.self) }
                .joined(separator: "\n")
                .appending("\n")
                .data(using: .utf8)!
            try data.write(to: url, options: .atomic)
            status = "Exported edited transcript to \(url.path)"
        } catch {
            status = "Export failed: \(error.localizedDescription)"
        }
    }

    private func expanded(_ path: String) -> String {
        if path == "~" { return FileManager.default.homeDirectoryForCurrentUser.path }
        if path.hasPrefix("~/") {
            return FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(String(path.dropFirst(2)))
                .path
        }
        return path
    }

    private func upsertLiveDraft(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        partialTranscript = trimmed
        guard !trimmed.isEmpty else {
            utterances.removeAll { $0.id == "live-draft" }
            return
        }

        let now = ISO8601DateFormatter().string(from: Date())
        let draft = TranscriptUtterance(
            id: "live-draft",
            timestamp: now,
            speaker: "room mic",
            detectedText: trimmed,
            text: trimmed,
            source: "live-mic-partial"
        )
        if let index = utterances.firstIndex(where: { $0.id == draft.id }) {
            utterances[index] = draft
        } else {
            utterances.append(draft)
            selectedID = draft.id
        }
    }

    private func commitLiveUtterance(_ utterance: TranscriptUtterance) {
        utterances.removeAll { $0.id == "live-draft" }
        if !utterances.contains(where: { $0.id == utterance.id }) {
            utterances.append(utterance)
        }
        partialTranscript = ""
        selectedID = utterance.id
    }
}

struct ContentView: View {
    @StateObject private var model = AppModel()

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            HSplitView {
                transcriptList
                    .frame(minWidth: 360)
                detail
                    .frame(minWidth: 620)
            }
            Divider()
            Text(model.status)
                .font(.footnote)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
        }
    }

    private var header: some View {
        VStack(spacing: 10) {
            HStack {
                Text("Satsang Guidance")
                    .font(.title2.weight(.semibold))
                Spacer()
                Toggle("Follow", isOn: $model.followTranscript)
                    .toggleStyle(.switch)
                if model.isListening {
                    Button("Stop Listening") { model.toggleListening() }
                        .buttonStyle(.bordered)
                } else {
                    Button("Start Listening") { model.toggleListening() }
                        .buttonStyle(.borderedProminent)
                }
                Button("Reload") { model.reload() }
                Button("Send to Form") { model.send() }
                    .keyboardShortcut(.return, modifiers: [.command])
            }
            Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 8) {
                GridRow {
                    Text("Transcript")
                    TextField("Transcript JSONL", text: $model.transcriptPath)
                }
                GridRow {
                    Text("Event queue")
                    TextField("Guidance event queue", text: $model.queuePath)
                }
            }
            .textFieldStyle(.roundedBorder)
            .font(.callout)
            if model.isListening || !model.partialTranscript.isEmpty {
                Text(model.partialTranscript.isEmpty ? "Listening..." : model.partialTranscript)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .lineLimit(2)
                    .textSelection(.enabled)
            }
        }
        .padding(16)
    }

    private var transcriptList: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Detected transcriptions")
                    .font(.headline)
                Spacer()
                Button("+") { model.addManualLine() }
                Button("-") { model.deleteSelected() }
                    .disabled(model.selectedID == nil)
            }
            List(selection: $model.selectedID) {
                ForEach(model.utterances) { utterance in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(utterance.speaker)
                                .font(.caption.weight(.semibold))
                            Spacer()
                            Text(utterance.timestamp)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        Text(utterance.text.isEmpty ? "Empty line" : utterance.text)
                            .font(.body)
                            .lineLimit(3)
                        if utterance.wasEdited {
                            Text("edited")
                                .font(.caption2)
                                .foregroundStyle(.orange)
                        }
                    }
                    .padding(.vertical, 4)
                    .tag(utterance.id)
                }
            }
        }
        .padding(16)
    }

    private var detail: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Edit selected utterance")
                .font(.headline)
            TextEditor(text: Binding(
                get: { model.selectedUtterance?.text ?? "" },
                set: { model.updateSelectedText($0) }
            ))
            .font(.body)
            .frame(minHeight: 130)
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(.quaternary))

            Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 8) {
                GridRow {
                    Text("Presence")
                    TextField("sema", text: $model.targetPresence)
                }
                GridRow {
                    Text("Turn mode")
                    Picker("Turn mode", selection: $model.turnMode) {
                        Text("turn offered").tag("turn-offered")
                        Text("named and asked").tag("named-and-asked")
                        Text("button invoked").tag("button-invoked")
                    }
                    .pickerStyle(.segmented)
                }
                GridRow {
                    Text("Invocation")
                    TextField("Invocation", text: $model.invocation)
                }
            }
            .textFieldStyle(.roundedBorder)

            Text("Request for guidance")
                .font(.headline)
            TextEditor(text: $model.guidanceQuestion)
                .frame(minHeight: 90)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(.quaternary))

            HStack {
                Button("Export edited transcript") { model.exportEditedTranscript() }
                Spacer()
                Button("Send to Form / Sema") { model.send() }
                    .buttonStyle(.borderedProminent)
            }

            Text("All transcript lines in this request")
                .font(.headline)
            ScrollView {
                Text(model.transcriptText.isEmpty ? "No transcript lines loaded." : model.transcriptText)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            .frame(minHeight: 140)
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(.quaternary))
        }
        .padding(16)
    }
}
