import AVFoundation
import Foundation
import SatsangMacCore
import Speech

final class RoomTranscriber: @unchecked Sendable {
    var onStateChange: (@MainActor @Sendable (Bool, String) -> Void)?
    var onPartial: (@MainActor @Sendable (String) -> Void)?
    var onUtterance: (@MainActor @Sendable (TranscriptUtterance) -> Void)?
    var onLevel: (@MainActor @Sendable (Double) -> Void)?

    private let workQueue = DispatchQueue(label: "earth.hati.satsang-guidance.room-transcriber")
    private let audioEngine = AVAudioEngine()
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en_US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var lastPartialText = ""
    private var keepListening = false
    private var inputTapInstalled = false
    private var lastLevelEmit = Date.distantPast

    static func detectResourceDoors() -> [HostResourceDoor] {
        let microphoneStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        let speechStatus = SFSpeechRecognizer.authorizationStatus()
        let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en_US"))
        let speechAvailable = speechRecognizer?.isAvailable == true
        return [
            HostResourceDoor(
                kind: "audio-input",
                state: microphoneDoorState(microphoneStatus),
                carrier: audioCarrier,
                detail: microphoneStatusName(microphoneStatus)
            ),
            HostResourceDoor(
                kind: "speech-transcript",
                state: speechDoorState(speechStatus, available: speechAvailable),
                carrier: speechCarrier,
                detail: "side-channel-during-live-capture;\(speechStatusName(speechStatus));available=\(speechAvailable ? "1" : "0")"
            ),
        ]
    }

