import Foundation

public enum HostResourceError: Error, LocalizedError, Sendable {
    case processExecutionUnsupported(platform: String)

    public var errorDescription: String? {
        switch self {
        case .processExecutionUnsupported(let platform):
            return "Process stdin/stdout execution is not available on \(platform)."
        }
    }
}

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
    func detectResourceDoors(transcriptURL: URL, queueURL: URL, formCLIURL: URL?) -> [HostResourceDoor]
}

public struct HostResourceDoor: Codable, Equatable, Sendable {
    public var kind: String
    public var state: String
    public var carrier: String
    public var detail: String

    public init(kind: String, state: String, carrier: String, detail: String = "") {
        self.kind = kind
        self.state = state
        self.carrier = carrier
        self.detail = detail
    }
}

public struct HostPlatformCarrier: Codable, Equatable, Sendable {
    public var platform: String
    public var hostCarrier: String
    public var resourceInterface: String
    public var resourceDoors: [HostResourceDoor]

    public init(
        platform: String,
        hostCarrier: String,
        resourceInterface: String,
        resourceDoors: [HostResourceDoor]
    ) {
        self.platform = platform
        self.hostCarrier = hostCarrier
        self.resourceInterface = resourceInterface
        self.resourceDoors = resourceDoors
    }

    public var doorSummary: String {
        resourceDoors
            .map { "\($0.kind):\($0.carrier)" }
            .joined(separator: ",")
    }

