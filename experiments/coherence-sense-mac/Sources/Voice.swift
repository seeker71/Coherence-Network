// Voice — the host TTS carrier. NSSpeechSynthesizer speaks the body's summary and
// surprise events aloud. This is the rented vocoder; the native vocoder (Form→asm
// audio) is the bring-home. Carrier thin: this file only voices strings the sensing
// body produced; it never decides what is true.

import AppKit
import Foundation

@MainActor
final class Voice {
    private let synth = NSSpeechSynthesizer()

    func speak(_ text: String, interrupt: Bool = false) {
        guard !text.isEmpty else { return }
        if interrupt && synth.isSpeaking {
            synth.stopSpeaking()
        }
        if !synth.isSpeaking {
            synth.startSpeaking(text)
        }
    }

    func hush() { synth.stopSpeaking() }
}
