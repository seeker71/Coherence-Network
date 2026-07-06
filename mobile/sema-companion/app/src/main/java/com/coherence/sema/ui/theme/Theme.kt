package com.coherence.sema.ui.theme

// The companion's design language: deep-field dark, pixel-dense, warm where it matters.
// Background is near-black blue (the night the field is read against); teal is the body's
// living signal; gold is witness/attestation; rose marks the honest edge (never alarm-red —
// an edge is a reading, not a failure). Density over chrome: small caps labels, tabular
// numerals, thin rules — the aesthetic of an instrument that respects the reader.

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

object SemaColors {
    val Night = Color(0xFF0B0F14)       // the field's background
    val Panel = Color(0xFF121821)       // raised surface
    val PanelHigh = Color(0xFF1A2230)   // focused surface
    val Rule = Color(0xFF243040)        // hairline dividers
    val Body = Color(0xFF7FD8C8)        // teal — the living body / native signal
    val BodyDim = Color(0xFF3E6B63)
    val Witness = Color(0xFFE8C069)     // gold — attestation, receipts, memory
    val Edge = Color(0xFFCE7B91)        // rose — the honest edge / seam markers
    val Ink = Color(0xFFDCE5EE)         // primary text
    val InkDim = Color(0xFF8A98A8)      // secondary text
    val InkFaint = Color(0xFF55616F)    // tertiary / labels
}

private val scheme = darkColorScheme(
    primary = SemaColors.Body,
    onPrimary = SemaColors.Night,
    secondary = SemaColors.Witness,
    onSecondary = SemaColors.Night,
    tertiary = SemaColors.Edge,
    background = SemaColors.Night,
    onBackground = SemaColors.Ink,
    surface = SemaColors.Panel,
    onSurface = SemaColors.Ink,
    surfaceVariant = SemaColors.PanelHigh,
    onSurfaceVariant = SemaColors.InkDim,
    outline = SemaColors.Rule,
)

// Pixel-dense type: compact sizes, generous weight contrast, monospace for live values
// so columns of readings align like an instrument panel.
private val semaTypography = Typography(
    headlineSmall = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.sp),
    titleMedium = TextStyle(fontSize = 15.sp, fontWeight = FontWeight.SemiBold),
    titleSmall = TextStyle(fontSize = 13.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = TextStyle(fontSize = 15.sp, lineHeight = 21.sp),
    bodyMedium = TextStyle(fontSize = 13.sp, lineHeight = 18.sp),
    bodySmall = TextStyle(fontSize = 11.sp, lineHeight = 15.sp),
    labelLarge = TextStyle(fontSize = 12.sp, fontWeight = FontWeight.Medium, letterSpacing = 0.8.sp),
    labelMedium = TextStyle(fontSize = 10.sp, fontWeight = FontWeight.Medium, letterSpacing = 1.2.sp),
    labelSmall = TextStyle(fontSize = 9.sp, fontWeight = FontWeight.Medium, letterSpacing = 1.4.sp),
)

val Mono = FontFamily.Monospace

@Composable
fun SemaTheme(content: @Composable () -> Unit) {
    // One committed look: the companion is a deep-field instrument in any system theme.
    MaterialTheme(colorScheme = scheme, typography = semaTypography, content = content)
}
