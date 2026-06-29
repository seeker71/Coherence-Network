// Sensing — the carrier eye. AVFoundation captures frames; Swift reduces each frame
// to a thin 16x16 luminance grid, then to two integers: grid-average brightness
// (presence/where) and frame-diff salience (surprise magnitude). The DECISIONS over
// those integers — present? and surprised? — run in fkwu (FkwuSense). The baseline
// the salience is measured against tracks by a sign step, mirroring ambient-surprise's
// integer sign-LMS as-refine. Carrier thin: this file measures, fkwu decides.

import AVFoundation
import CoreImage
import Combine
import Foundation

struct SurpriseEvent: Identifiable {
    let id = UUID()
    let at: Date
    let salience: Int
    let brightness: Int
}

@MainActor
final class SenseModel: NSObject, ObservableObject {
    // Live readings (the "what is being sensed" block).
    @Published var present: Bool = false
    @Published var brightness: Int = 0          // 0..255 grid-average luminance
    @Published var surprise: Int = 0            // carrier-computed salience magnitude
    @Published var surprised: Bool = false      // fkwu's as-surprise? verdict this tick
    @Published var cameraState: String = "warming the eye…"
    @Published var recipeNative: Bool = false   // last gate came from fkwu on metal
    @Published var lastExpr: String = ""
    @Published var frameCount: Int = 0

    @Published var events: [SurpriseEvent] = []

    // Inquiry-plane probe readings (filled live so a tap shows the current sense).
    @Published var sceneNote: String = "a lit/dark field (no VLM yet)"

    // Gate parameters — the same thresholds the phone used.
    let presenceThreshold = 50
    let surpriseTolerance = 18

    // The capture session lives on the eye queue, not the main actor — its mutating
    // calls (configure/start/stop) all run there.
    private nonisolated(unsafe) let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "earth.hati.coherence-sense.eye")

    // Per-frame state, touched ONLY on the capture queue (nonisolated). Kept off the
    // main actor so the hot path never hops threads to read its own scratch.
    private nonisolated(unsafe) var lastGrid: [Int]? = nil
    private nonisolated(unsafe) var lastSenseAtNS: Date = .distantPast
    private nonisolated(unsafe) var baselineNS: Int = -1
    private nonisolated(unsafe) var lastEventAtNS: Date = .distantPast

    func start() {
        AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
            Task { @MainActor in
                guard let self else { return }
                if granted {
                    self.configureAndRun()
                } else {
                    self.cameraState = "camera held — grant it in System Settings ▸ Privacy ▸ Camera"
                }
            }
        }
    }

    private func configureAndRun() {
        queue.async { [weak self] in
            guard let self else { return }
            self.session.beginConfiguration()
            self.session.sessionPreset = .vga640x480
            guard let dev = AVCaptureDevice.default(for: .video),
                  let input = try? AVCaptureDeviceInput(device: dev),
                  self.session.canAddInput(input)
            else {
                Task { @MainActor in self.cameraState = "no camera available" }
                self.session.commitConfiguration()
                return
            }
            self.session.addInput(input)
            let out = AVCaptureVideoDataOutput()
            out.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
            out.alwaysDiscardsLateVideoFrames = true
            out.setSampleBufferDelegate(self, queue: self.queue)
            if self.session.canAddOutput(out) { self.session.addOutput(out) }
            self.session.commitConfiguration()
            self.session.startRunning()
            Task { @MainActor in self.cameraState = "eye open — sensing" }
        }
    }

    func stop() {
        queue.async { [weak self] in self?.session.stopRunning() }
    }
}

extension SenseModel: AVCaptureVideoDataOutputSampleBufferDelegate {
    nonisolated func captureOutput(_ output: AVCaptureOutput,
                                   didOutput sampleBuffer: CMSampleBuffer,
                                   from connection: AVCaptureConnection) {
        guard let px = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        CVPixelBufferLockBaseAddress(px, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(px, .readOnly) }
        let w = CVPixelBufferGetWidth(px)
        let h = CVPixelBufferGetHeight(px)
        let bpr = CVPixelBufferGetBytesPerRow(px)
        guard let base = CVPixelBufferGetBaseAddress(px)?.assumingMemoryBound(to: UInt8.self) else { return }

        // Thin 16x16 luminance grid — all the body needs.
        let G = 16
        var grid = [Int](repeating: 0, count: G * G)
        var sum = 0
        for gy in 0..<G {
            for gx in 0..<G {
                let off = (gy * h / G) * bpr + (gx * w / G) * 4
                let v = (Int(base[off]) + Int(base[off + 1]) + Int(base[off + 2])) / 3 // BGR avg
                grid[gy * G + gx] = v
                sum += v
            }
        }
        let avgBrightness = sum / (G * G)
        let prev = self.lastGrid
        self.lastGrid = grid

        // Throttle BEFORE spending an fkwu spawn — sense at most ~3x/sec.
        let now = Date()
        guard now.timeIntervalSince(self.lastSenseAtNS) >= 0.33 else { return }
        self.lastSenseAtNS = now

        // Carrier-computed salience magnitude: mean absolute frame-diff (abs(reading - baseline)
        // shape from ambient-surprise as-salience, computed in Swift because the curated
        // loop-table vocabulary carries `le`/`sub` but not `abs`).
        var sal = 0
        if let p = prev {
            var s = 0
            for i in 0..<grid.count { let d = grid[i] - p[i]; s += d < 0 ? -d : d }
            sal = s / grid.count
        }

        // The two DECISIONS run in fkwu on metal.
        let pres = FkwuSense.sensePresence(luma: avgBrightness, threshold: self.presenceThreshold)
        let surp = FkwuSense.senseSurprise(salience: sal, tolerance: self.surpriseTolerance)

        // ambient-surprise as-refine: step the baseline one toward the reading (queue-local).
        if self.baselineNS < 0 { self.baselineNS = avgBrightness }
        else if avgBrightness > self.baselineNS { self.baselineNS += 1 }
        else if avgBrightness < self.baselineNS { self.baselineNS -= 1 }

        // Decide a logged event on the capture queue (debounced), publish to UI below.
        let surprised = (surp.value == 1)
        var newEvent: SurpriseEvent? = nil
        if surprised && now.timeIntervalSince(self.lastEventAtNS) > 0.8 {
            self.lastEventAtNS = now
            newEvent = SurpriseEvent(at: now, salience: sal, brightness: avgBrightness)
        }

        Task { @MainActor in
            self.frameCount += 1
            self.brightness = avgBrightness
            self.surprise = sal
            self.present = (pres.value == 1)
            self.surprised = surprised
            self.recipeNative = pres.native && surp.native
            self.lastExpr = surp.expr
            self.sceneNote = avgBrightness >= self.presenceThreshold
                ? "a lit field, presence likely (brightness \(avgBrightness)/255)"
                : "a dim/dark field (brightness \(avgBrightness)/255)"

            if let ev = newEvent {
                self.events.insert(ev, at: 0)
                if self.events.count > 100 { self.events.removeLast() }
                NotificationCenter.default.post(name: .surpriseSpike, object: ev.salience)
            }
        }
    }
}

extension Notification.Name {
    static let surpriseSpike = Notification.Name("earth.hati.coherence-sense.surpriseSpike")
}
