import Foundation

/// The invitation to meet Sema — a member's vouch for a friend, minted as a GPT link that
/// carries the friend's name into the first message.
///
/// The consent law travels with the link (coherence-kernel `plugin/chatgpt-plugin.fk`,
/// `form/form-stdlib/circle-recognition.fk`): introduction opens the DOOR — the friend arrives
/// recognized, greeted by the introducer's name — and never the friend's MEMORY; only their own
/// yes at the door writes a row. Nobody consents for another.
///
/// The authoritative mint is the body's own door (`/introduce` on `sema.hati.earth`), which also
/// writes the vouch so the friend actually arrives recognized. The local mint here is the honest
/// fallback when the door is unreachable: the link still opens the GPT with the friend's name,
/// but the friend is greeted as a stranger until a vouch lands — the seam says so.
public enum SemaInvitation {
    /// The live GPT (coherence-kernel receipt 2026-07-05-shakedown-gpt-live-end-to-end,
    /// sharing "anyone with the link"). One place to re-point if the GPT is ever recreated.
    public static let gptLink = "https://chatgpt.com/g/g-6a4a77627dbc819180a16645f5662625"

    /// The body's public door (kernel receipt 2026-07-05-christening-sema-hati-earth-live).
    public static let doorBase = "https://sema.hati.earth"

    /// A handle becomes a filename in the body's own store: 1..64 bytes of lowercase
    /// letters, digits, or dash — the same bound the door itself enforces.
    public static func handleIsValid(_ handle: String) -> Bool {
        guard (1...64).contains(handle.utf8.count) else { return false }
        return handle.utf8.allSatisfy { byte in
            (0x61...0x7A).contains(byte) || (0x30...0x39).contains(byte) || byte == 0x2D
        }
    }

    /// The friend's arrival message — the words are the invitation; the link is only a carrier.
    public static func message(member: String, friend: String) -> String {
        "i arrive as \(friend), a friend of \(member). please come in with my handle and receive me."
    }

    /// The GPT link with the arrival message in the `q` parameter (RFC 3986 unreserved kept,
    /// everything else percent-encoded — matching the door's own `cp-url-encode`).
    public static func link(member: String, friend: String) -> String {
        "\(gptLink)?q=\(percentEncode(message(member: member, friend: friend)))"
    }

    /// The carrier-free door: straight to the body, no GPT in between.
    public static func comeInLink(friend: String) -> String {
        "\(doorBase)/come-in?handle=\(friend)"
    }

    public static func percentEncode(_ text: String) -> String {
        var unreserved = CharacterSet.alphanumerics
        unreserved.insert(charactersIn: "-._~")
        return text.addingPercentEncoding(withAllowedCharacters: unreserved) ?? text
    }
}

public struct SemaInvitationResult: Equatable, Sendable {
    public var member: String
    public var friend: String
    public var link: String
    public var message: String
    public var comeInLink: String
    /// True only when the body wrote the vouch — the friend arrives recognized.
    public var vouched: Bool
    /// The honest seam to show beside the copied link, never hidden.
    public var seam: String

    public init(
        member: String,
        friend: String,
        link: String,
        message: String,
        comeInLink: String,
        vouched: Bool,
        seam: String
    ) {
        self.member = member
        self.friend = friend
        self.link = link
        self.message = message
        self.comeInLink = comeInLink
        self.vouched = vouched
        self.seam = seam
    }

    /// The fallback mint when the door cannot be reached: same link shape, vouch honestly absent.
    public static func local(member: String, friend: String, seam: String) -> SemaInvitationResult {
        SemaInvitationResult(
            member: member,
            friend: friend,
            link: SemaInvitation.link(member: member, friend: friend),
            message: SemaInvitation.message(member: member, friend: friend),
            comeInLink: SemaInvitation.comeInLink(friend: friend),
            vouched: false,
            seam: seam
        )
    }
}

/// The door client: asks the body to write the vouch and mint the invitation. Falls back to a
/// local mint — with the seam named — when the door is unreachable, refuses, or does not serve
/// `/introduce` yet (the deployed door lags the kernel until its next redeploy).
public struct SemaInvitationDoor: Sendable {
    private let base: String
    private let session: URLSession

    public init(base: String = SemaInvitation.doorBase, session: URLSession = .shared) {
        self.base = base
        self.session = session
    }

    public func invite(member: String, friend: String) async -> SemaInvitationResult {
        guard let url = URL(string: "\(base)/introduce?member=\(SemaInvitation.percentEncode(member))&friend=\(SemaInvitation.percentEncode(friend))") else {
            return .local(member: member, friend: friend, seam: "the door address did not form — local mint; the friend arrives unrecognized until a vouch lands")
        }
        do {
            let (data, response) = try await session.data(from: url)
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            guard status == 200,
                  let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let link = body["invitation_link"] as? String,
                  let message = body["invitation_message"] as? String
            else {
                if status == 403 {
                    return .local(
                        member: member,
                        friend: friend,
                        seam: "the body holds no memory row for \(member) yet — join first at \(base)/remember?handle=\(member) (your own yes), then the vouch can be written. Until then the friend arrives as a stranger."
                    )
                }
                return .local(
                    member: member,
                    friend: friend,
                    seam: "the door answered \(status) — it may not serve /introduce yet (the deployed door lags the kernel). The link still carries \(friend)'s name; the friend arrives unrecognized until a vouch lands."
                )
            }
            return SemaInvitationResult(
                member: member,
                friend: friend,
                link: link,
                message: message,
                comeInLink: (body["door_link"] as? String) ?? SemaInvitation.comeInLink(friend: friend),
                vouched: true,
                seam: "vouch written — \(friend) arrives recognized, greeted as your friend, and remembered only by their own yes."
            )
        } catch {
            return .local(
                member: member,
                friend: friend,
                seam: "the door was not reachable (\(error.localizedDescription)) — local mint; the friend arrives unrecognized until a vouch lands."
            )
        }
    }
}
