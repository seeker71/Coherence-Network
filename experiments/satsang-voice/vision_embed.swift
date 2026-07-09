// vision_embed.swift — the NATIVE feature the student learns on. VNGenerateImageFeaturePrint
// gives an on-device feature vector (VNFeaturePrintObservation) — NOT the oracle's ~1000-class
// label head, but the raw perceptual embedding beneath it. The native classifier is nearest-
// centroid over these vectors, its labels distilled from the oracle. When it can name a frame
// the oracle never labelled, from the embedding alone, it has learned the invariant (learning-
// witness.fk), and the oracle becomes falsework to be struck.
//
// Build: swiftc -O vision_embed.swift -o vision_embed
// Use:   ./vision_embed frame.jpg   ->   0.12,-0.03,...  (comma-joined floats)
import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count > 1,
      let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: CommandLine.arguments[1]) as CFURL, nil),
      let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
    FileHandle.standardError.write("usage: vision_embed <image>\n".data(using: .utf8)!); exit(1)
}
let req = VNGenerateImageFeaturePrintRequest()
do { try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req]) }
catch { FileHandle.standardError.write("vision failed\n".data(using: .utf8)!); exit(2) }
guard let obs = req.results?.first as? VNFeaturePrintObservation else { exit(3) }
let n = obs.elementCount
var floats = [Float](repeating: 0, count: n)
floats.withUnsafeMutableBytes { obs.data.copyBytes(to: $0) }
print(floats.map { String(format: "%.5f", $0) }.joined(separator: ","))
