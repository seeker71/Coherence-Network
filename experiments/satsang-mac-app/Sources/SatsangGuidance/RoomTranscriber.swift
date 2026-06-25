import AVFoundation
import Foundation
import SatsangMacCore
import Speech

final class RoomTranscriber: @unchecked Sendable {
    var onStateChange: (@MainActor @Sendable (Bool, String) -> Void)?
    var onPartial: (@MainActor @Sendable (String) -> Void)?
    var onUtterance: (@MainActor @Sendable (TranscriptUtterance) -> Void)?

    private let workQueue = DispatchQueue(label: "earth.hati.satsang-guidance.room-transcriber")
    private let audioEngine = AVAudioEngine()
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en_US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var lastPartialText = ""
    private var inputTapInstalled = false

    func start() {
        SFSpeechRecognizer.requestAuthorization { [weak self] speechStatus in
            guard let self else { return }
            guard speechStatus == .authorized else {
                self.emitState(false, "Speech recognition permission is \(Self.speechStatusName(speechStatus)).")
                return
            }

            AVCaptureDevice.requestAccess(for: .audio) { granted in
                guard granted else {
                    self.emitState(false, "Microphone permission was not granted.")
                    return
                }
                self.workQueue.async {
                    self.startRecognition()
                }
            }
        }
    }

    func stop(commitPartial: Bool = true) {
        workQueue.async {
            if commitPartial {
                self.commitPartialIfNeeded()
            }
            self.stopRecognition()
            self.emitPartial("")
            self.emitState(false, "Listening stopped")
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
                    self.stopRecognition()
                    self.emitState(false, "Listening stopped: \(error.localizedDescription)")
                }
            }
        }

        emitState(true, "Listening to room mic")
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
