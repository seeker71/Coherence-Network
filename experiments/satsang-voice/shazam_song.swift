// shazam_song.swift — name the song playing, on-device signature, via ShazamKit.
//
// A thin native CARRIER for the presence listener: reads an audio file, generates a
// Shazam signature ON-DEVICE, and matches it against the catalog → JSON {title, artist}.
// Only a fingerprint leaves the machine (never your audio); a custom catalog would be
// fully offline. Build: swiftc -O shazam_song.swift -o shazam_song
// Use:   ./shazam_song /path/to/clip.wav   ->   {"matched":true,"title":"…","artist":"…"}

import Foundation
import ShazamKit
import AVFoundation

final class Matcher: NSObject, SHSessionDelegate {
    let sem: DispatchSemaphore
    var out = "{\"matched\": false}"
    init(_ s: DispatchSemaphore) { sem = s }
    func session(_ session: SHSession, didFind match: SHMatch) {
        if let it = match.mediaItems.first {
            let obj: [String: Any] = ["matched": true, "title": it.title ?? "", "artist": it.artist ?? ""]
            if let d = try? JSONSerialization.data(withJSONObject: obj) { out = String(data: d, encoding: .utf8)! }
        }
        sem.signal()
    }
    func session(_ session: SHSession, didNotFindMatchFor signature: SHSignature, error: Error?) {
        if let e = error {
            out = "{\"matched\": false, \"note\": \"" + e.localizedDescription.replacingOccurrences(of: "\"", with: "'") + "\"}"
        }
        sem.signal()
    }
}

guard CommandLine.arguments.count > 1 else { print("{}"); exit(0) }
let url = URL(fileURLWithPath: CommandLine.arguments[1])
do {
    let file = try AVAudioFile(forReading: url)
    let gen = SHSignatureGenerator()
    guard let buf = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: AVAudioFrameCount(file.length)) else { print("{}"); exit(1) }
    try file.read(into: buf)
    try gen.append(buf, at: nil)
    let sem = DispatchSemaphore(value: 0)
    let m = Matcher(sem)
    let session = SHSession()
    session.delegate = m
    session.match(gen.signature())
    _ = sem.wait(timeout: .now() + 15)
    print(m.out)
} catch {
    FileHandle.standardError.write("shazam error: \(error)\n".data(using: .utf8)!)
    print("{\"matched\": false}")
}
