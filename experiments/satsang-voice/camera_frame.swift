// camera_frame.swift — grab ONE still from the default camera and write it to a path. The
// visible-light witness for the face domain, energy-light: one frame on demand, not a stream.
// The camera indicator lights while it captures — recording is never hidden.
//
// Build: swiftc -O camera_frame.swift -o camera_frame
// Use:   ./camera_frame /path/out.jpg    (exit 0 on success)
// Note:  needs Camera permission (TCC) for whatever process runs it. Under launchd, grant it
//        in System Settings > Privacy > Camera, or feed frames from the app instead.
import Foundation
import AVFoundation
import CoreImage

let out = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "/tmp/frame.jpg"

let session = AVCaptureSession()
session.sessionPreset = .photo
guard let dev = AVCaptureDevice.default(for: .video),
      let input = try? AVCaptureDeviceInput(device: dev), session.canAddInput(input) else {
    FileHandle.standardError.write("no camera / no access\n".data(using: .utf8)!); exit(1)
}
session.addInput(input)
let photoOut = AVCapturePhotoOutput()
guard session.canAddOutput(photoOut) else { FileHandle.standardError.write("no output\n".data(using: .utf8)!); exit(2) }
session.addOutput(photoOut)
session.startRunning()

final class Shooter: NSObject, AVCapturePhotoCaptureDelegate {
    let out: String; let done: (Bool) -> Void
    init(out: String, done: @escaping (Bool) -> Void) { self.out = out; self.done = done }
    func photoOutput(_ o: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        guard error == nil, let data = photo.fileDataRepresentation() else { done(false); return }
        done((try? data.write(to: URL(fileURLWithPath: out))) != nil)
    }
}

let sema = DispatchSemaphore(value: 0)
var ok = false
let shooter = Shooter(out: out) { success in ok = success; sema.signal() }
// let exposure settle briefly, then shoot
DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
    photoOut.capturePhoto(with: AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg]), delegate: shooter)
}
DispatchQueue.global().async { RunLoop.current.run(until: Date().addingTimeInterval(5)) }
_ = sema.wait(timeout: .now() + 6)
session.stopRunning()
exit(ok ? 0 : 3)
