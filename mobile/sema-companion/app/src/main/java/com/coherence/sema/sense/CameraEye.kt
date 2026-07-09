package com.coherence.sema.sense

// CameraEye — the phone's eye for the recognition pipeline. A single still on demand (never a
// stream), headless (camera2 + ImageReader, no preview surface), written to the app's files dir
// where the Mac's puller collects it into the same face/vision inboxes the mac camera feeds —
// two devices, multiple angles, one training set. Energy-light: open, one frame, close. Alternates
// front (the person) and back (the room) so both are witnessed over time.

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.media.ImageReader
import android.os.Handler
import android.os.HandlerThread
import androidx.core.content.ContextCompat
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

object CameraEye {
    fun granted(ctx: Context): Boolean =
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    fun dir(ctx: Context): File =
        File(ctx.getExternalFilesDir(null), "camera").apply { mkdirs() }

    // Capture one still from the chosen lens. Returns the file, or null on any failure/timeout.
    fun captureOnce(ctx: Context, front: Boolean): File? {
        if (!granted(ctx)) return null
        val cm = ctx.getSystemService(Context.CAMERA_SERVICE) as? CameraManager ?: return null
        val wantFacing = if (front) CameraCharacteristics.LENS_FACING_FRONT else CameraCharacteristics.LENS_FACING_BACK
        val camId = cm.cameraIdList.firstOrNull {
            cm.getCameraCharacteristics(it).get(CameraCharacteristics.LENS_FACING) == wantFacing
        } ?: cm.cameraIdList.firstOrNull() ?: return null

        val thread = HandlerThread("sema-eye").also { it.start() }
        val handler = Handler(thread.looper)
        val reader = ImageReader.newInstance(1280, 960, ImageFormat.JPEG, 1)
        val out = File(dir(ctx), "${if (front) "front" else "back"}-${System.currentTimeMillis()}.jpg")
        val done = CountDownLatch(1)
        var device: CameraDevice? = null
        var ok = false

        reader.setOnImageAvailableListener({ r ->
            val img = r.acquireLatestImage() ?: return@setOnImageAvailableListener
            try {
                val buf = img.planes[0].buffer
                val bytes = ByteArray(buf.remaining()); buf.get(bytes)
                out.writeBytes(bytes); ok = true
            } catch (_: Exception) {} finally { img.close(); done.countDown() }
        }, handler)

        try {
            cm.openCamera(camId, object : CameraDevice.StateCallback() {
                override fun onOpened(cam: CameraDevice) {
                    device = cam
                    try {
                        val req = cam.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE).apply {
                            addTarget(reader.surface)
                            set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO)
                            set(CaptureRequest.JPEG_QUALITY, 85.toByte())
                        }
                        @Suppress("DEPRECATION")
                        cam.createCaptureSession(listOf(reader.surface), object : CameraCaptureSession.StateCallback() {
                            override fun onConfigured(session: CameraCaptureSession) {
                                try { session.capture(req.build(), null, handler) } catch (_: Exception) { done.countDown() }
                            }
                            override fun onConfigureFailed(session: CameraCaptureSession) { done.countDown() }
                        }, handler)
                    } catch (_: Exception) { done.countDown() }
                }
                override fun onDisconnected(cam: CameraDevice) { cam.close(); done.countDown() }
                override fun onError(cam: CameraDevice, error: Int) { cam.close(); done.countDown() }
            }, handler)
        } catch (_: Exception) { done.countDown() }

        done.await(6, TimeUnit.SECONDS)
        try { device?.close() } catch (_: Exception) {}
        try { reader.close() } catch (_: Exception) {}
        thread.quitSafely()
        return if (ok && out.length() > 0) out else null.also { out.delete() }
    }

    // Keep the files dir bounded — the puller removes what it collects, this caps if it can't reach.
    fun prune(ctx: Context, keep: Int = 60) {
        val files = dir(ctx).listFiles()?.sortedByDescending { it.lastModified() } ?: return
        files.drop(keep).forEach { it.delete() }
    }
}
