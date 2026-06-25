// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SatsangMacApp",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "SatsangGuidance", targets: ["SatsangGuidance"]),
        .library(name: "SatsangMacCore", targets: ["SatsangMacCore"]),
    ],
    targets: [
        .target(name: "SatsangMacCore"),
        .executableTarget(
            name: "SatsangGuidance",
            dependencies: ["SatsangMacCore"]
        ),
        .testTarget(
            name: "SatsangMacCoreTests",
            dependencies: ["SatsangMacCore"]
        ),
    ]
)
