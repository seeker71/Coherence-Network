//! Pointer-rendering smoke tests. These exercise `render_frame` directly on
//! synthesized data planes (no ffmpeg, no global framebuffer) so they're
//! fast and deterministic.
//!
//! What's covered:
//! - target-color rendering: a pointer cell's inner 2x2 matches the target
//!   primitive's inner 2x2 (within ±2 RGB tolerance for any future jitter).
//! - aliasing equality: two pointer cells targeting the same primitive
//!   render pixel-identical inner regions.
//! - cycle bounded: a 3-cycle (A→B→C→A) renders without panic and the
//!   inner regions show the reserved cycle-terminator shade.

use mfb::allocator::{CELL_BYTES, GRID, NUM_CELLS};
use mfb::pointer::{
    encode_pointer_payload, CYCLE_TERMINATOR_RGB, TAG_PTR_BOX, TAG_PTR_RAW, TAG_PTR_RC,
};
use mfb::render::{compute_active_viewport, render_frame, RENDER_H, RENDER_W};
use mfb::{TAG_U32, TAG_U64};

/// Build a fresh data plane (all-zero / all-free) ready for hand-laid cells.
fn empty_plane() -> Vec<u8> {
    vec![0u8; NUM_CELLS * CELL_BYTES]
}

/// Write a primitive cell at index `idx` with tag `tag` and a deterministic
/// nonzero payload (so the entropy modulator gives a bright color).
fn place_primitive(plane: &mut [u8], idx: usize, tag: u16, fill: u8) {
    let base = idx * CELL_BYTES;
    let tag_bytes = tag.to_le_bytes();
    plane[base] = tag_bytes[0];
    plane[base + 1] = tag_bytes[1];
    for b in &mut plane[base + 2..base + CELL_BYTES] {
        *b = fill;
    }
}

/// Write a pointer cell at index `idx` with the given pointer-kind tag and
/// target index encoded in the first 2 payload bytes.
fn place_pointer(plane: &mut [u8], idx: usize, tag: u16, target: usize) {
    let base = idx * CELL_BYTES;
    let tag_bytes = tag.to_le_bytes();
    plane[base] = tag_bytes[0];
    plane[base + 1] = tag_bytes[1];
    let mut payload = [0u8; 14];
    let target_bytes = (target as u16).to_le_bytes();
    payload[0] = target_bytes[0];
    payload[1] = target_bytes[1];
    plane[base + 2..base + CELL_BYTES].copy_from_slice(&payload);
    let _ = encode_pointer_payload; // touch the helper so it's exercised by the public API.
}

/// Read the inner-region top-left RGB for cell `idx`. Honors the auto-viewport
/// computed from `plane`, so cell positions follow the renderer rather than
/// the original v0 4-px geometry.
fn read_inner_rgb(frame: &[u8], plane: &[u8], idx: usize) -> [u8; 3] {
    let (vx, vy, vside) = compute_active_viewport(plane);
    let cell_px = (RENDER_W / vside).max(1);
    let render_size = cell_px * vside;
    let pad_x = (RENDER_W - render_size) / 2;
    let pad_y = (RENDER_H - render_size) / 2;
    let inner_size = (cell_px / 2).max(1);
    let inner_offset = (cell_px - inner_size) / 2;

    let cx = idx % GRID;
    let cy = idx / GRID;
    let cx_local = cx.checked_sub(vx).expect("cell out of viewport x");
    let cy_local = cy.checked_sub(vy).expect("cell out of viewport y");
    let x = pad_x + cx_local * cell_px + inner_offset;
    let y = pad_y + cy_local * cell_px + inner_offset;
    let i = (y * RENDER_W + x) * 4;
    [frame[i], frame[i + 1], frame[i + 2]]
}

fn rgb_close(a: [u8; 3], b: [u8; 3], tol: u8) -> bool {
    let d = |x: u8, y: u8| if x > y { x - y } else { y - x };
    d(a[0], b[0]) <= tol && d(a[1], b[1]) <= tol && d(a[2], b[2]) <= tol
}

#[test]
fn test_pointer_renders_target_color() {
    // Cell 0: primitive u32 with bright payload.
    // Cell 1: pointer (raw) -> cell 0.
    let mut plane = empty_plane();
    place_primitive(&mut plane, 0, TAG_U32, 0xff);
    place_pointer(&mut plane, 1, TAG_PTR_RAW, 0);
    let prov = vec![0u32; NUM_CELLS];
    let frame = render_frame(&plane, &prov);

    let target_inner = read_inner_rgb(&frame, &plane, 0);
    let pointer_inner = read_inner_rgb(&frame, &plane, 1);

    // Inner 2x2 should match within tolerance (no compression here, but
    // keep ±2 to honor the spec's stated tolerance for the e2e mp4 case).
    assert!(
        rgb_close(target_inner, pointer_inner, 2),
        "expected pointer inner {:?} to match target inner {:?}",
        pointer_inner,
        target_inner
    );
    // And it should not be black (target is a live primitive).
    assert!(
        target_inner != [0, 0, 0],
        "primitive target rendered as black"
    );
}