    public static func resolvedDefaults(resourceInterface: String = "host-os-generic-resource-interface") -> [HostPlatformCarrier] {
        [
            HostPlatformCarrier(
                platform: "macos",
                hostCarrier: "swift-minimal-host-carrier",
                resourceInterface: resourceInterface,
                resourceDoors: [
                    HostResourceDoor(kind: "audio-input", state: "declared", carrier: "macos-avfoundation", detail: "AVAudioEngine input node"),
                    HostResourceDoor(kind: "speech-transcript", state: "declared", carrier: "macos-speech", detail: "SFSpeechRecognizer side channel fed during live capture"),
                    HostResourceDoor(kind: "file-read", state: "declared", carrier: "macos-foundation-filemanager", detail: "FileManager/Data"),
                    HostResourceDoor(kind: "file-append", state: "declared", carrier: "macos-foundation-filehandle", detail: "FileHandle append"),
                    HostResourceDoor(kind: "file-write-atomic", state: "declared", carrier: "macos-foundation-data-atomic", detail: "Data.write atomic"),
                    HostResourceDoor(kind: "process-stdin-stdout", state: "declared", carrier: "macos-foundation-process", detail: "Process with pipes"),
                    HostResourceDoor(kind: "health-samples", state: "declared", carrier: "macos-healthkit-unavailable", detail: "iPhone HealthKit carrier records direct wearable samples"),
                ]
            ),
            HostPlatformCarrier(
                platform: "windows",
                hostCarrier: "windows-minimal-host-carrier",
                resourceInterface: resourceInterface,
                resourceDoors: [
                    HostResourceDoor(kind: "audio-input", state: "declared", carrier: "windows-wasapi-capture", detail: "WASAPI shared input"),
                    HostResourceDoor(kind: "speech-transcript", state: "declared", carrier: "windows-speechrecognizer", detail: "Windows speech recognition side channel fed during live capture"),
                    HostResourceDoor(kind: "file-read", state: "declared", carrier: "windows-known-folder-filesystem", detail: "LocalAppData file read"),
                    HostResourceDoor(kind: "file-append", state: "declared", carrier: "windows-known-folder-filesystem", detail: "LocalAppData append"),
                    HostResourceDoor(kind: "file-write-atomic", state: "declared", carrier: "windows-replacefile-atomic", detail: "atomic replace"),
                    HostResourceDoor(kind: "process-stdin-stdout", state: "declared", carrier: "windows-createprocess-stdin-stdout", detail: "CreateProcessW pipes"),
                    HostResourceDoor(kind: "health-samples", state: "declared", carrier: "windows-health-export-import", detail: "bounded local import/export carrier until a native health store exists"),
                ]
            ),
            HostPlatformCarrier(
                platform: "android",
                hostCarrier: "android-minimal-host-carrier",
                resourceInterface: resourceInterface,
                resourceDoors: [
                    HostResourceDoor(kind: "audio-input", state: "declared", carrier: "android-audiorecord", detail: "AudioRecord with RECORD_AUDIO"),
                    HostResourceDoor(kind: "speech-transcript", state: "declared", carrier: "android-speechrecognizer", detail: "android.speech.SpeechRecognizer side channel fed during live capture"),
                    HostResourceDoor(kind: "file-read", state: "declared", carrier: "android-app-private-files", detail: "Context.filesDir read"),
                    HostResourceDoor(kind: "file-append", state: "declared", carrier: "android-app-private-files", detail: "Context.filesDir append"),
                    HostResourceDoor(kind: "file-write-atomic", state: "declared", carrier: "android-atomic-file", detail: "AtomicFile or rename"),
                    HostResourceDoor(kind: "process-stdin-stdout", state: "declared", carrier: "android-packaged-form-cli-process", detail: "packaged native form-cli with bounded pipes"),
                    HostResourceDoor(kind: "health-samples", state: "declared", carrier: "android-health-connect", detail: "Health Connect read door after explicit permission"),
                ]
            ),
            HostPlatformCarrier(
                platform: "ios",
                hostCarrier: "iphone-minimal-host-carrier",
                resourceInterface: resourceInterface,
                resourceDoors: [
                    HostResourceDoor(kind: "audio-input", state: "declared", carrier: "ios-avfoundation", detail: "AVAudioEngine with AVAudioSession record permission"),
                    HostResourceDoor(kind: "speech-transcript", state: "declared", carrier: "ios-speech", detail: "SFSpeechRecognizer side channel fed during live capture"),
                    HostResourceDoor(kind: "file-read", state: "declared", carrier: "ios-app-sandbox-files", detail: "FileManager/Data in app container"),
                    HostResourceDoor(kind: "file-append", state: "declared", carrier: "ios-app-sandbox-files", detail: "FileHandle append in app container"),
                    HostResourceDoor(kind: "file-write-atomic", state: "declared", carrier: "ios-foundation-data-atomic", detail: "Data.write atomic in app container"),
                    HostResourceDoor(kind: "process-stdin-stdout", state: "declared", carrier: "ios-embedded-form-cli-adapter", detail: "same protocol via embedded Form runtime adapter; arbitrary subprocess unavailable"),
                    HostResourceDoor(kind: "health-samples", state: "declared", carrier: "ios-healthkit", detail: "HealthKit read door for Oura/Oz/O2 wearable samples after explicit permission"),
                ]
            ),
        ]
    }
}

public struct FoundationHostResourceInterface: HostResourceInterface {
    public init() {}

    public var homeDirectory: URL {
        #if os(iOS) || os(tvOS) || os(watchOS)
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        #else
        FileManager.default.homeDirectoryForCurrentUser
        #endif
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
        #if os(iOS)
        throw HostResourceError.processExecutionUnsupported(platform: "iOS")
        #else
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
        #endif
    }

    public func detectResourceDoors(transcriptURL: URL, queueURL: URL, formCLIURL: URL?) -> [HostResourceDoor] {
        let formCLIDetail = formCLIURL?.path ?? "form-cli-not-found"
        let formCLIState = formCLIURL.map { isExecutableFile(at: $0) ? "open" : "unavailable" } ?? "unavailable"
        return [
            HostResourceDoor(
                kind: "file-read",
                state: fileExists(at: transcriptURL) ? "open" : "not-present",
                carrier: "host-filesystem",
                detail: transcriptURL.path
            ),
            HostResourceDoor(
                kind: "file-append",
                state: "available",
                carrier: "host-filesystem",
                detail: queueURL.path
            ),
            HostResourceDoor(
                kind: "file-write-atomic",
                state: "available",
                carrier: "host-filesystem",
                detail: queueURL.deletingLastPathComponent().path
            ),
            HostResourceDoor(
                kind: "process-stdin-stdout",
                state: formCLIState,
                carrier: "host-process",
                detail: formCLIDetail
            ),
        ]
    }
}

