package com.coherence.sema.voice

// LiveTranslator — on-device translation for the live transcript. Identifies the language each
// line was spoken in, then translates it into the chosen target (ML Kit; the model downloads
// once, then runs offline). So a room speaking English, Indonesian, whatever — the Brazilian
// member reads it all in Portuguese, live, without the words ever leaving the phone.

import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.nl.languageid.LanguageIdentification
import com.google.mlkit.nl.translate.TranslateLanguage
import com.google.mlkit.nl.translate.Translation
import com.google.mlkit.nl.translate.Translator
import com.google.mlkit.nl.translate.TranslatorOptions

class LiveTranslator {
    @Volatile private var target: String = TranslateLanguage.PORTUGUESE
    private val translators = HashMap<String, Translator>()   // keyed by source language
    private val langId = LanguageIdentification.getClient()

    fun setTarget(lang: String) {
        target = lang
        synchronized(translators) { translators.values.forEach { it.close() }; translators.clear() }
    }
    fun target(): String = target

    fun translate(text: String, onResult: (String) -> Unit) {
        if (text.isBlank()) { onResult(""); return }
        langId.identifyLanguage(text).addOnSuccessListener { code ->
            val source = if (code == "und") TranslateLanguage.ENGLISH
                         else TranslateLanguage.fromLanguageTag(code) ?: TranslateLanguage.ENGLISH
            if (source == target) { onResult(text); return@addOnSuccessListener }
            val t = synchronized(translators) {
                translators.getOrPut(source) {
                    Translation.getClient(
                        TranslatorOptions.Builder()
                            .setSourceLanguage(source)
                            .setTargetLanguage(target)
                            .build()
                    )
                }
            }
            t.downloadModelIfNeeded(DownloadConditions.Builder().build())
                .addOnSuccessListener {
                    t.translate(text)
                        .addOnSuccessListener { onResult(it) }
                        .addOnFailureListener { onResult("") }
                }
                .addOnFailureListener { onResult("") }
        }.addOnFailureListener { onResult("") }
    }

    fun close() {
        synchronized(translators) { translators.values.forEach { it.close() }; translators.clear() }
        try { langId.close() } catch (_: Exception) {}
    }
}
