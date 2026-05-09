//! Snapshot thread: every 1000/fps ms, grabs a snapshot of both planes,
//! renders a frame, and pipes it into ffmpeg. If a CaptureSink is provided
//! (via MFB_CAPTURE env var), the same snapshot is *also* written losslessly
//! to a .mfb binary file for any downstream renderer to consume.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use crate::capture::CaptureSink;
use crate::ffmpeg::FfmpegPipe;
use crate::render::{render_frame, FrameRgba};
use crate::FRAMEBUFFER;

pub use crate::render::FrameRgba as PublicFrameRgba;

/// Snapshot the substrate state (data + provenance planes) without rendering.
/// Returns None if the framebuffer hasn't been initialized yet.
pub fn snapshot_state() -> Option<(Vec<u8>, Vec<u32>)> {
    let fb = FRAMEBUFFER.get()?;
    let data_bytes = {
        let data = fb.data.lock().ok()?;
        data.snapshot_bytes()
    };
    let prov = {
        let prov = fb.provenance.lock().ok()?;
        prov.clone()
    };
    Some((data_bytes, prov))
}

/// Capture one rendered RGBA frame from the global framebuffer.
/// Returns None if the framebuffer hasn't been initialized yet.
pub fn capture_frame() -> Option<FrameRgba> {
    let (data, prov) = snapshot_state()?;
    Some(render_frame(&data, &prov))
}

/// Owns the snapshot thread + the ffmpeg pipe it writes into +
/// (optionally) the lossless .mfb capture sink.
pub struct SnapshotThread {
    stop: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
    pipe: Arc<FfmpegPipe>,
    capture: Option<Arc<Mutex<CaptureSink>>>,
}

impl SnapshotThread {
    pub fn spawn(fps: u32, pipe: FfmpegPipe, capture: Option<CaptureSink>) -> Self {
        let stop = Arc::new(AtomicBool::new(false));
        let stop_clone = stop.clone();
        let pipe = Arc::new(pipe);
        let pipe_clone = pipe.clone();
        let capture = capture.map(|c| Arc::new(Mutex::new(c)));
        let capture_clone = capture.clone();
        let frame_dur = Duration::from_micros(1_000_000 / fps as u64);

        let handle = thread::spawn(move || {
            let start = Instant::now();
            let mut next = Instant::now();
            let mut frame_idx: u64 = 0;
            while !stop_clone.load(Ordering::SeqCst) {
                let now = Instant::now();
                if now < next {
                    thread::sleep(next - now);
                }
                next += frame_dur;

                if let Some((data, prov)) = snapshot_state() {
                    // Lossless substrate capture (if MFB_CAPTURE was set).
                    if let Some(sink) = &capture_clone {
                        let elapsed_us = start.elapsed().as_micros() as u64;
                        if let Ok(mut s) = sink.lock() {
                            // Errors here are non-fatal for the rendering path —
                            // the preview mp4 keeps running even if capture fails.
                            let _ = s.write_frame(frame_idx, elapsed_us, &data, &prov);
                        }
                    }

                    // Lossy preview render → ffmpeg → mp4.
                    let frame = render_frame(&data, &prov);
                    if pipe_clone.write_frame(&frame).is_err() {
                        // ffmpeg died — bail.
                        break;
                    }
                    frame_idx += 1;
                }
            }
        });

        Self {
            stop,
            handle: Some(handle),
            pipe,
            capture,
        }
    }

    /// Stop the thread and finalize ffmpeg + capture.
    pub fn shutdown(mut self) {
        self.stop.store(true, Ordering::SeqCst);
        if let Some(h) = self.handle.take() {
            let _ = h.join();
        }
        self.pipe.finalize();
        // Flush capture sink (the inner BufWriter). Drop on the Arc<Mutex>
        // takes care of it, but explicit flush is harmless.
        if let Some(sink) = &self.capture {
            if let Ok(s) = sink.lock() {
                // Reach into the writer indirectly via Drop semantics;
                // there's no public flush() — relying on Drop is fine.
                drop(s);
            }
        }
    }
}