    func start() {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized:
            beginWithMicrophoneAccess()
        case .notDetermined:
            emitState(false, "Requesting microphone permission")
            AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
                guard let self else { return }
                if granted {
                    self.beginWithMicrophoneAccess()
                } else {
                    self.emitState(false, "Microphone permission was not granted.")
                }
            }
        case .denied:
            emitState(false, "Microphone permission is denied. Allow Satsang Guidance in \(Self.microphoneSettingsName).")
        case .restricted:
            emitState(false, "Microphone permission is restricted on this \(Self.platformDisplayName).")
        @unknown default:
            emitState(false, "Microphone permission is unavailable.")
        }
    }

    func stop(commitPartial: Bool = true) {
        workQueue.async {
            self.keepListening = false
            if commitPartial {
                self.commitPartialIfNeeded()
            }
            self.stopSpeechSideChannel()
            self.stopLiveCapture()
            self.emitPartial("")
            self.emitLevel(0)
            self.emitState(false, "Listening stopped")
        }
    }

    private func beginWithMicrophoneAccess() {
        workQueue.async {
            self.keepListening = true
            self.startLiveCapture()
            self.requestSpeechAuthorization()
        }
    }

    private func requestSpeechAuthorization() {
        switch SFSpeechRecognizer.authorizationStatus() {
        case .authorized:
            startRecognition()
        case .notDetermined:
            emitState(true, "Live room capture is active; requesting Speech side-channel permission")
            SFSpeechRecognizer.requestAuthorization { [weak self] speechStatus in
                guard let self else { return }
                self.workQueue.async {
                    self.handleSpeechAuthorization(speechStatus)
                }
            }
            workQueue.asyncAfter(deadline: .now() + 6.0) { [weak self] in
                guard let self, self.keepListening else { return }
                guard SFSpeechRecognizer.authorizationStatus() == .notDetermined else { return }
                self.emitState(true, "Live room capture is active; waiting for Speech side-channel permission")
            }
        case .denied:
            emitState(true, "Live room capture is active; Speech side-channel permission is denied.")
        case .restricted:
            emitState(true, "Live room capture is active; Speech side-channel is restricted on this \(Self.platformDisplayName).")
        @unknown default:
            emitState(true, "Live room capture is active; Speech side-channel permission is unavailable.")
        }
    }

    private func handleSpeechAuthorization(_ speechStatus: SFSpeechRecognizerAuthorizationStatus) {
        guard keepListening else { return }
        if speechStatus == .authorized {
            startRecognition()
        } else {
            emitState(true, "Live room capture is active; Speech side-channel permission is \(Self.speechStatusName(speechStatus)).")
        }
    }

    private func startLiveCapture() {
        guard !inputTapInstalled else {
            if !audioEngine.isRunning {
                startAudioEngine()
            }
            return
        }
        let inputNode = audioEngine.inputNode
        let format = inputNode.outputFormat(forBus: 0)
        guard format.sampleRate > 0 else {
            emitState(false, "No microphone input format is available.")
            return
        }

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
            self?.reportLevel(buffer)
        }
        inputTapInstalled = true

        startAudioEngine()
    }

    private func startAudioEngine() {
        do {
            try configureAudioSessionIfNeeded()
            audioEngine.prepare()
            try audioEngine.start()
            emitState(true, "Live room capture is active; preparing Speech side channel")
        } catch {
            stopSpeechSideChannel()
            stopLiveCapture()
            emitState(false, "Microphone start failed: \(error.localizedDescription)")
        }
    }

    private func startRecognition() {
        guard keepListening else { return }
        guard recognitionRequest == nil, recognitionTask == nil else { return }
        guard inputTapInstalled, audioEngine.isRunning else {
            startLiveCapture()
            guard inputTapInstalled, audioEngine.isRunning else { return }
            return startRecognition()
        }

        guard let speechRecognizer else {
            emitState(true, "Live room capture is active; Speech side channel is unavailable for this locale.")
            return
        }
        guard speechRecognizer.isAvailable else {
            emitState(true, "Live room capture is active; Speech side channel is not available right now.")
            return
        }

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.taskHint = .dictation
        if #available(iOS 16.0, macOS 13.0, *) {
            request.addsPunctuation = true
        }
        recognitionRequest = request
        lastPartialText = ""

        recognitionTask = speechRecognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let result {
                let text = result.bestTranscription.formattedString
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                let isFinal = result.isFinal
                self.workQueue.async {
                    self.handleRecognitionResult(text: text, isFinal: isFinal)
                }
            }
            if let error {
                self.workQueue.async {
                    self.handleRecognitionError(error)
                }
            }
        }

        emitState(true, "Live room capture is active; Speech side channel is transcribing")
    }

    private func handleRecognitionResult(text: String, isFinal: Bool) {
        guard keepListening || recognitionRequest != nil || recognitionTask != nil else { return }
        lastPartialText = text
        emitPartial(text)
        if isFinal {
            emitUtterance(text)
            lastPartialText = ""
            emitPartial("")
            recognitionRequest = nil
            recognitionTask = nil
            restartSpeechSideChannelSoon(message: "Live room capture is active; Speech side channel cycling")
        }
    }

    private func handleRecognitionError(_ error: Error) {
        commitPartialIfNeeded()
        stopSpeechSideChannel()
        emitPartial("")

        guard keepListening else {
            emitLevel(0)
            emitState(false, "Listening stopped: \(error.localizedDescription)")
            return
        }

        restartSpeechSideChannelSoon(message: "Live room capture is active; Speech side channel waiting for speech")
    }

    private func restartSpeechSideChannelSoon(message: String) {
        guard keepListening else { return }
        emitState(true, message)
        workQueue.asyncAfter(deadline: .now() + 0.35) { [weak self] in
            guard let self, self.keepListening else { return }
            self.startRecognition()
        }
    }

    private func stopSpeechSideChannel() {
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil
    }

    private func stopLiveCapture() {
        if audioEngine.isRunning {
            audioEngine.stop()
        }
        if inputTapInstalled {
            audioEngine.inputNode.removeTap(onBus: 0)
            inputTapInstalled = false
        }
        deactivateAudioSessionIfNeeded()
    }

    private func configureAudioSessionIfNeeded() throws {
        #if os(iOS)
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .measurement, options: [.allowBluetooth, .defaultToSpeaker])
        try session.setActive(true, options: [])
        #endif
    }

    private func deactivateAudioSessionIfNeeded() {
        #if os(iOS)
        try? AVAudioSession.sharedInstance().setActive(false, options: [.notifyOthersOnDeactivation])
        #endif
    }

    private func commitPartialIfNeeded() {
        let text = lastPartialText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        emitUtterance(text)
        lastPartialText = ""
    }

    private func reportLevel(_ buffer: AVAudioPCMBuffer) {
        let now = Date()
        guard now.timeIntervalSince(lastLevelEmit) >= 0.2 else { return }
        lastLevelEmit = now

        guard let channel = buffer.floatChannelData?[0] else {
            emitLevel(0)
            return
        }

        let frameCount = Int(buffer.frameLength)
        guard frameCount > 0 else {
            emitLevel(0)
            return
        }

        var sum: Float = 0
        for index in 0..<frameCount {
            let sample = channel[index]
            sum += sample * sample
        }
        let rms = sqrt(sum / Float(frameCount))
        emitLevel(min(1.0, Double(rms) * 18.0))
    }

    private func emitUtterance(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let now = ISO8601DateFormatter().string(from: Date())
        let utterance = TranscriptUtterance(
            id: "live-\(UUID().uuidString)",
            timestamp: now,
            speaker: "room mic",
            detectedText: trimmed,
            text: trimmed,
            source: "live-mic"
        )
        let handler = onUtterance
        Task { @MainActor in
            handler?(utterance)
        }
    }

    private func emitPartial(_ text: String) {
        let handler = onPartial
        Task { @MainActor in
            handler?(text)
        }
    }

    private func emitLevel(_ level: Double) {
        let handler = onLevel
        Task { @MainActor in
            handler?(level)
        }
    }

    private func emitState(_ listening: Bool, _ message: String) {
        let handler = onStateChange
        Task { @MainActor in
            handler?(listening, message)
        }
    }

    private static func speechStatusName(_ status: SFSpeechRecognizerAuthorizationStatus) -> String {
        switch status {
        case .authorized:
            return "authorized"
        case .denied:
            return "denied"
        case .restricted:
            return "restricted"
        case .notDetermined:
            return "not determined"
        @unknown default:
            return "unknown"
        }
    }

    private static func microphoneStatusName(_ status: AVAuthorizationStatus) -> String {
        switch status {
        case .authorized:
            return "authorized"
        case .denied:
            return "denied"
        case .restricted:
            return "restricted"
        case .notDetermined:
            return "not determined"
        @unknown default:
            return "unknown"
        }
    }

    private static func microphoneDoorState(_ status: AVAuthorizationStatus) -> String {
        switch status {
        case .authorized:
            return "open"
        case .denied, .restricted:
            return "unavailable"
        case .notDetermined:
            return "unknown"
        @unknown default:
            return "unknown"
        }
    }

    private static func speechDoorState(_ status: SFSpeechRecognizerAuthorizationStatus, available: Bool) -> String {
        switch status {
        case .authorized:
            return available ? "open" : "unavailable"
        case .denied, .restricted:
            return "unavailable"
        case .notDetermined:
            return "unknown"
        @unknown default:
            return "unknown"
        }
    }

    private static var audioCarrier: String {
        #if os(iOS)
        return "ios-avfoundation"
        #else
        return "macos-avfoundation"
        #endif
    }

    private static var speechCarrier: String {
        #if os(iOS)
        return "ios-speech"
        #else
        return "macos-speech"
        #endif
    }

    private static var platformDisplayName: String {
        #if os(iOS)
        return "iPhone"
        #else
        return "Mac"
        #endif
    }

    private static var microphoneSettingsName: String {
        #if os(iOS)
        return "Settings > Privacy & Security > Microphone"
        #else
        return "System Settings > Privacy & Security > Microphone"
        #endif
    }
}
