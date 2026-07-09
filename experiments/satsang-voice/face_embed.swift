// face_embed.swift — the face domain's native feature. Apple Vision has face DETECTION but no
// public face-EMBEDDING API, so we honor that floor: DETECT faces (VNDetectFaceRectangles),
// CROP each, then take VNGenerateImageFeaturePrint of the crop as the per-face embedding. It is
// a perceptual print over the face region, not a purpose-built faceprint — enough for nearest-
// centroid recognition of people we see often, distilled the same way voices are.
//
// Build: swiftc -O face_embed.swift -o face_embed
// Use:   ./face_embed frame.jpg  ->  [{"box":[x,y,w,h],"embedding":[..]}, ...]  (one per face)
import Foundation
import Vision
import ImageIO
import CoreImage

guard CommandLine.arguments.count > 1,
      let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: CommandLine.arguments[1]) as CFURL, nil),
      let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
    FileHandle.standardError.write("usage: face_embed <image>\n".data(using: .utf8)!); exit(1)
}
let W = cg.width, H = cg.height
let ci = CIImage(cgImage: cg)
let ctx = CIContext()

// 1. detect faces
let det = VNDetectFaceRectanglesRequest()
do { try VNImageRequestHandler(cgImage: cg, options: [:]).perform([det]) }
catch { FileHandle.standardError.write("detect failed\n".data(using: .utf8)!); exit(2) }
let faces = det.results ?? []

func featurePrint(_ image: CGImage) -> [Float]? {
    let req = VNGenerateImageFeaturePrintRequest()
    guard (try? VNImageRequestHandler(cgImage: image, options: [:]).perform([req])) != nil,
          let obs = req.results?.first as? VNFeaturePrintObservation else { return nil }
    var floats = [Float](repeating: 0, count: obs.elementCount)
    floats.withUnsafeMutableBytes { obs.data.copyBytes(to: $0) }
    return floats
}

var out: [[String: Any]] = []
for f in faces {
    // Vision boxes are normalized, origin bottom-left. Convert to pixel top-left crop.
    let bb = f.boundingBox
    let pad: CGFloat = 0.15
    let x = max(0, (bb.minX - pad) * CGFloat(W))
    let w = min(CGFloat(W) - x, (bb.width + 2 * pad) * CGFloat(W))
    let yTop = max(0, (1 - bb.maxY - pad) * CGFloat(H))
    let h = min(CGFloat(H) - yTop, (bb.height + 2 * pad) * CGFloat(H))
    let rect = CGRect(x: x, y: yTop, width: w, height: h)
    guard let crop = cg.cropping(to: rect) else { continue }
    guard let emb = featurePrint(crop) else { continue }
    out.append(["box": [Double(bb.minX), Double(bb.minY), Double(bb.width), Double(bb.height)],
                "embedding": emb.map { Double($0) }])
}
_ = ci; _ = ctx
let data = try JSONSerialization.data(withJSONObject: out)
print(String(data: data, encoding: .utf8)!)
