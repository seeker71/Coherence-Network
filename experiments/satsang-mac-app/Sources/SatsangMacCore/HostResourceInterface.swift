import Foundation

public protocol HostResourceInterface: Sendable {
    var homeDirectory: URL { get }
    var currentDirectory: URL { get }

    func fileExists(at url: URL) -> Bool
    func isExecutableFile(at url: URL) -> Bool
    func readData(from url: URL) throws -> Data?
    func writeData(_ data: Data, to url: URL, options: Data.WritingOptions) throws
    func appendLine(_ data: Data, to url: URL) throws
    func createDirectory(at url: URL) throws
    func runExecutable(at url: URL, workingDirectory: URL, standardInput: String) throws -> String
}

public struct FoundationHostResourceInterface: HostResourceInterface {
    public init() {}

    public var homeDirectory: URL {
        FileManager.default.homeDirectoryForCurrentUser
    }

    public var currentDirectory: URL {
        URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    }

    public func fileExists(at url: URL) -> Bool {
        FileManager.default.fileExists(atPath: url.path)
    }

    public func isExecutableFile(at url: URL) -> Bool {
        FileManager.default.isExecutableFile(atPath: url.path)
    }

    public func readData(from url: URL) throws -> Data? {
        guard fileExists(at: url) else { return nil }
        return try Data(contentsOf: url)
    }

    public func writeData(_ data: Data, to url: URL, options: Data.WritingOptions = .atomic) throws {
        try createDirectory(at: url.deletingLastPathComponent())
        try data.write(to: url, options: options)
    }

    public func appendLine(_ data: Data, to url: URL) throws {
        try createDirectory(at: url.deletingLastPathComponent())
        if !fileExists(at: url) {
            FileManager.default.createFile(atPath: url.path, contents: nil)
        }
        let handle = try FileHandle(forWritingTo: url)
        defer { try? handle.close() }
        try handle.seekToEnd()
        try handle.write(contentsOf: data)
        try handle.write(contentsOf: Data("\n".utf8))
    }

    public func createDirectory(at url: URL) throws {
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    }

    public func runExecutable(at url: URL, workingDirectory: URL, standardInput: String) throws -> String {
        let process = Process()
        let input = Pipe()
        let output = Pipe()
        process.executableURL = url
        process.currentDirectoryURL = workingDirectory
        process.standardInput = input
        process.standardOutput = output
        process.standardError = output

        try process.run()
        try input.fileHandleForWriting.write(contentsOf: Data(standardInput.utf8))
        try input.fileHandleForWriting.close()
        process.waitUntilExit()

        let data = output.fileHandleForReading.readDataToEndOfFile()
        return String(decoding: data, as: UTF8.self)
    }
}

public struct FormHostBoundaryReceipt: Codable, Equatable, Sendable {
    public var kind: String
    public var sharedLogic: String
    public var hostCarrier: String
    public var resourceInterface: String
    public var platformTargets: [String]
    public var allowedResourceKinds: [String]
    public var appBoundaryRuntimes: [String]
    public var forbiddenRuntimeCarriers: [String]

    public init(
        sharedLogic: String = "form-native-shared-logic",
        hostCarrier: String = "swift-minimal-host-carrier",
        resourceInterface: String = "host-os-generic-resource-interface",
        platformTargets: [String] = ["macos", "windows", "android"],
        allowedResourceKinds: [String] = [
            "audio-input",
            "speech-transcript",
            "file-read",
            "file-append",
            "file-write-atomic",
            "process-stdin-stdout"
        ],
        appBoundaryRuntimes: [String] = ["form", "swift-minimal-host-carrier"],
        forbiddenRuntimeCarriers: [String] = ["python", "go", "rust", "typescript"]
    ) {
        self.kind = "form-native-host-boundary"
        self.sharedLogic = sharedLogic
        self.hostCarrier = hostCarrier
        self.resourceInterface = resourceInterface
        self.platformTargets = platformTargets
        self.allowedResourceKinds = allowedResourceKinds
        self.appBoundaryRuntimes = appBoundaryRuntimes
        self.forbiddenRuntimeCarriers = forbiddenRuntimeCarriers
    }

    public var usesOnlyAllowedAppRuntimes: Bool {
        let allowed = Set(["form", "swift-minimal-host-carrier"])
        return appBoundaryRuntimes.allSatisfy { allowed.contains($0) }
            && forbiddenRuntimeCarriers.allSatisfy { !appBoundaryRuntimes.contains($0) }
    }
}
