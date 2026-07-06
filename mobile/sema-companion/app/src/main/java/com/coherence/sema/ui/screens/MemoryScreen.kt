package com.coherence.sema.ui.screens

// MEMORY — the second brain. Moments held on explicit word only (the explicit-Send
// boundary), people invited with their own consent about being remembered, everything
// local to the device. Nothing here ever leaves the phone.

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.coherence.sema.AppState
import com.coherence.sema.ui.KeyValueRow
import com.coherence.sema.ui.Panel
import com.coherence.sema.ui.SectionLabel
import com.coherence.sema.ui.theme.SemaColors
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun MemoryScreen(state: AppState) {
    var newMoment by remember { mutableStateOf("") }
    var newPerson by remember { mutableStateOf("") }
    var consent by remember { mutableStateOf(true) }
    var refresh by remember { mutableIntStateOf(0) }

    val moments = remember(refresh) { state.memory.moments() }
    val people = remember(refresh) { state.memory.people() }
    val stamp = remember { SimpleDateFormat("MMM d · HH:mm", Locale.US) }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            SectionLabel("hold a moment")
            Panel {
                OutlinedTextField(
                    value = newMoment,
                    onValueChange = { newMoment = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("what should I carry for you?", color = SemaColors.InkFaint) },
                    textStyle = MaterialTheme.typography.bodyMedium,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = SemaColors.BodyDim,
                        unfocusedBorderColor = SemaColors.Rule,
                        cursorColor = SemaColors.Body,
                    ),
                    shape = RoundedCornerShape(10.dp),
                    maxLines = 4,
                )
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick = {
                        if (newMoment.isNotBlank()) {
                            state.memory.remember(newMoment.trim(), source = "told")
                            newMoment = ""
                            refresh++
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = SemaColors.Witness),
                ) { Text("Hold it", color = SemaColors.Night) }
            }
        }

        item {
            SectionLabel("people in the circle (${people.size})")
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = newPerson,
                        onValueChange = { newPerson = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("invite by name", color = SemaColors.InkFaint) },
                        textStyle = MaterialTheme.typography.bodyMedium,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = SemaColors.BodyDim,
                            unfocusedBorderColor = SemaColors.Rule,
                            cursorColor = SemaColors.Body,
                        ),
                        shape = RoundedCornerShape(10.dp),
                        singleLine = true,
                    )
                    Spacer(Modifier.width(8.dp))
                    Button(
                        onClick = {
                            if (newPerson.isNotBlank()) {
                                state.memory.invite(newPerson.trim(), consentRemembered = consent)
                                newPerson = ""
                                refresh++
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = SemaColors.Body),
                    ) { Text("Invite", color = SemaColors.Night) }
                }
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Switch(
                        checked = consent,
                        onCheckedChange = { consent = it },
                        colors = SwitchDefaults.colors(checkedTrackColor = SemaColors.BodyDim),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        if (consent) "they consent to being remembered across visits"
                        else "greeted fresh each time — their choice, honored",
                        style = MaterialTheme.typography.bodySmall,
                        color = SemaColors.InkDim,
                    )
                }
            }
        }

        items(people) { p ->
            Panel {
                Text(p.name, style = MaterialTheme.typography.titleSmall)
                KeyValueRow(
                    "memory consent",
                    if (p.consentRemembered) "remembered" else "greeted fresh",
                    if (p.consentRemembered) SemaColors.Witness else SemaColors.InkDim,
                )
                KeyValueRow("invited", stamp.format(Date(p.invitedAt)))
            }
        }

        item { SectionLabel("moments held (${moments.size})") }
        items(moments) { m ->
            Panel {
                Text(m.text, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(3.dp))
                KeyValueRow(m.source, stamp.format(Date(m.at)), SemaColors.InkFaint)
            }
        }

        item {
            Text(
                "Everything on this screen lives only on this phone. Held on your word, " +
                    "never scraped — the explicit-Send boundary, kept.",
                style = MaterialTheme.typography.bodySmall,
                color = SemaColors.InkFaint,
                modifier = Modifier.padding(vertical = 12.dp),
            )
        }
    }
}
