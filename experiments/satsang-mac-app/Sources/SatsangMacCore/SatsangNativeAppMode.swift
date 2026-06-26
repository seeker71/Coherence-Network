import Foundation

public enum SatsangNativeAppMode: String, CaseIterable, Codable, Identifiable, Sendable {
    case room
    case guidance
    case memory
    case health
    case learning
    case resources
    case settings

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .room:
            return "Room"
        case .guidance:
            return "Guidance"
        case .memory:
            return "Memory"
        case .health:
            return "Health"
        case .learning:
            return "Learning"
        case .resources:
            return "Resources"
        case .settings:
            return "Settings"
        }
    }
}

public struct SatsangNativeAppModeReceipt: Codable, Equatable, Sendable {
    public var kind: String
    public var modes: [String]
    public var defaultMode: String
    public var singleAppBody: String

    public init(
        modes: [SatsangNativeAppMode] = SatsangNativeAppMode.allCases,
        defaultMode: SatsangNativeAppMode = .room,
        singleAppBody: String = "form-native-satsang-guidance-body"
    ) {
        self.kind = "satsang-native-tabbed-app"
        self.modes = modes.map(\.rawValue)
        self.defaultMode = defaultMode.rawValue
        self.singleAppBody = singleAppBody
    }
}
