package com.coherence.sema.satsang

// SatsangRecorder — the irreplaceable artifact. One MediaRecorder capturing the whole
// session to a timestamped .m4a in the app's external files dir (pullable over adb, no
// root: /sdcard/Android/data/com.coherence.sema/files/satsang/). Reliable capture is the
// non-negotiable — a satsang cannot be re-recorded. Transcription is a SEPARATE, later
// step from this file (the Mac's whisper lane), never a live mic-competitor that could
// starve the recording. AAC 44.1kHz mono @128kbps: clear speech, ~1MB/min.

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import java.io.File

object SatsangRecorder {
    @Volatile private var recorder: MediaRecorder? = null
    @Volatile var currentFile: File? = null; private set
    @Volatile var startedAt: Long = 0L; private set
    @Volatile var lastError: String? = null; private set

    val isRecording: Boolean get() = recorder != null

    fun dir(context: Context): File =
        (context.getExternalFilesDir("satsang") ?: File(context.filesDir, "satsang")).apply { mkdirs() }

    // Returns the file being recorded to, or null if start failed (lastError set).
    fun start(context: Context, stamp: String): File? {
        if (recorder != null) return currentFile
        lastError = null
        val file = File(dir(context), "satsang-$stamp.m4a")
        val r = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(context) else @Suppress("DEPRECATION") MediaRecorder()
        return try {
            r.setAudioSource(MediaRecorder.AudioSource.MIC)
            r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            r.setAudioEncodingBitRate(128_000)
            r.setAudioSamplingRate(44_100)
            r.setOutputFile(file.absolutePath)
            r.prepare()
            r.start()
            recorder = r
            currentFile = file
            startedAt = System.currentTimeMillis()
            file
        } catch (e: Exception) {
            lastError = "${e.javaClass.simpleName}: ${e.message}"
            try { r.release() } catch (_: Exception) {}
            null
        }
    }

    // Finalizes the file and returns it (a valid, playable recording), or null.
    fun stop(): File? {
        val r = recorder ?: return null
        val file = currentFile
        recorder = null
        return try {
            r.stop(); r.release()
            file
        } catch (e: Exception) {
            // stop() throws if stopped too early (no frames) — the file may be empty/invalid.
            lastError = "stop: ${e.javaClass.simpleName}: ${e.message}"
            try { r.release() } catch (_: Exception) {}
            file
        }
    }

    fun elapsedMs(): Long = if (isRecording) System.currentTimeMillis() - startedAt else 0L
}
