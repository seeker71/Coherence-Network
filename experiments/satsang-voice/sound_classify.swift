// sound_classify.swift — name the room's sounds, on-device, with confidence.
//
// A thin native CARRIER for the satsang voice interface: reads one audio file,
// runs Apple's built-in SoundAnalysis classifier (a few hundred everyday sounds —
// animals, music, instruments, environment), and prints the top matches as JSON
// [{"label","confidence"}, …]. Everything stays on this Mac; nothing uploaded.
//
// The confidence IS the honesty (lc-honest-lane): the body names what it hears
// only as far as it is sure. The Python carrier keeps matches above a threshold
// and lets the rest be silence — never an asserted match it doesn't carry.
//
// Build:  swiftc -O sound_classify.swift -o sound_classify
// Use:    ./sound_classify /path/to/chunk.wav   ->   [{"label":"speech","confidence":0.92}, …]

import Foundation
import SoundAnalysis

final class Collector: NSObject, SNResultsObserving {
    var best: [String: Float] = [:]   // label -> max confidence seen across the file's windows
    func request(_ request: SNRequest, didProduce result: SNResult) {
        guard let r = result as? SNClassificationResult else { return }
        for c in r.classifications where c.confidence > 0 {
            if (best[c.identifier] ?? 0) < Float(c.confidence) { best[c.identifier] = Float(c.confidence) }
        }
    }
}

func emit(_ obj: Any) {
    if let d = try? JSONSerialization.data(withJSONObject: obj, options: []),
       let s = String(data: d, encoding: .utf8) { print(s) } else { print("[]") }
}

guard CommandLine.arguments.count > 1 else { print("[]"); exit(0) }
let url = URL(fileURLWithPath: CommandLine.arguments[1])
do {
    let analyzer = try SNAudioFileAnalyzer(url: url)
    let request = try SNClassifySoundRequest(classifierIdentifier: .version1)
    let collector = Collector()
    try analyzer.add(request, withObserver: collector)
    analyzer.analyze()   // synchronous: delivers all window results, then returns
    let top = collector.best.sorted { $0.value > $1.value }.prefix(8)
    emit(top.map { ["label": $0.key, "confidence": Double($0.value)] as [String: Any] })
} catch {
    FileHandle.standardError.write("sound_classify error: \(error)\n".data(using: .utf8)!)
    print("[]")
}
