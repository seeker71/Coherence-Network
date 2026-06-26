import SwiftUI
import SatsangMacCore

public enum SatsangHostShell: Sendable {
    case macOS
    case iPhone

    var title: String {
        switch self {
        case .macOS:
            return "Satsang Guidance"
        case .iPhone:
            return "Satsang Guidance"
        }
    }

    var platformName: String {
        switch self {
        case .macOS:
            return "macOS"
        case .iPhone:
            return "iPhone"
        }
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
    @Published var micLevel: Double = 0
    @Published var partialTranscript: String = ""
    @Published var utterances: [TranscriptUtterance] = []
    @Published var selectedID: TranscriptUtterance.ID?
    @Published var routeSummary: String = "Form route: waiting for request"
    @Published var memoryContextSummary: String = "Trusted memory: waiting for Send"
    @Published var healthContextSummary: String = "Health memory: waiting for import"
    @Published var healthSourceHints: String = WearableHealthImporter.defaultSourceHints.joined(separator: ", ")
    @Published var healthLookbackDays: Int = 7
    @Published var healthSamples: [TrustedHealthSample] = []
    @Published var isImportingHealth: Bool = false
    @Published var status: String = "Ready"

    private let defaultTranscriptPath: String
    private let defaultQueuePath: String
    private let repositoryRoot: URL?
    private let hostResources: FoundationHostResourceInterface
    private let roomMemoryStore: TrustedRoomMemoryStore
    private let healthMemoryStore: TrustedHealthMemoryStore
    private var timer: Timer?
    private let roomTranscriber = RoomTranscriber()

    init() {
        let hostResources = FoundationHostResourceInterface()
        self.hostResources = hostResources
        let home = hostResources.homeDirectory
        defaultTranscriptPath = home.appendingPathComponent(".coherence-network/agent-room-memory/transcript.jsonl").path
        defaultQueuePath = home.appendingPathComponent(".coherence-network/satsang-guidance/events.jsonl").path
        roomMemoryStore = TrustedRoomMemoryStore(
            rootURL: home.appendingPathComponent(".coherence-network/agent-room-memory"),
            host: hostResources
        )
        healthMemoryStore = TrustedHealthMemoryStore(
            rootURL: home.appendingPathComponent(".coherence-network/health-memory"),
            host: hostResources
        )
        repositoryRoot = Self.resolveRepositoryRoot(home: home, host: hostResources)
        transcriptPath = defaultTranscriptPath
        queuePath = defaultQueuePath
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
        roomTranscriber.onLevel = { [weak self] level in
            self?.micLevel = level
        }
        reload()
        reloadHealthContext(silent: true)
        timer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.followTranscript else { return }
                self.reload(silent: true)
                self.reloadHealthContext(silent: true)
            }
        }
    }

    func resetInvalidPathsIfNeeded() {
        var didReset = false
        if !isLikelyFilePath(transcriptPath) {
            transcriptPath = defaultTranscriptPath
            didReset = true
        }
        if !isLikelyFilePath(queuePath) {
            queuePath = defaultQueuePath
            didReset = true
        }
        if didReset {
            reload()
        }
    }

    var selectedUtterance: TranscriptUtterance? {
        guard let selectedID else { return utterances.first }
        return utterances.first { $0.id == selectedID }
    }

    var transcriptText: String {
        utterances.map { "\($0.speaker): \($0.text)" }.joined(separator: "\n")
    }

    var hostBoundaryPreview: FormHostBoundaryReceipt {
        let formCLIURL = repositoryRoot.flatMap { resolveFormCLI(repositoryRoot: $0) }
        return makeHostBoundary(formCLIURL: formCLIURL)
    }

    func reload(silent: Bool = false) {
        do {
            let loaded = try TranscriptParser.load(
                from: URL(fileURLWithPath: expanded(transcriptPath)),
                host: hostResources
            )
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
        utterances = roomMemoryStore.utterancesWithSpeakerProfiles(utterances)
        let memoryContext = loadMemoryContext()
        let healthContext = loadHealthContext()
        memoryContextSummary = memoryContext.summaryLine
        healthContextSummary = healthContext.summaryLine
        let routeReceipt = makeRouteReceipt(memoryContext: memoryContext, healthContext: healthContext)
        routeSummary = routeReceipt.summary
        let request = GuidanceRequest(
            sessionTitle: sessionTitle,
            targetPresence: targetPresence,
            invocation: invocation,
            turnMode: turnMode,
            guidanceQuestion: guidanceQuestion,
            utterances: utterances,
            routeReceipt: routeReceipt,
            memoryContext: memoryContext,
            healthContext: healthContext
        )
        do {
            let sender = GuidanceRequestSender(
                queueURL: URL(fileURLWithPath: expanded(queuePath)),
                host: hostResources
            )
            let result = try sender.send(request)
            let memoryResult = try roomMemoryStore.record(request)
            memoryContextSummary = "\(memoryContext.summaryLine); \(memoryResult.summary)"
            status = "Sent \(request.utterances.count) lines to \(targetPresence). \(routeReceipt.summary). \(memoryResult.summary). \(healthContext.summaryLine). Form envelope: \(result.latestFormURL.path)"
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
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.sortedKeys]
            let data = try utterances.map { try String(decoding: encoder.encode($0), as: UTF8.self) }
                .joined(separator: "\n")
                .appending("\n")
                .data(using: .utf8)!
            try hostResources.writeData(data, to: url, options: .atomic)
            status = "Exported edited transcript to \(url.path)"
        } catch {
            status = "Export failed: \(error.localizedDescription)"
        }
    }

    func importHealthSamples() {
        guard !isImportingHealth else { return }
        isImportingHealth = true
        status = "Requesting Health access"
        let daysBack = healthLookbackDays
        let hints = healthSourceHintList
        Task {
            do {
                let importer = WearableHealthImporter()
                let samples = try await importer.importRecentSamples(daysBack: daysBack, sourceNameHints: hints)
                let snapshot = TrustedHealthMemorySnapshot(sourceHints: hints, samples: samples)
                let result = try healthMemoryStore.record(snapshot)
                let context = try healthMemoryStore.context()
                await MainActor.run {
                    self.healthSamples = samples
                    self.healthContextSummary = "\(context.summaryLine); \(result.summary)"
                    self.status = "Imported \(samples.count) health samples. \(result.summary)."
                    self.isImportingHealth = false
                }
            } catch {
                await MainActor.run {
                    self.status = "Health import failed: \(error.localizedDescription)"
                    self.isImportingHealth = false
                }
            }
        }
    }

    private func expanded(_ path: String) -> String {
        if path == "~" { return hostResources.homeDirectory.path }
        if path.hasPrefix("~/") {
            return hostResources.homeDirectory
                .appendingPathComponent(String(path.dropFirst(2)))
                .path
        }
        return path
    }

    private func makeRouteReceipt(
        memoryContext: TrustedRoomMemoryContext,
        healthContext: TrustedHealthMemoryContext
    ) -> FormNativeRouteReceipt {
        let bodySources = formBodySources()
        let body = FormNativeLookupSignal.bodyProtocol(sourceIDs: bodySources, sufficient: false)
        let formCLIURL = repositoryRoot.flatMap { resolveFormCLI(repositoryRoot: $0) }
        let hostBoundary = makeHostBoundary(formCLIURL: formCLIURL)
        let rag = formNativeAskSignal(formCLIURL: formCLIURL, memoryContext: memoryContext, healthContext: healthContext)
        return FormNativeRouteReceipt(hostBoundary: hostBoundary, bodyLookup: body, ragLookup: rag)
    }

    private func loadMemoryContext() -> TrustedRoomMemoryContext {
        do {
            return try roomMemoryStore.context()
        } catch {
            return TrustedRoomMemoryContext(
                priorSessionCount: 0,
                priorTurnCount: 0,
                speakerCount: 0,
                speakerSummary: "memory read failed",
                recentExchangeSummary: error.localizedDescription
            )
        }
    }

    private func loadHealthContext() -> TrustedHealthMemoryContext {
        do {
            return try healthMemoryStore.context()
        } catch {
            return TrustedHealthMemoryContext(
                priorImportCount: 0,
                recentSampleCount: 0,
                sourceSummary: "health memory read failed",
                metricSummary: "health memory read failed",
                recentObservationSummary: error.localizedDescription
            )
        }
    }

    func reloadHealthContext(silent: Bool = false) {
        let context = loadHealthContext()
        healthContextSummary = context.summaryLine
        if !silent, context.recentSampleCount > 0 {
            status = context.summaryLine
        }
    }

    private func formBodySources() -> [String] {
        guard let repositoryRoot else { return [] }
        let candidates = [
            "form/form-stdlib/satsang-guidance-event.fk",
            "form/form-stdlib/form-cli-sufficiency.fk",
            "form/form-stdlib/satsang-room-memory.fk",
            "form/form-stdlib/satsang-health-memory.fk",
            "form/form-stdlib/rag-ask.fk",
            "docs/coherence-substrate/satsang-guidance-event.form",
            "docs/coherence-substrate/satsang-room-memory.form",
            "docs/coherence-substrate/satsang-health-memory.form",
            "docs/coherence-substrate/form-first-reasoning.form"
        ]
        return candidates.filter {
            hostResources.fileExists(at: repositoryRoot.appendingPathComponent($0))
        }
    }

    private func makeHostBoundary(formCLIURL: URL?) -> FormHostBoundaryReceipt {
        let fileProcessDoors = hostResources.detectResourceDoors(
            transcriptURL: URL(fileURLWithPath: expanded(transcriptPath)),
            queueURL: URL(fileURLWithPath: expanded(queuePath)),
            formCLIURL: formCLIURL
        )
        return FormHostBoundaryReceipt(resourceDoors: fileProcessDoors + RoomTranscriber.detectResourceDoors() + WearableHealthImporter.detectResourceDoors())
    }

    private func formNativeAskSignal(
        formCLIURL: URL?,
        memoryContext: TrustedRoomMemoryContext,
        healthContext: TrustedHealthMemoryContext
    ) -> FormNativeLookupSignal {
        guard let repositoryRoot else {
            return .unavailable("form-native-rag-local-llm", reason: "repository root not found")
        }
        guard let formCLIURL else {
            return .unavailable("form-native-rag-local-llm", reason: "form-cli executable not found")
        }
        let memoryText = [
            memoryContext.speakerSummary,
            memoryContext.recentExchangeSummary,
            healthContext.sourceSummary,
            healthContext.metricSummary,
            healthContext.recentObservationSummary
        ].joined(separator: "\n")
        let query = [guidanceQuestion, memoryText, transcriptText]
            .joined(separator: "\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let runner = FormNativeLookupRunner(
            formCLIURL: formCLIURL,
            workingDirectory: repositoryRoot,
            host: hostResources
        )
        return runner.ask(query.isEmpty ? guidanceQuestion : query)
    }

    private static func resolveRepositoryRoot(home: URL, host: FoundationHostResourceInterface) -> URL? {
        var candidates: [URL] = []
        candidates.append(host.currentDirectory)
        let bundleURL = Bundle.main.bundleURL
        candidates.append(bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent())
        candidates.append(home.appendingPathComponent("source/Coherence-Network"))

        return candidates.first { candidate in
            host.fileExists(at: candidate.appendingPathComponent("form/form-stdlib/satsang-guidance-event.fk"))
        }
    }

    private func resolveFormCLI(repositoryRoot: URL) -> URL? {
        let candidates = [
            repositoryRoot.appendingPathComponent("form/form-cli"),
            hostResources.homeDirectory.appendingPathComponent(".local/bin/form-cli")
        ]
        return candidates.first { hostResources.isExecutableFile(at: $0) }
    }

    private func isLikelyFilePath(_ path: String) -> Bool {
        path.hasPrefix("/") || path.hasPrefix("~/") || path.hasPrefix("./") || path.hasPrefix("../")
    }

    private var healthSourceHintList: [String] {
        healthSourceHints
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private func upsertLiveDraft(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        partialTranscript = trimmed
        guard !trimmed.isEmpty else {
            utterances.removeAll { $0.id == "live-draft" }
            return
        }

        let now = ISO8601DateFormatter().string(from: Date())
        var draft = TranscriptUtterance(
            id: "live-draft",
            timestamp: now,
            speaker: "room mic",
            detectedText: trimmed,
            text: trimmed,
            source: "live-mic-partial"
        )
        draft.speakerProfileID = TrustedRoomMemoryStore.speakerProfileID(for: draft)
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
            var profiled = utterance
            profiled.speakerProfileID = profiled.speakerProfileID ?? TrustedRoomMemoryStore.speakerProfileID(for: profiled)
            utterances.append(profiled)
        }
        partialTranscript = ""
        selectedID = utterance.id
    }
}

