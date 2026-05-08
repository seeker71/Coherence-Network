//! Snapshot thread: every 1000/fps ms, grabs a snapshot of both planes,
//! renders a frame, and pipes it into ffmpeg.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use crate::ffmpeg::FfmpegPipe;
use crate::render::{render_frame, FrameRgba};
use crate::FRAMEBUFFER;

pub use crate::render::FrameRgba as PublicFrameRgba;

/// Capture one frame from the global framebuffer (data + provenance planes).
/// Returns None if the framebuffer hasn't been initialized yet.
pub fn capture_frame() -> Option<FrameRgba> {
    let fb = FRAMEBUFFER.get()?;
    let data_bytes = {
        let data = fb.data.lock().ok()?;
        data.snapshot_bytes()
    };
    let prov = {
        let prov = fb.provenance.lock().ok()?;
        prov.clone()
    };
    Some(render_frame(&data_bytes, &prov))
}

/// Owns the snapshot thread + the ffmpeg pipe it writes into.
pub struct SnapshotThread {
    stop: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
    pipe: Arc<FfmpegPipe>,
}

impl SnapshotThread {
    pub fn spawn(fps: u32, pipe: FfmpegPipe) -> Self {
        let stop = Arc::new(AtomicBool::new(false));
        let stop_clone = stop.clone();
        let pipe = Arc::new(pipe);
        let pipe_clone = pipe.clone();
        let frame_dur = Duration::from_micros(1_000_000 / fps as u64);

        let handle = thread::spawn(move || {
            let mut next = Instant::now();
            while !stop_clone.load(Ordering::SeqCst) {
                let now = Instant::now();
                if now < next {
                    thread::sleep(next - now);
                }
                next += frame_dur;
                if let Some(frame) = capture_frame() {
                    if pipe_clone.write_frame(&frame).is_err() {
                        // ffmpeg died — bail.
                        break;
                    }
                }
            }
        });

        Self {
            stop,
            handle: Some(handle),
            pipe,
        }
    }

    /// Stop the thread and finalize ffmpeg.
    pub fn shutdown(mut self) {
        self.stop.store(true, Ordering::SeqCst);
        if let Some(h) = self.handle.take() {
            let _ = h.join();
        }
        self.pipe.finalize();
    }
}
