// vision_classify.swift — name what the camera sees, on-device, with confidence.
//
// Sibling of sound_classify.swift; a thin vision CARRIER. Apple's Vision framework classifies
// an image ON-DEVICE (~1000 scene/object classes) -> JSON [{label, confidence}]. These readings
// feed the SAME form-stdlib/recognition-router.fk that routes the sound carriers — a reading is
// a reading, whether the body heard it or saw it. Nothing leaves the Mac.
//
// Build: swiftc -O vision_classify.swift -o vision_classify
// Use:   ./vision_classify /path/to/frame.jpg   ->   [{"label":"person","confidence":0.9}, …]

import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count > 1,
      let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: CommandLine.arguments[1]) as CFURL, nil),
      let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else { print("[]"); exit(0) }
let request = VNClassifyImageRequest()
do {
    try VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
    let obs = (request.results ?? []).filter { $0.confidence > 0.1 }
                .sorted { $0.confidence > $1.confidence }.prefix(10)
    let arr = obs.map { ["label": $0.identifier, "confidence": Double($0.confidence)] as [String: Any] }
    print(String(data: try JSONSerialization.data(withJSONObject: arr), encoding: .utf8) ?? "[]")
} catch {
    FileHandle.standardError.write("vision error: \(error)\n".data(using: .utf8)!)
    print("[]")
}
