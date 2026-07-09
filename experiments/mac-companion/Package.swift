// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "SemaCompanion",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "SemaCompanion",
            path: "Sources/SemaCompanion"
        )
    ]
)