public struct FormHostBoundaryReceipt: Codable, Equatable, Sendable {
    public var kind: String
    public var sharedLogic: String
    public var hostCarrier: String
    public var resourceInterface: String
    public var platformTargets: [String]
    public var allowedResourceKinds: [String]
    public var resourceDoors: [HostResourceDoor]
    public var platformCarriers: [HostPlatformCarrier]
    public var appBoundaryRuntimes: [String]
    public var forbiddenRuntimeCarriers: [String]

    public init(
        sharedLogic: String = "form-native-shared-logic",
        hostCarrier: String = "swift-minimal-host-carrier",
        resourceInterface: String = "host-os-generic-resource-interface",
        platformTargets: [String] = ["macos", "windows", "android", "ios"],
        allowedResourceKinds: [String] = [
            "audio-input",
            "speech-transcript",
            "file-read",
            "file-append",
            "file-write-atomic",
            "process-stdin-stdout",
            "health-samples"
        ],
        resourceDoors: [HostResourceDoor]? = nil,
        platformCarriers: [HostPlatformCarrier]? = nil,
        appBoundaryRuntimes: [String] = ["form", "swift-minimal-host-carrier"],
        forbiddenRuntimeCarriers: [String] = ["python", "go", "rust", "typescript"]
    ) {
        self.kind = "form-native-host-boundary"
        self.sharedLogic = sharedLogic
        self.hostCarrier = hostCarrier
        self.resourceInterface = resourceInterface
        self.platformTargets = platformTargets
        self.allowedResourceKinds = allowedResourceKinds
        self.resourceDoors = resourceDoors ?? allowedResourceKinds.map {
            HostResourceDoor(kind: $0, state: "declared", carrier: resourceInterface)
        }
        self.platformCarriers = platformCarriers ?? HostPlatformCarrier.resolvedDefaults(resourceInterface: resourceInterface)
        self.appBoundaryRuntimes = appBoundaryRuntimes
        self.forbiddenRuntimeCarriers = forbiddenRuntimeCarriers
    }

    public var usesOnlyAllowedAppRuntimes: Bool {
        let allowed = Set(["form", "swift-minimal-host-carrier"])
        let allowedResources = Set(allowedResourceKinds)
        let platforms = Set(platformTargets)
        let hostCarriers = Set([
            "swift-minimal-host-carrier",
            "windows-minimal-host-carrier",
            "android-minimal-host-carrier",
            "iphone-minimal-host-carrier"
        ])
        return appBoundaryRuntimes.allSatisfy { allowed.contains($0) }
            && forbiddenRuntimeCarriers.allSatisfy { !appBoundaryRuntimes.contains($0) }
            && resourceDoors.allSatisfy { allowedResources.contains($0.kind) }
            && platformCarriers.allSatisfy {
                platforms.contains($0.platform)
                    && hostCarriers.contains($0.hostCarrier)
                    && $0.resourceInterface == resourceInterface
                    && $0.resourceDoors.allSatisfy { allowedResources.contains($0.kind) }
            }
    }

    public var doorSummary: String {
        resourceDoors
            .map { "\($0.kind):\($0.state):\($0.carrier)" }
            .joined(separator: ",")
    }

    public var platformCarrierSummary: String {
        platformCarriers
            .map { "\($0.platform):\($0.hostCarrier):\($0.doorSummary)" }
            .joined(separator: "|")
    }
}
