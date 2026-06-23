package com.coherence.sense

import android.content.Context

// FormKernel — the phone-native door to the Form body. The SAME `run_source`
// evaluator the Mac kernel runs, now IN-PROCESS via libform_kernel_rust.so
// (built by form/form-kernel-rust/build-android.sh with --features cabi; the .so
// exports the JNI-named `Java_com_coherence_sense_FormKernel_eval` over the same
// evaluator the C-ABI form_eval runs). The phone recognizes / predicts / learns
// through proven Form recipes WITHOUT the Mac — v1 of the README's "phone-native
// kernel" lane: shim + .so in jniLibs/arm64-v8a + recipes bundled as assets.
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

    // The on-device self-test: reproduce signal-derivative-band's proven verdict
    // (127 — four-way Go=Rust=TS=fkwu) ON THE PHONE. signal-derivative.fk is
    // self-contained on kernel builtins, so no core.fk is concatenated (adding it
    // collides). A "127" result is the body recognizing without the Mac.
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