public struct SatsangGuidanceRootView: View {
    private let shell: SatsangHostShell
    @StateObject private var model = AppModel()
    @State private var selectedMode: SatsangNativeAppMode = .room
    @FocusState private var focusedPathField: PathField?

    private enum PathField: Hashable {
        case transcript
        case queue
    }

    public init(shell: SatsangHostShell = .macOS) {
        self.shell = shell
    }

    public var body: some View {
        VStack(spacing: 0) {
            commandBar
            Divider()
            TabView(selection: $selectedMode) {
                roomTab
                    .tabItem { Label("Room", systemImage: "waveform") }
                    .tag(SatsangNativeAppMode.room)
                guidanceTab
                    .tabItem { Label("Guidance", systemImage: "sparkles") }
                    .tag(SatsangNativeAppMode.guidance)
                memoryTab
                    .tabItem { Label("Memory", systemImage: "archivebox") }
                    .tag(SatsangNativeAppMode.memory)
                healthTab
                    .tabItem { Label("Health", systemImage: "heart.text.square") }
                    .tag(SatsangNativeAppMode.health)
                learningTab
                    .tabItem { Label("Learning", systemImage: "arrow.triangle.2.circlepath") }
                    .tag(SatsangNativeAppMode.learning)
                resourcesTab
                    .tabItem { Label("Resources", systemImage: "switch.2") }
                    .tag(SatsangNativeAppMode.resources)
                settingsTab
                    .tabItem { Label("Settings", systemImage: "slider.horizontal.3") }
                    .tag(SatsangNativeAppMode.settings)
            }
            Divider()
            statusBar
        }
        .onAppear {
            model.resetInvalidPathsIfNeeded()
            focusedPathField = nil
        }
    }

