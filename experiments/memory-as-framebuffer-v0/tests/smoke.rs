//! Smoke test: run the fizzbuzz example end-to-end, validate the mp4.

use std::path::PathBuf;
use std::process::Command;

fn ffmpeg_available() -> bool {
    Command::new("ffmpeg")
        .arg("-version")
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn crate_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

#[test]
fn fizzbuzz_produces_watchable_mp4() {
    if !ffmpeg_available() {
        println!("SKIP: ffmpeg not found");
        return;
    }

    let dir = crate_dir();
    let mp4 = dir.join("fizzbuzz.mp4");
    let _ = std::fs::remove_file(&mp4);

    let status = Command::new("cargo")
        .args(["run", "--release", "--example", "fizzbuzz"])
        .current_dir(&dir)
        .status()
        .expect("failed to spawn cargo run");
    assert!(status.success(), "fizzbuzz example exited non-zero");

    let meta = std::fs::metadata(&mp4).expect("fizzbuzz.mp4 not produced");
    assert!(meta.len() > 0, "fizzbuzz.mp4 is empty");

    // Dump first frame and decode it.
    let frame_png = dir.join("frame.png");
    let _ = std::fs::remove_file(&frame_png);
    let status = Command::new("ffmpeg")
        .args([
            "-loglevel", "error",
            "-i", mp4.to_str().unwrap(),
            "-vframes", "1",
            "-y",
            frame_png.to_str().unwrap(),
        ])
        .status()
        .expect("failed to run ffmpeg for frame extract");
    assert!(status.success(), "ffmpeg frame extract failed");

    let img = image::open(&frame_png).expect("decode frame.png").to_rgb8();
    let (w, h) = img.dimensions();
    assert!(w > 0 && h > 0);

    // Find at least two pixels with distinct RGB values.
    let mut first: Option<[u8; 3]> = None;
    let mut found_distinct = false;
    'outer: for px in img.pixels() {
        let rgb = [px.0[0], px.0[1], px.0[2]];
        match first {
            None => first = Some(rgb),
            Some(prev) if prev != rgb => {
                found_distinct = true;
                break 'outer;
            }
            _ => {}
        }
    }
    assert!(found_distinct, "first frame is uniform; renderer not producing color variance");
}
