import SatsangGuidanceKit
import SwiftUI

@main
struct SatsangGuidanceApp: App {
    var body: some Scene {
        WindowGroup {
            SatsangGuidanceRootView(shell: .macOS)
                .frame(minWidth: 1040, minHeight: 700)
        }
    }
}
