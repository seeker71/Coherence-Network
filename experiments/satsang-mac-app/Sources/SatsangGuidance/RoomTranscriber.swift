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
            emitState(false, "Microphone permission is denied. Allow Satsang Guidance in System Settings > Privacy & Security > Microphone.")
        case .restricted:
            emitState(false, "Microphone permission is restricted on this Mac.")
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
            self.stopRecognition()
            self.emitPartial("")
            self.emitLevel(0)
            self.emitState(false, "Listening stopped")
        }
    }

    private func beginWithMicrophoneAccess() {
        workQueue.async {
            self.keepListening = true
            self.startMeteringOnly()
            self.requestSpeechAuthorization()
        }
    }

    private func requestSpeechAuthorization() {
        switch SFSpeechRecognizer.authorizationStatus() {
        case .authorized:
            startRecognition()
        case .notDetermined:
            emitState(true, "Room mic is active; requesting speech recognition permission")
            SFSpeechRecognizer.requestAuthorization { [weak self] speechStatus in
                guard let self else { return }
                self.workQueue.async {
                    self.handleSpeechAuthorization(speechStatus)
                }
            }
            workQueue.asyncAfter(deadline: .now() + 6.0) { [weak self] in
                guard let self, self.keepListening else { return }
                guard SFSpeechRecognizer.authorizationStatus() == .notDetermined else { return }
                self.emitState(true, "Room mic is active; waiting for speech recognition permission")
            }
        case .denied:
            emitState(true, "Room mic is active; Speech Recognition permission is denied.")
        case .restricted:
            emitState(true, "Room mic is active; Speech Recognition is restricted on this Mac.")
        @unknown default:
            emitState(true, "Room mic is active; Speech Recognition permission is unavailable.")
        }
    }

    private func handleSpeechAuthorization(_ speechStatus: SFSpeechRecognizerAuthorizationStatus) {
        guard keepListening else { return }
        if speechStatus == .authorized {
            startRecognition()
        } else {
            emitState(true, "Room mic is active; Speech Recognition permission is \(Self.speechStatusName(speechStatus)).")
        }
    }

    private func startMeteringOnly() {
        stopRecognition()

        let inputNode = audioEngine.inputNode
        let format = inputNode.outputFormat(forBus: 0)
        guard format.sampleRate > 0 else {
            emitState(false, "No microphone input format is available.")
            return
        }

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            self?.reportLevel(buffer)
        }
        inputTapInstalled = true

        audioEngine.prepare()
        do {
            try audioEngine.start()
            emitState(true, "Room mic is active; preparing speech recognition")
        } catch {
            stopRecognition()
            emitState(false, "Microphone start failed: \(error.localizedDescription)")
        }
    }

    private func startRecognition() {
        stopRecognition()

        guard let speechRecognizer else {
            emitState(false, "Speech recognizer is unavailable for this locale.")
            return
        }
        guard speechRecognizer.isAvailable else {
            emitState(false, "Speech recognizer is not available right now.")
            return
        }

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.taskHint = .dictation
        if #available(macOS 13.0, *) {
            request.addsPunctuation = true
        }
        recognitionRequest = request
        lastPartialText = ""

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

        audioEngine.prepare()
        do {
            try audioEngine.start()
        } catch {
            stopRecognition()
            emitState(false, "Microphone start failed: \(error.localizedDescription)")
            return
        }

        recognitionTask = speechRecognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let result {
                let text = result.bestTranscription.formattedString
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                self.lastPartialText = text
                self.emitPartial(text)
                if result.isFinal {
                    self.emitUtterance(text)
                    self.lastPartialText = ""
                    self.emitPartial("")
                }
            }
            if let error {
                self.workQueue.async {
                    self.handleRecognitionError(error)
                }
            }
        }

        emitState(true, "Listening to room mic")
    }

    private func handleRecognitionError(_ error: Error) {
        commitPartialIfNeeded()
        stopRecognition()
        emitPartial("")

        guard keepListening else {
            emitLevel(0)
            emitState(false, "Listening stopped: \(error.localizedDescription)")
            return
        }

        emitState(true, "Listening to room mic, waiting for speech")
        workQueue.asyncAfter(deadline: .now() + 0.35) { [weak self] in
            guard let self, self.keepListening else { return }
            self.startRecognition()
        }
    }

    private func stopRecognition() {
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil

        if audioEngine.isRunning {
            audioEngine.stop()
        }
        if inputTapInstalled {
            audioEngine.inputNode.removeTap(onBus: 0)
            inputTapInstalled = false
        }
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
}