    private var commandBar: some View {
        ViewThatFits(in: .horizontal) {
            HStack {
                titleBlock
                Spacer()
                commands
            }
            VStack(alignment: .leading, spacing: 10) {
                titleBlock
                commands
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    private var titleBlock: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(shell.title)
                    .font(.title2.weight(.semibold))
            Text("\(shell.platformName) native shell · \(selectedMode.title)")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private var commands: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 10) {
                commandButtons
            }
            VStack(alignment: .leading, spacing: 8) {
                commandButtons
            }
        }
    }

    private var commandButtons: some View {
        Group {
            Toggle("Follow", isOn: $model.followTranscript)
                .toggleStyle(.switch)
            if model.isListening {
                Button { model.toggleListening() } label: {
                    Label("Stop", systemImage: "stop.circle")
                }
                .buttonStyle(.bordered)
            } else {
                Button { model.toggleListening() } label: {
                    Label("Start", systemImage: "mic")
                }
                .buttonStyle(.borderedProminent)
            }
            Button { model.reload() } label: {
                Label("Reload", systemImage: "arrow.clockwise")
            }
            Button { model.send() } label: {
                Label("Send", systemImage: "paperplane")
            }
            .keyboardShortcut(.return, modifiers: [.command])
        }
    }

    private var statusBar: some View {
        Text(model.status)
            .font(.footnote)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
    }

