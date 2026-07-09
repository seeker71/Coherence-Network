import Foundation

// The mesh side: poll the deployed membrane for every organ's heartbeat. The web
// observatory can run underneath; this reads the same source natively.

struct Organ: Identifiable, Decodable {
    let organ_id: String
    let display_name: String?
    let organ_kind: String?
    let dwelling_name: String?
    let listening: Bool?
    let discovery_state: String?
    let last_seen_at: String?
    let trust_score_ppm: Int?
    let signal_strength_ppm: Int?
    let battery_level_ppm: Int?
    var id: String { organ_id }

    var name: String { display_name?.isEmpty == false ? display_name! : organ_id }

    // seconds since last heartbeat, parsed from the ISO8601 last_seen_at
    var ageSeconds: Double? {
        guard let s = last_seen_at else { return nil }
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = iso.date(from: s) { return Date().timeIntervalSince(d) }
        iso.formatOptions = [.withInternetDateTime]
        if let d = iso.date(from: s.replacingOccurrences(of: "+00:00", with: "Z")) {
            return Date().timeIntervalSince(d)
        }
        return nil
    }

    // present = listening and heard within the last 5 minutes
    var isPresent: Bool {
        (listening ?? false) && (ageSeconds ?? 1e9) < 300
    }
}

struct OrgansResponse: Decodable { let items: [Organ] }

@MainActor
final class MeshModel: ObservableObject {
    @Published var organs: [Organ] = []
    @Published var lastError: String? = nil
    @Published var fetchedAt: Date = .distantPast

    private let url = URL(string: "https://api.coherencycoin.com/api/hati/mesh/organs?limit=80")!

    func start() { Task { await loop() } }

    private func loop() async {
        while !Task.isCancelled {
            await refresh()
            try? await Task.sleep(nanoseconds: 3_000_000_000)
        }
    }

    func refresh() async {
        do {
            var req = URLRequest(url: url)
            req.timeoutInterval = 8
            let (data, _) = try await URLSession.shared.data(for: req)
            let resp = try JSONDecoder().decode(OrgansResponse.self, from: data)
            organs = resp.items.sorted { ($0.isPresent ? 0 : 1, $0.name) < ($1.isPresent ? 0 : 1, $1.name) }
            fetchedAt = Date()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }
}
