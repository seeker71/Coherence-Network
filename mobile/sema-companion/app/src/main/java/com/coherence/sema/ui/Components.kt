package com.coherence.sema.ui

// The instrument vocabulary: small-caps labels, hairline panels, live dots, mono values.
// Every screen composes these — one voice, pixel-dense, no chrome for chrome's sake.

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.coherence.sema.ui.theme.SemaColors
import java.util.Locale

@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text.uppercase(Locale.US),
        style = MaterialTheme.typography.labelMedium,
        color = SemaColors.InkFaint,
        modifier = modifier.padding(top = 14.dp, bottom = 6.dp),
    )
}

@Composable
fun Panel(
    modifier: Modifier = Modifier,
    tint: Color = SemaColors.Panel,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(tint, RoundedCornerShape(10.dp))
            .border(1.dp, SemaColors.Rule, RoundedCornerShape(10.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
        content = content,
    )
}

@Composable
fun LiveDot(on: Boolean, onColor: Color = SemaColors.Body) {
    Box(
        modifier = Modifier
            .size(7.dp)
            .background(if (on) onColor else SemaColors.InkFaint, CircleShape)
    )
}

@Composable
fun KeyValueRow(label: String, value: String, valueColor: Color = SemaColors.Ink) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = SemaColors.InkDim,
        )
        Text(
            value,
            style = MaterialTheme.typography.bodySmall,
            fontFamily = FontFamily.Monospace,
            color = valueColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
fun SeamBadge(seamNamed: Boolean) {
    val (text, color) = if (seamNamed) {
        "seam named" to SemaColors.Witness
    } else {
        "seam hidden" to SemaColors.Edge
    }
    Text(
        text = text,
        style = MaterialTheme.typography.labelSmall,
        color = color,
        modifier = Modifier
            .border(1.dp, color.copy(alpha = 0.5f), RoundedCornerShape(4.dp))
            .padding(horizontal = 5.dp, vertical = 2.dp),
    )
}

@Composable
fun LaneTag(lane: String) {
    val color = when (lane) {
        "memory" -> SemaColors.Witness
        "sense" -> SemaColors.Body
        "grounded", "substrate" -> SemaColors.Body
        "edge" -> SemaColors.Edge
        else -> SemaColors.InkFaint
    }
    Text(
        text = lane,
        style = MaterialTheme.typography.labelSmall,
        color = color,
    )
}
