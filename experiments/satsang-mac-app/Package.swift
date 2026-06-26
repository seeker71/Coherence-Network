// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SatsangMacApp",
    platforms: [.macOS(.v13), .iOS(.v17)],
    products: [
        .executable(name: "SatsangGuidance", targets: ["SatsangGuidance"]),
        .executable(name: "SatsangGuidancePhone", targets: ["SatsangGuidancePhone"]),
        .library(name: "SatsangGuidanceKit", targets: ["SatsangGuidanceKit"]),
        .library(name: "SatsangMacCore", targets: ["SatsangMacCore"]),
    ],
    targets: [
        .target(name: "SatsangMacCore"),
        .target(
            name: "SatsangGuidanceKit",
            dependencies: ["SatsangMacCore"],
            linkerSettings: [
                .linkedFramework("AVFoundation"),
                .linkedFramework("Speech"),
            ]
        ),
        .executableTarget(
            name: "SatsangGuidance",
            dependencies: ["SatsangGuidanceKit"]
        ),
        .executableTarget(
            name: "SatsangGuidancePhone",
            dependencies: ["SatsangGuidanceKit"],
            linkerSettings: [
                .linkedFramework("AVFoundation"),
                .linkedFramework("Speech"),
            ]
        ),
        .testTarget(
            name: "SatsangMacCoreTests",
            dependencies: ["SatsangMacCore"]
        ),
    ]
)