    private var roomTab: some View {
        VStack(spacing: 0) {
            liveCaptureStrip
            Divider()
            GeometryReader { proxy in
                if proxy.size.width >= 820 {
                    HStack(spacing: 0) {
                        transcriptList
                            .frame(width: 420)
                        Divider()
                        utteranceEditor
                            .frame(maxWidth: .infinity)
                    }
                } else {
                    VStack(spacing: 0) {
                        transcriptList
                            .frame(minHeight: 280)
                        Divider()
                        utteranceEditor
                    }
                }
            }
        }
    }

    private var guidanceTab: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                requestFields
                Text("Request for guidance")
                    .font(.headline)
                TextEditor(text: $model.guidanceQuestion)
                    .frame(minHeight: 120)
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(.quaternary))
                HStack {
                    Button { model.exportEditedTranscript() } label: {
                        Label("Export", systemImage: "square.and.arrow.down")
                    }
                    Spacer()
                    Button { model.send() } label: {
                        Label("Send to Form", systemImage: "paperplane")
                    }
                    .buttonStyle(.borderedProminent)
                }
                routeSummary
                transcriptPreview
            }
            .padding(16)
        }
    }

    private var memoryTab: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                metricRow("Sessions", model.memoryContextSummary)
                metricRow("Speakers", "\(model.utterances.compactMap(\.speakerProfileID).filter { !$0.isEmpty }.count)")
                metricRow("Health", model.healthContextSummary)
                routeSummary
                transcriptPreview
            }
            .padding(16)
        }
    }

    private var healthTab: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 8) {
                    GridRow {
                        Text("Sources")
                        TextField("Oura Ring 4, Wellue O2Ring S", text: $model.healthSourceHints)
                    }
                    GridRow {
                        Text("Days")
                        Stepper("\(model.healthLookbackDays)", value: $model.healthLookbackDays, in: 1...30)
                    }
                }
                .textFieldStyle(.roundedBorder)

                metricRow("Essential sources", WearableHealthImporter.essentialSourceSummary)

                HStack {
                    Button { model.importHealthSamples() } label: {
                        Label(model.isImportingHealth ? "Importing" : "Import", systemImage: "heart.text.square")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.isImportingHealth)
                    Spacer()
                    Button { model.reloadHealthContext() } label: {
                        Label("Reload", systemImage: "arrow.clockwise")
                    }
                }

                metricRow("Health memory", model.healthContextSummary)
                healthSampleList
            }
            .padding(16)
        }
    }

    private var learningTab: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                metricRow("Route", model.routeSummary)
                metricRow("Memory", model.memoryContextSummary)
                metricRow("Health", model.healthContextSummary)
                metricRow("Edited turns", "\(model.utterances.filter(\.wasEdited).count)")
                metricRow("Transcript turns", "\(model.utterances.count)")
            }
            .padding(16)
        }
    }

    private var resourcesTab: some View {
        let boundary = model.hostBoundaryPreview
        return ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                metricRow("Host carrier", boundary.hostCarrier)
                metricRow("Targets", boundary.platformTargets.joined(separator: ", "))
                metricRow("Allowed doors", boundary.allowedResourceKinds.joined(separator: ", "))
                Text("Detected doors")
                    .font(.headline)
                ForEach(boundary.resourceDoors, id: \.kind) { door in
                    resourceDoorRow(door)
                }
                Text("Platform carriers")
                    .font(.headline)
                ForEach(boundary.platformCarriers, id: \.platform) { carrier in
                    VStack(alignment: .leading, spacing: 6) {
                        Text("\(carrier.platform): \(carrier.hostCarrier)")
                            .font(.subheadline.weight(.semibold))
                        Text(carrier.doorSummary)
                            .font(.caption.monospaced())
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 8)
                }
            }
            .padding(16)
        }
    }

    private var settingsTab: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                pathFields
                requestFields
            }
            .padding(16)
        }
    }

    private var liveCaptureStrip: some View {
        HStack(spacing: 10) {
            Text(model.partialTranscript.isEmpty ? (model.isListening ? "Listening..." : "Room listener idle") : model.partialTranscript)
                .font(.callout)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .lineLimit(2)
                .textSelection(.enabled)
            ProgressView(value: model.micLevel)
                .frame(width: 120)
            Text("\(Int(model.micLevel * 100))%")
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)
                .frame(width: 36, alignment: .trailing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }

    private var pathFields: some View {
        Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 8) {
            GridRow {
                Text("Transcript")
                TextField("Transcript JSONL", text: $model.transcriptPath)
                    .focused($focusedPathField, equals: .transcript)
            }
            GridRow {
                Text("Event queue")
                TextField("Guidance event queue", text: $model.queuePath)
                    .focused($focusedPathField, equals: .queue)
            }
        }
        .textFieldStyle(.roundedBorder)
        .font(.callout)
    }

    private var requestFields: some View {
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
    }

    private var transcriptList: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Detected transcriptions")
                    .font(.headline)
                Spacer()
                Button { model.addManualLine() } label: {
                    Image(systemName: "plus")
                }
                Button { model.deleteSelected() } label: {
                    Image(systemName: "minus")
                }
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
                        if let speakerProfileID = utterance.speakerProfileID {
                            Text(speakerProfileID)
                                .font(.caption2.monospaced())
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 4)
                    .tag(utterance.id)
                }
            }
        }
        .padding(16)
    }

    private var utteranceEditor: some View {
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
        }
        .padding(16)
    }

    private var routeSummary: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(model.routeSummary)
                .font(.footnote)
                .foregroundStyle(model.routeSummary.contains("remote oracle") ? .orange : .secondary)
            Text(model.memoryContextSummary)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private var transcriptPreview: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("All transcript lines in this request")
                .font(.headline)
            ScrollView {
                Text(model.transcriptText.isEmpty ? "No transcript lines loaded." : model.transcriptText)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            }
            .frame(minHeight: 180)
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(.quaternary))
        }
    }

    private var healthSampleList: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Latest imported samples")
                .font(.headline)
            if model.healthSamples.isEmpty {
                Text("No samples imported.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(model.healthSamples.suffix(24)) { sample in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(sample.kind)
                                .font(.caption.weight(.semibold))
                            Spacer()
                            Text(sample.endDate)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        Text("\(sample.value, specifier: "%.2f") \(sample.unit) · \(sample.sourceName)")
                            .font(.callout)
                        if let stage = sample.metadata["stage"] {
                            Text(stage)
                                .font(.caption2.monospaced())
                                .foregroundStyle(.secondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 4)
                }
            }
        }
    }

    private func metricRow(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value.isEmpty ? "none" : value)
                .font(.callout)
                .textSelection(.enabled)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func resourceDoorRow(_ door: HostResourceDoor) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("\(door.kind): \(door.state)")
                .font(.subheadline.weight(.semibold))
            Text("\(door.carrier) \(door.detail)")
                .font(.caption.monospaced())
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 4)
    }
}
