import SwiftUI
import AVFoundation
import CoreImage
import ImageIO
import UniformTypeIdentifiers
import Vision

// Camera — this Mac's eye, wired into the recognition pipeline. A still every ~20s (energy-light,
// not a stream), written to the face and vision inboxes the producers already drain. The macOS
// camera indicator lights whenever a frame is grabbed — the seeing is never hidden. Consent is
// standing (eyes-open, on his own device); the toggle is here so it can also rest.

private let cameraIntervalSec: Double = 20

@MainActor
final class CameraModel: NSObject, ObservableObject {
    @Published var running = false
    @Published var framesSaved = 0
    @Published var lastFrameAt: Date? = nil
    @Published var status = "camera idle"
    // Live eye: normalized face rects (Vision boundingBox), published only while a preview is on
    // screen so the Recognition room can draw boxes over the live feed. "Who" stays the feed's job.
    @Published var faceRects: [CGRect] = []
    // AVFoundation session objects are thread-safe; the capture queue touches them off the main actor
    nonisolated(unsafe) private let session = AVCaptureSession()
    nonisolated(unsafe) private let output = AVCaptureVideoDataOutput()
    nonisolated(unsafe) private let ctx = CIContext()
    private let queue = DispatchQueue(label: "earth.hati.camera")
    // owned by the serial capture queue only — safe there
    nonisolated(unsafe) private var lastCapture = Date(timeIntervalSince1970: 0)
    // Live-preview gate: face detection runs ONLY while the eye is shown (energy-light ethos held).
    nonisolated(unsafe) private var previewing = false
    nonisolated(unsafe) private var lastFaceAt = Date(timeIntervalSince1970: 0)

    /// The running session, for an on-screen live preview (AVCaptureVideoPreviewLayer). The same eye
    /// that offers stills to the pipeline — one organ, now also watchable.
    var previewSession: AVCaptureSession { session }

    /// Turn live face-boxing on/off — the room calls this on appear/disappear so detection only runs
    /// while you are actually watching the eye.
    func setPreviewing(_ on: Bool) {
        queue.async { [weak self] in self?.previewing = on }
        if !on { faceRects = [] }
    }

    private let faceInbox = URL(fileURLWithPath: NSHomeDirectory() + "/.coherence-network/face-training/inbox")
    private let visionInbox = URL(fileURLWithPath: NSHomeDirectory() + "/.coherence-network/vision-training/inbox")

    func start() {
        guard !running else { return }
        try? FileManager.default.createDirectory(at: faceInbox, withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: visionInbox, withIntermediateDirectories: true)
        AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
            Task { @MainActor in granted ? self?.configure() : (self?.status = "camera not granted") }
        }
    }

    private func configure() {
        session.beginConfiguration()
        session.sessionPreset = .high
        guard let dev = AVCaptureDevice.default(for: .video),
              let input = try? AVCaptureDeviceInput(device: dev), session.canAddInput(input) else {
            status = "no camera"; session.commitConfiguration(); return
        }
        session.addInput(input)
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        output.alwaysDiscardsLateVideoFrames = true
        output.setSampleBufferDelegate(self, queue: queue)
        if session.canAddOutput(output) { session.addOutput(output) }
        session.commitConfiguration()
        queue.async { [weak self] in self?.session.startRunning() }
        running = true
        status = "camera live — a frame every \(Int(cameraIntervalSec))s"
    }

    func stop() {
        guard running else { return }
        queue.async { [weak self] in self?.session.stopRunning() }
        running = false
        status = "camera resting"
    }

    fileprivate func write(_ image: CGImage) {
        let data = NSMutableData()
        guard let dst = CGImageDestinationCreateWithData(data, UTType.jpeg.identifier as CFString, 1, nil) else { return }
        CGImageDestinationAddImage(dst, image, [kCGImageDestinationLossyCompressionQuality as String: 0.85] as CFDictionary)
        guard CGImageDestinationFinalize(dst) else { return }
        let name = "mac-\(Int(Date().timeIntervalSince1970)).jpg"
        try? (data as Data).write(to: faceInbox.appendingPathComponent(name))
        try? (data as Data).write(to: visionInbox.appendingPathComponent(name))
        framesSaved += 1; lastFrameAt = Date()
        status = "camera live — \(framesSaved) frames offered"
    }
}

extension CameraModel: AVCaptureVideoDataOutputSampleBufferDelegate {
    nonisolated func captureOutput(_ o: AVCaptureOutput, didOutput buf: CMSampleBuffer, from c: AVCaptureConnection) {
        guard let px = CMSampleBufferGetImageBuffer(buf) else { return }
        let now = Date()
        // Live eye — only while the room shows the preview; ~4/s, just face rectangles so the boxes
        // stay live. Runs before the 20s still gate so it isn't starved by it.
        if previewing, now.timeIntervalSince(lastFaceAt) >= 0.25 {
            lastFaceAt = now
            let req = VNDetectFaceRectanglesRequest()
            try? VNImageRequestHandler(cvPixelBuffer: px, orientation: .up, options: [:]).perform([req])
            let rects = (req.results ?? []).map { $0.boundingBox }
            Task { @MainActor in self.faceRects = rects }
        }
        // Energy-light still every 20s → the face/vision inboxes (unchanged).
        guard now.timeIntervalSince(lastCapture) >= cameraIntervalSec else { return }
        lastCapture = now
        let ci = CIImage(cvPixelBuffer: px)
        guard let cg = ctx.createCGImage(ci, from: ci.extent) else { return }
        Task { @MainActor in self.write(cg) }
    }
}
