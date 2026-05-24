//! ffmpeg subprocess pipeline. Spawns `ffmpeg -f rawvideo -pix_fmt rgba ...`
//! and accepts RGBA frames written to stdin. On finalize, closes stdin and
//! waits for the child to exit cleanly.

use std::io::Write;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::Mutex;

use crate::render::{RENDER_H, RENDER_W};

/// Returns Ok(()) if `ffmpeg` is on PATH, otherwise an error string.
pub fn ensure_ffmpeg_available() -> Result<(), String> {
    match Command::new("ffmpeg")
        .arg("-version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
    {
        Ok(s) if s.success() => Ok(()),
        Ok(s) => Err(format!("ffmpeg present but exited with status {:?}", s)),
        Err(e) => Err(format!("ffmpeg not found on PATH: {}", e)),
    }
}

/// Owns the ffmpeg child process and its stdin pipe.
pub struct FfmpegPipe {
    child: Mutex<Option<Child>>,
    stdin: Mutex<Option<ChildStdin>>,
}

impl FfmpegPipe {
    /// Spawn ffmpeg expecting raw RGBA frames at `fps` and writing to `output_path`.
    pub fn spawn(output_path: &str, fps: u32) -> Result<Self, String> {
        let size = format!("{}x{}", RENDER_W, RENDER_H);
        let rate = fps.to_string();
        let mut cmd = Command::new("ffmpeg");
        cmd.args([
            "-loglevel", "error",
            "-f", "rawvideo",
            "-pix_fmt", "rgba",
            "-s", &size,
            "-r", &rate,
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-y",
            output_path,
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::inherit());

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("failed to spawn ffmpeg: {}", e))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "ffmpeg child has no stdin".to_string())?;

        Ok(Self {
            child: Mutex::new(Some(child)),
            stdin: Mutex::new(Some(stdin)),
        })
    }

    /// Write one RGBA frame. Returns Err on I/O failure (treat as terminal).
    pub fn write_frame(&self, frame: &[u8]) -> std::io::Result<()> {
        let mut guard = self.stdin.lock().unwrap();
        if let Some(stdin) = guard.as_mut() {
            stdin.write_all(frame)?;
        }
        Ok(())
    }

    /// Close stdin and wait for ffmpeg to exit. Idempotent.
    pub fn finalize(&self) {
        // Drop stdin first so ffmpeg sees EOF.
        {
            let mut guard = self.stdin.lock().unwrap();
            *guard = None;
        }
        // Wait for the child.
        let mut guard = self.child.lock().unwrap();
        if let Some(mut child) = guard.take() {
            let _ = child.wait();
        }
    }
}

impl Drop for FfmpegPipe {
    fn drop(&mut self) {
        self.finalize();
    }
}
