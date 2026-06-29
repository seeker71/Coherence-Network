package com.coherence.sense

// FkwuSense — the thin bridge to the on-device C-bootstrapped fkwu kernel.
//
// CARRIER, not body. Kotlin measures ONE number (the camera-frame luminance) and
// hands a Form EXPRESSION to fkwu; fkwu runs the decision and returns the verdict.
// The "presence: yes/no" the screen shows is fkwu's own evaluation of
//   (if (le <threshold> <luma>) 1 0)
// over the proven loop-table — the same form-eval-full grammar witnessed four-way
// and run on this exact Galaxy S23 Ultra (receipts/2026-06-29-android-runtime.md).
// No sensing logic lives here: Kotlin pipes a byte and reads a line.

import android.content.Context
import java.io.File
import java.util.concurrent.TimeUnit

object FkwuSense {
    // The proven fkwu binary, packaged as an executable jniLib (extracted to an
    // executable nativeLibraryDir by the installer — the same trick the form-cli
    // carrier uses). The byte-identical binary that ran 42/100/99 on this phone.
    private const val EXEC_NAME = "libfkwu_exec.so"
    private const val TABLE_ASSET = "native/loop-table.txt"

    fun executable(context: Context): File =
        File(context.applicationInfo.nativeLibraryDir, EXEC_NAME)

    fun available(context: Context): Boolean {
        val exe = executable(context)
        return exe.exists() && exe.canExecute()
    }

    // Copy the loop-table asset into the app's files dir once; fkwu reads it as argv[1].
    private fun tableFile(context: Context): File {
        val out = File(context.filesDir, "loop-table.txt")
        if (!out.exists() || out.length() == 0L) {
            context.assets.open(TABLE_ASSET).use { input ->
                out.outputStream().use { input.copyTo(it) }
            }
        }
        return out
    }

    data class Verdict(
        val raw: String,        // exact first line fkwu emitted (the native value)
        val value: Long?,       // parsed verdict, or null if fkwu was unreachable
        val expr: String,       // the Form expression fkwu evaluated
        val native: Boolean,    // true => the number came from fkwu on metal
        val error: String? = null,
    )

    // Run ONE Form expression through fkwu on the phone, return its first emitted line.
    // The loop-table's read-eval loop prints the verdict as line 1; we take exactly that.
    fun evaluate(context: Context, expr: String): Verdict {
        val exe = executable(context)
        if (!exe.exists() || !exe.canExecute()) {
            return Verdict("", null, expr, native = false, error = "fkwu binary missing")
        }
        return try {
            val table = tableFile(context)
            val input = File(context.filesDir, "sense-input.txt")
            input.writeText(expr + "\n")
            val process = ProcessBuilder(
                exe.absolutePath, table.absolutePath, "0", input.absolutePath,
            ).redirectErrorStream(true).start()
            if (!process.waitFor(2000, TimeUnit.MILLISECONDS)) {
                process.destroy()
                return Verdict("", null, expr, native = false, error = "timeout")
            }
            val text = process.inputStream.bufferedReader().readText()
            // The verdict is line 1; the loop-table re-reads past EOF and emits
            // internal counters after (the named EOF gap in the android receipt),
            // so we take the FIRST non-empty line — that is the native answer.
            val first = text.lineSequence().map { it.trim() }.firstOrNull { it.isNotEmpty() }
            if (first.isNullOrBlank()) {
                Verdict("", null, expr, native = false, error = "empty output")
            } else {
                Verdict(first, first.toLongOrNull(), expr, native = true)
            }
        } catch (e: Exception) {
            Verdict("", null, expr, native = false, error = "${e.javaClass.simpleName}:${e.message}")
        }
    }

    // The sense recipe, expressed as a Form decision fkwu evaluates: is the live
    // luminance at/above the presence threshold? (le thr luma) => present.
    fun sensePresence(context: Context, luma: Int, threshold: Int = 50): Verdict =
        evaluate(context, "(if (le $threshold $luma) 1 0)")

    // The surprise recipe — also fkwu's own decision, never Kotlin's. Kotlin measures
    // the frame-to-frame absolute luminance delta as ONE number; fkwu decides whether
    // that delta crosses the attend threshold: (le attend delta) => surprise.
    // The delta magnitude is the measured byte; the verdict (did it cross?) is native.
    fun senseSurprise(context: Context, delta: Int, attend: Int = 18): Verdict =
        evaluate(context, "(if (le $attend $delta) 1 0)")
}
