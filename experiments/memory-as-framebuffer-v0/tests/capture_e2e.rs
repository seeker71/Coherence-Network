//! End-to-end test: run the fizzbuzz example with MFB_CAPTURE set, then
//! replay the .mfb file frame-by-frame and verify the substrate carries
//! enough information for any future renderer to reconstruct cell state.

use std::path::PathBuf;
use std::process::{Command, Stdio};

use mfb::{CaptureReader, CELL_BYTES, NUM_CELLS, TAG_FREE, TAG_U32};

fn ffmpeg_available() -> bool {
    Command::new("ffmpeg")
        .arg("-version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn crate_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

#[test]
fn fizzbuzz_writes_replayable_capture() {
    if !ffmpeg_available() {
        println!("SKIP: ffmpeg not found");
        return;
    }

    let dir = crate_dir();
    let mp4 = dir.join("fizzbuzz_capture.mp4");
    let mfb = dir.join("fizzbuzz_capture.mfb");
    let _ = std::fs::remove_file(&mp4);
    let _ = std::fs::remove_file(&mfb);

    // Run the fizzbuzz example with MFB_CAPTURE set.
    // We override the example's output by setting an env var the example
    // doesn't read — so we have to run the example with its built-in path
    // ("fizzbuzz.mp4") and accept that side effect; for the .mfb capture
    // it's the env var that matters.
    let status = Command::new("cargo")
        .args(["run", "--release", "--example", "fizzbuzz"])
        .env("MFB_CAPTURE", mfb.to_str().unwrap())
        .current_dir(&dir)
        .status()
        .expect("failed to spawn cargo run");
    assert!(status.success(), "fizzbuzz example exited non-zero");

    let meta = std::fs::metadata(&mfb).expect("fizzbuzz_capture.mfb not produced");
    assert!(meta.len() > 0, ".mfb capture is empty");

    // Replay the capture and verify each frame's state is sane.
    let mut reader = CaptureReader::open(&mfb).expect("open .mfb");
    assert_eq!(reader.fps_hint(), 60);

    let mut frame_count: u64 = 0;
    let mut max_u32_cells_seen: usize = 0;
    let mut last_timestamp_us: u64 = 0;
    let mut any_frame_had_provenance = false;
    let mut any_frame_had_distinct_payloads = false;

    let mut last_frame_data: Option<Vec<u8>> = None;

    while let Some(frame) = reader.next() {
        let frame = frame.expect("frame decode");
        frame_count += 1;

        // Timestamps must be monotonically increasing.
        if frame.frame_index > 0 {
            assert!(
                frame.timestamp_us >= last_timestamp_us,
                "timestamps must not regress (frame {})",
                frame.frame_index
            );
        }
        last_timestamp_us = frame.timestamp_us;

        // Count u32 cells (TAG_U32 = 0x0003).
        let mut u32_cells = 0;
        let mut payload_bytes_for_u32: std::collections::HashSet<[u8; 14]> =
            std::collections::HashSet::new();
        for i in 0..NUM_CELLS {
            let off = i * CELL_BYTES;
            let tag = u16::from_le_bytes([frame.data[off], frame.data[off + 1]]);
            if tag == TAG_U32 {
                u32_cells += 1;
                let mut payload = [0u8; 14];
                payload.copy_from_slice(&frame.data[off + 2..off + CELL_BYTES]);
                payload_bytes_for_u32.insert(payload);
            } else {
                assert!(
                    tag == TAG_FREE,
                    "fizzbuzz only allocates u32 cells; saw tag 0x{:04x} at cell {}",
                    tag,
                    i
                );
            }
        }
        if u32_cells > max_u32_cells_seen {
            max_u32_cells_seen = u32_cells;
        }
        if frame.provenance.iter().any(|&p| p != 0) {
            any_frame_had_provenance = true;
        }
        if payload_bytes_for_u32.len() > 1 {
            any_frame_had_distinct_payloads = true;
        }

        last_frame_data = Some(frame.data);
    }

    // Sanity bounds — fizzbuzz allocates 100 u32 cells and runs ~6 sec at 60fps.
    assert!(
        frame_count > 100,
        "expected > 100 frames, got {}",
        frame_count
    );
    assert_eq!(
        max_u32_cells_seen, 100,
        "fizzbuzz allocates 100 u32 cells; capture saw peak {}",
        max_u32_cells_seen
    );

    // The final frame may or may not have all 100 cells live — the snapshot
    // loop and the example's final drop+shutdown race, so the last captured
    // frame could be mid-loop, just-after-loop, or post-cleanup.
    let last_data = last_frame_data.expect("at least one frame");
    let final_u32 = (0..NUM_CELLS)
        .filter(|i| {
            let off = i * CELL_BYTES;
            u16::from_le_bytes([last_data[off], last_data[off + 1]]) == TAG_U32
        })
        .count();
    assert!(
        final_u32 <= 100,
        "final frame has more than 100 u32 cells ({}); fizzbuzz only allocates 100",
        final_u32
    );

    // SOMEWHERE in the capture, track! must have fired (provenance recorded).
    assert!(
        any_frame_had_provenance,
        "no frame in the capture had any nonzero provenance — track! macro never fired?"
    );

    // SOMEWHERE in the capture, distinct cells must have held distinct values
    // (proves the substrate is recording the rolling-history change, not just
    // a static snapshot).
    assert!(
        any_frame_had_distinct_payloads,
        "no frame had cells with distinct u32 payloads — the rolling history isn't being captured?"
    );

    eprintln!(
        ".mfb stats: {} frames, peak {} u32 cells, file size {} bytes",
        frame_count,
        max_u32_cells_seen,
        meta.len()
    );

    // Cleanup
    let _ = std::fs::remove_file(&mp4);
    let _ = std::fs::remove_file(&mfb);
}
