package com.coherence.sense

import android.content.Context

// Legacy optional JNI adapter for the old Android Rust-kernel experiment. The
// default Android native path is NativeFormCli: the APK packages the
// C-bootstrapped form-cli executable and calls native-host-instance.fk through
// stdin/stdout. Keep this file only for historical signal-derivative comparison
// when libform_kernel_rust.so is explicitly bundled.
object FormKernel {
    @Volatile private var loaded = false
    private var loadError: String? = null

    init {
        try {
            System.loadLibrary("form_kernel_rust")
            loaded = true
        } catch (t: Throwable) {
            loadError = t.message ?: t.toString()
        }
    }

    val available: Boolean get() = loaded
    val error: String? get() = loadError

    // Evaluate a full Form source string; returns the kernel's display() text
    // (or an "ERR:" string — the native side never throws across the boundary).
    private external fun eval(src: String): String

    private fun evalOrErr(src: String): String =
        if (loaded) try { eval(src) } catch (t: Throwable) { "ERR: ${t.message}" }
        else "ERR: kernel .so not loaded (${loadError ?: "unknown"})"

    // Bundled recipe assets, read once and cached.
    private val recipeCache = HashMap<String, String>()
    private fun asset(ctx: Context, name: String): String =
        recipeCache.getOrPut(name) {
            ctx.assets.open("recipes/$name").bufferedReader().use { it.readText() }
        }

    // Compose recipe preludes + a trailing driver, then eval. Mirrors how the
    // Mac kernel concatenates the recipe(s) + the trailing call before running.
    private fun run(ctx: Context, recipeFiles: List<String>, driver: String): String {
        val src = buildString {
            for (f in recipeFiles) { append(asset(ctx, f)); append('\n') }
            append(driver)
        }
        return evalOrErr(src)
    }

    // Legacy self-test for the optional signal-derivative lane.
    fun selfTestVerdict(ctx: Context): String =
        run(ctx, listOf("signal-derivative.fk", "signal-derivative-band.fk"), "").trim()

    // Live recognition: still vs moving from a window of scalar samples, via the
    // proven signal-derivative recipe (sd-moving?), entirely on-device.
    fun moving(ctx: Context, window: List<Int>, floor: Int): Boolean {
        val list = window.joinToString(" ")
        return run(ctx, listOf("signal-derivative.fk"), "(sd-moving? (list $list) $floor)")
            .trim() == "1"
    }
}
