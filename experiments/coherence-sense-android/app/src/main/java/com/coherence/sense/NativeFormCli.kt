package com.coherence.sense

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

object NativeFormCli {
    private const val EXEC_NAME = "libform_cli_exec.so"

    fun executable(context: Context): File =
        File(context.applicationInfo.nativeLibraryDir, EXEC_NAME)

    fun available(context: Context): Boolean {
        val exe = executable(context)
        return exe.exists() && exe.canExecute()
    }

    fun nativeHostJson(
        context: Context,
        platform: String = "android",
        mic: Boolean,
        camera: Boolean,
        screen: Boolean,
        speechGate: Int,
        freq: Int,
        surprises: Long,
        samples: Long,
        message: String = "",
    ): JSONObject {
        val msg = message.trim().replace(Regex("\\s+"), "-").take(64)
        val command = listOf(
            "native-host",
            platform,
            if (mic) "1" else "0",
            if (camera) "1" else "0",
            if (screen) "1" else "0",
            speechGate.coerceAtLeast(0).toString(),
            freq.coerceAtLeast(0).toString(),
            surprises.coerceAtLeast(0).toString(),
            samples.coerceAtLeast(0).toString(),
        ).let { base ->
            if (msg.isBlank()) base.joinToString(" ") else (base + msg).joinToString(" ")
        }
        return parseNativeHostRow(runLine(context, command))
    }

    private fun runLine(context: Context, line: String, timeoutMs: Long = 2000): String {
        val exe = executable(context)
        if (!exe.exists()) return "error|missing $EXEC_NAME"
        return try {
            val process = ProcessBuilder(exe.absolutePath)
                .redirectErrorStream(true)
                .start()
            process.outputStream.bufferedWriter().use { writer ->
                writer.write(line)
                writer.newLine()
                writer.write("quit")
                writer.newLine()
            }
            if (!process.waitFor(timeoutMs, TimeUnit.MILLISECONDS)) {
                process.destroy()
                return "error|timeout"
            }
            val text = process.inputStream.bufferedReader().readText()
            val first = text.lineSequence().map { it.trim() }.firstOrNull { it.isNotEmpty() }
            if (first.isNullOrBlank()) "error|empty" else first
        } catch (e: Exception) {
            "error|${e.javaClass.simpleName}:${e.message ?: "native form-cli failed"}"
        }
    }

    private fun parseNativeHostRow(row: String): JSONObject {
        val parts = row.split("|")
        if (parts.size == 10 && parts[0] == "native-host-instance") {
            return JSONObject()
                .put("kind", parts[0])
                .put("platform", parts[1])
                .put("native", parts[2] == "1")
                .put("listening", parts[3] == "1")
                .put("sharing", parts[4] == "1")
                .put("transcribing", parts[5] == "1")
                .put("surprise_count", parts[6].toLongOrNull() ?: 0L)
                .put("learned_count", parts[7].toLongOrNull() ?: 0L)
                .put("decision", parts[8])
                .put("share_route", parts[9])
                .put("raw", row)
        }
        return JSONObject()
            .put("kind", "native-host-instance")
            .put("native", false)
            .put("decision", "native-form-cli-unavailable")
            .put("share_route", "quiet")
            .put("error", row)
    }
}