#[test]
fn test_pointer_aliasing_visible() {
    // Cell 0: primitive u64 with bright payload.
    // Cell 1, 2: two pointer cells, both targeting cell 0. Different kinds
    // (raw + Box) so their halos differ — but inner regions must match.
    let mut plane = empty_plane();
    place_primitive(&mut plane, 0, TAG_U64, 0xaa);
    place_pointer(&mut plane, 1, TAG_PTR_RAW, 0);
    place_pointer(&mut plane, 2, TAG_PTR_BOX, 0);

    let mut prov = vec![0u32; NUM_CELLS];
    // Distinct provenance for each pointer cell so their halos are distinct
    // by *origin* even though the kind frame for raw uses provenance directly.
    prov[1] = 0xdead_beef;
    prov[2] = 0xfeed_face;

    let frame = render_frame(&plane, &prov);

    let inner_a = read_inner_rgb(&frame, &plane, 1);
    let inner_b = read_inner_rgb(&frame, &plane, 2);
    let inner_target = read_inner_rgb(&frame, &plane, 0);

    assert!(
        rgb_close(inner_a, inner_b, 2),
        "aliasing pointers' inner regions must match: {:?} vs {:?}",
        inner_a,
        inner_b
    );
    assert!(
        rgb_close(inner_a, inner_target, 2),
        "aliasing pointer's inner region must match target: {:?} vs {:?}",
        inner_a,
        inner_target
    );
}

#[test]
fn test_pointer_cycle_bounded() {
    // 3-cycle: A(idx 5) -> B(idx 6) -> C(idx 7) -> A(idx 5).
    // Render must not panic; the inner regions of A/B/C must show the
    // reserved cycle-terminator shade after follow-cap exhausts.
    let mut plane = empty_plane();
    place_pointer(&mut plane, 5, TAG_PTR_RAW, 6);
    place_pointer(&mut plane, 6, TAG_PTR_RAW, 7);
    place_pointer(&mut plane, 7, TAG_PTR_RC, 5); // mix kinds for variety
    let prov = vec![0u32; NUM_CELLS];

    let frame = render_frame(&plane, &prov);

    for idx in [5usize, 6, 7] {
        let inner = read_inner_rgb(&frame, &plane, idx);
        assert!(
            rgb_close(inner, CYCLE_TERMINATOR_RGB, 2),
            "cycle node {} expected terminator {:?}, got {:?}",
            idx,
            CYCLE_TERMINATOR_RGB,
            inner
        );
    }
}

#[test]
fn test_pointer_aliasing_stable_across_100_frames() {
    // The spec's R3 says: assert pixel equality across at least 100
    // consecutive frames. Render 100 frames in a row with the same plane
    // (mutator quiescent, so inner colors stay equal) and check.
    let mut plane = empty_plane();
    place_primitive(&mut plane, 10, TAG_U32, 0x77);
    place_pointer(&mut plane, 11, TAG_PTR_RAW, 10);
    place_pointer(&mut plane, 12, TAG_PTR_BOX, 10);
    let prov = vec![0u32; NUM_CELLS];

    for _frame in 0..100 {
        let frame = render_frame(&plane, &prov);
        let inner_a = read_inner_rgb(&frame, &plane, 11);
        let inner_b = read_inner_rgb(&frame, &plane, 12);
        assert!(rgb_close(inner_a, inner_b, 2));
    }
}

#[test]
fn test_pointer_chain_deeper_than_cap_truncates_to_terminator() {
    // Build a chain of 6 pointer cells: 20 -> 21 -> 22 -> 23 -> 24 -> 25
    // and 25 -> primitive at 30. The follow-cap is 4 hops; starting at
    // cell 20, after visiting 20,21,22,23,24 (5 cells, exhausts cap+1),
    // we should render terminator. Chain starting at 21 (one shorter)
    // also exhausts and renders terminator; chain at 25 (the last
    // pointer hop reaches a primitive on hop 1) renders the primitive.
    let mut plane = empty_plane();
    place_primitive(&mut plane, 30, TAG_U32, 0xff);
    for k in 0..5 {
        place_pointer(&mut plane, 20 + k, TAG_PTR_RAW, 20 + k + 1);
    }
    place_pointer(&mut plane, 25, TAG_PTR_RAW, 30);
    let prov = vec![0u32; NUM_CELLS];

    let frame = render_frame(&plane, &prov);

    let inner_20 = read_inner_rgb(&frame, &plane, 20);
    let inner_25 = read_inner_rgb(&frame, &plane, 25);
    let inner_30 = read_inner_rgb(&frame, &plane, 30);

    assert!(
        rgb_close(inner_20, CYCLE_TERMINATOR_RGB, 2),
        "depth-overflow at cell 20 expected terminator {:?}, got {:?}",
        CYCLE_TERMINATOR_RGB,
        inner_20
    );
    assert!(
        rgb_close(inner_25, inner_30, 2),
        "1-hop pointer inner {:?} must match primitive inner {:?}",
        inner_25,
        inner_30
    );
}
